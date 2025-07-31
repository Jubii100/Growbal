"""
Fixed FastAPI application with proper Gradio integration
- Uses a single chat app with dynamic parameters
- Fixed redirect handling between country selection and chat
- Proper session management via query parameters
- Fixed URL parameter passing to chat interface
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


def create_fixed_country_selection_app():
    """Create country selection interface with fixed redirect functionality"""
    
    # Import COUNTRY_CHOICES from the utils module
    try:
        from growbal_django.accounts.utils import COUNTRY_CHOICES
        print("✅ Successfully imported country choices from utils module")
    except ImportError as e:
        print(f"⚠️ Warning: Could not import country choices from utils: {e}")
        # Fallback to a minimal list if import fails
        COUNTRY_CHOICES = [
            ('USA', 'USA'), ('UK', 'UK'), ('Canada', 'Canada'), 
            ('Australia', 'Australia'), ('Germany', 'Germany')
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
    
    # Same CSS as main app
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
    
    /* Button Styling */
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
    
    /* Header Styling */
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
    
    /* Country selection specific */
    .country-section {
        max-width: 600px !important;
        margin: 40px auto !important;
        text-align: center !important;
        padding: 40px !important;
        background: white !important;
        border-radius: 15px !important;
        box-shadow: 0 8px 32px rgba(25, 132, 132, 0.08) !important;
    }

    /* Dropdown Styling */
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
    
    # Create custom theme with same colors
    custom_theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.emerald,
        secondary_hue=gr.themes.colors.teal,
        neutral_hue=gr.themes.colors.gray,
        font=[gr.themes.GoogleFont("Inter"), "Arial", "sans-serif"]
    )
    
    with gr.Blocks(title="Growbal Intelligence - Country Selection", theme=custom_theme, css=css, fill_height=True) as interface:
        # Header (same as main app)
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
            """Handle proceeding to chat interface with better redirect"""
            if not country:
                return gr.HTML("Please select a country first.")
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Enhanced JavaScript with better redirect handling
            redirect_js = f"""
            <script>
                console.log('Country selection: Proceeding to chat with session: {session_id}, country: {country}');
                
                // Function to handle the redirect
                function redirectToChat() {{
                    const targetUrl = '/chat/{session_id}/{country}/';
                    console.log('Redirecting to:', targetUrl);
                    
                    // Try multiple approaches for better compatibility
                    try {{
                        // Method 1: Try to message parent window first
                        if (window.parent && window.parent !== window) {{
                            console.log('Attempting to message parent window...');
                            window.parent.postMessage({{
                                type: 'redirect',
                                url: targetUrl
                            }}, '*');
                            
                            // Give the parent a moment to handle the message
                            setTimeout(() => {{
                                // If parent didn't handle it, try direct redirect
                                console.log('Fallback: Direct redirect');
                                window.location.href = targetUrl;
                            }}, 500);
                        }} else {{
                            // Method 2: Direct redirect for standalone mode
                            console.log('Direct redirect (standalone mode)');
                            window.location.href = targetUrl;
                        }}
                    }} catch (error) {{
                        console.error('Redirect error:', error);
                        // Fallback method
                        window.location.href = targetUrl;
                    }}
                }}
                
                // Execute redirect immediately
                redirectToChat();
            </script>
            
            <div style="text-align: center; padding: 20px; color: #198484;">
                <h3>🚀 Redirecting to chat interface...</h3>
                <p><strong>Session:</strong> {session_id}</p>
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
                <p><em>If redirect doesn't work automatically, <a href="/chat/{session_id}/{country}/" style="color: #198484; text-decoration: underline;">click here</a>.</em></p>
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
    """Serve the country selection page with improved iframe handling"""
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
                <iframe src="/country-gradio/" id="countryFrame" allow="camera; microphone; geolocation"></iframe>
            </div>
        </div>
        
        <script>
            // Enhanced message listener for better redirect handling
            window.addEventListener('message', function(event) {
                console.log('Parent window received message:', event.data);
                
                if (event.data && event.data.type === 'redirect') {
                    console.log('Processing redirect to:', event.data.url);
                    
                    // Multiple redirect strategies for better compatibility
                    try {
                        // Strategy 1: Direct navigation (most reliable)
                        window.location.href = event.data.url;
                    } catch (error) {
                        console.error('Redirect error:', error);
                        // Strategy 2: Use location.replace as fallback
                        window.location.replace(event.data.url);
                    }
                }
            });
            
            // Additional debugging
            window.addEventListener('load', function() {
                console.log('Country selection page loaded');
                const iframe = document.getElementById('countryFrame');
                iframe.addEventListener('load', function() {
                    console.log('Country Gradio iframe loaded');
                });
            });
        </script>
    </body>
    </html>
    """


@app.get("/chat/{session_id}/{country}/", response_class=HTMLResponse)
async def chat_interface_page(session_id: str, country: str, request: Request):
    """Serve the chat interface page with enhanced parameter passing"""
    
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
                <iframe src="/chat-gradio/?session_id={session_id}&country={country}" id="chatFrame" allow="camera; microphone; geolocation"></iframe>
            </div>
        </div>
        
        <script>
            // Enhanced message handling for chat interface
            window.addEventListener('message', function(event) {{
                console.log('Chat parent received message:', event.data);
                
                if (event.data && event.data.type === 'redirect') {{
                    console.log('Processing redirect to:', event.data.url);
                    try {{
                        window.location.href = event.data.url;
                    }} catch (error) {{
                        console.error('Redirect error:', error);
                        window.location.replace(event.data.url);
                    }}
                }}
            }});
            
            // Debug information
            console.log('Chat interface loaded with session: {session_id}, country: {country}');
            
            // Send session info to iframe when it loads
            window.addEventListener('load', function() {{
                const iframe = document.getElementById('chatFrame');
                iframe.addEventListener('load', function() {{
                    console.log('Chat Gradio iframe loaded');
                    // Send session info to the iframe
                    iframe.contentWindow.postMessage({{
                        type: 'session_info',
                        session_id: '{session_id}',
                        country: '{country}'
                    }}, '*');
                }});
            }});
        </script>
    </body>
    </html>
    """


def create_enhanced_chat_interface():
    """Create enhanced chat interface with better parameter handling"""
    
    def chat_wrapper(message: str, history: list, request: gr.Request):
        """Enhanced wrapper that properly extracts session info from request"""
        session_id = "unknown"
        country = "unknown"
        
        # Method 1: Try to get from query parameters (preferred)
        if request and hasattr(request, 'query_params'):
            query_params = dict(request.query_params)
            session_id = query_params.get('session_id', 'unknown')
            country = query_params.get('country', 'unknown')
            print(f"[Method 1] Extracted from query params - Session: {session_id}, Country: {country}")
        
        # Method 2: Fallback to global session info
        if session_id == "unknown" or country == "unknown":
            session_id = current_session_info.get("session_id", "unknown")
            country = current_session_info.get("country", "unknown")
            print(f"[Method 2] Using global session info - Session: {session_id}, Country: {country}")
        
        # Method 3: Try to extract from headers (additional fallback)
        if request and hasattr(request, 'headers'):
            headers = dict(request.headers)
            session_id = headers.get('x-session-id', session_id)
            country = headers.get('x-country', country)
            print(f"[Method 3] Checked headers - Session: {session_id}, Country: {country}")
        
        print(f"🔍 Chat request processing:")
        print(f"   Session ID: {session_id}")
        print(f"   Country: {country}")
        print(f"   Message: {message}")
        
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
    
    /* Session info styling */
    .session-info {
        background: white !important;
        padding: 15px !important;
        border-radius: 10px !important;
        margin-bottom: 15px !important;
        box-shadow: 0 4px 15px rgba(25, 132, 132, 0.08) !important;
        text-align: center !important;
        font-family: 'Inter', Arial, sans-serif !important;
    }
    
    .session-info-highlight {
        color: #198484 !important;
        font-weight: bold !important;
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
    
    # Add enhanced session info display and back button
    with interface:
        with gr.Row():
            session_info_display = gr.HTML("""
                <div class="session-info" id="session-info-display">
                    <div id="session-details">
                        <span class="session-info-highlight">🌍 Country:</span> <span id="country-display">Loading...</span> | 
                        <span class="session-info-highlight">🔗 Session:</span> <span id="session-display">Loading...</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.9em; color: #666;">
                        <span id="status-display">Connected and ready</span>
                    </div>
                </div>
                
                <script>
                    // Enhanced session info extraction and display
                    function updateSessionInfo() {
                        try {
                            // Method 1: Extract from current URL
                            const urlParams = new URLSearchParams(window.location.search);
                            let sessionId = urlParams.get('session_id');
                            let country = urlParams.get('country');
                            
                            console.log('URL params:', { sessionId, country });
                            
                            // Method 2: Try to get from parent window URL if iframe
                            if ((!sessionId || !country) && window.parent && window.parent !== window) {
                                try {
                                    const parentUrl = new URL(window.parent.location.href);
                                    const pathParts = parentUrl.pathname.split('/');
                                    if (pathParts.length >= 4 && pathParts[1] === 'chat') {
                                        sessionId = pathParts[2];
                                        country = pathParts[3];
                                        console.log('Extracted from parent URL:', { sessionId, country });
                                    }
                                } catch (e) {
                                    console.log('Could not access parent URL (expected for cross-origin)');
                                }
                            }
                            
                            // Default values if still not found
                            sessionId = sessionId || 'unknown';
                            country = country || 'unknown';
                            
                            // Update display
                            document.getElementById('country-display').textContent = country;
                            document.getElementById('session-display').textContent = sessionId.substring(0, 8) + (sessionId.length > 8 ? '...' : '');
                            
                            // Update status
                            if (sessionId !== 'unknown' && country !== 'unknown') {
                                document.getElementById('status-display').textContent = '✅ Session parameters loaded successfully';
                                document.getElementById('status-display').style.color = '#16a085';
                            } else {
                                document.getElementById('status-display').textContent = '⚠️ Session parameters not fully loaded';
                                document.getElementById('status-display').style.color = '#e67e22';
                            }
                            
                            console.log('Session info updated:', { sessionId, country });
                        } catch (error) {
                            console.error('Error updating session info:', error);
                            document.getElementById('status-display').textContent = '❌ Error loading session info';
                            document.getElementById('status-display').style.color = '#e74c3c';
                        }
                    }
                    
                    // Update session info on page load
                    updateSessionInfo();
                    
                    // Listen for session info messages from parent
                    window.addEventListener('message', function(event) {
                        if (event.data && event.data.type === 'session_info') {
                            console.log('Received session info from parent:', event.data);
                            document.getElementById('country-display').textContent = event.data.country;
                            document.getElementById('session-display').textContent = event.data.session_id.substring(0, 8) + '...';
                            document.getElementById('status-display').textContent = '✅ Session info received from parent';
                            document.getElementById('status-display').style.color = '#16a085';
                        }
                    });
                    
                    // Retry updating session info after a delay (in case of timing issues)
                    setTimeout(updateSessionInfo, 1000);
                </script>
            """)
            
            back_btn = gr.Button("← Back to Country Selection", variant="secondary")
            
            def go_back():
                return gr.HTML("""
                <script>
                    console.log('Back button clicked');
                    if (window.parent && window.parent !== window) {
                        console.log('Sending message to parent for redirect');
                        window.parent.postMessage({
                            type: 'redirect',
                            url: '/country/'
                        }, '*');
                    } else {
                        console.log('Direct redirect to country selection');
                        window.location.href = '/country/';
                    }
                </script>
                <div style="text-align: center; padding: 20px; color: #198484;">
                    <h3>🔙 Returning to country selection...</h3>
                </div>
                """)
            
            back_output = gr.HTML(visible=False)
            back_btn.click(go_back, outputs=[back_output])
    
    return interface


# Mount the enhanced country selection Gradio app
print("🔧 Setting up enhanced Gradio applications...")

fixed_country_app = create_fixed_country_selection_app()
app = gr.mount_gradio_app(
    app, 
    fixed_country_app, 
    path="/country-gradio"
)

print("✅ Enhanced country selection app mounted at /country-gradio")

# Create and mount the enhanced chat interface
global_chat_app = create_enhanced_chat_interface()
app = gr.mount_gradio_app(
    app,
    global_chat_app,
    path="/chat-gradio"
)

print("✅ Enhanced chat app mounted at /chat-gradio")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "growbal-intelligence-fixed",
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
    
    print("🚀 Starting Growbal Intelligence FastAPI application (Fixed Version)...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page")
    print("   - /chat/{session_id}/{country}/ → Chat interface")
    print("   - /country-gradio/ → Country selection Gradio app")
    print("   - /chat-gradio/ → Global chat Gradio app (with query params)")
    print("   - /health → Health check")
    print("   - /debug/sessions → Debug session information")
    print()
    print("🔧 Key fixes implemented:")
    print("   ✅ Enhanced redirect handling with multiple fallback strategies")
    print("   ✅ Improved URL parameter extraction and display")
    print("   ✅ Better iframe communication between parent and child")
    print("   ✅ Enhanced session info display with real-time updates")
    print("   ✅ Multiple parameter extraction methods for reliability")
    
    uvicorn.run(
        "fixed_main_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )