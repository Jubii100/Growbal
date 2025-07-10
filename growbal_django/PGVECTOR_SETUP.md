# PGVector Setup and Usage Guide

## Overview
This guide explains how to set up and use pgvector for similarity search with ServiceProviderProfile embeddings in the Growbal Django project.

## Prerequisites

1. **PostgreSQL with pgvector extension**
   - PostgreSQL 11+ is required
   - Install pgvector extension:
   ```bash
   # On Ubuntu/Debian
   sudo apt install postgresql-14-pgvector
   
   # On macOS with Homebrew
   brew install pgvector
   
   # Or build from source
   git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
   cd pgvector
   make
   make install
   ```

2. **Python packages** (already added to requirements.txt)
   ```bash
   pip install pgvector==0.3.3
   pip install django-pgvector==0.3.0
   ```

3. **OpenAI API Key** (for generating embeddings)
   - Add to your Django settings:
   ```python
   OPENAI_API_KEY = 'your-api-key-here'
   ```

## Database Setup

1. **Enable pgvector extension in your database**:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   
   Or use the provided utility function:
   ```python
   from accounts.embedding_utils import setup_pgvector_extension
   setup_pgvector_extension()
   ```

2. **Run migrations**:
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

## Model Changes

The `ServiceProviderProfile` model now includes:

1. **profile_embedding field**: A 1536-dimensional vector field for storing OpenAI embeddings
2. **get_profile_text() method**: Generates a comprehensive text representation of the profile including:
   - All profile fields (name, country, vision, contacts, etc.)
   - All associated services with complete details
   - Company members (if applicable)

## Usage Examples

### 1. Generate Embedding for a Single Profile

```python
from accounts.models import ServiceProviderProfile
from accounts.embedding_utils import EmbeddingGenerator

# Get a profile
profile = ServiceProviderProfile.objects.get(id=1)

# Initialize generator
generator = EmbeddingGenerator()

# Generate and save embedding
generator.update_profile_embedding(profile)
```

### 2. Bulk Update All Profile Embeddings

```python
from accounts.embedding_utils import bulk_update_embeddings

# Update all profiles
bulk_update_embeddings()

# Or update specific profiles
profiles = ServiceProviderProfile.objects.filter(country='USA')
bulk_update_embeddings(profiles=profiles, batch_size=5)
```

### 3. Find Similar Profiles

```python
from accounts.embedding_utils import find_similar_profiles

# Find profiles similar to a specific profile
profile = ServiceProviderProfile.objects.get(id=1)
similar_profiles = find_similar_profiles(profile, limit=5)

for similar in similar_profiles:
    print(f"{similar.name} - Similarity: {similar.similarity}")
```

### 4. Search by Text Query

```python
from accounts.embedding_utils import search_profiles_by_text

# Search for profiles matching a text description
search_query = "AI and machine learning consulting services in Europe"
results = search_profiles_by_text(search_query, limit=10)

for result in results:
    print(f"{result.name} - {result.country}")
```

### 5. Manual Similarity Search

```python
from pgvector.django import CosineDistance
from accounts.models import ServiceProviderProfile

# Get a profile's embedding
profile = ServiceProviderProfile.objects.get(id=1)
embedding = profile.profile_embedding

# Find similar profiles using raw query
similar = ServiceProviderProfile.objects.filter(
    profile_embedding__isnull=False
).exclude(
    id=profile.id
).annotate(
    similarity=CosineDistance('profile_embedding', embedding)
).order_by('similarity')[:10]
```

## API Integration

To integrate with the existing REST API, you can add custom actions to the ViewSet:

```python
# In accounts/views.py
from rest_framework.decorators import action
from rest_framework.response import Response
from .embedding_utils import search_profiles_by_text

class ServiceProviderProfileViewSet(viewsets.ModelViewSet):
    # ... existing code ...
    
    @action(detail=False, methods=['post'])
    def search_similar(self, request):
        query = request.data.get('query', '')
        limit = request.data.get('limit', 10)
        
        if not query:
            return Response({'error': 'Query is required'}, status=400)
        
        results = search_profiles_by_text(query, limit=limit)
        serializer = self.get_serializer(results, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def find_similar(self, request, pk=None):
        profile = self.get_object()
        limit = request.query_params.get('limit', 10)
        
        similar = find_similar_profiles(profile, limit=int(limit))
        serializer = self.get_serializer(similar, many=True)
        return Response(serializer.data)
```

## Performance Considerations

1. **Indexing**: pgvector automatically creates indexes for vector fields
2. **Embedding Generation**: 
   - OpenAI API calls can be slow and costly
   - Consider caching embeddings and only regenerating when profile data changes significantly
3. **Batch Processing**: Use the `bulk_update_embeddings` function for initial setup
4. **Distance Metrics**: 
   - `CosineDistance`: Best for normalized vectors (recommended)
   - `L2Distance`: Euclidean distance
   - `MaxInnerProduct`: For dot product similarity

## Maintenance

### Updating Embeddings

When profile or service data changes, update the embedding:

```python
# In a signal or save method
from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.embedding_utils import EmbeddingGenerator

@receiver(post_save, sender=ServiceProviderProfile)
def update_profile_embedding(sender, instance, **kwargs):
    # Only update if significant fields changed
    if kwargs.get('update_fields') and 'profile_embedding' not in kwargs['update_fields']:
        generator = EmbeddingGenerator()
        generator.update_profile_embedding(instance)
```

### Monitoring

- Track embedding generation costs in OpenAI dashboard
- Monitor query performance using Django Debug Toolbar or logging
- Consider implementing rate limiting for similarity search endpoints

## Troubleshooting

1. **"vector extension not found"**: Ensure pgvector is installed and extension is created
2. **"dimension mismatch"**: All embeddings must have the same dimension (1536 for text-embedding-ada-002)
3. **Slow queries**: Consider adding indexes or reducing the search scope
4. **OpenAI errors**: Check API key, rate limits, and network connectivity

## Future Enhancements

1. **Alternative Embedding Models**: 
   - Use open-source models (Sentence Transformers)
   - Support for different embedding dimensions
2. **Hybrid Search**: Combine vector similarity with keyword search
3. **Clustering**: Group similar profiles automatically
4. **Real-time Updates**: Update embeddings asynchronously using Celery
5. **Multi-language Support**: Generate embeddings in different languages