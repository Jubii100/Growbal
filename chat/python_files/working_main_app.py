"""
Working FastAPI application with proper Gradio integration
- Uses a single chat app with dynamic parameters
- Proper redirect handling
- Session management via query parameters
"""

import os
import sys
import uuid
import time
from typing import Dict, Any, Optional
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
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-in-production-2024")
)

# Global storage
session_store: Dict[str, Dict[str, Any]] = {}

# Global chat app that will handle all sessions
global_chat_app = None
current_session_info = {"session_id": None, "country": None}


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
                    // Direct navigation
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
        "created_at": time.time(),
        "active": True,
        "last_activity": time.time()
    }
    
    # Update global session info for the chat app
    current_session_info["session_id"] = session_id
    current_session_info["country"] = country
    
    # Store in FastAPI session
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
                <iframe src="/chat-gradio/?session_id={session_id}&country={country}" id="chatFrame"></iframe>
            </div>
        </div>
        
        <script>
            window.addEventListener('message', function(event) {{
                console.log('Chat parent received message:', event.data);
                
                if (event.data && event.data.type === 'redirect') {{
                    console.log('Redirecting to:', event.data.url);
                    window.location.href = event.data.url;
                }}
            }});
        </script>
    </body>
    </html>
    """


def create_global_chat_interface():
    """Create a single chat interface that handles all sessions"""
    
    def chat_wrapper(message: str, history: list, request: gr.Request):
        """Wrapper that extracts session info from request"""
        # Get session info from query parameters
        if request and hasattr(request, 'query_params'):
            session_id = dict(request.query_params).get('session_id', 'unknown')
            country = dict(request.query_params).get('country', 'unknown')
        else:
            session_id = current_session_info.get("session_id", "unknown")
            country = current_session_info.get("country", "unknown")
        
        print(f"Chat request - Session: {session_id}, Country: {country}, Message: {message}")
        
        # Import the actual chat response function
        from chat.python_files.chat_interface import chat_response
        import asyncio
        
        # Run the async chat response
        async def get_response():
            response = ""
            async for chunk in chat_response(message, history):
                response = chunk
                yield response
        
        # Create event loop if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Run and return response
        gen = get_response()
        response = ""
        try:
            while True:
                response = loop.run_until_complete(gen.__anext__())
                yield response
        except StopAsyncIteration:
            pass
        
        return response
    
    # Read the logo file
    logo_path = os.path.join(os.path.dirname(__file__), "growbal_logoheader.svg")
    logo_html = ""
    if os.path.exists(logo_path):
        with open(logo_path, 'r') as f:
            logo_content = f.read()
            logo_html = f"""
            <div style="display: flex; justify-content: center; align-items: center; padding: 10px 0; background: #ffffff; margin-bottom: 10px; border-radius: 15px; box-shadow: 0 8px 32px rgba(43, 85, 86, 0.15);">
                <div style="max-width: 200px; height: auto;">
                    {logo_content}
                </div>
            </div>
            """
    
    # Create CSS
    css = """
    /* Global Container Styling */
    .gradio-container {
        max-width: 1400px !important;
        margin: 0 auto !important;
        background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%) !important;
        padding: 20px !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 50px rgba(25, 132, 132, 0.1) !important;
    }
    
    /* Chat Interface Styling */
    .chat-interface {
        height: 900px !important;
        border-radius: 15px !important;
        overflow: hidden !important;
        box-shadow: 0 8px 32px rgba(25, 132, 132, 0.08) !important;
    }
    
    /* Chatbot container */
    .chatbot {
        height: 750px !important;
        max-height: 750px !important;
    }
    """
    
    # Create theme
    custom_theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.emerald,
        secondary_hue=gr.themes.colors.teal,
        neutral_hue=gr.themes.colors.gray,
        font=[gr.themes.GoogleFont("Inter"), "Arial", "sans-serif"]
    )
    
    # Create chat interface
    interface = gr.ChatInterface(
        fn=chat_wrapper,
        type="messages",
        title=f"{logo_html}<div class='app-header'><h1 class='app-title'>Growbal Intelligence</h1><p class='app-description'>AI-powered service provider search</p></div>",
        examples=[
            "🏢 I need immigration services for business migration",
            "💼 Find accounting firms for tech startups", 
            "💻 Looking for IT consulting with cloud expertise",
            "⚖️ Need legal services for fintech company setup",
            "📈 Find B2B marketing agencies with AI experience"
        ],
        cache_examples=False,
        theme=custom_theme,
        css=css,
        textbox=gr.Textbox(
            placeholder="🔍 Ask me about service providers...",
            container=False,
            scale=7,
            lines=1
        ),
        submit_btn=gr.Button("Search Providers", variant="primary"),
        retry_btn=None,
        undo_btn=None,
        clear_btn=gr.Button("🗑️ Clear Chat", variant="stop"),
        multimodal=False,
        concurrency_limit=3,
        fill_height=True
    )
    
    # Add session info display and back button
    with interface:
        with gr.Row():
            gr.HTML("""
                <div id="session-info" style="padding: 10px; background: #f8fffe; border-radius: 10px; margin: 10px 0;">
                    Session info will be displayed here...
                </div>
                <script>
                    // Extract and display session info from URL
                    const urlParams = new URLSearchParams(window.location.search);
                    const sessionId = urlParams.get('session_id') || 'unknown';
                    const country = urlParams.get('country') || 'unknown';
                    
                    document.getElementById('session-info').innerHTML = `
                        <strong>🌍 Country:</strong> ${country} | 
                        <strong>🔗 Session:</strong> ${sessionId.substring(0, 8)}...
                    `;
                </script>
            """)
            
            back_btn = gr.Button("← Back to Country Selection", variant="secondary")
            
            def go_back():
                return gr.HTML("""
                <script>
                    if (window.parent && window.parent !== window) {
                        window.parent.postMessage({
                            type: 'redirect',
                            url: '/country/'
                        }, '*');
                    } else {
                        window.location.href = '/country/';
                    }
                </script>
                """)
            
            back_output = gr.HTML(visible=False)
            back_btn.click(go_back, outputs=[back_output])
    
    return interface


# Mount the country selection Gradio app
print("🔧 Setting up Gradio applications...")

country_app = create_country_selection_app()
app = gr.mount_gradio_app(
    app, 
    country_app, 
    path="/country-gradio"
)

print("✅ Country selection app mounted at /country-gradio")

# Create and mount the global chat interface
global_chat_app = create_global_chat_interface()
app = gr.mount_gradio_app(
    app,
    global_chat_app,
    path="/chat-gradio"
)

print("✅ Global chat app mounted at /chat-gradio")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "growbal-intelligence",
        "active_sessions": len(session_store)
    }


# Debug endpoint
@app.get("/debug/sessions")
async def debug_sessions():
    """Debug endpoint to show all active sessions"""
    return {
        "total_sessions": len(session_store),
        "sessions": session_store,
        "current_session_info": current_session_info
    }


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Growbal Intelligence FastAPI application (Working Version)...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page")
    print("   - /chat/{session_id}/{country}/ → Chat interface")
    print("   - /country-gradio/ → Country selection Gradio app")
    print("   - /chat-gradio/ → Global chat Gradio app (with query params)")
    print("   - /health → Health check")
    print("   - /debug/sessions → Debug session information")
    
    uvicorn.run(
        "working_main_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )