"""
Hybrid FastAPI application - Gradio iframe + Server-side POST redirect
- Uses existing country_selection.py Gradio app in iframe
- Iframe sends message to parent window
- Parent window submits hidden form via POST for proper redirect
- Best of both worlds: Gradio UI + Server-side redirect
"""

import os
import sys
import uuid
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, HTTPException, Form
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
from gradio_chat_ui.country_selection import create_country_selection_app
from gradio_chat_ui.chat_interface import create_chat_interface_app

# Global storage for session management
session_store: Dict[str, Dict[str, Any]] = {}

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

# Add session middleware (ESSENTIAL for parameter passing)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET_KEY", "your-secret-key-change-in-production-2024")
)


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint that redirects to country selection"""
    return RedirectResponse(url="/country/")


def create_enhanced_country_selection_app():
    """Create country selection app that can communicate with parent window"""
    
    # Import COUNTRY_CHOICES from the utils module
    try:
        from growbal_django.accounts.utils import COUNTRY_CHOICES
        print("✅ Successfully imported country choices from utils module")
    except ImportError as e:
        print(f"⚠️ Warning: Could not import country choices from utils: {e}")
        # Fallback to a minimal list if import fails
        COUNTRY_CHOICES = [
            ('USA', 'USA'), ('UK', 'UK'), ('Canada', 'Canada'), 
            ('Australia', 'Australia'), ('Germany', 'Germany'), ('Afghanistan', 'Afghanistan')
        ]
    
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
    
    # CSS styling (same as original)
    css = """
    .gradio-container {
        max-width: 1400px !important;
        margin: 0 auto !important;
        background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%) !important;
        padding: 20px !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 50px rgba(25, 132, 132, 0.1) !important;
    }
    
    .btn-primary {
        background: linear-gradient(135deg, #198484 0%, #16a6a6 100%) !important;
        border: none !important;
        color: white !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        padding: 12px 24px !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 4px 15px rgba(25, 132, 132, 0.2) !important;
    }
    
    .btn-primary:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 25px rgba(25, 132, 132, 0.3) !important;
        background: linear-gradient(135deg, #16a6a6 0%, #198484 100%) !important;
    }
    
    .app-header {
        text-align: center !important;
        padding: 10px 0 !important;
        background: linear-gradient(135deg, #2b5556 0%, #21908f 100%) !important;
        border-radius: 15px !important;
        margin-bottom: 20px !important;
        box-shadow: 0 8px 32px rgba(25, 132, 132, 0.15) !important;
    }
    
    .app-title {
        color: #ffffff !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
        margin-bottom: 4px !important;
        text-shadow: 0 2px 10px rgba(0, 0, 0, 0.1) !important;
    }
    
    .app-description {
        color: #f8fffe !important;
        font-size: 0.9rem !important;
        font-weight: 400 !important;
        max-width: 600px !important;
        margin: 0 auto !important;
    }
    
    .country-section {
        max-width: 600px !important;
        margin: 40px auto !important;
        text-align: center !important;
        padding: 40px !important;
        background: white !important;
        border-radius: 15px !important;
        box-shadow: 0 8px 32px rgba(25, 132, 132, 0.08) !important;
    }

    .dropdown select {
        border: 2px solid rgba(25, 132, 132, 0.2) !important;
        border-radius: 10px !important;
        padding: 12px !important;
        font-size: 15px !important;
        transition: all 0.3s ease !important;
        background: #ffffff !important;
    }
    
    .dropdown select:focus {
        border-color: #198484 !important;
        box-shadow: 0 0 0 3px rgba(25, 132, 132, 0.1) !important;
        outline: none !important;
    }
    """
    
    # Create custom theme
    custom_theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.emerald,
        secondary_hue=gr.themes.colors.teal,
        neutral_hue=gr.themes.colors.gray,
        font=[gr.themes.GoogleFont("Inter"), "Arial", "sans-serif"]
    )
    
    with gr.Blocks(title="Growbal Intelligence - Country Selection", theme=custom_theme, css=css, fill_height=True) as interface:
        # Header
        gr.HTML(f"{logo_html}<div class='app-header'><h1 class='app-title'>Growbal Intelligence</h1><p class='app-description'>AI-powered service provider search</p></div>")
        
        # Country selection section
        with gr.Column(elem_classes="country-section"):
            gr.Markdown("## 🌍 Please select a country to begin")
            gr.Markdown("Choose your target country for service provider search")
            
            country_dropdown = gr.Dropdown(
                choices=[choice[1] for choice in COUNTRY_CHOICES],
                label="Select Country",
                info="Choose a country to search for service providers",
                container=True,
                elem_classes="dropdown"
            )
            
            continue_btn = gr.Button(
                "Continue to Search", 
                variant="primary", 
                visible=False,
                size="lg"
            )
            
            status = gr.Markdown("")
            
            # Output component for JavaScript redirect
            redirect_output = gr.HTML(visible=False)
        
        def show_continue(country):
            """Show continue button when country is selected"""
            if country:
                return gr.Button(visible=True), gr.Markdown(f"**Selected:** {country}")
            return gr.Button(visible=False), gr.Markdown("")
        
        def proceed_to_chat(country):
            """
            Enhanced proceed function that sends POST message to parent window
            This triggers the hidden form submission in the parent
            """
            if not country:
                return gr.HTML("Please select a country first.")
            
            # JavaScript to send POST message to parent window
            # The parent window will handle the form submission
            redirect_js = f"""
            <script>
                (function() {{
                    const country = '{country}';
                    console.log('🚀 Sending POST message to parent for country:', country);
                    
                    // Send message to parent window to trigger form submission
                    if (window.parent && window.parent !== window) {{
                        window.parent.postMessage({{
                            type: 'submit_form',
                            country: country
                        }}, '*');
                        
                        console.log('✅ POST message sent to parent window');
                    }} else {{
                        console.log('❌ Not in iframe - cannot send message to parent');
                    }}
                }})();
            </script>
            
            <div style="text-align: center; padding: 20px; color: #198484;">
                <h3>🚀 Submitting to chat interface...</h3>
                <p><strong>Country:</strong> {country}</p>
                <div style="margin-top: 20px;">
                    <div style="display: inline-block; width: 20px; height: 20px; border: 3px solid #198484; border-radius: 50%; border-top: 3px solid transparent; animation: spin 1s linear infinite;"></div>
                    <style>
                        @keyframes spin {{
                            0% {{ transform: rotate(0deg); }}
                            100% {{ transform: rotate(360deg); }}
                        }}
                    </style>
                </div>
                <p style="margin-top: 15px;"><em>Processing your request...</em></p>
            </div>
            """
            
            return gr.HTML(redirect_js, visible=True)
        
        # Event handlers
        country_dropdown.change(
            show_continue, 
            inputs=[country_dropdown], 
            outputs=[continue_btn, status]
        )
        
        continue_btn.click(
            proceed_to_chat, 
            inputs=[country_dropdown], 
            outputs=[redirect_output]
        )
        
    return interface


@app.get("/country/", response_class=HTMLResponse)
async def country_selection_page():
    """
    Serve country selection page with iframe + hidden form
    The iframe contains the Gradio app, the hidden form handles POST submission
    """
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
            #hiddenForm {
                display: none;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="gradio-container">
                <iframe src="/country-gradio/" id="countryFrame" allow="camera; microphone; geolocation"></iframe>
            </div>
        </div>
        
        <!-- Hidden form for POST submission -->
        <form id="hiddenForm" action="/proceed-to-chat" method="post">
            <input type="hidden" name="country" id="hiddenCountry" value="">
        </form>
        
        <script>
            // Enhanced message handling for iframe communication
            window.addEventListener('message', function(event) {
                console.log('🎯 Parent received message:', event.data);
                
                if (event.data && event.data.type === 'submit_form') {
                    const country = event.data.country;
                    console.log('🚀 Submitting form with country:', country);
                    
                    // Set the hidden form value and submit
                    document.getElementById('hiddenCountry').value = country;
                    document.getElementById('hiddenForm').submit();
                }
            });
            
            // Listen for iframe load events
            document.getElementById('countryFrame').addEventListener('load', function() {
                console.log('✅ Country selection iframe loaded');
            });
        </script>
    </body>
    </html>
    """


@app.post("/proceed-to-chat")
async def proceed_to_chat(request: Request, country: str = Form(...)):
    """
    Handle form submission and redirect to chat interface
    This is triggered by the hidden form submission from the parent window
    """
    if not country:
        raise HTTPException(status_code=400, detail="Country is required")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
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
    
    print(f"🚀 Server-side redirect to chat: Session={session_id}, Country={country}")
    
    # SERVER-SIDE REDIRECT - this actually works!
    return RedirectResponse(url=f"/chat/{session_id}/{country}/", status_code=303)


@app.get("/chat/{session_id}/{country}/", response_class=HTMLResponse)
async def chat_interface_page(session_id: str, country: str, request: Request):
    """Serve the chat interface page with proper parameter passing"""
    
    # Verify session exists
    if session_id not in session_store:
        session_store[session_id] = {
            "country": country,
            "created_at": time.time(),
            "active": True,
            "last_activity": time.time()
        }
    
    # Update session
    session_store[session_id]["last_activity"] = time.time()
    
    # Store in FastAPI session
    request.session["session_id"] = session_id
    request.session["country"] = country
    
    print(f"✅ Chat interface loaded: Session={session_id}, Country={country}")
    
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
            }}
            iframe {{
                width: 100%;
                height: 100%;
                border: none;
                background: transparent;
            }}
            .session-info {{
                background: white;
                padding: 15px;
                text-align: center;
                border-bottom: 1px solid rgba(25, 132, 132, 0.1);
                font-family: 'Inter', Arial, sans-serif;
            }}
            .session-info-highlight {{
                color: #198484;
                font-weight: bold;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="session-info">
                <span class="session-info-highlight">🌍 Country:</span> {country} | 
                <span class="session-info-highlight">🔗 Session:</span> {session_id[:8]}...
                <a href="/country/" style="margin-left: 20px; color: #198484; text-decoration: none;">← Back to Country Selection</a>
            </div>
            <div class="gradio-container">
                <iframe src="/chat-gradio/?session_id={session_id}&country={country}" id="chatFrame" allow="camera; microphone; geolocation"></iframe>
            </div>
        </div>
        
        <script>
            console.log('✅ Chat interface loaded with:');
            console.log('  Session ID: {session_id}');
            console.log('  Country: {country}');
            console.log('  URL: ' + window.location.href);
        </script>
    </body>
    </html>
    """


def create_working_chat_interface():
    """Create chat interface with proper parameter extraction"""
    
    def chat_wrapper(message: str, history: list, request: gr.Request):
        """
        Chat wrapper with reliable parameter extraction
        """
        session_id = "unknown"
        country = "unknown"
        
        print(f"🔍 Chat wrapper called with message: {message}")
        
        # Method 1: Extract from query parameters (MOST RELIABLE)
        if request and hasattr(request, 'query_params'):
            query_params = dict(request.query_params)
            session_id = query_params.get('session_id', session_id)
            country = query_params.get('country', country)
            print(f"✅ [Query] Session: {session_id}, Country: {country}")
        
        # Method 2: Extract from FastAPI session
        if (session_id == "unknown" or country == "unknown") and request:
            try:
                fastapi_request = request.request if hasattr(request, 'request') else request
                if hasattr(fastapi_request, 'session'):
                    session_id = fastapi_request.session.get('session_id', session_id)
                    country = fastapi_request.session.get('country', country)
                    print(f"✅ [FastAPI Session] Session: {session_id}, Country: {country}")
            except Exception as e:
                print(f"❌ [FastAPI Session] Error: {e}")
        
        # Method 3: Check session store
        if session_id != "unknown" and session_id in session_store:
            country = session_store[session_id].get("country", country)
            print(f"✅ [Session Store] Session: {session_id}, Country: {country}")
        
        print(f"🎯 Final parameters: Session={session_id}, Country={country}")
        
        # Import and run the actual chat response function
        try:
            from gradio_chat_ui.chat_interface import chat_response
            import asyncio
            
            # Create async wrapper
            async def get_response():
                async for chunk in chat_response(message, history):
                    yield chunk
            
            # Run the async response
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Generate and return response
            gen = get_response()
            response = ""
            try:
                while True:
                    response = loop.run_until_complete(gen.__anext__())
                    yield response
            except StopAsyncIteration:
                pass
            
            return response
            
        except Exception as e:
            print(f"❌ Error in chat response: {e}")
            return f"Error processing your request: {str(e)}"
    
    # Use the same chat interface from the original
    return create_chat_interface_app(chat_wrapper)


# Mount the enhanced country selection app
print("🔧 Setting up enhanced country selection app...")
enhanced_country_app = create_enhanced_country_selection_app()
app = gr.mount_gradio_app(
    app, 
    enhanced_country_app, 
    path="/country-gradio"
)
print("✅ Enhanced country selection app mounted at /country-gradio")

# Mount the chat interface
print("🔧 Setting up chat interface...")
working_chat_app = create_working_chat_interface()
app = gr.mount_gradio_app(
    app,
    working_chat_app,
    path="/chat-gradio"
)
print("✅ Chat app mounted at /chat-gradio")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "growbal-intelligence-hybrid",
        "active_sessions": len(session_store)
    }


# Debug endpoint
@app.get("/debug/sessions")
async def debug_sessions():
    """Debug endpoint to show all active sessions"""
    return {
        "total_sessions": len(session_store),
        "sessions": session_store
    }


if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting HYBRID Growbal Intelligence FastAPI application...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page with iframe + hidden form")
    print("   - /country-gradio/ → Enhanced Gradio country selection app")
    print("   - /proceed-to-chat → Form submission handler (SERVER-SIDE REDIRECT)")
    print("   - /chat/{session_id}/{country}/ → Chat interface")
    print("   - /chat-gradio/ → Chat Gradio app (with query params)")
    print("   - /health → Health check")
    print("   - /debug/sessions → Debug session information")
    print()
    print("🔧 HYBRID APPROACH FEATURES:")
    print("   ✅ Uses your existing country_selection.py Gradio app")
    print("   ✅ Iframe sends message to parent window")
    print("   ✅ Parent window submits hidden form via POST")
    print("   ✅ Server-side redirect with proper URL change")
    print("   ✅ Proper parameter extraction in chat interface")
    print("   ✅ Best of both worlds: Gradio UI + Server redirect")
    
    uvicorn.run(
        "main_1:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )