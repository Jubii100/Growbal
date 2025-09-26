# Growbal Django Backend

A comprehensive Django backend system for managing service provider profiles, web scraping data, and enabling AI-powered search capabilities. This system stores and manages data from AI agents that crawl and extract business information from websites.

## System Architecture

### Core Concept

Growbal is a **service provider directory platform** that combines traditional web scraping with AI-powered data extraction to create comprehensive business profiles. The system operates on three fundamental pillars:

1. **Profile Management**: Comprehensive service provider profiles (companies and individual agents)
2. **Service Catalog**: Detailed service offerings with tagging and rating systems
3. **AI-Enhanced Search**: Vector-based similarity search using OpenAI embeddings

### Data Flow Overview

```
Web Crawlers/AI Agents → Raw Web Data → Django Backend → Structured Profiles → Vector Embeddings → Search API
```

## Project Structure

```
growbal_django/
├── manage.py                   # Django management commands
├── requirements.txt            # Python dependencies
├── TECHNICAL_DOCUMENTATION.md # Detailed technical docs
├── PGVECTOR_SETUP.md          # Vector search setup guide
│
├── growbal/                    # Main Django settings
│   ├── settings.py            # Configuration (PostgreSQL, DRF, etc.)
│   ├── urls.py                # Root URL routing
│   └── asgi.py/wsgi.py        # Deployment configurations
│
├── accounts/                   # User & Profile Management
│   ├── models.py              # CustomUser, ServiceProviderProfile, Members
│   ├── views.py               # REST API ViewSets
│   ├── serializers.py         # API serialization
│   ├── admin.py               # Django Admin interface
│   └── management/commands/   # CLI utilities (embedding generation)
│
├── services/                   # Service Catalog Management
│   ├── models.py              # Service model with tagging
│   ├── views.py               # Service API endpoints
│   └── admin.py               # Service administration
│
├── scraper/                    # Web Scraping Data Storage
│   ├── models.py              # Scrape model for raw HTML storage
│   └── admin.py               # Scraping data management
│
├── chats/                      # Chat Session Management
│   ├── models.py              # ChatSession & ChatMessage
│   └── admin.py               # Chat administration
│
├── api/                        # API Configuration
│   └── urls.py                # REST API routing
│
└── media/                      # File Storage
    └── logos/                 # Company logo storage
```

## Database Schema & Models

### Core Entity Relationships

```
CustomUser ←1:1→ ServiceProviderProfile ←1:N→ Service
                                      ↑
                                      └←1:N→ ServiceProviderMemberProfile
                                      ↑
                                      └←1:N→ Scrape
```

### 1. CustomUser (Authentication)
- Purpose: Extended Django user model
- Key Fields: `username`, `name`, `email`
- Features: Auto-generated usernames from names, flexible email requirement

### 2. ServiceProviderProfile (Core Business Entity)
- Purpose: Main profile for companies and individual agents
- Provider Types: `Company` | `Agent`
- Key Features:
  - 195 country choices for global coverage
  - PostgreSQL ArrayFields for multiple contacts (emails, phones)
  - Social media integration (LinkedIn, Facebook, Instagram)
  - **Vector embeddings** for AI-powered search (1536 dimensions)
  - Auto-generated Growbal links
  - Session status tracking

Critical Methods:
- `get_profile_text()`: Generates comprehensive text for AI embeddings
- `save()`: Auto-populates Growbal links

### 3. ServiceProviderMemberProfile (Company Staff)
- Purpose: Individual employee/member profiles within companies
- Constraint: Only allowed for `provider_type='Company'`
- Features: Role descriptions, contact info, social media links

### 4. Service (Service Catalog)
- Purpose: Individual services offered by providers
- Features:
  - Django-taggit integration for flexible categorization
  - Rating system (1-5 scale with descriptions)
  - Pricing information storage
  - Custom deletion logic to clean up unused tags

### 5. Scrape (Raw Web Data)
- Purpose: Stores cleaned HTML from web crawling
- Features:
  - Optional linking to profiles and services
  - URL similarity detection (70% prefix matching)
  - Supports orphaned scrapes for later processing

### 6. ChatSession & ChatMessage (Conversation Management)
- Purpose: Manages user interactions and chat history
- Features:
  - UUID-based session identification
  - Support for authenticated and anonymous users
  - Service type categorization
  - JSON metadata storage for AI responses

## Technology Stack

### Backend Framework
- Django 5.2: Modern Python web framework
- Django REST Framework: API development
- PostgreSQL: Primary database with advanced features

### AI & Machine Learning
- OpenAI Integration: Text embeddings (text-embedding-ada-002)
- pgvector: Vector similarity search in PostgreSQL
- Anthropic & LangChain: Additional AI capabilities
- Transformers: Local ML model support

### Web Scraping & Data Processing
- BeautifulSoup4: HTML parsing
- Firecrawl: Advanced web scraping
- Pandas: Data manipulation
- django-taggit: Flexible tagging system

## API Architecture

### Authentication
- Token-based authentication (DRF tokens)
- Global authentication requirement for all endpoints
- Admin interface uses Django sessions

### Core Endpoints

```
GET  /api/profiles/              # List all profiles
POST /api/profiles/              # Create profile
GET  /api/profiles/{id}/         # Retrieve specific profile
PUT  /api/profiles/{id}/         # Update profile

GET  /api/services/              # List all services
POST /api/services/              # Create service
GET  /api/services/{id}/         # Retrieve specific service

POST /api/api-token-auth/        # Obtain API token
```

