# Growbal AI Crawler - Technical Documentation

## Project Overview

Growbal is an AI-powered web crawler and data extraction system designed to automatically discover, crawl, and extract structured information about service providers from the web. The system leverages Large Language Models (LLMs) to intelligently parse unstructured web content and transform it into structured data stored in a MySQL database.

## Architecture Overview

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Search APIs    │────▶│   Crawler    │────▶│  Web Scraper    │
│  (Discovery)    │     │  (crawl.py)  │     │ (scrapper.py)   │
└─────────────────┘     └──────────────┘     └─────────────────┘
                                                      │
                                                      ▼
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│ Django Backend  │◀────│ MySQL Ingest │◀────│   LLM Parser    │
│  (REST API)     │     │(ingest_MySQL)│     │ (Ollama/OpenAI) │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

## Core Components

### 1. Web Crawler (`crawl.py`)
- **Purpose**: Main orchestrator for discovering and processing service providers
- **Key Features**:
  - Searches for service providers using search APIs
  - Processes email lists for targeted crawling
  - Manages crawling workflow and error handling
  - Integrates with LLMs for intelligent data extraction

### 2. Web Scraper (`scrapper.py`)
- **Purpose**: HTML content extraction and cleaning
- **Key Features**:
  - Fetches web pages using various methods (requests, Playwright)
  - Cleans HTML using BeautifulSoup and jusText
  - Pattern matching for page types (about, services, contact)
  - Handles dynamic content and JavaScript-rendered pages

### 3. LLM Integration (`ollama_wrapper.py`)
- **Purpose**: Interface for Large Language Model operations
- **Supported Models**:
  - OpenAI GPT models
  - Anthropic Claude
  - Local models via Ollama
  - Custom models via exllamav2/tabbyAPI
- **Functions**:
  - Extract structured data from unstructured HTML
  - Classify content types
  - Generate summaries and descriptions

### 4. Data Ingestion (`ingest_MySQL.py`)
- **Purpose**: Load processed data into MySQL database
- **Process**:
  - Validates extracted data
  - Maps to Django ORM models
  - Handles deduplication
  - Manages relationships between entities

### 5. Django Backend (`growbal_django/`)
- **Purpose**: Data storage, API layer, and business logic
- **Key Models**:
  - `CustomUser`: User authentication
  - `ServiceProviderProfile`: Main provider entity
  - `ServiceProviderMemberProfile`: Staff/team members
  - `Service`: Services offered
- **APIs**: RESTful endpoints via Django REST Framework

## Data Flow

1. **Discovery Phase**:
   - Search APIs find potential service provider websites
   - Email lists provide additional targets

2. **Crawling Phase**:
   - Scraper fetches HTML content
   - Content is cleaned and structured

3. **Extraction Phase**:
   - LLM analyzes content
   - Structured data is extracted (name, services, contact info, etc.)

4. **Storage Phase**:
   - Data is validated and normalized
   - Stored in MySQL via Django ORM

5. **Access Phase**:
   - REST API provides data access
   - Frontend applications can query provider information

## Current Issues & Technical Debt

### 1. **Security Vulnerabilities**
- ❌ API keys exposed in `1.env` file
- ❌ No secret management system
- ❌ Credentials in version control

### 2. **Code Organization**
- ❌ Multiple experimental Jupyter notebooks scattered
- ❌ No clear separation between production and experimental code
- ❌ Missing proper package structure
- ❌ Inconsistent naming conventions

### 3. **Infrastructure**
- ❌ No containerization (partial Docker setup)
- ❌ Manual deployment process
- ❌ No CI/CD pipeline
- ❌ Mixed dependencies (local PyTorch installation)

### 4. **Code Quality**
- ❌ No unit tests
- ❌ No code linting configuration
- ❌ Missing type hints
- ❌ No logging framework

### 5. **Documentation**
- ❌ No API documentation
- ❌ Missing setup instructions
- ❌ No contribution guidelines

## Improvement Recommendations

### Phase 1: Security & Environment (Priority: CRITICAL)

1. **Secure Credentials**
   ```bash
   # Create proper .env file structure
   cp 1.env .env.example
   # Remove all actual values from .env.example
   # Add .env to .gitignore
   ```

2. **Implement Secret Management**
   - Use python-dotenv for environment variables
   - Consider AWS Secrets Manager or HashiCorp Vault
   - Rotate all exposed API keys immediately

### Phase 2: Code Restructuring (Priority: HIGH)

1. **Project Structure**
   ```
   growbal/
   ├── src/
   │   ├── crawler/
   │   │   ├── __init__.py
   │   │   ├── crawler.py
   │   │   ├── scraper.py
   │   │   └── utils.py
   │   ├── llm/
   │   │   ├── __init__.py
   │   │   ├── wrapper.py
   │   │   └── prompts.py
   │   ├── ingestion/
   │   │   ├── __init__.py
   │   │   └── mysql_ingest.py
   │   └── config/
   │       ├── __init__.py
   │       └── settings.py
   ├── tests/
   ├── docs/
   ├── scripts/
   ├── requirements/
   │   ├── base.txt
   │   ├── dev.txt
   │   └── prod.txt
   └── docker/
   ```

2. **Remove Redundant Files**
   - Archive experimental notebooks
   - Remove local PyTorch installation
   - Clean up duplicate crawler versions

### Phase 3: Development Standards (Priority: HIGH)

1. **Code Quality Tools**
   ```toml
   # pyproject.toml
   [tool.black]
   line-length = 88
   
   [tool.pylint]
   max-line-length = 88
   
   [tool.mypy]
   python_version = "3.11"
   warn_return_any = true
   ```

2. **Testing Framework**
   ```python
   # tests/test_scraper.py
   import pytest
   from src.crawler.scraper import Scrapper
   
   def test_scraper_initialization():
       scraper = Scrapper()
       assert scraper is not None
   ```

3. **Logging Configuration**
   ```python
   # src/config/logging.py
   import logging
   from logging.handlers import RotatingFileHandler
   
   def setup_logging():
       logger = logging.getLogger('growbal')
       logger.setLevel(logging.INFO)
       
       handler = RotatingFileHandler(
           'logs/growbal.log',
           maxBytes=10485760,
           backupCount=5
       )
       logger.addHandler(handler)
   ```

### Phase 4: Containerization (Priority: MEDIUM)

1. **Docker Setup**
   ```dockerfile
   # Dockerfile
   FROM python:3.11-slim
   
   WORKDIR /app
   
   COPY requirements/prod.txt .
   RUN pip install --no-cache-dir -r prod.txt
   
   COPY src/ ./src/
   COPY growbal_django/ ./growbal_django/
   
   CMD ["python", "src/crawler/crawler.py"]
   ```

2. **Docker Compose**
   ```yaml
   # docker-compose.yml
   version: '3.8'
   
   services:
     crawler:
       build: .
       env_file: .env
       depends_on:
         - db
         - ollama
     
     db:
       image: mysql:8.0
       environment:
         MYSQL_DATABASE: growbal
         MYSQL_ROOT_PASSWORD: ${DB_PASSWORD}
       volumes:
         - mysql_data:/var/lib/mysql
     
     ollama:
       image: ollama/ollama
       volumes:
         - ollama_data:/root/.ollama
     
     django:
       build:
         context: .
         dockerfile: Dockerfile.django
       depends_on:
         - db
       ports:
         - "8000:8000"
   
   volumes:
     mysql_data:
     ollama_data:
   ```

### Phase 5: CI/CD Pipeline (Priority: HIGH)

1. **GitHub Actions Workflow**
   ```yaml
   # .github/workflows/ci.yml
   name: CI/CD Pipeline
   
   on:
     push:
       branches: [main, develop]
     pull_request:
       branches: [main]
   
   jobs:
     test:
       runs-on: ubuntu-latest
       
       steps:
       - uses: actions/checkout@v3
       
       - name: Set up Python
         uses: actions/setup-python@v4
         with:
           python-version: '3.11'
       
       - name: Install dependencies
         run: |
           pip install -r requirements/dev.txt
       
       - name: Run linting
         run: |
           black --check src/
           pylint src/
           mypy src/
       
       - name: Run tests
         run: |
           pytest tests/ --cov=src --cov-report=xml
       
       - name: Upload coverage
         uses: codecov/codecov-action@v3
   
     build:
       needs: test
       runs-on: ubuntu-latest
       if: github.ref == 'refs/heads/main'
       
       steps:
       - uses: actions/checkout@v3
       
       - name: Build Docker image
         run: |
           docker build -t growbal:${{ github.sha }} .
       
       - name: Push to registry
         run: |
           echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
           docker push growbal:${{ github.sha }}
   ```

