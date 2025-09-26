# AI-Powered Business Crawler

## Overview

This project is an intelligent web crawler designed to systematically search, scrape, and extract business information from company websites. The system integrates with a Django backend to store structured data about service providers, companies, and their services.

## Architecture

The crawler follows a multi-stage pipeline:

1. **Search Term Generation**: Uses AI to generate optimal Google search terms for company discovery
2. **Relevance Checking**: Employs AI to identify the most relevant search results
3. **HTML Scraping**: Renders JavaScript-heavy pages and extracts full page content
4. **Content Slicing**: Uses AI to identify and extract relevant business information from HTML
5. **Navigation Discovery**: Finds and processes related pages (About, Contact, Services, etc.)
6. **Data Extraction**: Converts raw HTML into structured business data
7. **Django Integration**: Stores extracted data in the backend database

## Core Components

### Main Crawler Logic (`crawl.ipynb`)

The main notebook contains the end-to-end crawling workflow:

- **Input Processing**: Reads from CSV files containing organization data
- **Search Pipeline**: Generates search terms and finds official websites
- **Content Processing**: Scrapes and processes multiple pages per organization
- **Data Storage**: Creates users, service provider profiles, and services in Django

### HTML Scraper (`scrapper.py`)

The `HtmlScraper` class provides:

- **JavaScript Rendering**: Uses Scraping Fish API to render dynamic content
- **Smart Scrolling**: Simulates user interactions to load lazy-loaded content
- **Navigation Extraction**: Identifies relevant internal links using keyword patterns
- **Content Cleaning**: Removes unnecessary elements while preserving business data

### AI-Powered Data Extraction

The system uses Claude (Anthropic) for multiple AI tasks:

#### HTML Slicing (`generate_slices.md`)
- Identifies relevant sections within large HTML documents
- Focuses on business identifiers, services, contact information
- Excludes analytics, CSS/JS, and generic boilerplate

#### Relevance Assessment (`relevance_check_one_link.md`)
- Evaluates search results to find official company websites
- Distinguishes between official sites and aggregators/directories
- Ensures crawling targets authentic business sources

#### Navigation Filtering (`generate_about_us_link.md`)
- Identifies important internal pages (About, Contact, Services, Team)
- Converts relative URLs to absolute URLs
- Prioritizes information-rich pages

#### Data Extraction (`generate_fields_with_email.md`)
- Converts HTML content into structured business data
- Extracts company details, contact information, services
- Validates and formats extracted data according to schema

### Data Models

The system uses Pydantic models for structured data:

- **ServiceProviderOutput**: Company information, contact details, services
- **Slice/SliceSet**: HTML content segmentation
- **Country/ProviderType**: Enumerated values for data consistency

## Workflow

### 1. Input Processing
```python
# Load organization data from CSV
df = pd.read_csv(EMAIL_LIST_PATH)
# Group by organization to avoid duplicates
grouped = df.groupby(df.index).agg(lambda x: x.dropna().iloc[0])
```

### 2. Search Term Generation
```python
# Generate optimized search terms for each organization
search_term = call_llm(
    prompt_template=search_prompt,
    input_dict={"row_dict": organization_data},
    structured_output=SearchTermOutput
)
```

### 3. Website Discovery
```python
# Search Google using Serper API
search_results = search_serper(search_term)
# Use AI to identify most relevant result
relevant_result = check_search_relevance(search_term, search_results)
```

### 4. Content Scraping
```python
# Scrape main page with JavaScript rendering
base_html = scraper.scrape_html_base(website_url)
# Extract relevant content using AI slicing
sliced_html = get_relevant_html(base_html)
```

### 5. Navigation Discovery
```python
# Find navigation links
nav_links = scraper.get_nav_links(html_content)
# Filter for relevant pages (About, Contact, Services)
about_us_links = filter_navigation_links(nav_links)
```

### 6. Multi-Page Processing
```python
# Process additional pages up to token limit
for link in about_us_links:
    if token_count < MAX_TOKENS:
        page_html = scraper.scrape_html_base(link)
        sliced_content = get_relevant_html(page_html)
        aggregated_content += sliced_content
```

### 7. Data Extraction
```python
# Convert aggregated HTML to structured data
business_data = call_llm(
    prompt_template=extraction_prompt,
    input_dict={"html_content": aggregated_content},
    structured_output=ServiceProviderOutput
)
```

