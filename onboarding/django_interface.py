"""
Django interface utilities for the Growbal Intelligence system.
Provides functions to interact with the Django ORM and retrieve profile data.
"""
import os
import sys
import django
from typing import List, Set
import time

# Setup Django
django_path = os.path.join(os.path.dirname(__file__), '..', 'growbal_django')
sys.path.insert(0, django_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "growbal.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from accounts.models import ServiceProviderProfile
from services.models import Service
from django.db.models import Q, Count

from pydantic import BaseModel, Field

class ProfileMatch(BaseModel):
    """
    Represents a service provider profile matched through similarity search.
    Contains the complete profile information as text.
    """
    profile_id: int = Field(
        description="Unique identifier of the service provider profile in the database"
    )
    similarity_score: float = Field(
        description="Cosine similarity score (0-1) indicating how closely this profile matches the search query. Higher scores indicate better matches."
    )
    profile_text: str = Field(
        description="Complete textual representation of the profile obtained from get_profile_text() method, including all company details, services offered, contact information, key personnel, and any other relevant information"
    )

def get_profile_by_id(profile_id: int) -> ProfileMatch:
    """
    Retrieve a specific profile by ID.
    
    Args:
        profile_id: Database ID of the profile
    
    Returns:
        ProfileMatch object or None if not found
    """
    try:
        profile = ServiceProviderProfile.objects.filter(growbal_link__isnull=False).get(id=profile_id)
        if profile.growbal_link is None:
            return None
        return ProfileMatch(
            profile_id=profile.id,
            similarity_score=1.0,  # Default score for direct retrieval
            profile_text=profile.get_onboarding_profile_text()
        )
    except ServiceProviderProfile.DoesNotExist:
        return None

def get_filtered_uae_profiles(min_description_length: int = 100, require_location: bool = False) -> List[ProfileMatch]:
    """
    Get UAE profiles with sufficient service descriptions and optionally location coverage.
    
    Args:
        min_description_length: Minimum total length of service descriptions (default: 100 chars)
        require_location: Whether to require office_locations to be filled (default: False)
    
    Returns:
        List of ProfileMatch objects that meet the criteria
    """
    # Base query for UAE profiles with services
    base_query = ServiceProviderProfile.objects.filter(
        country='UAE',
        growbal_link__isnull=False,
        services__isnull=False  # Must have at least one service
    ).prefetch_related('services').distinct()
    
    # Add location requirement if specified
    if require_location:
        base_query = base_query.filter(
            office_locations__isnull=False
        ).exclude(office_locations='')
    
    # Filter profiles with sufficient service descriptions
    qualified_profiles = []
    
    for profile in base_query:
        # Calculate total service description length
        total_description_length = 0
        services = profile.services.all()
        
        if not services:
            continue
            
        for service in services:
            if service.service_description:
                total_description_length += len(service.service_description.strip())
            if service.general_service_description:
                total_description_length += len(service.general_service_description.strip())
        
        # Check if profile meets description length requirement
        if total_description_length >= min_description_length:
            qualified_profiles.append(ProfileMatch(
                profile_id=profile.id,
                similarity_score=1.0,
                profile_text=profile.get_onboarding_profile_text()
            ))
    
    return qualified_profiles

def get_random_uae_profile(min_description_length: int = 100, require_location: bool = False) -> ProfileMatch:
    """
    Get a random UAE profile with sufficient service descriptions.
    
    Args:
        min_description_length: Minimum total length of service descriptions (default: 100 chars)
        require_location: Whether to require office_locations to be filled (default: False)
    
    Returns:
        Random ProfileMatch object that meets the criteria, or None if none found
    """
    import random
    
    qualified_profiles = get_filtered_uae_profiles(min_description_length, require_location)
    
    if not qualified_profiles:
        return None
    
    return random.choice(qualified_profiles)