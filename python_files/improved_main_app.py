"""
Improved FastAPI application with better Gradio integration
Features:
- Country selection at /country/ route
- Chat interface at /chat/{session_id}/{country}/ route
- Proper dynamic mounting of chat apps
- Event handling between Gradio and FastAPI
- Session management
"""

import os
import sys
import uuid
import asyncio
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import gradio as gr
from dotenv import load_dotenv
import threading
import time

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

# Global storage
session_store: Dict[str, Dict[str, Any]] = {}
chat_app_cache: Dict[str, gr.Blocks] = {}
app_instances: Dict[str, FastAPI] = {}

# Configuration
MAX_CHAT_SESSIONS = 10  # Limit concurrent chat sessions
SESSION_CLEANUP_INTERVAL = 300  # 5 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan events for the FastAPI app"""
    # Startup
    print("🚀 Starting Growbal Intelligence Platform...")
    
    # Start background cleanup task
    cleanup_task = asyncio.create_task(cleanup_old_sessions())
    
    yield
    
    # Shutdown
    print("🔄 Shutting down Growbal Intelligence Platform...")
    cleanup_task.cancel()
    
    # Clean up chat apps
    for app_instance in app_instances.values():
        try:
            # Graceful shutdown of Gradio apps
            pass
        except Exception as e:
            print(f"Error during cleanup: {e}")


