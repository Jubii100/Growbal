# Detailed Gradio mount_gradio_app Documentation

Source: https://www.gradio.app/docs/gradio/mount_gradio_app

## Overview

The `mount_gradio_app` function allows you to mount a Gradio Blocks interface to an existing FastAPI application, enabling seamless integration between the two frameworks.

## Function Signature

```python
gr.mount_gradio_app(
    app: fastapi.FastAPI,
    blocks: gr.Blocks,
    path: str,
    server_name: str = "0.0.0.0",
    server_port: int = 7860,
    show_api: bool = True,
    auth: Optional[Callable] = None,
    root_path: str = "",
    allowed_paths: Optional[List[str]] = None,
    blocked_paths: Optional[List[str]] = None
)
```

## Parameters

### Required Parameters
- **`app`**: The parent FastAPI application instance
- **`blocks`**: The Gradio Blocks object to mount
- **`path`**: URL path where the Gradio app will be mounted (e.g., "/gradio")

### Optional Parameters
- **`server_name`**: Server name (default: "0.0.0.0")
- **`server_port`**: Port number (default: 7860)
- **`show_api`**: Hide/show API button in the interface
- **`auth`**: Authentication configuration
- **`root_path`**: Subpath for public deployment
- **`allowed_paths`**: List of permitted file/directory access paths
- **`blocked_paths`**: List of restricted file/directory access paths

## Example Usage

```python
from fastapi import FastAPI
import gradio as gr

app = FastAPI()

@app.get("/")
def read_main():
    return {"message": "This is your main app"}

# Create Gradio interface
io = gr.Interface(lambda x: "Hello, " + x + "!", "textbox", "textbox")

# Mount Gradio app to FastAPI
app = gr.mount_gradio_app(app, io, path="/gradio")

# Run with: uvicorn run:app
# Access at: http://localhost:8000/gradio
```

## Integration Benefits

1. **Unified Server**: Run both FastAPI and Gradio on the same server
2. **Shared Context**: Access FastAPI request/session data in Gradio callbacks
3. **Seamless Navigation**: Handle redirects between different parts of your app
4. **Resource Sharing**: Share authentication, middleware, and other FastAPI features

## Best Practices

1. **Path Structure**: Use clear, descriptive paths for mounting (e.g., "/gradio", "/chat")
2. **Authentication**: Leverage FastAPI's auth systems with Gradio interfaces
3. **Session Management**: Use FastAPI's session middleware for state management
4. **Error Handling**: Implement proper error handling for both frameworks