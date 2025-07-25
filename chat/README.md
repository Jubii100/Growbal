# Growbal Intelligence FastAPI Application

A comprehensive FastAPI application that integrates Gradio-based country selection and chat interface components for AI-powered service provider search.

## Features

- **Country Selection Interface**: Interactive country selection with Gradio UI
- **Chat Interface**: AI-powered chat interface for service provider search
- **Session Management**: Proper session handling and parameter passing
- **FastAPI Integration**: Seamless integration between FastAPI and Gradio
- **Event Handling**: JavaScript-based communication between components
- **Responsive Design**: Mobile-friendly interface with proper styling

## Architecture

```
FastAPI App (Port 8000)
├── / → Redirects to /country/
├── /country/ → Country selection page (iframe wrapper)
├── /country-gradio/ → Gradio country selection app
├── /chat/{session_id}/{country}/ → Chat interface page (iframe wrapper)
├── /chat-gradio/{session_id}/{country}/ → Gradio chat app
├── /api/session/{session_id} → Session management API
├── /health → Health check endpoint
└── /debug/sessions → Debug session information
```

## Installation

### Prerequisites

- Python 3.8+
- pip package manager
- Virtual environment (recommended)

### Dependencies

```bash
pip install fastapi uvicorn gradio python-dotenv python-multipart
```

### Environment Setup

1. Create a `.env` file in the `envs/` directory:
```env
SESSION_SECRET_KEY=your-secret-key-change-in-production
ANTHROPIC_API_KEY=your-anthropic-api-key
```

2. Ensure the following directory structure:
```
growbal/
├── chat/
│   ├── main_app.py
│   ├── improved_main_app.py
│   ├── run_app.py
│   ├── country_selection.py
│   ├── chat_interface.py
│   └── growbal_logoheader.svg
├── gradio_chat_ui/
│   ├── country_selection.py
│   └── chat_interface.py
└── envs/
    └── 1.env
```

## Running the Application

### Method 1: Using the Runner Script

```bash
cd chat/
python run_app.py
```

### Method 2: Direct uvicorn Command

```bash
cd chat/
uvicorn improved_main_app:app --host 0.0.0.0 --port 8000 --reload
```

### Method 3: Python Module

```bash
cd chat/
python -m improved_main_app
```

## Application Flow

1. **Start**: User visits http://localhost:8000
2. **Country Selection**: Redirected to `/country/` which displays the country selection interface
3. **Selection**: User selects a country and clicks "Continue to Search"
4. **Redirect**: JavaScript sends postMessage to parent window with redirect URL
5. **Chat Interface**: User is redirected to `/chat/{session_id}/{country}/`
6. **Chat**: Chat interface loads with the selected country context
7. **Session Management**: Session data is stored and managed by FastAPI

## API Endpoints

### Main Routes

- `GET /` - Root redirect to country selection
- `GET /country/` - Country selection page
- `GET /chat/{session_id}/{country}/` - Chat interface page

### Gradio Mounts

- `GET /country-gradio/` - Country selection Gradio app
- `GET /chat-gradio/{session_id}/{country}/` - Chat Gradio app

### API Routes

- `GET /api/session/{session_id}` - Get session information
- `POST /api/session/{session_id}/update` - Update session data
- `GET /health` - Health check endpoint
- `GET /debug/sessions` - Debug session information

## Event Handling

The application uses JavaScript `postMessage` API for communication between the parent window and Gradio iframes:

```javascript
// In Gradio apps
window.parent.postMessage({
    type: 'redirect',
    url: '/chat/{session_id}/{country}/'
}, '*');

// In parent window
window.addEventListener('message', function(event) {
    if (event.data.type === 'redirect') {
        window.location.href = event.data.url;
    }
});
```

## Session Management

- Sessions are automatically created when users select a country
- Session data includes country, creation time, and activity tracking
- Automatic cleanup of old sessions (configurable)
- Session limit enforcement to prevent resource exhaustion

## Configuration

### Environment Variables

- `SESSION_SECRET_KEY`: Secret key for session encryption
- `ANTHROPIC_API_KEY`: API key for AI chat functionality

### Application Settings

- `MAX_CHAT_SESSIONS`: Maximum concurrent chat sessions (default: 10)
- `SESSION_CLEANUP_INTERVAL`: Session cleanup interval in seconds (default: 300)

## Development

### File Structure

- `main_app.py` - Basic FastAPI application
- `improved_main_app.py` - Enhanced version with better session management
- `run_app.py` - Application runner script
- `country_selection.py` - Country selection Gradio app
- `chat_interface.py` - Chat interface Gradio app

### Adding New Features

1. Create new Gradio components in separate files
2. Import and mount them in the main FastAPI app
3. Update routing and session management as needed
4. Add proper error handling and logging

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure all dependencies are installed and the project root is in Python path
2. **Session Issues**: Check that session middleware is properly configured
3. **Gradio Mounting**: Verify that Gradio apps are properly imported and mounted
4. **JavaScript Errors**: Check browser console for postMessage communication issues

### Debug Commands

```bash
# Check application health
curl http://localhost:8000/health

# View active sessions
curl http://localhost:8000/debug/sessions

# Test specific session
curl http://localhost:8000/api/session/{session_id}
```

### Logs

The application uses uvicorn's logging system. Enable debug logging:

```bash
uvicorn improved_main_app:app --log-level debug
```

## Production Deployment

### Security Considerations

1. Change the `SESSION_SECRET_KEY` to a strong, random value
2. Set up proper CORS policies
3. Use HTTPS in production
4. Implement rate limiting
5. Add authentication if needed

### Performance Optimizations

1. Use a production ASGI server (e.g., Gunicorn with uvicorn workers)
2. Implement Redis for session storage
3. Add caching for frequently accessed data
4. Use a reverse proxy (nginx) for static files

### Docker Deployment

```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["uvicorn", "improved_main_app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## License

This project is part of the Growbal Intelligence platform. All rights reserved.

## Support

For issues and support, please check the application logs and debug endpoints first. Common solutions can be found in the troubleshooting section above.