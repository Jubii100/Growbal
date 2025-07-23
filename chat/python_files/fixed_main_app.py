"""
Fixed FastAPI application with proper Gradio integration
- Proper mounting of chat interface apps
- Working JavaScript redirects
- Session management
"""

import os
import sys
import uuid
import time
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import gradio as gr
from dotenv import load_dotenv

# Load environment variables
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, 'envs', '1.env')
load_dotenv(env_path)

# Add the project root to the path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import our Gradio apps
from country_selection import create_country_selection_app
from chat.python_files.chat_interface import create_chat_interface_app

# Create FastAPI app
app = FastAPI(
    title="Growbal Intelligence Platform",
    description="AI-powered service provider search with country selection and chat interface",
    version="1.0.0"
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-in-production-2024")
)

# Global storage
session_store: Dict[str, Dict[str, Any]] = {}
mounted_apps: Dict[str, Any] = {}


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint that redirects to country selection"""
    return RedirectResponse(url="/country/")


@app.get("/country/", response_class=HTMLResponse)
async def country_selection_page():
    """Serve the country selection page"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Growbal Intelligence - Country Selection</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                margin: 0;
                padding: 0;
                font-family: 'Inter', Arial, sans-serif;
                background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%);
                min-height: 100vh;
            }
            .container {
                width: 100%;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }
            .gradio-container {
                flex: 1;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            iframe {
                width: 100%;
                height: 100%;
                border: none;
                background: transparent;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="gradio-container">
                <iframe src="/country-gradio/" id="countryFrame"></iframe>
            </div>
        </div>
        
        <script>
            // Listen for messages from the Gradio iframe
            window.addEventListener('message', function(event) {
                console.log('Parent window received message:', event.data);
                
                if (event.data && event.data.type === 'redirect') {
                    console.log('Redirecting to:', event.data.url);
                    // Use location.assign for better history management
                    window.location.assign(event.data.url);
                }
            });
            
            // Debug: Check if iframe loads
            document.getElementById('countryFrame').onload = function() {
                console.log('Country selection iframe loaded successfully');
            };
        </script>
    </body>
    </html>
    """


@app.get("/chat/{session_id}/{country}/", response_class=HTMLResponse)
async def chat_interface_page(session_id: str, country: str, request: Request):
    """Serve the chat interface page with session and country parameters"""
    
    # Store session data
    session_store[session_id] = {
        "country": country,
        "created_at": time.time(),
        "active": True,
        "last_activity": time.time()
    }
    
    # Store in FastAPI session
    request.session["session_id"] = session_id
    request.session["country"] = country
    
    # URL encode the country name for the iframe src
    import urllib.parse
    encoded_country = urllib.parse.quote(country)
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Growbal Intelligence - Chat Interface</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: 'Inter', Arial, sans-serif;
                background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%);
                min-height: 100vh;
            }}
            .container {{
                width: 100%;
                height: 100vh;
                display: flex;
                flex-direction: column;
            }}
            .gradio-container {{
                flex: 1;
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }}
            iframe {{
                width: 100%;
                height: 100%;
                border: none;
                background: transparent;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="gradio-container">
                <iframe src="/chat-gradio-{session_id}/{encoded_country}/" id="chatFrame"></iframe>
            </div>
        </div>
        
        <script>
            // Listen for messages from the Gradio iframe
            window.addEventListener('message', function(event) {{
                console.log('Chat parent received message:', event.data);
                
                if (event.data && event.data.type === 'redirect') {{
                    console.log('Redirecting to:', event.data.url);
                    window.location.assign(event.data.url);
                }}
            }});
            
            // Debug: Check if iframe loads
            document.getElementById('chatFrame').onload = function() {{
                console.log('Chat interface iframe loaded successfully');
                console.log('Session ID: {session_id}');
                console.log('Country: {country}');
            }};
        </script>
    </body>
    </html>
    """


# Mount the country selection Gradio app
print("🔧 Setting up Gradio applications...")

country_app = create_country_selection_app()
app = gr.mount_gradio_app(
    app, 
    country_app, 
    path="/country-gradio"
)

print("✅ Country selection app mounted at /country-gradio")


# Dynamic mounting for chat interfaces
def mount_chat_app(session_id: str, country: str):
    """Mount a chat app for a specific session if not already mounted"""
    mount_path = f"/chat-gradio-{session_id}/{country}"
    
    if mount_path not in mounted_apps:
        try:
            # Create the chat app with parameters
            chat_app = create_chat_interface_app(session_id, country)
            
            # Mount it using Gradio's mount function
            global app
            app = gr.mount_gradio_app(
                app,
                chat_app,
                path=mount_path
            )
            
            mounted_apps[mount_path] = True
            print(f"✅ Mounted chat app at {mount_path}")
            
        except Exception as e:
            print(f"❌ Error mounting chat app: {e}")
            raise e
    
    return mount_path


# Handle all routes for chat-gradio with parameters
@app.api_route("/chat-gradio-{session_id}/{country}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def handle_chat_gradio_routes(session_id: str, country: str, request: Request, path: str = ""):
    """Handle all requests to chat Gradio apps"""
    
    # Mount the app if needed
    mount_path = mount_chat_app(session_id, country)
    
    # The Gradio app should now handle this request
    # Since it's already mounted, FastAPI will route it correctly
    # This handler ensures the app is mounted before the request is processed
    
    # Return 404 if we somehow get here (shouldn't happen if mount worked)
    raise HTTPException(status_code=404, detail="Chat interface not found")


# Also handle the root path for chat-gradio
@app.api_route("/chat-gradio-{session_id}/{country}/", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD", "PATCH"])
async def handle_chat_gradio_root(session_id: str, country: str, request: Request):
    """Handle root requests to chat Gradio apps"""
    
    # Mount the app if needed
    mount_path = mount_chat_app(session_id, country)
    
    # For root path, we might need to redirect to the actual Gradio app
    # But the mount should handle this automatically
    # This is a fallback
    
    # Return 404 if we somehow get here
    raise HTTPException(status_code=404, detail="Chat interface not found")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "growbal-intelligence",
        "active_sessions": len(session_store),
        "mounted_apps": len(mounted_apps)
    }


# Debug endpoint
@app.get("/debug/sessions")
async def debug_sessions():
    """Debug endpoint to show all active sessions"""
    return {
        "total_sessions": len(session_store),
        "sessions": session_store,
        "mounted_apps": list(mounted_apps.keys())
    }


# API endpoints for session management
@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session information"""
    if session_id in session_store:
        return session_store[session_id]
    else:
        raise HTTPException(status_code=404, detail="Session not found")


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Growbal Intelligence FastAPI application (Fixed Version)...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page")
    print("   - /chat/{session_id}/{country}/ → Chat interface")
    print("   - /country-gradio/ → Country selection Gradio app")
    print("   - /chat-gradio-{session_id}/{country}/ → Chat Gradio app")
    print("   - /health → Health check")
    print("   - /debug/sessions → Debug session information")
    
    uvicorn.run(
        "fixed_main_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )