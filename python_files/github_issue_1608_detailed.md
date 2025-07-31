# GitHub Issue #1608: Embedding Gradio within FastAPI App

Source: https://github.com/gradio-app/gradio/issues/1608

## Issue Overview

This GitHub issue discusses best practices and techniques for embedding Gradio interfaces within FastAPI applications, covering integration patterns, session management, and common challenges.

## Key Integration Approaches

### 1. Using FastAPI's mount() Method
```python
from fastapi import FastAPI
import gradio as gr

app = FastAPI()

# Create Gradio interface
io = gr.Interface(lambda x: f"Hello, {x}!", "textbox", "textbox")
gradio_app = gr.routes.App.create_app(io)

# Mount Gradio app at a specific path
app.mount("/gradio", gradio_app)
```

### 2. Using gr.mount_gradio_app() (Recommended)
```python
from fastapi import FastAPI
import gradio as gr

app = FastAPI()

# Create Gradio interface
io = gr.Interface(lambda x: f"Hello, {x}!", "textbox", "textbox")

# Mount using Gradio's helper function
app = gr.mount_gradio_app(app, io, path="/gradio")
```

## Technical Details

### Gradio App Structure
- Gradio automatically creates a FastAPI instance under the hood
- The Gradio interface runs at the root path `/`
- Prediction API is typically available at `/api/predict`
- You can access the FastAPI app via `demo.app` or through launch return values

### API Endpoints
When mounting a Gradio app, the following endpoints become available:
- `/gradio/` - Main Gradio interface
- `/gradio/api/predict` - Prediction API endpoint
- `/gradio/api/` - API documentation

## Session Management and Parameter Passing

### Query Parameters
```python
def process_with_context(input_text, request: gr.Request):
    # Extract parameters from URL query string
    params = dict(request.query_params)
    session_id = params.get("session_id")
    country = params.get("country")
    
    # Process with context
    return f"Processing for {country} (session: {session_id}): {input_text}"
```

### FastAPI Session Integration
```python
from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

def chat_function(message, history, request: gr.Request):
    # Access FastAPI session data
    if request.request:
        user_data = request.request.session.get("user_data")
        session_info = request.request.session.get("session_info")
    
    return response, updated_history
```

## Common Challenges and Solutions

### 1. Complex Gradio Blocks and Queuing
- **Issue**: Some users reported issues with more complex Gradio Blocks and queuing systems
- **Solution**: Use the latest Gradio version and test thoroughly with your specific use case

### 2. Path Handling
- **Issue**: Confusion about relative vs absolute paths when mounting
- **Solution**: Use clear, descriptive paths and test routing thoroughly

### 3. Static File Serving
- **Issue**: Static files not being served correctly
- **Solution**: Configure allowed_paths and blocked_paths parameters properly

## Best Practices

1. **Version Compatibility**: Use the latest Gradio version for best compatibility
2. **Clear Path Structure**: Use descriptive paths for mounting (e.g., "/gradio", "/chat")
3. **Testing**: Thoroughly test complex interfaces with queuing enabled
4. **Documentation**: Document your API endpoints and integration patterns
5. **Error Handling**: Implement proper error handling for both frameworks

## Advanced Integration Patterns

### Multi-App Architecture
```python
app = FastAPI()

# Mount multiple Gradio apps
country_app = create_country_selection_app()
chat_app = create_chat_interface_app()

app = gr.mount_gradio_app(app, country_app, path="/country")
app = gr.mount_gradio_app(app, chat_app, path="/chat")
```

### Middleware Integration
```python
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])
app.add_middleware(SessionMiddleware, secret_key="secret")

# Mount Gradio with middleware support
app = gr.mount_gradio_app(app, interface, path="/gradio")
```

## Community Feedback

The discussion reveals that this approach provides excellent flexibility for:
- Combining prediction endpoints with interactive interfaces
- Building complex multi-page applications
- Integrating with existing FastAPI applications
- Sharing authentication and session management

The consensus is that `gr.mount_gradio_app()` is the recommended approach for most use cases.