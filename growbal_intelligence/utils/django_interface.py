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
django_path = os.path.join(os.path.dirname(__file__), '..', '..', 'growbal_django')
sys.path.insert(0, django_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "growbal.settings")
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
django.setup()

from accounts.models import ServiceProviderProfile
from services.models import Service
from accounts.embedding_utils import search_profiles_by_text, find_similar_profiles
from django.db.models import Q, Count
from taggit.models import Tag
from ..core.models import ProfileMatch, SearchAgentOutput


def search_profiles(query: str, max_results: int = 5, minimum_similarity: float = 0.0) -> SearchAgentOutput:
    """
    Search for service provider profiles using semantic similarity.
    
    Args:
        query: Natural language search query
        max_results: Maximum number of profiles to return
        minimum_similarity: Minimum similarity threshold (0-1)
    
    Returns:
        SearchAgentOutput with matched profiles and metadata
    """
    start_time = time.time()
    
    try:
        # Get total profile count
        total_profiles = ServiceProviderProfile.objects.count()
        
        # Perform similarity search
        similar_profiles = search_profiles_by_text(query, limit=max_results * 2)  # Get more results for filtering
        
        # Convert to ProfileMatch objects
        candidate_profiles = []
        for profile in similar_profiles:
            # Get cosine distance and convert to similarity score
            cosine_distance = getattr(profile, 'similarity', 0.0)  # Default to 0.0 if not available
            # Convert cosine distance to similarity score (1 - distance)
            # Cosine distance ranges from 0 (identical) to 2 (opposite), so similarity = 1 - distance/2
            # But for typical use cases, we'll use 1 - distance with max clamping
            similarity_score = max(0.0, 1.0 - cosine_distance)
            
            if similarity_score >= minimum_similarity:
                profile_match = ProfileMatch(
                    profile_id=profile.id,
                    similarity_score=similarity_score,
                    profile_text=profile.get_profile_text()
                )
                candidate_profiles.append(profile_match)
        
        # Sort by similarity score in descending order (highest similarity first)
        candidate_profiles.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Limit to requested number of results
        candidate_profiles = candidate_profiles[:max_results]
        
        search_time = time.time() - start_time
        
        return SearchAgentOutput(
            candidate_profiles=candidate_profiles,
            total_profiles_searched=total_profiles,
            search_time_seconds=search_time,
            search_strategy="Vector similarity search using OpenAI embeddings"
        )
        
    except Exception as e:
        search_time = time.time() - start_time
        return SearchAgentOutput(
            candidate_profiles=[],
            total_profiles_searched=0,
            search_time_seconds=search_time,
            search_strategy=f"Failed: {str(e)}"
        )


def search_profiles_by_service_tags(tags: List[str], match_all: bool = False, max_results: int = 10) -> SearchAgentOutput:
    """
    Search for service provider profiles by service tags.
    
    Args:
        tags: List of tag names to search for
        match_all: If True, profiles must have services with ALL tags. If False, ANY tag match is sufficient.
        max_results: Maximum number of profiles to return
    
    Returns:
        SearchAgentOutput with matched profiles and metadata
    """
    start_time = time.time()
    
    try:
        from django.db.models import Q
        
        # Get services that match the tags using case-insensitive matching
        if match_all:
            # Find services that have ALL the specified tags
            services = Service.objects.all()
            for tag in tags:
                services = services.filter(service_tags__name__iexact=tag)
        else:
            # Find services that have ANY of the specified tags using Q objects
            tag_queries = Q()
            for tag in tags:
                tag_queries |= Q(service_tags__name__iexact=tag)
            services = Service.objects.filter(tag_queries).distinct()
        
        # Get unique profiles from these services
        profile_ids = services.values_list('profile_id', flat=True).distinct()
        profiles = ServiceProviderProfile.objects.filter(id__in=profile_ids)
        
        # For each profile, count matching tags to create a relevance score
        profile_matches = []
        for profile in profiles:
            # Count matching tags for this profile using optimized query
            tag_queries = Q()
            for tag in tags:
                tag_queries |= Q(service_tags__name__iexact=tag)
            
            # Count distinct matching tags for this profile
            matching_count = Service.objects.filter(
                profile=profile
            ).filter(tag_queries).values('service_tags__name').distinct().count()
            
            # Calculate similarity score based on tag matches
            if match_all:
                similarity_score = 1.0 if matching_count == len(tags) else matching_count / len(tags)
            else:
                similarity_score = matching_count / len(tags)
            
            # Only include profiles with at least one matching tag
            if matching_count > 0:
                profile_match = ProfileMatch(
                    profile_id=profile.id,
                    similarity_score=similarity_score,
                    profile_text=profile.get_profile_text()
                )
                profile_matches.append(profile_match)
        
        # Sort by similarity score and limit results
        profile_matches.sort(key=lambda x: x.similarity_score, reverse=True)
        profile_matches = profile_matches[:max_results]
        
        search_time = time.time() - start_time
        total_profiles = ServiceProviderProfile.objects.count()
        
        return SearchAgentOutput(
            candidate_profiles=profile_matches,
            total_profiles_searched=total_profiles,
            search_time_seconds=search_time,
            search_strategy=f"Tag-based search ({'ALL' if match_all else 'ANY'} match) for tags: {', '.join(tags)}"
        )
        
    except Exception as e:
        search_time = time.time() - start_time
        return SearchAgentOutput(
            candidate_profiles=[],
            total_profiles_searched=0,
            search_time_seconds=search_time,
            search_strategy=f"Failed: {str(e)}"
        )


