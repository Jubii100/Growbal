# GitHub Issue #1608: Embedding Gradio within a FastAPI App

Source: https://github.com/gradio-app/gradio/issues/1608

## Issue Overview

This GitHub issue discusses methods and best practices for embedding Gradio applications within FastAPI applications.

## Key Solutions

### 1. Basic Mounting Approach

```python
from fastapi import FastAPI
import gradio as gr

CUSTOM_PATH = "/gradio"

app = FastAPI()

# Create Gradio interface
io = gr.Interface(lambda x: f"Hello, {x}!", "textbox", "textbox")
gradio_app = gr.routes.App.create_app(io)

# Mount Gradio app at a specific path
app.mount(CUSTOM_PATH, gradio_app)
```

### 2. Alternative Approach with gr.mount_gradio_app

```python
from fastapi import FastAPI
import gradio as gr

app = FastAPI()
io = gr.Interface(lambda x: "Hello, " + x + "!", "textbox", "textbox")
app = gr.mount_gradio_app(app, io, path="/gradio")
```

## Important Considerations

### Compatibility
- Works with both `gr.Interface()` and `gr.Blocks()`
- Can access FastAPI app via `demo.app` or `app, local_url, share_url = demo.launch()`
- Gradio automatically creates routes like `/` for interface and `/api/predict`

### Potential Challenges
- Some users reported issues with `demo.queue().launch()` and more complex Gradio configurations
- Recommended to use the latest Gradio version for better compatibility
- Complex Gradio apps with queuing might require additional configuration

### Benefits
- Creates a unified application with multiple routes and interfaces
- Maintains flexibility in routing and functionality
- Allows sharing of session state between FastAPI and Gradio
- Single server process for both FastAPI and Gradio

## Advanced Usage Tips

1. **Route Prefixing**: All Gradio routes will be prefixed with the mount path
2. **Authentication**: Can integrate FastAPI authentication with Gradio
3. **Static Files**: Gradio static files will be served from the mounted path
4. **API Access**: Gradio API endpoints remain accessible under the mounted path

## Community Feedback

Users have successfully implemented this approach for:
- Multi-page applications
- Integrating ML models with web APIs
- Creating admin interfaces alongside main applications
- Building complex dashboards with mixed FastAPI/Gradio functionality