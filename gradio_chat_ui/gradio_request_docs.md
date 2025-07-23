# Gradio Request Documentation

Source: https://www.gradio.app/docs/gradio/request

## Description

A Gradio Request object provides access to request details within a prediction function, wrapping the FastAPI Request class.

## Key Attributes

- **`headers`**: Request headers
- **`client`**: Client information
- **`query_params`**: URL query parameters
- **`session_hash`**: Unique session identifier
- **`username`**: Logged-in user (if auth enabled)

## Example Usage

```python
import gradio as gr

def echo(text, request: gr.Request):
    if request:
        print("Request headers:", request.headers)
        print("IP address:", request.client.host)
        print("Query parameters:", dict(request.query_params))
        print("Session hash:", request.session_hash)
    return text

io = gr.Interface(echo, "textbox", "textbox").launch()
```

## Initialization Parameters

- **`request`**: FastAPI Request object (default: None)
- **`username`**: Logged-in username (default: None)
- **`session_hash`**: Unique session hash (default: None)

## Important Notes

- Dict-like attributes should be converted to dictionaries for consistent behavior
- Useful for accessing request metadata within prediction functions
- The `gr.Request` parameter must be included in your function signature to access request information
- When used with FastAPI integration, `request.request` provides access to the underlying FastAPI Request object

## Use Cases

1. **Authentication**: Access logged-in username
2. **Session Management**: Track user sessions with session_hash
3. **Client Information**: Get client IP address and other details
4. **Custom Headers**: Access any custom headers sent with the request
5. **Query Parameters**: Read URL query parameters