### API Features
- Paginated responses for large datasets
- Filtering and search capabilities
- Nested serialization (profiles with services)
- Tag-based filtering for services

## AI Integration & Vector Search

### Embedding Generation
The system generates comprehensive text representations of profiles that include:
- All profile information (contact, location, social media)
- Complete service catalog with descriptions and tags
- Company member information
- Pricing and rating data

### Vector Search Capabilities
```python
# Find similar profiles
similar_profiles = find_similar_profiles(profile, limit=5)

# Search by text query
results = search_profiles_by_text("AI consulting services in Europe", limit=10)
```

### Management Commands
```bash
# Generate embeddings for all profiles
python manage.py generate_embeddings --batch-size=10

# Force regenerate all embeddings
python manage.py generate_embeddings --force

# Only process profiles without embeddings
python manage.py generate_embeddings --profiles-only
```

## Development Setup

### Prerequisites
- Python 3.x
- PostgreSQL with pgvector extension
- OpenAI API key (for embeddings)

### Installation
```bash
# Navigate to Django project
cd growbal_django

# Install dependencies
pip install -r ../requirements.txt

# Set up environment variables
cp envs/1.env.example envs/1.env
# Edit envs/1.env with your database and API keys

# Database setup
createdb growbal_db
psql growbal_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### Environment Variables
Create `envs/1.env` with:
```bash
DJANGO_SECRET_KEY=your-secret-key
POSTGRES_DB_NAME=growbal_db
POSTGRES_DB_USERNAME=your-username
POSTGRES_DB_PASSWORD=your-password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
OPENAI_API_KEY=your-openai-key
```

## Admin Interface

### Customized Admin Features

#### ServiceProviderProfileAdmin
- Enhanced Search: Searches across profiles, services, and tags
- Inline Service Editing: Manage services directly within profile admin
- Computed Columns: Services list, contact summary
- Performance Optimized: Uses `prefetch_related` for efficiency

#### ServiceAdmin
- Tag Management: Full taggit integration
- Rating Display: Visual rating scores
- Profile Integration: Easy navigation between profiles and services

#### Advanced Search Features
```python
# Custom search implementation supports:
- Profile names and contact information
- Service titles and descriptions
- Tag names across all services
- Cross-model relationship searches
```

## Data Integration Patterns

### Web Scraping Integration
```python
# Create scrape record with similarity checking
if not Scrape.check_similar_base_url(url):
    scrape = Scrape.objects.create(
        base_url=url,
        cleaned_html=cleaned_content,
        provider=profile  # Optional linking
    )
```

### Profile Creation from Scraped Data
```python
# AI agents typically follow this pattern:
user, created = CustomUser.objects.get_or_create_user(
    name=company_name,
    email=contact_email
)

profile = ServiceProviderProfile.objects.create(
    user=user,
    name=company_name,
    country=detected_country,
    provider_type='Company',
    # ... other fields from scraped data
)

# Add services
for service_data in extracted_services:
    Service.objects.create(
        profile=profile,
        service_title=service_data['title'],
        service_description=service_data['description'],
        # ... other service fields
    )
```

## Common Operations

### Bulk Operations
```python
# Bulk update embeddings
from accounts.embedding_utils import bulk_update_embeddings
bulk_update_embeddings(batch_size=10)

# Bulk import from scraped data
profiles = []
for scraped_data in data_batch:
    profile = create_profile_from_scraped_data(scraped_data)
    profiles.append(profile)
ServiceProviderProfile.objects.bulk_create(profiles)
```

### Search Operations
```python
# Complex filtering
profiles = ServiceProviderProfile.objects.filter(
    country='USA',
    services__service_tags__name__in=['AI', 'Machine Learning'],
    services__rating_score__gte=4.0
).distinct()

# Vector similarity search
from pgvector.django import CosineDistance
similar = ServiceProviderProfile.objects.filter(
    profile_embedding__isnull=False
).annotate(
    similarity=CosineDistance('profile_embedding', query_embedding)
).order_by('similarity')[:10]
```

## Deployment Considerations

### Database Requirements
- PostgreSQL 11+ with pgvector extension
- Recommended indexes on frequently queried fields
- Regular VACUUM for vector fields

### Performance Optimization
- Connection pooling for database connections
- Redis caching for frequently accessed data
- CDN for media files (logos)
- Async task processing for embedding generation

### Security
- Environment-based configuration
- Token-based API authentication
- Rate limiting for embedding generation
- Input validation and sanitization

## Future Enhancements

### Planned Features
1. Real-time sync with web scrapers
2. Multi-language support for international expansion
3. Advanced analytics dashboard for profile performance
4. Automated profile matching and deduplication
5. Integration APIs for third-party services

### Scalability Roadmap
1. Microservices architecture for independent scaling
2. Event-driven updates for real-time profile changes
3. Distributed vector search for large-scale deployments
4. Machine learning pipelines for automated data quality

## Additional Resources

- `TECHNICAL_DOCUMENTATION.md`: Detailed technical specifications
- `PGVECTOR_SETUP.md`: Vector search configuration guide
- Django Admin: `/admin/` (comprehensive data management)
- API Documentation: DRF browsable API at `/api/`

## Contributing

When extending this system:

1. Follow Django best practices for model design and API development
2. Update embeddings when modifying profile text generation
3. Test vector search functionality after model changes
4. Document API changes in serializers and views
5. Consider performance impact of new fields on vector operations

---

*This backend serves as the foundation for AI-powered business discovery and matching, designed to scale from thousands to millions of service provider profiles worldwide.*
