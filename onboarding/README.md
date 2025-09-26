# Growbal Onboarding System

A comprehensive AI-powered onboarding system designed to streamline the collection and validation of service provider information through intelligent conversational interactions, automated research, and dynamic questionnaire adaptation.

## System Overview

The Growbal Onboarding System is a state-driven, event-sourced architecture that enables dynamic workflow adaptation, intelligent research integration, and seamless human-in-the-loop capabilities. It combines conversational AI with automated web research to minimize user friction while maximizing data collection quality.

### Core Philosophy

- **Research-Driven Approach**: Automatically adapts questionnaires based on industry-specific findings
- **Minimal User Friction**: Reduces repetitive questions through intelligent pre-research
- **Quality Assurance**: Validates responses against industry standards and best practices
- **Dynamic Adaptation**: Adjusts workflow based on user responses and profile data

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Profile Data  │────▶│  State Manager   │────▶│  Research Loop  │
│   (Django DB)   │     │  (Initialization)│     │  (Web + LLM)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                          │
                                                          ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│ Final Summary   │◀────│ Question Engine  │◀────│ Dynamic Checklist│
│ & Validation    │     │ (Interactive)    │     │ (Customized)    │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Core Components

### 1. State Manager (`state_manager.py`)
- **Purpose**: Central state management for the onboarding workflow
- **Features**:
  - Workflow status tracking with enum-based states
  - Dynamic checklist management with customizable items
  - Provider profile data integration
  - Research content capture and indexing
  - Completion metrics and progress tracking

### 2. Research Engine (`research_engine.py`)
- **Purpose**: Two-phase research system for intelligent data gathering
- **Features**:
  - **Phase 1**: Checklist customization based on industry standards
  - **Phase 2**: Answer gathering from web sources and existing data
  - Intelligent web search with query generation
  - Content extraction and business-focused parsing
  - Research result ranking and validation

### 3. Workflow Agent (`workflow_agent.py`)
- **Purpose**: Main orchestrator for the adaptive onboarding workflow
- **Features**:
  - LangGraph-based state machine with decision points
  - Interactive and simulation modes
  - Intelligent question generation and sequencing
  - User response processing and validation
  - Research integration and checklist updates
  - Final confirmation and summary generation

### 4. LLM Wrapper (`llm_wrapper.py`)
- **Purpose**: Production-ready LangChain + OpenAI implementation
- **Features**:
  - Structured output parsing with Pydantic schemas
  - Retry logic with timeout protection
  - Token counting and optimization
  - Dynamic prompt generation
  - Error handling and fallback mechanisms

### 5. Research Tools (`research_tools.py`)
- **Purpose**: Web search and content extraction utilities
- **Features**:
  - OpenAI web search integration
  - ScrapingFish API for content extraction
  - Academic content cleaning and filtering
  - Business content parsing and structuring
  - Rate limiting and error handling

### 6. Django Interface (`django_interface.py`)
- **Purpose**: Integration layer with Growbal Django backend
- **Features**:
  - Profile retrieval with filtering capabilities
  - UAE-specific profile filtering
  - Database connection management
  - Profile matching and similarity search integration

### 7. Schemas (`schemas.py`)
- **Purpose**: Pydantic data models for structured responses
- **Features**:
  - Checklist item definitions and validation
  - Search query and result structures
  - Research response schemas
  - Answer extraction and validation models

## Installation and Setup

### Prerequisites

- Python 3.11+
- Poetry (recommended) or pip
- Access to OpenAI API
- Access to ScrapingFish API (optional, for enhanced web scraping)
- PostgreSQL database (for Django integration)

### Required Environment Variables

Create a `.env` file with the following configuration:

```bash
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Optional: Alternative LLM APIs
ANTHROPIC_API_KEY=your_anthropic_key_here

# Web Search API
SERPER_API_KEY=your_serper_api_key_here

# Optional: Enhanced Web Scraping
SCRAPINGFISH_API_KEY=your_scrapingfish_key_here

# Django Database Connection
DATABASE_URL=postgresql://user:password@localhost:5432/growbal

# Optional: LangSmith Tracing
LANGSMITH_API_KEY=your_langsmith_key_here
LANGCHAIN_TRACING_V2=true
```

