#!/usr/bin/env python3
"""
Script to update ServiceProviderProfile logo paths from absolute to relative format.

This script:
1. Finds all ServiceProviderProfile records with absolute logo paths
2. Converts them to relative paths if the logo file exists in the current directory
3. Updates the database with the new relative paths

Usage:
    python update_logo_paths.py [--dry-run] [--test]
    
    --dry-run: Show what would be changed without making changes
    --test: Create a test record and run the conversion on it
"""

import os
import sys
import django
from pathlib import Path
import argparse
from datetime import datetime

# Add the Django project root to the Python path
script_dir = Path(__file__).resolve().parent
django_project_root = script_dir.parent.parent
sys.path.insert(0, str(django_project_root))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'growbal.settings')
django.setup()

from accounts.models import ServiceProviderProfile, CustomUser


def is_absolute_path(path):
    """Check if a path is absolute (contains full filesystem path)"""
    if not path:
        return False
    # Unix absolute paths start with /
    # Windows absolute paths have : in position 1
    # Also check for paths that contain full directory structure but don't start with /
    return (path.startswith('/') or 
            (len(path) > 1 and path[1] == ':') or
            ('growbal_django/media/logos/' in path and not path.startswith('../growbal_django/media/logos/')))


def is_correct_relative_path(path):
    """Check if a path is in the correct relative format (../growbal_django/media/logos/)"""
    if not path:
        return False
    return path.startswith('../growbal_django/media/logos/')


def extract_filename_from_path(path):
    """Extract filename from an absolute path"""
    if not path:
        return None
    return os.path.basename(path)


def file_exists_in_logos_dir(filename):
    """Check if a file exists in the current logos directory"""
    logos_dir = Path(__file__).resolve().parent
    return (logos_dir / filename).exists()


def convert_to_relative_path(absolute_path):
    """Convert absolute path to relative path format"""
    filename = extract_filename_from_path(absolute_path)
    if not filename:
        return None
    
    # Format: ../growbal_django/media/logos/filename
    return f"../growbal_django/media/logos/{filename}"


def update_logo_paths(dry_run=False, verbose=True):
    """
    Update all ServiceProviderProfile records with absolute logo paths to relative paths.
    
    Args:
        dry_run: If True, show what would be changed without making changes
        verbose: If True, print detailed output
    
    Returns:
        dict: Statistics about the operation
    """
    stats = {
        'total_records': 0,
        'absolute_paths_found': 0,
        'files_not_found': 0,
        'updated_records': 0,
        'skipped_records': 0,
        'errors': 0
    }
    
    # Get all ServiceProviderProfile records
    profiles = ServiceProviderProfile.objects.all()
    stats['total_records'] = profiles.count()
    
    if verbose:
        print(f"Found {stats['total_records']} ServiceProviderProfile records")
        print(f"Logos directory: {Path(__file__).resolve().parent}")
        print("-" * 60)
    
    for profile in profiles:
        try:
            if not profile.logo:
                continue
            
            # Check if logo path is already in correct relative format
            if is_correct_relative_path(profile.logo):
                if verbose:
                    print(f"Profile {profile.id} ({profile.name}): Already has correct relative path: {profile.logo}")
                continue
            
            # Check if logo path is absolute and needs conversion
            if is_absolute_path(profile.logo):
                stats['absolute_paths_found'] += 1
                
                # Extract filename from absolute path
                filename = extract_filename_from_path(profile.logo)
                if not filename:
                    if verbose:
                        print(f"Profile {profile.id} ({profile.name}): Could not extract filename from: {profile.logo}")
                    stats['errors'] += 1
                    continue
                
                # Check if file exists in logos directory
                if not file_exists_in_logos_dir(filename):
                    if verbose:
                        print(f"Profile {profile.id} ({profile.name}): File not found in logos directory: {filename}")
                    stats['files_not_found'] += 1
                    continue
                
                # Convert to relative path
                new_path = convert_to_relative_path(profile.logo)
                
                if verbose:
                    print(f"Profile {profile.id} ({profile.name}):")
                    print(f"  Old path: {profile.logo}")
                    print(f"  New path: {new_path}")
                
                if not dry_run:
                    # Update the database record
                    old_path = profile.logo
                    profile.logo = new_path
                    profile.save(update_fields=['logo'])
                    
                    if verbose:
                        print(f"  ✓ Updated successfully")
                    stats['updated_records'] += 1
                else:
                    if verbose:
                        print(f"  [DRY RUN] Would update")
                    stats['updated_records'] += 1
            else:
                # Unknown format
                if verbose:
                    print(f"Profile {profile.id} ({profile.name}): Unknown path format: {profile.logo}")
                stats['errors'] += 1
                
        except Exception as e:
            if verbose:
                print(f"Profile {profile.id} ({profile.name}): Error - {str(e)}")
            stats['errors'] += 1
    
    return stats


def create_test_record():
    """Create a test record with absolute path for testing"""
    # Create a test user
    user, created = CustomUser.objects.get_or_create(
        username='test_logo_user',
        defaults={
            'name': 'Test Logo User',
            'email': 'test@example.com'
        }
    )
    
    # Create or get test profile
    profile, created = ServiceProviderProfile.objects.get_or_create(
        user=user,
        defaults={
            'name': 'Test Logo Company',
            'logo': f'{Path(__file__).resolve().parent}/logo-placeholder.png',  # Absolute path
            'provider_type': 'Company',
            'country': 'UAE'
        }
    )
    
    if not created:
        # Update existing profile to have absolute path
        profile.logo = f'{Path(__file__).resolve().parent}/logo-placeholder.png'
        profile.save(update_fields=['logo'])
    
    print(f"Created/Updated test profile with ID: {profile.id}")
    print(f"Test profile logo path: {profile.logo}")
    return profile


def cleanup_test_record():
    """Clean up test record"""
    try:
        user = CustomUser.objects.get(username='test_logo_user')
        profile = ServiceProviderProfile.objects.get(user=user)
        profile.delete()
        user.delete()
        print("Test record cleaned up successfully")
    except (CustomUser.DoesNotExist, ServiceProviderProfile.DoesNotExist):
        print("No test record found to clean up")


def main():
    """Main function"""
    parser = argparse.ArgumentParser(description='Update ServiceProviderProfile logo paths')
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be changed without making changes')
    parser.add_argument('--test', action='store_true',
                       help='Create a test record and run the conversion')
    parser.add_argument('--cleanup-test', action='store_true',
                       help='Clean up test record')
    parser.add_argument('--quiet', action='store_true',
                       help='Suppress verbose output')
    
    args = parser.parse_args()
    
    verbose = not args.quiet
    
    if args.cleanup_test:
        cleanup_test_record()
        return
    
    if args.test:
        print("Creating test record...")
        test_profile = create_test_record()
        print("\nRunning conversion on test record...")
        stats = update_logo_paths(dry_run=args.dry_run, verbose=verbose)
        print(f"\nTest completed. Check profile ID {test_profile.id} for results.")
    else:
        print("Starting logo path conversion...")
        stats = update_logo_paths(dry_run=args.dry_run, verbose=verbose)
    
    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Total records examined: {stats['total_records']}")
    print(f"Absolute paths found: {stats['absolute_paths_found']}")
    print(f"Files not found in logos dir: {stats['files_not_found']}")
    print(f"Records updated: {stats['updated_records']}")
    print(f"Errors encountered: {stats['errors']}")
    
    if args.dry_run:
        print("\n[DRY RUN] No changes were made to the database.")
    else:
        print(f"\n✓ Operation completed successfully!")


if __name__ == '__main__':
    main()