### 8. Django Integration
```python
# Create user account
user = await get_or_create_user(
    name=business_data.name,
    email=business_data.emails[0]
)

# Create service provider profile
profile = await create_service_provider_profile({
    "user": user.username,
    "name": business_data.name,
    "website": business_data.website,
    # ... other fields
})

# Create service record
service = await create_service({
    "profile": profile.id,
    "service_title": business_data.service_title,
    "service_description": business_data.service_description,
    # ... other fields
})
```

## Configuration

### Environment Variables
- `ANTHROPIC_API_KEY`: Claude API key for AI processing
- `SERPER_API_KEY`: Google search API key
- `SCRAPING_API_KEY`: Scraping Fish API key for HTML rendering
- `EMAIL_LIST_PATH`: Path to input CSV file
- `LOG_FILE_PATH`: Path for error logging
- `MISSED_ENTRIES_PATH`: Path for failed processing entries

### Django Integration
The crawler connects to the Django backend located in `growbal_django/`:
- Models: `CustomUser`, `ServiceProviderProfile`, `Service`, `Scrape`
- Async operations using `sync_to_async` decorators
- Validation using Django serializers

## Key Features

### Intelligent Content Extraction
- **Token-Aware Processing**: Manages Claude's token limits by chunking large HTML content
- **Context-Aware Slicing**: Identifies business-relevant content while filtering noise
- **Multi-Page Aggregation**: Combines information from multiple pages for comprehensive data

### Robust Error Handling
- **Retry Logic**: Automatic retries for API failures
- **Graceful Degradation**: Continues processing other entries when individual entries fail
- **Comprehensive Logging**: Detailed logs for debugging and monitoring

### Data Quality Assurance
- **Email Validation**: Validates extracted email addresses
- **URL Validation**: Ensures website URLs are properly formatted
- **Duplicate Detection**: Avoids reprocessing existing entries

### Scalability Considerations
- **Async Processing**: Uses asyncio for database operations
- **API Rate Limiting**: Implements delays and retries for external APIs
- **Memory Management**: Processes entries sequentially to manage memory usage

## Limitations and Considerations

### API Dependencies
- Relies on external APIs (Claude, Serper, Scraping Fish)
- Subject to rate limits and service availability
- Costs associated with API usage

### Data Quality Challenges
- Website structure variations affect extraction accuracy
- Dynamic content may not be fully captured
- AI extraction quality depends on content clarity

### Processing Time
- Each organization requires multiple API calls
- JavaScript rendering adds processing overhead
- Large-scale processing requires significant time investment

## Future Enhancements

### Performance Optimization
- Parallel processing for independent operations
- Caching mechanisms for repeated requests
- Batch processing optimizations

### Data Enhancement
- Social media profile extraction
- Business hours and location data
- Industry classification and tagging

### Quality Assurance
- Automated data validation pipelines
- Human review workflows for edge cases
- Confidence scoring for extracted data

## Usage

### Setup
1. Install dependencies: `pip install -r requirements.txt`
2. Configure environment variables in `envs/1.env`
3. Ensure Django backend is configured and running
4. Prepare input CSV with organization data

### Execution
```python
# Run the main crawler
await main("../envs/1.env")
```

The crawler will process each organization in the input CSV, extract business data, and store it in the Django backend.

### Monitoring
- Check `logs/` directory for detailed execution logs
- Monitor `MISSED_ENTRIES_PATH` for failed processing cases
- Review Django admin for stored data quality

## Technical Dependencies

### Python Libraries
- `langchain_anthropic`: Claude API integration
- `requests`: HTTP client for API calls
- `beautifulsoup4`: HTML parsing
- `pandas`: Data processing
- `pydantic`: Data validation and serialization
- `django`: Backend integration

### External Services
- **Claude (Anthropic)**: AI-powered content extraction and analysis
- **Serper**: Google search API for website discovery
- **Scraping Fish**: JavaScript rendering and HTML extraction

### Django Models
- **CustomUser**: User account management
- **ServiceProviderProfile**: Business profile information
- **Service**: Service offerings and descriptions
- **Scrape**: Raw crawling data and metadata

This crawler represents a sophisticated approach to automated business intelligence gathering, combining modern AI capabilities with robust web scraping techniques to extract and structure business information at scale.
