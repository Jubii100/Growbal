# Detailed Gradio Request Documentation

Source: https://www.gradio.app/docs/gradio/request

## Overview

The `gr.Request` class provides access to request metadata and headers from within a Gradio prediction function, enabling integration with FastAPI request handling.

## Class Definition

```python
class gr.Request:
    def __init__(
        self,
        request: fastapi.Request | None = None,
        username: str | None = None,
        session_hash: str | None = None
    )
```

## Attributes

### Core Attributes
- **`headers`**: Request headers (dict-like)
- **`client`**: Client connection details
- **`query_params`**: URL query parameters (dict-like)
- **`session_hash`**: Unique session identifier
- **`path_params`**: URL path parameters
- **`username`**: Logged-in user (if auth is enabled)

### FastAPI Integration
- **`request`**: Access to underlying FastAPI Request object
- **`request.session`**: FastAPI session data (if SessionMiddleware is configured)

## Usage Examples

### Basic Request Information
```python
def echo(text, request: gr.Request):
    if request:
        print("Request headers:", dict(request.headers))
        print("IP address:", request.client.host)
        print("Query parameters:", dict(request.query_params))
        print("Session hash:", request.session_hash)
    return text

interface = gr.Interface(echo, "textbox", "textbox")
```

### FastAPI Session Access
```python
def chat_fn(message, history, request: gr.Request):
    user_id = request.username  # if using Gradio auth
    session_hash = request.session_hash
    
    # Access full FastAPI request via request.request
    if request.request:
        username = request.request.session.get("username")
        user_data = request.request.session.get("user_data")
    
    return response, updated_history
```

### Parameter Extraction
```python
def process_with_params(input_text, request: gr.Request):
    # Extract query parameters
    params = dict(request.query_params)
    country = params.get("country", "default")
    session_id = params.get("session_id")
    
    # Process with context
    return f"Processing for {country} (session: {session_id}): {input_text}"
```

## Best Practices

1. **Type Conversion**: Convert dict-like attributes to dictionaries for consistent behavior
2. **Null Checking**: Always check if request object exists before accessing attributes
3. **Session Management**: Use FastAPI's SessionMiddleware for persistent session data
4. **Security**: Validate and sanitize all request data before processing

## Integration with FastAPI

When using `gr.mount_gradio_app()`, the Gradio request object automatically wraps the FastAPI request, providing seamless access to:
- HTTP headers
- Query parameters
- Session data
- Client information
- Authentication details

This enables building sophisticated applications that combine FastAPI's robust web framework capabilities with Gradio's interactive interface features.