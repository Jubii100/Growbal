# Growbal Intelligence Chat Application

A sophisticated AI-powered FastAPI chat application that provides intelligent service provider search and recommendation through an orchestrator-based agent system. The application features secure authentication, persistent session management, and real-time streaming responses.

## Overview

The Growbal Intelligence Chat Application is the primary user interface for the Growbal platform, offering users an intelligent conversational experience to discover and connect with service providers. The system leverages advanced AI orchestration to coordinate tool selection, provide contextual responses, and maintain persistent conversation history across sessions.

## Architecture

### Core Components

**FastAPI Backend**: High-performance web framework providing RESTful endpoints and WebSocket support
**Authentication System**: Secure user authentication with BCrypt password hashing and session management
**Session Management**: Database-backed session persistence using Django ORM with PostgreSQL
**Orchestrator Agent**: Intelligent agent coordination system for tool selection and response generation
**Streaming Interface**: Real-time response streaming through Gradio integration
**Database Integration**: Multi-database architecture connecting PostgreSQL (sessions) and MySQL (authentication)

### Agent Architecture

The application utilizes a multi-agent architecture powered by the Growbal Intelligence system:

**Search Agent**: Performs semantic and tag-based searches across service provider profiles
**Adjudicator Agent**: Evaluates relevance and quality of search results
**Summarizer Agent**: Generates comprehensive summaries and recommendations
**Orchestrator Agent**: Coordinates tool selection based on message analysis and context

## Key Features

### Authentication and Security

- **Secure Login System**: BCrypt-hashed password verification against external MySQL database
- **Session Management**: Server-side session storage with automatic cleanup and expiration
- **User Context**: Persistent user identification and authorization across sessions
- **Route Protection**: Authentication middleware protecting all endpoints
- **Cross-Origin Support**: Configurable CORS middleware for secure multi-domain deployment

### Intelligent Chat Interface

- **Orchestrator-Driven Responses**: AI-powered tool selection based on message analysis
- **Real-Time Streaming**: Progressive response delivery for improved user experience
- **Context-Aware Suggestions**: Dynamic suggestions based on country, service type, and conversation history
- **Session History**: Persistent chat history with collapsible view and Markdown rendering
- **Multi-Session Support**: Users can maintain multiple concurrent chat sessions

### Database-Backed Session Management

- **Duplicate Prevention**: Automatic detection and reuse of existing sessions with identical parameters
- **Activity Tracking**: Real-time updates of session activity timestamps
- **Message Persistence**: Complete conversation history stored with metadata
- **User Session Listing**: Sidebar navigation showing all user sessions with activity indicators
- **Automatic Cleanup**: Weekly background task to deactivate sessions older than 7 days

### User Interface Features

- **Responsive Design**: Mobile-friendly interface with collapsible sidebars
- **Session Sidebar**: Navigation panel showing all active sessions with metadata
- **Chat History Panel**: Collapsible view of previous conversation history
- **Markdown Support**: Rich text rendering for formatted responses
- **Real-Time Updates**: Progressive content delivery with streaming support

## Technical Specifications

### Framework and Dependencies

**Core Framework**: FastAPI 0.115.12 with Uvicorn ASGI server
**AI Integration**: Anthropic Claude models via official Python SDK
**UI Framework**: Gradio 4.44.1 for interactive web interfaces
**Database**: Django 5.2 ORM with PostgreSQL and MySQL support
**Authentication**: Custom BCrypt-based system with session middleware

### Database Schema

**ChatSession Model**: Session management with UUID identification, user association, and metadata storage
**ChatMessage Model**: Message storage with role, content, and timestamp tracking
**Authentication Models**: User credential verification with external MySQL integration

### API Endpoints

- `GET /` - Root endpoint with authentication-based routing
- `GET /login` - User login page with form interface
- `POST /login` - Authentication processing endpoint
- `POST /logout` - Session termination endpoint
- `GET|POST /proceed-to-chat` - Session creation and parameter handling
- `GET /chat/` - Main chat interface with session context
- `GET /chat-public/` - Embedded Gradio chat interface

