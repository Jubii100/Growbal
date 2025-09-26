# Growbal Django Project - Technical Documentation

## Table of Contents
1. [Project Overview](#project-overview)
2. [Technology Stack](#technology-stack)
3. [Project Structure](#project-structure)
4. [Database Architecture](#database-architecture)
5. [API Architecture](#api-architecture)
6. [Authentication & Security](#authentication--security)
7. [Admin Interface](#admin-interface)
8. [Third-Party Integrations](#third-party-integrations)
9. [Deployment Considerations](#deployment-considerations)
10. [Development Setup](#development-setup)

## Project Overview

**Growbal** is a Django-based service provider platform that enables companies and individual agents to create profiles, list their services, and manage their digital presence. The platform includes web scraping capabilities, AI integrations, and a comprehensive REST API.

### Key Features
- Multi-tenant service provider profiles (Companies and Agents)
- Service catalog management with tagging system
- Web scraping and content caching
- Token-based REST API
- PostgreSQL with array field support
- AI/ML integrations (Anthropic, OpenAI, LangChain)
- Rich admin interface with custom configurations

## Technology Stack

### Core Framework
- **Django**: 5.2
- **Django REST Framework**: 3.16.0
- **Python**: 3.x (inferred from Django 5.2 requirement)

### Database
- **PostgreSQL**: Primary database
- **psycopg2-binary**: 2.9.10 (PostgreSQL adapter)

### Authentication & API
- **djangorestframework**: 3.16.0
- **Token Authentication**: Built-in DRF token auth
- **django-taggit**: 6.1.0 (Tagging system)

### AI/ML Libraries
- **anthropic**: 0.51.0
- **langchain**: 0.3.25
- **langchain-anthropic**: 0.3.13
- **openai**: 1.76.2
- **torch**: 2.6.0
- **transformers**: 4.51.3

### Web Scraping
- **beautifulsoup4**: 4.13.4
- **firecrawl-py**: 2.5.3
- **lxml**: 5.4.0
- **requests**: 2.32.3

### Data Processing
- **pandas**: 2.2.3
- **numpy**: 2.2.5

### Additional Frameworks
- **FastAPI**: 0.115.12 (Potentially for additional endpoints)

## Project Structure

```
growbal_django/
├── manage.py                    # Django management script
├── structure.txt               # Project structure documentation
├── media/                      # Media files directory
│   ├── logos/                  # Company logos storage
│   │   ├── logo-placeholder.png
│   │   └── [various logo files]
│   └── logos_test/            # Test logos directory
│
├── growbal/                    # Main Django settings package
│   ├── __init__.py
│   ├── asgi.py                # ASGI configuration
│   ├── settings.py            # Django settings
│   ├── urls.py                # Main URL configuration
│   └── wsgi.py                # WSGI configuration
│
├── accounts/                   # User accounts and profiles app
│   ├── __init__.py
│   ├── admin.py               # Admin configurations
│   ├── apps.py                # App configuration
│   ├── models.py              # User and profile models
│   ├── serializers.py         # DRF serializers
│   ├── tests.py               # Test cases
│   ├── views.py               # API views
│   └── migrations/            # Database migrations
│
├── services/                   # Services management app
│   ├── __init__.py
│   ├── admin.py               # Admin configurations
│   ├── apps.py                # App configuration
│   ├── models.py              # Service model
│   ├── serializers.py         # DRF serializers
│   ├── tests.py               # Test cases
│   ├── views.py               # API views
│   └── migrations/            # Database migrations
│
├── scraper/                    # Web scraping app
│   ├── __init__.py
│   ├── admin.py               # Admin configurations
│   ├── apps.py                # App configuration
│   ├── models.py              # Scrape model
│   ├── serializers.py         # DRF serializers
│   └── migrations/            # Database migrations
│
└── api/                        # API URL configuration
    ├── __init__.py
    └── urls.py                 # API URL patterns
```

## Database Architecture

### Models Overview

#### 1. CustomUser (accounts.models)
Extended Django user model for authentication.

**Fields:**
- `username`: CharField (unique, max_length=200)
- `name`: CharField (max_length=200)
- `email`: EmailField (optional, unique)
- Inherits from AbstractUser

**Custom Methods:**
- `create_user()`: Auto-generates unique username from name
- `create_superuser()`: Creates admin users
- `get_or_create_user()`: Finds or creates users

#### 2. ServiceProviderProfile (accounts.models)
Main profile for service providers.

**Fields:**
- `user`: OneToOneField → CustomUser
- `provider_type`: CharField (choices: 'Company', 'Agent')
- `country`: CharField (195 country choices)
- `session_status`: CharField (choices: 'active', 'inactive')
- `name`: CharField
- `vision`: TextField
- `logo`: TextField (stores logo data, possibly base64)
- `website`, `linkedin`, `facebook`, `instagram`: URLField
- `telephones`: ArrayField (PostgreSQL array)
- `mobiles`: ArrayField (PostgreSQL array)
- `emails`: ArrayField (PostgreSQL array)
- `office_locations`: TextField
- `key_individuals`: TextField
- `representatives`: TextField
- `date_modified`: DateTimeField (auto_now=True)
- `date_created`: DateTimeField (auto_now_add=True)

#### 3. ServiceProviderMemberProfile (accounts.models)
Profile for company employees/members.

**Fields:**
- `user`: OneToOneField → CustomUser
- `name`: CharField (required)
- `company`: ForeignKey → ServiceProviderProfile
- `role_description`: CharField
- `telephone`: CharField
- `mobile`: CharField
- `email`: EmailField
- Social media URLs (linkedin, facebook, instagram, twitter)
- `additional_info`: TextField

**Validation:** Only allowed when parent has provider_type='Company'

#### 4. Service (services.models)
Individual services offered by providers.

**Fields:**
- `profile`: ForeignKey → ServiceProviderProfile
- `service_title`: CharField
- `service_description`: TextField
- `general_service_description`: TextField
- `service_tags`: TaggableManager (django-taggit)
- `rating_score`: DecimalField (max_digits=3, decimal_places=1)
- `rating_description`: TextField
- `pricing`: TextField
- Timestamp fields (auto-managed)

**Special Features:**
- Tag-based categorization
- Custom delete method for tag cleanup

#### 5. Scrape (scraper.models)
Stores scraped web content.

**Fields:**
- `provider`: ForeignKey → ServiceProviderProfile (optional)
- `service`: ForeignKey → Service (optional)
- `base_url`: CharField
- `cleaned_html`: TextField
- Timestamp fields

**Methods:**
- `check_similar_base_url()`: Checks for 70% URL prefix match

### Database Relationships

```
CustomUser ←1:1→ ServiceProviderProfile ←1:N→ Service
                                      ↑
                                      └←1:N→ ServiceProviderMemberProfile

ServiceProviderProfile ←N:1→ Scrape
Service ←N:1→ Scrape
```

## API Architecture

### Base Configuration
- **Base URL**: `/api/`
- **Authentication**: Token Authentication (required for all endpoints)
- **Permissions**: IsAuthenticated (global)
- **Format**: JSON

### Endpoints

#### 1. Authentication
- `POST /api/api-token-auth/` - Obtain authentication token
  - Request: `{"username": "...", "password": "..."}`
  - Response: `{"token": "..."}`

#### 2. Service Provider Profiles
- `GET /api/profiles/` - List all profiles
- `POST /api/profiles/` - Create new profile
- `GET /api/profiles/{id}/` - Retrieve specific profile
- `PUT /api/profiles/{id}/` - Update profile
- `DELETE /api/profiles/{id}/` - Delete profile

#### 3. Services
- `GET /api/services/` - List all services
- `POST /api/services/` - Create new service
- `GET /api/services/{id}/` - Retrieve specific service
- `PUT /api/services/{id}/` - Update service
- `DELETE /api/services/{id}/` - Delete service

### Serializers

#### ServiceProviderProfileSerializer
- Exposes all profile fields except timestamps
- Uses username slug for user reference
- Handles PostgreSQL array fields

#### ServiceSerializer
- Integrates with django-taggit
- References profile by primary key
- Full service detail serialization

#### ScrapeSerializer
- Simple serialization of all scrape fields
- References related models by primary key

## Authentication & Security

### Current Configuration
1. **Authentication Backend**: Django's default with custom user model
2. **API Authentication**: Token-based (DRF tokens)
3. **Session Management**: Django sessions for admin
4. **Password Management**: Django's built-in password hashing

### Security Considerations
**Development Settings Detected:**
- `DEBUG = True` - Must be set to False in production
- `SECRET_KEY` is hardcoded - Must use environment variables
- `ALLOWED_HOSTS = []` - Must specify allowed domains
- Database credentials in settings - Should use environment variables

### Recommended Security Improvements
1. Move sensitive settings to environment variables
2. Implement HTTPS in production
3. Configure CORS headers for API access
4. Add rate limiting for API endpoints
5. Implement proper logging and monitoring
6. Regular security audits

## Admin Interface

### Customizations

#### 1. CustomUserAdmin
- **List Display**: name, username, email, is_staff, is_superuser
- **Search**: name, email, username

#### 2. ServiceProviderProfileAdmin
- **List Display**: name, provider_type, country, services_list, office_locations, timestamps
- **Filters**: provider_type, country
- **Search**: Complex search across profiles, services, and tags
- **Inline Editing**: Services can be edited directly in profile admin
- **Performance**: Optimized with prefetch_related

#### 3. ServiceProviderMemberProfileAdmin
- **List Display**: name, company, role, contact information
- **Filters**: Company's provider type
- **Search**: User details, role, company

#### 4. ServiceAdmin
- **List Display**: title, profile, rating, pricing, timestamps
- **Search**: Title, description, tags, rating, pricing

#### 5. ScrapeAdmin
- **List Display**: URL, provider, service, timestamps
- **Search**: URL, provider name, service title

## Third-Party Integrations

### AI/ML Capabilities
The presence of multiple AI libraries suggests:
- **Anthropic Integration**: Claude AI capabilities
- **OpenAI Integration**: GPT models access
- **LangChain**: AI application framework
- **Transformers**: Local ML model support

### Web Scraping
Multiple scraping libraries indicate:
- **BeautifulSoup4**: HTML parsing
- **Firecrawl**: Advanced web scraping
- **Requests**: HTTP client

### Potential Use Cases
1. AI-powered service descriptions
2. Automated content extraction from provider websites
3. Intelligent matching of services to user needs
4. Natural language processing for search

## Deployment Considerations

### Database
1. **PostgreSQL Setup**: Required for ArrayField support
2. **Migrations**: Ensure all migrations are applied
3. **Indexes**: Consider adding indexes for:
   - `Scrape.base_url`
   - `Service.service_tags`
   - Search fields

### Environment Variables
Required environment variables:
```bash
SECRET_KEY=<secure-random-key>
DEBUG=False
ALLOWED_HOSTS=<your-domain.com>
DATABASE_URL=postgresql://user:password@host:port/dbname
```

### Static Files
1. Configure `STATIC_ROOT` for production
2. Run `collectstatic` command
3. Serve static files via web server

### Media Files
1. Configure proper media file serving
2. Implement file upload restrictions
3. Consider CDN for media delivery

### Performance
1. Enable caching (Redis recommended)
2. Database connection pooling
3. Gunicorn/uWSGI for production
4. Consider async support (ASGI)

## Development Setup

### Prerequisites
- Python 3.x
- PostgreSQL
- Virtual environment

### Installation Steps
```bash
# Clone repository
git clone <repository-url>
cd growbal/growbal_django

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r ../requirements.txt

# Database setup
createdb growbal_db
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
```

### Development Tools
- Django Debug Toolbar (recommended)
- Pre-commit hooks for code quality
- pytest for testing (tests need to be written)

### API Testing
Use tools like:
- Postman
- curl
- httpie
- Django REST Framework browsable API

## Future Considerations

### Scalability
1. Implement caching strategy
2. Database optimization and indexing
3. Consider microservices for scraping
4. Queue system for async tasks

### Features
1. User registration workflow
2. Email notifications
3. Payment integration
4. Analytics dashboard
5. Mobile API optimization

### Code Quality
1. Implement comprehensive test suite
2. API documentation (Swagger/OpenAPI)
3. Code coverage monitoring
4. Continuous Integration/Deployment

---

*This documentation provides a comprehensive technical overview of the Growbal Django project. For specific implementation details, refer to the source code and inline documentation.*