def get_available_service_tags() -> List[dict]:
    """
    Get all available service tags in the system with usage counts.
    
    Returns:
        List of dictionaries containing tag information
    """
    tags = Tag.objects.filter(
        taggit_taggeditem_items__content_type__model='service'
    ).annotate(
        usage_count=Count('taggit_taggeditem_items')
    ).order_by('-usage_count')
    
    return [
        {
            'name': tag.name,
            'slug': tag.slug,
            'usage_count': tag.usage_count
        }
        for tag in tags
    ]


def search_profiles_hybrid(query: str, tags: List[str] = None, max_results: int = 10, 
                          weight_similarity: float = 0.7, weight_tags: float = 0.3) -> SearchAgentOutput:
    """
    Hybrid search combining semantic similarity and tag matching.
    Combines vector similarity scores with tag-based scores (0.3 for tag matches).
    Final score is the sum of both scores, capped at 1.0.
    
    Args:
        query: Natural language search query
        tags: Optional list of tags to filter by
        max_results: Maximum number of profiles to return
        weight_similarity: Weight for similarity search (0-1) - DEPRECATED, kept for compatibility
        weight_tags: Weight for tag matching (0-1) - DEPRECATED, kept for compatibility
    
    Returns:
        SearchAgentOutput with matched profiles and metadata
    """
    start_time = time.time()
    
    try:
        # Perform similarity search
        similarity_results = search_profiles(query, max_results=max_results * 2)
        similarity_profiles = {p.profile_id: p for p in similarity_results.candidate_profiles}
        
        # If tags provided, perform tag search
        if tags:
            tag_results = search_profiles_by_service_tags(tags, match_all=False, max_results=max_results * 2)
            tag_profiles = {p.profile_id: p for p in tag_results.candidate_profiles}
            
            # Get all unique profile IDs from both searches
            all_profile_ids = set(similarity_profiles.keys()) | set(tag_profiles.keys())
            
            combined_profiles = []
            for profile_id in all_profile_ids:
                # Get similarity score (0 if not found in similarity search)
                similarity_score = similarity_profiles.get(profile_id, ProfileMatch(profile_id=profile_id, similarity_score=0.0, profile_text="")).similarity_score
                
                # Get tag score (0.3 if found in tag search, 0 if not)
                tag_score = 0.3 if profile_id in tag_profiles else 0.0
                
                # Combine scores with ceiling of 1.0
                combined_score = min(1.0, similarity_score + tag_score)
                
                # Get profile text (prefer from similarity search, fallback to tag search)
                if profile_id in similarity_profiles:
                    profile_text = similarity_profiles[profile_id].profile_text
                elif profile_id in tag_profiles:
                    profile_text = tag_profiles[profile_id].profile_text
                else:
                    # This shouldn't happen, but handle it gracefully
                    try:
                        profile = ServiceProviderProfile.objects.get(id=profile_id)
                        profile_text = profile.get_profile_text()
                    except ServiceProviderProfile.DoesNotExist:
                        continue  # Skip this profile if it doesn't exist
                
                combined_profiles.append(ProfileMatch(
                    profile_id=profile_id,
                    similarity_score=combined_score,
                    profile_text=profile_text
                ))
            
            # Sort by combined score in descending order (highest score first)
            combined_profiles.sort(key=lambda x: x.similarity_score, reverse=True)
            combined_profiles = combined_profiles[:max_results]
        else:
            # No tags provided, just use similarity results
            combined_profiles = similarity_results.candidate_profiles[:max_results]
        
        search_time = time.time() - start_time
        total_profiles = ServiceProviderProfile.objects.count()
        
        strategy = f"Hybrid search (vector similarity + tag scores combined)"
        if tags:
            strategy += f" with tags: {', '.join(tags)}"
        
        return SearchAgentOutput(
            candidate_profiles=combined_profiles,
            total_profiles_searched=total_profiles,
            search_time_seconds=search_time,
            search_strategy=strategy
        )
        
    except Exception as e:
        search_time = time.time() - start_time
        return SearchAgentOutput(
            candidate_profiles=[],
            total_profiles_searched=0,
            search_time_seconds=search_time,
            search_strategy=f"Failed: {str(e)}"
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
        profile = ServiceProviderProfile.objects.get(id=profile_id)
        return ProfileMatch(
            profile_id=profile.id,
            similarity_score=1.0,  # Default score for direct retrieval
            profile_text=profile.get_profile_text()
        )
    except ServiceProviderProfile.DoesNotExist:
        return None


def get_all_profiles() -> List[ProfileMatch]:
    """
    Retrieve all profiles from the database.
    
    Returns:
        List of ProfileMatch objects
    """
    profiles = ServiceProviderProfile.objects.all()
    return [
        ProfileMatch(
            profile_id=profile.id,
            similarity_score=1.0,
            profile_text=profile.get_profile_text()
        )
        for profile in profiles
    ]


def get_profiles_by_similarity(reference_profile_id: int, limit: int = 5) -> List[ProfileMatch]:
    """
    Find profiles similar to a reference profile.
    
    Args:
        reference_profile_id: ID of the reference profile
        limit: Maximum number of similar profiles to return
    
    Returns:
        List of ProfileMatch objects ordered by similarity
    """
    try:
        reference_profile = ServiceProviderProfile.objects.get(id=reference_profile_id)
        similar_profiles = find_similar_profiles(reference_profile, limit=limit)
        
        return [
            ProfileMatch(
                profile_id=profile.id,
                similarity_score=getattr(profile, 'similarity', 1.0),
                profile_text=profile.get_profile_text()
            )
            for profile in similar_profiles
        ]
    except ServiceProviderProfile.DoesNotExist:
        return []