### Installation

1. **Install Dependencies**
   ```bash
   cd onboarding
   pip install -r onboarding_requirements.txt
   ```

2. **Set up Django Integration** (if using database features)
   ```bash
   cd ../growbal_django
   python manage.py migrate
   python manage.py collectstatic
   ```

3. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys and database settings
   ```

## Usage

### Quick Start with Jupyter Notebook

The primary interface is through the Jupyter notebook `onboarding.ipynb`:

1. **Launch Jupyter**
   ```bash
   jupyter notebook onboarding.ipynb
   ```

2. **Run All Cells**
   - Cell 1-3: Environment setup and imports
   - Cell 4-5: Agent initialization with mode selection
   - Cell 6: Graph visualization
   - Cell 7-8: Profile data loading (from Django or mock data)
   - Cell 9: Workflow execution

### Interactive vs Simulation Mode

The system supports two operational modes:

#### Interactive Mode (Production)
```python
INTERACTIVE_MODE = True
agent = AdaptiveOnboardingAgent(interactive_mode=True)
```
- Prompts for real user input during the workflow
- Provides realistic onboarding experience
- Suitable for production environments

#### Simulation Mode (Testing)
```python
INTERACTIVE_MODE = False
agent = AdaptiveOnboardingAgent(interactive_mode=False)
```
- Uses automated responses for testing
- Enables development and debugging
- Runs without user intervention

### Programmatic Usage

```python
from state_manager import initialize_state
from workflow_agent import AdaptiveOnboardingAgent
from django_interface import get_random_uae_profile

# Initialize agent
agent = AdaptiveOnboardingAgent(interactive_mode=True)

# Get profile data
profile_data = get_random_uae_profile(min_description_length=150)

# Initialize state
initial_state = initialize_state({
    'id': profile_data.profile_id,
    'profile_text': profile_data.profile_text
})

# Run workflow
final_state = await agent.run(initial_state)
```

## Workflow Description

### Phase 1: Initialization
1. **Profile Data Loading**: Retrieves service provider profile from Django database
2. **State Initialization**: Creates initial workflow state with default checklist
3. **Research Content Capture**: Extracts and indexes existing profile information

### Phase 2: Research Loop
1. **Checklist Research**: Customizes questionnaire based on industry standards
2. **Answer Research**: Attempts to find answers from existing data and web sources
3. **Research Evaluation**: Determines confidence levels and completeness

### Phase 3: Interactive Collection
1. **Question Generation**: Creates contextual, personalized questions
2. **User Interaction**: Presents questions and captures responses
3. **Response Validation**: Validates and processes user inputs
4. **Progress Tracking**: Updates completion status and metrics

### Phase 4: Finalization
1. **Confirmation**: Reviews completed information with user
2. **Summary Generation**: Creates comprehensive profile summary
3. **Data Persistence**: Saves results to database or export format

## Configuration

### Checklist Customization

The system uses industry-specific templates that can be customized:

```python
# Default checklist items for UAE service providers
DEFAULT_CHECKLIST = [
    {
        "key": "flagship_package_pricing_and_terms",
        "prompt": "Please specify pricing, inclusions, and terms...",
        "required": True,
        "weight": 1.0
    },
    {
        "key": "service_scope_clients_process_and_timelines",
        "prompt": "Outline your service scope and client profiles...",
        "required": True,
        "weight": 1.0
    }
]
```

### Research Configuration

```python
# Web search parameters
SEARCH_CONFIG = {
    "max_queries": 3,
    "max_results_per_query": 5,
    "timeout_seconds": 30,
    "retry_attempts": 2
}

# LLM configuration
LLM_CONFIG = {
    "model": "gpt-4",
    "temperature": 0.1,
    "max_tokens": 4000,
    "timeout_seconds": 60
}
```

## API Integration

### Django Backend Integration

The system integrates with the Growbal Django backend for:

- **Profile Retrieval**: `get_profile_by_id()`, `get_random_uae_profile()`
- **Data Filtering**: Advanced filtering by location, description length, etc.
- **Database Persistence**: Automatic saving of completed onboarding data

### External APIs

- **OpenAI**: GPT-4 for intelligent question generation and content analysis
- **Serper**: Web search for industry research and data gathering
- **ScrapingFish**: Enhanced web content extraction (optional)

## Testing and Development

### Testing Framework

```bash
# Run basic functionality tests
python test_ollama_simple.py