### Environment Configuration

The application requires the following environment variables:

```bash
# API Keys
ANTHROPIC_API_KEY=your_anthropic_api_key

# Session Security
SESSION_SECRET_KEY=your_session_secret_key
COOKIE_DOMAIN=your_domain.com
COOKIE_SAMESITE=Lax
COOKIE_SECURE=true

# CORS Configuration
ALLOWED_ORIGINS=https://your-domain.com
CORS_STRICT=true

# Database Configuration (inherited from Django settings)
DJANGO_SETTINGS_MODULE=growbal.settings
```

## Installation and Setup

### Prerequisites

- Python 3.8+
- PostgreSQL 11+ with pgvector extension
- MySQL 5.7+ (for authentication)
- Node.js (for frontend dependencies)

### Installation Steps

1. **Clone and Navigate**
   ```bash
   cd /path/to/growbal/chat
   ```

2. **Install Dependencies**
   ```bash
   pip install -r ../requirements.txt
   ```

3. **Environment Configuration**
   ```bash
   cp ../envs/1.env.example ../envs/1.env
   # Edit ../envs/1.env with your configuration
   ```

4. **Database Setup**
   ```bash
   # PostgreSQL setup (for session management)
   createdb growbal_sessions
   psql growbal_sessions -c "CREATE EXTENSION IF NOT EXISTS vector;"
   
   # MySQL setup (for authentication)
   mysql -u root -p -e "CREATE DATABASE growbal_auth;"
   ```

5. **Django Migration**
   ```bash
   cd ../growbal_django
   python manage.py migrate
   cd ../chat
   ```

6. **Start Application**
   ```bash
   python main.py
   ```

The application will be available at `http://localhost:8000`

## Usage Guide

### User Authentication

1. **Initial Access**: Navigate to the application URL
2. **Login Required**: Unauthenticated users are redirected to login page
3. **Credential Entry**: Enter email and password for authentication
4. **Session Creation**: Successful login creates secure session and redirects to chat

### Chat Interface

1. **Session Parameters**: Specify country and service type for contextualized search
2. **Message Entry**: Submit queries through the chat interface
3. **AI Processing**: Orchestrator analyzes message and selects appropriate tools
4. **Streaming Response**: Receive real-time progressive responses
5. **History Access**: View previous conversation history in collapsible panel

### Session Management

1. **Multiple Sessions**: Create multiple sessions with different parameters
2. **Session Navigation**: Switch between sessions using the sidebar
3. **Activity Tracking**: Sessions show last activity timestamps
4. **Automatic Cleanup**: Inactive sessions are automatically deactivated after 7 days

## Integration Points

### Growbal Intelligence System

The chat application integrates with the Growbal Intelligence system located in `../growbal_intelligence/`:

- **Workflow Orchestration**: LangGraph-based agent coordination
- **Search Capabilities**: Vector similarity and tag-based search
- **Profile Evaluation**: Relevance assessment and filtering
- **Summary Generation**: Comprehensive response synthesis

### Django Backend Integration

Session and user data is managed through Django models:

- **ChatSession**: Session persistence and metadata
- **ChatMessage**: Message history and conversation tracking
- **User Authentication**: External MySQL credential verification

### Database Architecture

**PostgreSQL (Primary)**:
- Session management and chat history
- Vector embeddings for search functionality
- Django ORM integration

**MySQL (Authentication)**:
- User credential storage with BCrypt hashing
- External authentication system integration

## Security Considerations

### Authentication Security

- **Password Hashing**: BCrypt with configurable rounds for password security
- **Session Management**: Server-side session storage with secure cookies
- **HTTPS Enforcement**: Secure cookie attributes for production deployment
- **CORS Protection**: Configurable origin restrictions for cross-site security

### Data Protection

- **Session Isolation**: User sessions are isolated and access-controlled
- **Metadata Encryption**: Sensitive session data encrypted at rest
- **Activity Logging**: User actions logged for security monitoring
- **Automatic Cleanup**: Regular purging of inactive sessions

## Performance Optimization

### Streaming and Responsiveness

- **Progressive Loading**: Real-time content delivery through streaming
- **Asynchronous Processing**: Non-blocking I/O for concurrent user handling
- **Connection Pooling**: Efficient database connection management
- **Background Tasks**: Automated maintenance tasks for optimal performance

### Caching and Memory Management

- **Session Caching**: In-memory session context for active users
- **Database Optimization**: Efficient queries with Django ORM optimization
- **Memory Cleanup**: Automatic cleanup of inactive session data
- **Resource Management**: Controlled resource allocation for agent processing

## Monitoring and Maintenance

### Logging and Debugging

- **Application Logging**: Comprehensive logging with configurable levels
- **Session Debugging**: Debug output for session lifecycle tracking
- **Agent Tracing**: Detailed orchestrator decision tracking
- **Error Handling**: Graceful error recovery with user-friendly messages

### Maintenance Tasks

- **Weekly Cleanup**: Automatic deactivation of sessions older than 7 days
- **Database Maintenance**: Regular optimization of session and message tables
- **Security Updates**: Regular dependency updates for security patches
- **Performance Monitoring**: Application performance tracking and optimization

## Deployment Considerations

### Production Configuration

**Environment Variables**: Secure configuration management with environment-specific settings
**Database Scaling**: Connection pooling and read replica configuration
**Load Balancing**: Multi-instance deployment with session affinity
**SSL/TLS**: HTTPS enforcement with proper certificate management

### Infrastructure Requirements

**Compute**: Minimum 2GB RAM, 2 CPU cores for single instance
**Storage**: SSD storage for database performance and session management
**Network**: Low-latency connection for real-time streaming functionality
**Monitoring**: Application and infrastructure monitoring for production stability

## Development Guidelines

### Code Organization

- **Modular Architecture**: Clear separation of concerns across components
- **Async/Await**: Consistent asynchronous programming patterns
- **Type Hints**: Comprehensive type annotations for code clarity
- **Error Handling**: Robust exception handling with graceful degradation

### Testing Approach

- **Unit Testing**: Individual component testing with mock dependencies
- **Integration Testing**: End-to-end workflow testing with database
- **Performance Testing**: Load testing for concurrent user scenarios
- **Security Testing**: Authentication and authorization validation

## Troubleshooting

### Common Issues

**Authentication Failures**: Verify MySQL connection and user credentials
**Session Persistence**: Check PostgreSQL connectivity and Django configuration
**Streaming Issues**: Verify WebSocket support and network configuration
**Agent Errors**: Confirm Anthropic API key and quota availability

### Debug Information

The application provides extensive debug output including:
- Session lifecycle events and state transitions
- Orchestrator decision making and tool selection
- Database query execution and performance metrics
- User authentication and authorization events

## Future Enhancements

### Planned Features

- **Multi-Language Support**: Internationalization for global deployment
- **Advanced Analytics**: User behavior tracking and conversation analytics
- **API Integration**: RESTful API for programmatic access
- **Mobile Application**: Native mobile app with chat functionality

### Scalability Improvements

- **Microservices Architecture**: Service decomposition for independent scaling
- **Message Queuing**: Asynchronous message processing with queue systems
- **Distributed Sessions**: Redis-based session management for horizontal scaling
- **CDN Integration**: Content delivery optimization for global accessibility

## Contributing

When contributing to this application:

1. **Follow Conventions**: Maintain consistent code style and naming conventions
2. **Test Coverage**: Ensure comprehensive testing for new features
3. **Documentation**: Update documentation for architectural changes
4. **Security Review**: Consider security implications of all modifications
5. **Performance Impact**: Evaluate performance effects of new features

## License

This project is proprietary and confidential to Growbal Intelligence Platform.

---

*This chat application represents the primary user interface for the Growbal platform, providing intelligent service provider discovery through advanced AI agent coordination and secure user session management.*
