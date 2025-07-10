"""
Utility functions for generating and managing profile embeddings.
"""
import numpy as np
import os
from typing import List, Optional
import openai
from django.conf import settings
from pgvector.django import VectorExtension
from dotenv import load_dotenv

# Load environment variables from the 1.env file
env_path = os.path.join(os.path.dirname(__file__), '..', '..', 'envs', '1.env')
load_dotenv(env_path)


class EmbeddingGenerator:
    """
    Class to handle embedding generation for ServiceProviderProfiles.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-ada-002"):
        """
        Initialize the embedding generator.
        
        Args:
            api_key: OpenAI API key. If not provided, will look for OPENAI_API_KEY in environment variables.
            model: The embedding model to use. Default is text-embedding-ada-002 (1536 dimensions).
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', None)
        self.model = model
        
        if self.api_key:
            openai.api_key = self.api_key
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a given text using OpenAI API.
        
        Args:
            text: The text to generate embedding for.
            
        Returns:
            List of floats representing the embedding vector.
        """
        if not self.api_key:
            raise ValueError("OpenAI API key not configured. Set OPENAI_API_KEY in environment variables or Django settings.")
        
        # OpenAI has a token limit, so we might need to truncate very long texts
        # For text-embedding-ada-002, the limit is 8191 tokens
        # As a rough estimate, we'll limit to ~30000 characters
        if len(text) > 30000:
            text = text[:30000] + "..."
        
        try:
            response = openai.embeddings.create(
                model=self.model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"Error generating embedding: {str(e)}")
    
    def update_profile_embedding(self, profile):
        """
        Generate and update the embedding for a ServiceProviderProfile.
        
        Args:
            profile: ServiceProviderProfile instance
        """
        # Generate the text representation
        profile_text = profile.get_profile_text()
        
        # Generate the embedding
        embedding = self.generate_embedding(profile_text)
        
        # Update the profile
        profile.profile_embedding = embedding
        profile.save(update_fields=['profile_embedding'])
        
        return embedding


def bulk_update_embeddings(profiles=None, batch_size=10):
    """
    Update embeddings for multiple profiles.
    
    Args:
        profiles: QuerySet of ServiceProviderProfile instances. If None, updates all profiles.
        batch_size: Number of profiles to process at once.
    """
    from .models import ServiceProviderProfile
    
    if profiles is None:
        profiles = ServiceProviderProfile.objects.all()
    
    generator = EmbeddingGenerator()
    
    total = profiles.count()
    processed = 0
    
    # Process in batches to avoid memory issues
    for i in range(0, total, batch_size):
        batch = profiles[i:i+batch_size]
        for profile in batch:
            try:
                generator.update_profile_embedding(profile)
                processed += 1
                print(f"Updated embedding for profile: {profile.name} ({processed}/{total})")
            except Exception as e:
                print(f"Error updating embedding for profile {profile.name}: {str(e)}")


def find_similar_profiles(profile_or_embedding, limit=10, exclude_self=True):
    """
    Find profiles similar to a given profile or embedding vector.
    
    Args:
        profile_or_embedding: Either a ServiceProviderProfile instance or an embedding vector
        limit: Maximum number of similar profiles to return
        exclude_self: If True and a profile is provided, exclude it from results
        
    Returns:
        QuerySet of similar ServiceProviderProfile instances with similarity scores
    """
    from .models import ServiceProviderProfile
    from django.contrib.postgres.search import SearchVector
    from pgvector.django import L2Distance, MaxInnerProduct, CosineDistance
    
    if hasattr(profile_or_embedding, 'profile_embedding'):
        # It's a profile instance
        embedding = profile_or_embedding.profile_embedding
        profile_id = profile_or_embedding.id if exclude_self else None
    else:
        # It's an embedding vector
        embedding = profile_or_embedding
        profile_id = None
    
    if embedding is None or (hasattr(embedding, '__len__') and len(embedding) == 0):
        return ServiceProviderProfile.objects.none()
    
    # Use cosine distance for similarity (smaller distance = more similar)
    # You can also use L2Distance or MaxInnerProduct
    queryset = ServiceProviderProfile.objects.filter(
        profile_embedding__isnull=False
    ).annotate(
        similarity=CosineDistance('profile_embedding', embedding)
    ).order_by('similarity')
    
    if profile_id:
        queryset = queryset.exclude(id=profile_id)
    
    return queryset[:limit]


def search_profiles_by_text(search_text: str, limit=10):
    """
    Search for profiles similar to a given text query.
    
    Args:
        search_text: The text to search for
        limit: Maximum number of results to return
        
    Returns:
        QuerySet of ServiceProviderProfile instances with similarity scores
    """
    generator = EmbeddingGenerator()
    
    # Generate embedding for the search text
    search_embedding = generator.generate_embedding(search_text)
    
    # Find similar profiles
    return find_similar_profiles(search_embedding, limit=limit, exclude_self=False)


# Database setup function
def setup_pgvector_extension():
    """
    Ensure pgvector extension is installed in the database.
    This should be run once during initial setup.
    """
    from django.db import connection
    
    with connection.cursor() as cursor:
        cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    
    print("pgvector extension setup completed.")