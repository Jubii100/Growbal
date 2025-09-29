# Stack Overflow: Gradio HTML Component Display Mounted on FastAPI

Source: https://stackoverflow.com/questions/77195870/gradio-html-component-display-mounted-on-fast-api

## Overview

This Stack Overflow discussion covers how to display user-specific content in a Gradio HTML component when mounted on FastAPI, particularly focusing on session management and user context.

## Key Points from Discussion

### Problem Statement
The user wanted to display personalized content (like a welcome message with username) in a Gradio app mounted on FastAPI, using session data from FastAPI.

### Solution Approaches

1. **Using `demo.load()` to Initialize Session-Based Content**
   - Can call `demo.load(get_user_info, outputs=user_info_html)` on page load
   - This fetches FastAPI session info and populates a hidden HTML or State component

2. **Accessing Session Data via `gr.Request`**
   ```python
   def callback_function(input_data, request: gr.Request):
       # Access FastAPI session through request.request
       username = request.request.session.get('username')
       # Use the username in your logic
       return f"Welcome, {username}!"
   ```

3. **Using SessionMiddleware**
   - Add SessionMiddleware to FastAPI app
   - Access session data through `request.request.session[...]`

### Important Considerations

- Session data from FastAPI is accessible in Gradio callbacks
- The `gr.Request` parameter wraps the underlying FastAPI Request
- Can use Gradio's state components to hold per-session data
- HTML components can be dynamically updated based on session information

## Example Implementation Pattern

```python
# In FastAPI setup
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

# In Gradio callback
def display_user_info(request: gr.Request):
    if request and request.request:
        username = request.request.session.get('username', 'Guest')
        return f"<h2>Welcome, {username}!</h2>"
    return "<h2>Welcome!</h2>"
```

This approach enables seamless integration of FastAPI session management with Gradio UI components.