# Test individual components
python -c "from state_manager import initialize_state; print('State manager working')"
python -c "from llm_wrapper import OnboardingLLM; print('LLM wrapper working')"
```

### Development Tools

- **Interactive Testing**: Use simulation mode for rapid development
- **Component Testing**: Individual module testing capabilities
- **Debug Logging**: Comprehensive logging with adjustable levels
- **Error Handling**: Robust retry logic and fallback mechanisms

## Deployment Considerations

### Production Requirements

- **API Keys**: Secure storage of OpenAI and search API credentials
- **Database**: PostgreSQL connection for Django integration
- **Monitoring**: Integration with LangSmith for tracing and analytics
- **Scaling**: Horizontal scaling support for multiple concurrent sessions

### Performance Optimization

- **Caching**: Research results and LLM responses are cached where appropriate
- **Timeout Protection**: All external API calls include timeout safeguards
- **Retry Logic**: Automatic retry for failed operations
- **Rate Limiting**: Respectful API usage with built-in rate limiting

## Troubleshooting

### Common Issues

1. **API Authentication Errors**
   - Verify API keys in environment configuration
   - Check API key validity and quotas

2. **Django Connection Issues**
   - Ensure Django database is properly configured
   - Verify PostgreSQL connection settings

3. **LLM Timeout Issues**
   - Adjust timeout settings in configuration
   - Check network connectivity and API status

4. **Research Failures**
   - Verify web search API credentials
   - Check rate limiting and quota usage

### Debug Mode

Enable verbose logging for troubleshooting:

```python
import logging
logging.getLogger().setLevel(logging.DEBUG)
```

## File Structure

```
onboarding/
├── README.md                    # This documentation
├── onboarding.ipynb            # Main interface notebook
├── onboarding_requirements.txt # Python dependencies
├── state_manager.py           # Central state management
├── workflow_agent.py          # Main workflow orchestrator
├── research_engine.py         # Two-phase research system
├── llm_wrapper.py            # OpenAI/LangChain integration
├── research_tools.py         # Web search and scraping tools
├── django_interface.py       # Django backend integration
├── schemas.py                # Pydantic data models
├── test_ollama_simple.py     # Basic functionality tests
├── docs/                     # Technical documentation
├── docs_2/                   # Advanced documentation
├── docs_3/                   # Implementation guides
├── backup/                   # Backup files and debugging docs
└── prompts/                  # LLM prompt templates
```

## Version History

- **v1.0**: Initial prototype with basic conversational flow
- **v2.0**: Two-phase research integration and dynamic checklist
- **v3.0**: Enhanced Django integration and UAE-specific filtering
- **Current**: Production-ready system with comprehensive error handling

## Contributing

### Development Guidelines

1. **Code Style**: Follow PEP 8 standards
2. **Documentation**: Update documentation for new features
3. **Testing**: Include tests for new functionality
4. **Error Handling**: Implement robust error handling and logging

### Adding New Features

1. **Checklist Items**: Add new items to `DEFAULT_CHECKLIST` in `state_manager.py`
2. **Research Queries**: Extend search logic in `research_engine.py`
3. **Validation Rules**: Add validation in `schemas.py`
4. **Workflow Nodes**: Extend graph in `workflow_agent.py`

## Support and Maintenance

For technical support or feature requests, please refer to the technical documentation in the `docs/` directory or contact the development team.

### Key Metrics

- **Completion Rate**: Tracks percentage of checklist items completed
- **Research Effectiveness**: Measures successful answer extraction from research
- **User Experience**: Monitors session duration and abandonment rates
- **API Performance**: Tracks response times and error rates

---

**Note**: This system is part of the larger Growbal ecosystem. For full platform documentation, see the main project README and technical documentation in the `growbal_django/` directory.