2. **Pre-commit Hooks**
   ```yaml
   # .pre-commit-config.yaml
   repos:
   - repo: https://github.com/pre-commit/pre-commit-hooks
     rev: v4.4.0
     hooks:
     - id: trailing-whitespace
     - id: end-of-file-fixer
     - id: check-yaml
     - id: check-added-large-files
   
   - repo: https://github.com/psf/black
     rev: 23.3.0
     hooks:
     - id: black
   
   - repo: https://github.com/PyCQA/pylint
     rev: v2.17.4
     hooks:
     - id: pylint
   ```

### Phase 6: Documentation (Priority: MEDIUM)

1. **API Documentation**
   ```python
   # Use Django REST Swagger
   from drf_yasg.views import get_schema_view
   from drf_yasg import openapi
   
   schema_view = get_schema_view(
      openapi.Info(
         title="Growbal API",
         default_version='v1',
         description="Service provider discovery and information API",
      ),
      public=True,
   )
   ```

2. **README.md Template**
   ```markdown
   # Growbal - AI-Powered Service Provider Discovery
   
   ## Quick Start
   
   ### Prerequisites
   - Python 3.11+
   - Docker & Docker Compose
   - MySQL 8.0+
   
   ### Installation
   
   1. Clone the repository
   ```bash
   git clone https://github.com/yourusername/growbal.git
   cd growbal
   ```
   
   2. Set up environment
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```
   
   3. Run with Docker
   ```bash
   docker-compose up -d
   ```
   
   ## Development
   
   ### Local Setup
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements/dev.txt
   pre-commit install
   ```
   
   ### Running Tests
   ```bash
   pytest tests/
   ```
   ```

## Implementation Roadmap

### Week 1-2: Security & Environment
- [ ] Secure all API keys and credentials
- [ ] Set up proper .env management
- [ ] Create .gitignore with security in mind
- [ ] Rotate exposed credentials

### Week 3-4: Code Restructuring
- [ ] Create new project structure
- [ ] Move code to appropriate modules
- [ ] Archive experimental notebooks
- [ ] Implement logging framework

### Week 5-6: Testing & Quality
- [ ] Write unit tests for core components
- [ ] Set up pytest configuration
- [ ] Implement code linting
- [ ] Add type hints

### Week 7-8: Containerization
- [ ] Create Dockerfiles
- [ ] Set up docker-compose
- [ ] Test container orchestration
- [ ] Document deployment process

### Week 9-10: CI/CD Implementation
- [ ] Set up GitHub repository
- [ ] Configure GitHub Actions
- [ ] Implement automated testing
- [ ] Set up deployment pipeline

### Week 11-12: Documentation & Polish
- [ ] Write comprehensive README
- [ ] Create API documentation
- [ ] Write contribution guidelines
- [ ] Create deployment guides

## Performance Optimization Suggestions

1. **Crawling Efficiency**
   - Implement concurrent crawling with asyncio
   - Add request caching to avoid duplicate fetches
   - Use connection pooling for HTTP requests

2. **LLM Optimization**
   - Batch process multiple pages
   - Cache LLM responses for similar content
   - Use smaller models for classification tasks

3. **Database Performance**
   - Add proper indexes to frequently queried fields
   - Implement database connection pooling
   - Consider read replicas for scaling

## Monitoring & Observability

1. **Application Monitoring**
   ```python
   # Integrate Prometheus metrics
   from prometheus_client import Counter, Histogram
   
   crawl_counter = Counter('growbal_pages_crawled', 'Total pages crawled')
   parse_duration = Histogram('growbal_parse_duration_seconds', 'Time to parse page')
   ```

2. **Error Tracking**
   - Integrate Sentry for error monitoring
   - Set up alerts for critical failures
   - Track LLM API usage and costs

## Conclusion

The Growbal project has solid foundations but requires significant refactoring to meet professional standards. The recommended improvements focus on security, code organization, testing, and deployment automation. Following this roadmap will transform the project into a production-ready system suitable for professional CI/CD workflows.

### Next Steps
1. **Immediate**: Secure all exposed credentials
2. **Short-term**: Restructure codebase and add tests
3. **Medium-term**: Implement containerization and CI/CD
4. **Long-term**: Scale and optimize for production use