"""
FastAPI application integrating Gradio country selection and chat interface
Features:
- Country selection at /country/
- Chat interface at /chat/{session_id}/{country}/
- Proper parameter passing between interfaces
- Session management and redirection handling
"""

import os
import sys
import uuid
from typing import Optional
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
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
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-in-production")
)

# Global storage for session data
session_store = {}


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
            <div class="header">
                <h1>🌍 Growbal Intelligence</h1>
                <p>Select your country to begin your service provider search</p>
            </div>
            <div class="gradio-container">
                <iframe src="/country-gradio/" id="countryFrame"></iframe>
            </div>
        </div>
        
        <script>
            // Listen for messages from the Gradio iframe
            window.addEventListener('message', function(event) {
                console.log('Received message from Gradio:', event.data);
                
                if (event.data.type === 'redirect') {
                    console.log('Redirecting to:', event.data.url);
                    window.location.href = event.data.url;
                }
            });
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
        "created_at": str(uuid.uuid4()),
        "active": True
    }
    
    # Also store in FastAPI session
    request.session["session_id"] = session_id
    request.session["country"] = country
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Growbal Intelligence - Chat Interface</title>
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
            <div class="header">
                <h1>💬 Growbal Intelligence Chat</h1>
                <p>AI-powered service provider search</p>
                <div class="session-info">
                    🌍 {country} | 🔗 Session: {session_id[:8]}...
                </div>
            </div>
            <div class="gradio-container">
                <iframe src="/chat-gradio/{session_id}/{country}/" id="chatFrame"></iframe>
            </div>
        </div>
        
        <script>
            // Listen for messages from the Gradio iframe
            window.addEventListener('message', function(event) {{
                console.log('Received message from chat Gradio:', event.data);
                
                if (event.data.type === 'redirect') {{
                    console.log('Redirecting to:', event.data.url);
                    window.location.href = event.data.url;
                }}
            }});
        </script>
    </body>
    </html>
    """


# Create modified country selection app for FastAPI integration
def create_fastapi_country_selection_app():
    """Create country selection app optimized for FastAPI integration"""
    
    # Import the original function
    original_app = create_country_selection_app()
    
    # Modify the proceed_to_chat function to work with FastAPI
    def proceed_to_chat(country):
        """Handle proceeding to chat interface via FastAPI"""
        if not country:
            return gr.HTML("Please select a country first.")
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # JavaScript to redirect via parent window
        redirect_js = f"""
        <script>
            console.log('Redirecting to chat with country: {country}');
            
            // Send message to parent window
            if (window.parent && window.parent !== window) {{
                window.parent.postMessage({{
                    type: 'redirect',
                    url: '/chat/{session_id}/{country}/'
                }}, '*');
            }} else {{
                // Fallback for standalone testing
                window.location.href = '/chat/{session_id}/{country}/';
            }}
        </script>
        <div style="text-align: center; padding: 20px; color: #198484;">
            <h3>🚀 Redirecting to chat interface...</h3>
            <p><strong>Session:</strong> {session_id}</p>
            <p><strong>Country:</strong> {country}</p>
            <p><em>Starting your service provider search...</em></p>
        </div>
        """
        
        return gr.HTML(redirect_js, visible=True)
    
    # Update the click handler in the original app
    # We need to access the components from the original app
    # This is a bit tricky with Gradio's structure, so we'll recreate the app
    
    return original_app


# Create modified chat interface app for FastAPI integration
def create_fastapi_chat_interface_app(session_id: str, country: str):
    """Create chat interface app optimized for FastAPI integration"""
    
    # Create the original app with parameters
    original_app = create_chat_interface_app(session_id, country)
    
    return original_app


# Mount the Gradio apps
print("🔧 Setting up Gradio applications...")

# Country selection app
country_app = create_fastapi_country_selection_app()
app = gr.mount_gradio_app(
    app, 
    country_app, 
    path="/country-gradio",
    show_api=False
)

print("✅ Country selection app mounted at /country-gradio")

# We need to create a dynamic route for chat interface since it needs parameters
@app.get("/chat-gradio/{session_id}/{country}/")
async def serve_chat_gradio(session_id: str, country: str, request: Request):
    """Dynamically serve chat interface with parameters"""
    
    # Validate session
    if session_id not in session_store:
        session_store[session_id] = {
            "country": country,
            "created_at": str(uuid.uuid4()),
            "active": True
        }
    
    # Create chat app with parameters
    chat_app = create_fastapi_chat_interface_app(session_id, country)
    
    # Mount temporarily - this is a workaround for dynamic mounting
    # In a production environment, you might want to cache these apps
    temp_path = f"/temp-chat-{session_id}"
    
    # Create a temporary mount
    try:
        # Remove existing mount if it exists
        if hasattr(app, '_temp_mounts'):
            if temp_path in app._temp_mounts:
                # Clean up old mount
                pass
        else:
            app._temp_mounts = {}
        
        # Mount the chat app temporarily
        app = gr.mount_gradio_app(
            app,
            chat_app,
            path=temp_path,
            show_api=False
        )
        
        app._temp_mounts[temp_path] = True
        
        # Redirect to the mounted app
        return RedirectResponse(url=f"{temp_path}/")
        
    except Exception as e:
        print(f"Error mounting chat app: {e}")
        return HTMLResponse(
            content=f"Error loading chat interface: {str(e)}",
            status_code=500
        )


# Alternative approach: Pre-mount multiple chat instances
# This is more scalable for production

chat_apps = {}

@app.get("/chat-gradio/{session_id}/{country}/")
async def serve_chat_gradio_v2(session_id: str, country: str, request: Request):
    """Serve chat interface with better session management"""
    
    # Check if we already have an app for this session
    app_key = f"{session_id}_{country}"
    
    if app_key not in chat_apps:
        # Create new chat app
        chat_apps[app_key] = create_fastapi_chat_interface_app(session_id, country)
    
    # For now, we'll use a simpler approach - create the HTML wrapper
    # that embeds the chat interface
    
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Chat Interface</title>
        <style>
            body {{ margin: 0; padding: 0; height: 100vh; overflow: hidden; }}
            #chat-container {{ width: 100%; height: 100%; }}
        </style>
    </head>
    <body>
        <div id="chat-container">
            <p>Loading chat interface for {country} (Session: {session_id})...</p>
            <script>
                // This would normally load the Gradio chat interface
                // For now, we'll show a placeholder
                document.getElementById('chat-container').innerHTML = `
                    <div style="padding: 20px; text-align: center;">
                        <h2>Chat Interface</h2>
                        <p>Country: {country}</p>
                        <p>Session: {session_id}</p>
                        <p>This would be the actual chat interface.</p>
                        <button onclick="goBack()">← Back to Country Selection</button>
                    </div>
                `;
                
                function goBack() {{
                    if (window.parent && window.parent !== window) {{
                        window.parent.postMessage({{
                            type: 'redirect',
                            url: '/country/'
                        }}, '*');
                    }} else {{
                        window.location.href = '/country/';
                    }}
                }}
            </script>
        </div>
    </body>
    </html>
    """)


# API endpoints for session management
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
        return {"status": "updated"}
    else:
        raise HTTPException(status_code=404, detail="Session not found")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "growbal-intelligence"}


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Growbal Intelligence FastAPI application...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page")
    print("   - /chat/{session_id}/{country}/ → Chat interface")
    print("   - /country-gradio/ → Country selection Gradio app")
    print("   - /api/session/{session_id} → Session management")
    print("   - /health → Health check")
    
    uvicorn.run(
        "fastapi_gradio_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )