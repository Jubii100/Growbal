# GitHub Issue #7838: Allow Event Listeners to Redirect to Another Page

Source: https://github.com/gradio-app/gradio/issues/7838

## Issue Overview

This GitHub issue discusses the need for hyperlink functionality in Gradio components and the ability to redirect users to other pages after certain events.

## Problem Statement

The user wanted to add hyperlink functionality to Gradio gallery images and captions, specifically:

1. Ability to redirect after clicking an image
2. Add redirect buttons near images  
3. Make captions clickable with URLs

## Current Limitations

- Gradio doesn't natively support image/caption hyperlinks
- No built-in way for callbacks to change browser URL
- Limited navigation options within Gradio applications

## Proposed Solutions

### 1. JavaScript-Based Redirect (Current Workaround)

```python
greet_btn.click(None, None, None, js="() => {window.location.href = '/up'}")
```

This approach uses the `js` parameter to execute JavaScript that redirects the browser.

### 2. Alternative JavaScript Methods

```python
button = gr.Button("Go to Home")
button.click(None, [], [], _js="window.location.pathname='/home'")
```

Using the `_js` parameter for client-side navigation.

### 3. FastAPI Integration Approach

```python
# Define FastAPI route that returns RedirectResponse
@app.get("/redirect-endpoint")
def redirect_handler():
    return RedirectResponse(url="/target-page")

# Link to it from Gradio UI
```

## Official Response

A Gradio maintainer (abidlabs) commented that the "general solution would be to allow event listeners to return an argument that redirects the Gradio application to a separate page."

## Future Development

- This feature is part of the Gradio 5.x milestone
- The team is considering multi-page app support
- Enhanced navigation capabilities are being planned

## Current Best Practices

1. **Use JavaScript workarounds** for simple redirects
2. **Integrate with FastAPI routes** for complex navigation logic
3. **Consider external links** for navigation outside the app
4. **Use Gradio Tabs** for internal navigation where appropriate

## Implementation Examples

### Basic Page Redirect
```python
def create_redirect_button(target_url):
    button = gr.Button("Navigate")
    button.click(
        None, 
        [], 
        [], 
        _js=f"() => {{window.location.href = '{target_url}'}}"
    )
    return button
```

### Conditional Redirects
```python
def conditional_redirect(condition, success_url, failure_url):
    if condition:
        return None, None, None, f"() => {{window.location.href = '{success_url}'}}"
    else:
        return None, None, None, f"() => {{window.location.href = '{failure_url}'}}"
```

## Status

The issue remains open and is actively being considered for future Gradio versions. The current workarounds provide functional solutions while native support is being developed.