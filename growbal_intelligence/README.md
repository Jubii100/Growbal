# Growbal Intelligence

A sophisticated AI-powered agent system for intelligent service provider search and recommendation. This system powers the core intelligence features of the Growbal platform, providing semantic search, relevance evaluation, and intelligent summarization capabilities.

## Overview

The Growbal Intelligence system is built on a multi-agent architecture that processes user queries through a coordinated pipeline of specialized AI agents. Each agent is responsible for a specific aspect of the search and recommendation process, ensuring high-quality, relevant results for users seeking service providers.

## Architecture

The system follows a modular agent-based architecture with the following key components:

### Core Components

- **Agents**: Specialized AI agents that handle different aspects of the workflow
- **Core Models**: Pydantic data models that define the structure and contracts between components
- **Workflow Orchestration**: LangGraph-based workflow management with streaming support
- **Django Interface**: Database integration and data access layer

### Data Flow

1. **Search Phase**: Query analysis and candidate profile retrieval
2. **Adjudication Phase**: Relevance evaluation and filtering
3. **Summarization Phase**: Intelligent synthesis and recommendation generation

## Directory Structure

```
growbal_intelligence/
├── agents/                 # AI agent implementations
│   ├── search_agent.py    # Profile search and retrieval
│   ├── adjudicator_agent.py # Relevance evaluation
│   └── summarizer_agent.py # Summary generation
├── core/                  # Core system components
│   ├── models.py          # Pydantic data models
│   └── workflow.py        # LangGraph workflow orchestration
├── utils/                 # Utility modules
│   └── django_interface.py # Database access layer
├── mcp_server/           # MCP server components (legacy)
└── testing/              # Test notebooks and validation
```

## Agent System

### Search Agent (`agents/search_agent.py`)

The Search Agent is responsible for finding relevant service provider profiles based on user queries.

**Key Features:**
- Intelligent query analysis using Claude Haiku 3.5
- Multiple search strategies: semantic, tag-based, and hybrid
- Streaming support for real-time progress updates
- Automatic strategy selection based on query characteristics

**Search Strategies:**
- **Semantic Search**: Vector similarity using OpenAI embeddings
- **Tag-based Search**: Exact matching on service categories and tags
- **Hybrid Search**: Combination of semantic and tag-based approaches

**Usage:**
```python
from growbal_intelligence.agents.search_agent import SearchAgent
from growbal_intelligence.core.models import SearchAgentInput

agent = SearchAgent(api_key="your_api_key")
search_input = SearchAgentInput(
    query="I need help with digital marketing",
    max_results=10,
    minimum_similarity=0.3
)

# Streaming execution
async for update in agent.search_streaming(search_input):
    print(update)

# Non-streaming execution
response = await agent.search(search_input)
```

### Adjudicator Agent (`agents/adjudicator_agent.py`)

The Adjudicator Agent evaluates the relevance of candidate profiles returned by the search agent.

**Key Features:**
- Profile relevance assessment using Claude Haiku 3.5
- Configurable relevance thresholds
- Detailed reasoning for inclusion/exclusion decisions
- Confidence scoring for quality assessment

**Evaluation Criteria:**
- Service alignment with user requirements
- Geographic relevance and accessibility
- Expertise matching and specialization
- Capacity to handle user needs

**Usage:**
```python
from growbal_intelligence.agents.adjudicator_agent import AdjudicatorAgent
from growbal_intelligence.core.models import AdjudicatorAgentInput

agent = AdjudicatorAgent(api_key="your_api_key")
adjudicator_input = AdjudicatorAgentInput(
    original_query="I need help with digital marketing",
    candidate_profiles=candidate_profiles,
    relevance_threshold=0.7
)

response = await agent.adjudicate(adjudicator_input)
```

### Summarizer Agent (`agents/summarizer_agent.py`)

The Summarizer Agent creates comprehensive summaries and recommendations based on relevant profiles.

**Key Features:**
- Executive summary generation
- Provider recommendations with reasoning
- Key insights extraction
- Statistical analysis of results
- Multiple summary styles (brief, comprehensive)

**Output Components:**
- Executive summary of findings
- Ranked provider recommendations
- Key insights and patterns
- Summary statistics and metadata

**Usage:**
```python
from growbal_intelligence.agents.summarizer_agent import SummarizerAgent
from growbal_intelligence.core.models import SummarizerAgentInput

agent = SummarizerAgent(api_key="your_api_key")
summarizer_input = SummarizerAgentInput(
    original_query="I need help with digital marketing",
    relevant_profiles=relevant_profiles,
    summary_style="comprehensive"
)

response = await agent.summarize(summarizer_input)
```

## Core Models (`core/models.py`)

The system uses Pydantic models to ensure type safety and data validation across all components.

### Key Models

**Agent Input/Output Models:**
- `SearchAgentInput/Output`: Search parameters and results
- `AdjudicatorAgentInput/Output`: Evaluation parameters and decisions
- `SummarizerAgentInput/Output`: Summary parameters and content

**Data Models:**
- `ProfileMatch`: Represents a service provider profile with similarity score
- `AdjudicationResult`: Contains relevance assessment and reasoning
- `WorkflowState`: Complete workflow state for LangGraph orchestration

**Response Models:**
- `AgentResponse`: Standardized response format for all agents
- `AgentRole`: Enumeration of available agent types

## Workflow Orchestration (`core/workflow.py`)

The workflow system uses LangGraph to orchestrate the execution of multiple agents in a coordinated pipeline.

**Key Features:**
- Asynchronous execution with streaming support
- Error handling and recovery mechanisms
- State management and persistence
- Conditional routing based on results
- Comprehensive logging and monitoring

**Workflow States:**
1. **Search**: Query analysis and candidate retrieval
2. **Adjudicate**: Relevance evaluation and filtering
3. **Summarize**: Summary generation and recommendations
4. **No Results**: Handling cases with no relevant matches

**Usage:**
```python
from growbal_intelligence.core.workflow import GrowbalIntelligenceWorkflow

workflow = GrowbalIntelligenceWorkflow(api_key="your_api_key")

# Streaming execution
async for update in workflow.run_streaming(
    query="I need help with digital marketing",
    max_results=5
):
    print(update)

# Non-streaming execution
result = await workflow.run(
    query="I need help with digital marketing",
    max_results=5
)
```

## Django Interface (`utils/django_interface.py`)

The Django interface provides seamless integration with the Growbal platform's database layer.

**Key Features:**
- Vector similarity search using OpenAI embeddings
- Tag-based profile filtering
- Hybrid search combining multiple approaches
- Profile retrieval and management
- Service tag management

**Available Functions:**
- `search_profiles()`: Semantic similarity search
- `search_profiles_by_service_tags()`: Tag-based filtering
- `search_profiles_hybrid()`: Combined approach
- `get_profile_by_id()`: Direct profile retrieval
- `get_available_service_tags()`: Available service categories

## Streaming Support

All agents support streaming execution for real-time progress updates and improved user experience.

**Streaming Benefits:**
- Real-time progress feedback
- Incremental result display
- Better responsiveness for long-running operations
- Token-level streaming for LLM operations

**Stream Update Types:**
- `strategy_start/complete`: Search strategy analysis
- `search_start/progress/complete`: Profile search operations
- `profile_start/complete`: Individual profile evaluation
- `summarization_start/complete`: Summary generation
- `workflow_start/complete`: Overall workflow status

## Error Handling

The system includes comprehensive error handling at multiple levels:

**Agent Level:**
- Individual agent failure recovery
- Graceful degradation for partial failures
- Detailed error reporting and logging

**Workflow Level:**
- State persistence across failures
- Retry mechanisms for transient errors
- Alternative execution paths

**Response Level:**
- Standardized error responses
- Confidence scoring for quality assessment
- Metadata preservation for debugging

## Performance Considerations

**Optimization Features:**
- Asynchronous execution throughout
- Streaming for improved perceived performance
- Efficient database queries with Django ORM
- Vector similarity search optimization
- Result caching where appropriate

**Scaling Considerations:**
- Stateless agent design for horizontal scaling
- Database connection pooling
- Rate limiting for API calls
- Memory-efficient processing for large result sets

## Configuration

The system is configured through environment variables and initialization parameters:

**Required Environment Variables:**
- `ANTHROPIC_API_KEY`: API key for Claude models
- Django database settings (inherited from main application)

**Optional Configuration:**
- Model selection (default: claude-3-5-haiku-20241022)
- Temperature settings for different agents
- Timeout and retry configurations
- Logging levels and output formats

## Integration with Main Application

This system integrates with the main Growbal application (`main.py`) through:

1. **Orchestrator Interface**: High-level interface for chat interactions
2. **Session Management**: Integration with database-backed sessions
3. **Real-time Streaming**: WebSocket-compatible progress updates
4. **Authentication**: User context and permissions handling

The intelligence system is instantiated and used by the orchestrator agent in the main application, providing the core AI capabilities that power the chat interface and search functionality.

## Development and Testing

**Testing Resources:**
- `testing/test_all_agents.ipynb`: Comprehensive agent testing notebook
- Unit tests for individual components
- Integration tests for workflow execution
- Performance benchmarking utilities

**Development Guidelines:**
- All agents must support both streaming and non-streaming execution
- Pydantic models ensure type safety and validation
- Comprehensive error handling and logging required
- Documentation for all public interfaces

## Future Enhancements

**Planned Features:**
- Multi-language support for queries and responses
- Advanced filtering and sorting options
- Learning capabilities based on user feedback
- Enhanced caching and performance optimization
- Additional search strategies and algorithms

This intelligent agent system forms the foundation of Growbal's AI-powered service provider matching capabilities, providing sophisticated search, evaluation, and recommendation features through a clean, modular architecture.
