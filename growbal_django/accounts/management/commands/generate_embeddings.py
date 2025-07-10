"""
Django management command to generate embeddings for all ServiceProviderProfiles.
Usage: python manage.py generate_embeddings [--batch-size=10] [--force]
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from accounts.models import ServiceProviderProfile
from accounts.embedding_utils import EmbeddingGenerator
import time


class Command(BaseCommand):
    help = 'Generate embeddings for all ServiceProviderProfiles'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=10,
            help='Number of profiles to process in each batch (default: 10)',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Regenerate embeddings even if they already exist',
        )
        parser.add_argument(
            '--profiles-only',
            action='store_true',
            help='Only process profiles that have null embeddings',
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        force_regenerate = options['force']
        profiles_only = options['profiles_only']
        
        # Get profiles to process
        if force_regenerate:
            profiles = ServiceProviderProfile.objects.all()
            self.stdout.write(f"Processing ALL {profiles.count()} profiles (force regeneration)")
        elif profiles_only:
            profiles = ServiceProviderProfile.objects.filter(profile_embedding__isnull=True)
            self.stdout.write(f"Processing {profiles.count()} profiles without embeddings")
        else:
            profiles = ServiceProviderProfile.objects.filter(profile_embedding__isnull=True)
            self.stdout.write(f"Processing {profiles.count()} profiles with missing embeddings")
        
        if not profiles.exists():
            self.stdout.write(
                self.style.SUCCESS('No profiles need embedding generation.')
            )
            return
        
        # Initialize embedding generator
        try:
            generator = EmbeddingGenerator()
            self.stdout.write(
                self.style.SUCCESS('✓ OpenAI API key loaded successfully')
            )
        except ValueError as e:
            self.stdout.write(
                self.style.ERROR(f'Error initializing embedding generator: {e}')
            )
            return
        
        # Process profiles in batches
        total_profiles = profiles.count()
        processed = 0
        successful = 0
        failed = 0
        
        self.stdout.write(f"\nStarting embedding generation...")
        self.stdout.write(f"Batch size: {batch_size}")
        self.stdout.write("=" * 80)
        
        start_time = time.time()
        
        for i in range(0, total_profiles, batch_size):
            batch = list(profiles[i:i+batch_size])
            self.stdout.write(f"\nProcessing batch {i//batch_size + 1}/{(total_profiles + batch_size - 1)//batch_size}")
            
            for profile in batch:
                processed += 1
                try:
                    # Generate profile text
                    profile_text = profile.get_profile_text()
                    
                    if not profile_text.strip():
                        self.stdout.write(
                            f"  ⚠️  Skipping profile {profile.id} ({profile.name}): Empty profile text"
                        )
                        continue
                    
                    # Generate embedding
                    self.stdout.write(
                        f"  🔄 Generating embedding for: {profile.name} (ID: {profile.id})"
                    )
                    self.stdout.write(
                        f"     Text length: {len(profile_text)} characters"
                    )
                    
                    embedding = generator.generate_embedding(profile_text)
                    
                    # Save embedding
                    profile.profile_embedding = embedding
                    profile.save(update_fields=['profile_embedding'])
                    
                    successful += 1
                    self.stdout.write(
                        f"  ✅ Successfully updated embedding for: {profile.name}"
                    )
                    
                    # Add a small delay to respect API rate limits
                    time.sleep(0.1)
                    
                except Exception as e:
                    failed += 1
                    error_msg = f"  ❌ Error processing profile {profile.id} ({profile.name}): {str(e)}"
                    self.stdout.write(self.style.ERROR(error_msg))
                    continue
            
            # Progress update
            elapsed = time.time() - start_time
            self.stdout.write(
                f"\nProgress: {processed}/{total_profiles} profiles processed "
                f"({successful} successful, {failed} failed) - "
                f"Elapsed: {elapsed:.1f}s"
            )
        
        # Final summary
        total_time = time.time() - start_time
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("EMBEDDING GENERATION COMPLETE"))
        self.stdout.write("=" * 80)
        self.stdout.write(f"Total profiles processed: {processed}")
        self.stdout.write(f"Successful embeddings: {successful}")
        self.stdout.write(f"Failed embeddings: {failed}")
        self.stdout.write(f"Total time: {total_time:.1f} seconds")
        self.stdout.write(f"Average time per profile: {total_time/processed:.1f} seconds")
        
        if successful > 0:
            self.stdout.write(self.style.SUCCESS(f"\n🎉 Successfully generated embeddings for {successful} profiles!"))
        
        if failed > 0:
            self.stdout.write(self.style.WARNING(f"\n⚠️  {failed} profiles failed to process. Check the errors above."))
        
        # Verify results
        profiles_with_embeddings = ServiceProviderProfile.objects.exclude(
            profile_embedding__isnull=True
        ).count()
        total_profiles_count = ServiceProviderProfile.objects.count()
        
        self.stdout.write(f"\nDatabase status:")
        self.stdout.write(f"Profiles with embeddings: {profiles_with_embeddings}/{total_profiles_count}")
        
        if profiles_with_embeddings == total_profiles_count:
            self.stdout.write(self.style.SUCCESS("✅ All profiles now have embeddings!"))
        else:
            remaining = total_profiles_count - profiles_with_embeddings
            self.stdout.write(self.style.WARNING(f"⚠️  {remaining} profiles still need embeddings."))