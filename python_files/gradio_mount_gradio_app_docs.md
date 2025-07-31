# Gradio mount_gradio_app Documentation

Source: https://www.gradio.app/docs/gradio/mount_gradio_app

## Overview

`mount_gradio_app` is a method in Gradio that allows you to mount a Gradio Blocks application to an existing FastAPI application.

## Parameters

### Required Parameters
- **`app`**: The parent FastAPI application
- **`blocks`**: The Gradio Blocks object to mount
- **`path`**: The URL path where the Gradio app will be mounted (e.g. "/gradio")

### Optional Parameters
- **`server_name`**: Server name (default "0.0.0.0")
- **`server_port`**: Port number (default 7860)
- **`auth`**: Authentication mechanism
- **`show_api`**: Control API button visibility
- **`allowed_paths`**: Specify allowed file serving paths
- **`blocked_paths`**: Specify paths not allowed to be served

## Example Usage

```python
from fastapi import FastAPI
import gradio as gr

app = FastAPI()
io = gr.Interface(lambda x: "Hello, " + x + "!", "textbox", "textbox")
app = gr.mount_gradio_app(app, io, path="/gradio")
```

## Return Value

The method returns a modified FastAPI application with the Gradio app integrated at the specified path.

## Important Notes

- This allows you to integrate Gradio interfaces into existing FastAPI applications seamlessly
- The Gradio app will be accessible at the specified path (e.g., http://localhost:8000/gradio)
- All Gradio routes will be prefixed with the specified path