# Create FastAPI app with lifespan
app = FastAPI(
    title="Growbal Intelligence Platform",
    description="AI-powered service provider search with country selection and chat interface",
    version="1.0.0",
    lifespan=lifespan
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


async def cleanup_old_sessions():
    """Background task to clean up old sessions"""
    while True:
        try:
            current_time = time.time()
            sessions_to_remove = []
            
            for session_id, session_data in session_store.items():
                # Remove sessions older than 1 hour
                if current_time - session_data.get("created_at", 0) > 3600:
                    sessions_to_remove.append(session_id)
            
            for session_id in sessions_to_remove:
                # Clean up session
                if session_id in session_store:
                    del session_store[session_id]
                
                # Clean up cached chat apps
                keys_to_remove = [k for k in chat_app_cache.keys() if k.startswith(session_id)]
                for key in keys_to_remove:
                    del chat_app_cache[key]
                    
                print(f"🧹 Cleaned up session: {session_id}")
            
            await asyncio.sleep(SESSION_CLEANUP_INTERVAL)
            
        except Exception as e:
            print(f"Error in cleanup task: {e}")
            await asyncio.sleep(60)  # Wait before retrying


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
            .header {
                background: linear-gradient(135deg, #2b5556 0%, #21908f 100%);
                color: white;
                padding: 20px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(25, 132, 132, 0.15);
                z-index: 1000;
            }
            .header h1 {
                margin: 0;
                font-size: 2rem;
                font-weight: 700;
            }
            .header p {
                margin: 10px 0 0 0;
                font-size: 1.1rem;
                opacity: 0.9;
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
            .loading {
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100%;
                font-size: 1.2rem;
                color: #198484;
            }
            .spinner {
                border: 4px solid #f3f3f3;
                border-top: 4px solid #198484;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin-right: 20px;
            }
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌍 Growbal Intelligence</h1>
                <p>Select your country to begin your service provider search</p>
            </div>
            <div class="gradio-container">
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    Loading country selection...
                </div>
                <iframe src="/country-gradio/" id="countryFrame" style="display: none;" onload="showFrame()"></iframe>
            </div>
        </div>
        
        <script>
            function showFrame() {
                document.getElementById('loading').style.display = 'none';
                document.getElementById('countryFrame').style.display = 'block';
            }
            
            // Listen for messages from the Gradio iframe
            window.addEventListener('message', function(event) {
                console.log('Received message from Gradio:', event.data);
                
                if (event.data.type === 'redirect') {
                    console.log('Redirecting to:', event.data.url);
                    window.location.href = event.data.url;
                }
            });
            
            // Timeout fallback
            setTimeout(function() {
                if (document.getElementById('loading').style.display !== 'none') {
                    document.getElementById('loading').innerHTML = '<div class="spinner"></div>Loading taking longer than expected...';
                }
            }, 10000);
        </script>
    </body>
    </html>
    """


@app.get("/chat/{session_id}/{country}/", response_class=HTMLResponse)
async def chat_interface_page(session_id: str, country: str, request: Request):
    """Serve the chat interface page with session and country parameters"""
    
    # Store session data with timestamp
    session_store[session_id] = {
        "country": country,
        "created_at": time.time(),
        "active": True,
        "last_activity": time.time()
    }
    
    # Also store in FastAPI session
    request.session["session_id"] = session_id
    request.session["country"] = country
    
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
            .header {{
                background: linear-gradient(135deg, #2b5556 0%, #21908f 100%);
                color: white;
                padding: 15px 20px;
                text-align: center;
                box-shadow: 0 4px 20px rgba(25, 132, 132, 0.15);
                z-index: 1000;
            }}
            .header h1 {{
                margin: 0;
                font-size: 1.8rem;
                font-weight: 700;
            }}
            .header p {{
                margin: 8px 0 0 0;
                font-size: 1rem;
                opacity: 0.9;
            }}
            .session-info {{
                background: rgba(255, 255, 255, 0.1);
                padding: 8px 16px;
                border-radius: 20px;
                margin: 10px auto 0;
                display: inline-block;
                font-size: 0.9rem;
                backdrop-filter: blur(10px);
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
            .loading {{
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100%;
                font-size: 1.2rem;
                color: #198484;
            }}
            .spinner {{
                border: 4px solid #f3f3f3;
                border-top: 4px solid #198484;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin-right: 20px;
            }}
            @keyframes spin {{
                0% {{ transform: rotate(0deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>💬 Growbal Intelligence Chat</h1>
                <p>AI-powered service provider search</p>
                <div class="session-info">
                    🌍 {country} | 🔗 Session: {session_id[:8]}...
                </div>
            </div>
            <div class="gradio-container">
                <div class="loading" id="loading">
                    <div class="spinner"></div>
                    Loading chat interface...
                </div>
                <iframe src="/chat-gradio/{session_id}/{country}/" id="chatFrame" style="display: none;" onload="showFrame()"></iframe>
            </div>
        </div>
        
        <script>
            function showFrame() {{
                document.getElementById('loading').style.display = 'none';
                document.getElementById('chatFrame').style.display = 'block';
            }}
            
            // Listen for messages from the Gradio iframe
            window.addEventListener('message', function(event) {{
                console.log('Received message from chat Gradio:', event.data);
                
                if (event.data.type === 'redirect') {{
                    console.log('Redirecting to:', event.data.url);
                    window.location.href = event.data.url;
                }}
            }});
            
            // Timeout fallback
            setTimeout(function() {{
                if (document.getElementById('loading').style.display !== 'none') {{
                    document.getElementById('loading').innerHTML = '<div class="spinner"></div>Initializing chat interface...';
                }}
            }}, 10000);
        </script>
    </body>
    </html>
    """


def create_fastapi_country_selection_app():
    """Create country selection app optimized for FastAPI integration"""
    return create_country_selection_app()


def create_fastapi_chat_interface_app(session_id: str, country: str):
    """Create chat interface app with FastAPI integration"""
    return create_chat_interface_app(session_id, country)


# Mount the country selection Gradio app
print("🔧 Setting up Gradio applications...")

# Country selection app
country_app = create_fastapi_country_selection_app()
app = gr.mount_gradio_app(
    app, 
    country_app, 
    path="/country-gradio"
)

print("✅ Country selection app mounted at /country-gradio")


# Pre-mount chat interfaces for each session dynamically
@app.api_route("/chat-gradio/{session_id}/{country}/", methods=["GET", "POST", "HEAD"])
async def serve_chat_gradio(session_id: str, country: str, request: Request):
    """Dynamically serve the Gradio chat interface"""
    
    # Update session activity
    if session_id in session_store:
        session_store[session_id]["last_activity"] = time.time()
    else:
        session_store[session_id] = {
            "country": country,
            "created_at": time.time(),
            "active": True,
            "last_activity": time.time()
        }
    
    # Create a unique key for this chat session
    cache_key = f"{session_id}_{country}"
    
    # Create the chat app if not cached
    if cache_key not in chat_app_cache:
        try:
            chat_app_cache[cache_key] = create_fastapi_chat_interface_app(session_id, country)
            print(f"✅ Created chat app for session: {session_id}, country: {country}")
        except Exception as e:
            print(f"❌ Error creating chat app: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to create chat interface: {str(e)}")
    
    # Get the cached chat app
    chat_app = chat_app_cache[cache_key]
    
    # Mount it at a dynamic path if not already mounted
    mount_path = f"/mounted-chat-{session_id[:8]}"
    
    if not hasattr(app, '_dynamic_mounts'):
        app._dynamic_mounts = {}
    
    if mount_path not in app._dynamic_mounts:
        # Use Gradio's mount function
        app = gr.mount_gradio_app(
            app,
            chat_app,
            path=mount_path
        )
        app._dynamic_mounts[mount_path] = True
        print(f"✅ Mounted chat interface at {mount_path}")
    
    # Redirect to the mounted chat app
    return RedirectResponse(url=mount_path + "/")


# API endpoints
@app.get("/api/session/{session_id}")
async def get_session(session_id: str):
    """Get session information"""
    if session_id in session_store:
        return session_store[session_id]
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@app.post("/api/session/{session_id}/update")
async def update_session(session_id: str, data: dict):
    """Update session data"""
    if session_id in session_store:
        session_store[session_id].update(data)
        session_store[session_id]["last_activity"] = time.time()
        return {"status": "updated"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "growbal-intelligence",
        "active_sessions": len(session_store),
        "cached_apps": len(chat_app_cache)
    }


@app.get("/debug/sessions")
async def debug_sessions():
    """Debug endpoint to show all active sessions"""
    return {
        "total_sessions": len(session_store),
        "sessions": session_store,
        "chat_apps_cached": len(chat_app_cache),
        "mounted_paths": getattr(app, '_mounted_paths', set())
    }


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Growbal Intelligence FastAPI application...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page")
    print("   - /chat/{session_id}/{country}/ → Chat interface")
    print("   - /country-gradio/ → Country selection Gradio app")
    print("   - /chat-gradio/{session_id}/{country}/ → Chat Gradio app")
    print("   - /api/session/{session_id} → Session management")
    print("   - /health → Health check")
    print("   - /debug/sessions → Debug session information")
    
    uvicorn.run(
        "improved_main_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )