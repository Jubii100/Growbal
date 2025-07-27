#!/usr/bin/env python3
"""Test script to verify Gradio mounting works correctly"""

import gradio as gr
from fastapi import FastAPI

# Create a simple test
app = FastAPI()

# Create a simple Gradio interface
def greet(name):
    return f"Hello {name}!"

# Create a ChatInterface (returns Blocks)
chat_interface = gr.ChatInterface(
    fn=lambda message, history: f"Echo: {message}",
    title="Test Chat"
)

# Test mounting
print("Testing gr.mount_gradio_app...")
try:
    mounted_app = gr.mount_gradio_app(
        app,
        chat_interface,
        path="/test",
        app_kwargs={"docs_url": None}
    )
    print("✅ Successfully mounted Gradio app!")
    print(f"Mounted app type: {type(mounted_app)}")
except Exception as e:
    print(f"❌ Error mounting: {e}")
    import traceback
    traceback.print_exc()

# Test if the mount persists
print(f"\nApp routes after mounting:")
for route in app.routes:
    print(f"  - {route.path}")