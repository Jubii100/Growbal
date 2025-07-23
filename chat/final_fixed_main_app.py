"""
Final Fixed FastAPI application with proper Gradio integration
- Fixed auto-redirection with immediate execution
- Fixed URL parameter extraction in chat interface
- Proper iframe src URL construction
- Reliable session management
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
current_session_info = {"session_id": None, "country": None}


@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint that redirects to country selection"""
    return RedirectResponse(url="/country/")


def create_final_country_selection_app():
    """Create country selection interface with reliable auto-redirect"""
    
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
            """Handle proceeding to chat interface with immediate redirect"""
            if not country:
                return gr.HTML("Please select a country first.")
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # Immediate redirect with multiple strategies
            redirect_js = f"""
            <script>
                (function() {{
                    const targetUrl = '/chat/{session_id}/{country}/';
                    console.log('Immediate redirect to:', targetUrl);
                    
                    // Strategy 1: Immediate redirect (most reliable)
                    window.location.href = targetUrl;
                    
                    // Strategy 2: If still here after 100ms, try parent message
                    setTimeout(() => {{
                        if (window.parent && window.parent !== window) {{
                            console.log('Backup: Messaging parent');
                            window.parent.postMessage({{
                                type: 'redirect',
                                url: targetUrl
                            }}, '*');
                        }}
                    }}, 100);
                    
                    // Strategy 3: Final fallback after 500ms
                    setTimeout(() => {{
                        console.log('Final fallback: Force redirect');
                        window.location.replace(targetUrl);
                    }}, 500);
                }})();
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
                <p style="margin-top: 15px;"><em>If redirect doesn't work, <a href="/chat/{session_id}/{country}/" style="color: #198484; text-decoration: underline; font-weight: bold;">click here</a>.</em></p>
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
    """Serve the country selection page with immediate redirect handling"""
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
            // Immediate redirect handling
            window.addEventListener('message', function(event) {
                console.log('Parent received message:', event.data);
                
                if (event.data && event.data.type === 'redirect') {
                    console.log('Executing immediate redirect to:', event.data.url);
                    // Immediate redirect without delay
                    window.location.href = event.data.url;
                }
            });
        </script>
    </body>
    </html>
    """


@app.get("/chat/{session_id}/{country}/", response_class=HTMLResponse)
async def chat_interface_page(session_id: str, country: str, request: Request):
    """Serve the chat interface page with proper parameter passing"""
    
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
    
    # The key fix: Make sure the iframe src URL is properly constructed
    chat_iframe_url = f"/chat-gradio/?session_id={session_id}&country={country}"
    
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
                <iframe src="{chat_iframe_url}" id="chatFrame" allow="camera; microphone; geolocation"></iframe>
            </div>
        </div>
        
        <script>
            // Debug information
            console.log('Chat interface loaded with:');
            console.log('  Session ID: {session_id}');
            console.log('  Country: {country}');
            console.log('  Iframe URL: {chat_iframe_url}');
            
            // Handle messages from iframe
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


def create_final_chat_interface():
    """Create chat interface with proper URL parameter extraction"""
    
    def chat_wrapper(message: str, history: list, request: gr.Request):
        """Final fixed wrapper that properly extracts session info"""
        session_id = "unknown"
        country = "unknown"
        
        # Primary method: Extract from query parameters
        if request and hasattr(request, 'query_params'):
            query_params = dict(request.query_params)
            session_id = query_params.get('session_id', 'unknown')
            country = query_params.get('country', 'unknown')
            print(f"✅ [Primary] Query params - Session: {session_id}, Country: {country}")
        
        # Secondary method: Check request URL directly
        if (session_id == "unknown" or country == "unknown") and request:
            try:
                # Get the full URL from the request
                if hasattr(request, 'url'):
                    url_str = str(request.url)
                    print(f"🔍 [Secondary] Full request URL: {url_str}")
                    
                    # Parse URL parameters manually
                    if '?' in url_str:
                        query_string = url_str.split('?')[1]
                        params = {}
                        for param in query_string.split('&'):
                            if '=' in param:
                                key, value = param.split('=', 1)
                                params[key] = value
                        
                        session_id = params.get('session_id', session_id)
                        country = params.get('country', country)
                        print(f"✅ [Secondary] Parsed params - Session: {session_id}, Country: {country}")
            except Exception as e:
                print(f"❌ [Secondary] Error parsing URL: {e}")
        
        # Tertiary method: Use global session info as fallback
        if session_id == "unknown" or country == "unknown":
            session_id = current_session_info.get("session_id", session_id)
            country = current_session_info.get("country", country)
            print(f"🔄 [Tertiary] Global fallback - Session: {session_id}, Country: {country}")
        
        print(f"🎯 Final chat processing:")
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
    
    # Add session info display and back button
    with interface:
        with gr.Row():
            session_info_display = gr.HTML("""
                <div class="session-info" id="session-info-display">
                    <div id="session-details">
                        <span class="session-info-highlight">🌍 Country:</span> <span id="country-display">Loading...</span> | 
                        <span class="session-info-highlight">🔗 Session:</span> <span id="session-display">Loading...</span>
                    </div>
                    <div style="margin-top: 10px; font-size: 0.9em; color: #666;">
                        <span id="status-display">Extracting session parameters...</span>
                    </div>
                </div>
                
                <script>
                    // Final fixed session info extraction
                    function extractSessionInfo() {
                        try {
                            console.log('🔍 Extracting session info from URL...');
                            console.log('Current URL:', window.location.href);
                            
                            // Extract from current URL query parameters
                            const urlParams = new URLSearchParams(window.location.search);
                            const sessionId = urlParams.get('session_id');
                            const country = urlParams.get('country');
                            
                            console.log('Extracted parameters:', { sessionId, country });
                            
                            if (sessionId && country) {
                                // Update display
                                document.getElementById('country-display').textContent = decodeURIComponent(country);
                                document.getElementById('session-display').textContent = sessionId.substring(0, 8) + '...';
                                document.getElementById('status-display').textContent = '✅ Parameters loaded successfully';
                                document.getElementById('status-display').style.color = '#16a085';
                                
                                console.log('✅ Session info updated successfully');
                                return true;
                            } else {
                                console.log('⚠️ Parameters not found in URL');
                                document.getElementById('status-display').textContent = '⚠️ Parameters not found in URL';
                                document.getElementById('status-display').style.color = '#e67e22';
                                return false;
                            }
                        } catch (error) {
                            console.error('❌ Error extracting session info:', error);
                            document.getElementById('status-display').textContent = '❌ Error loading session info';
                            document.getElementById('status-display').style.color = '#e74c3c';
                            return false;
                        }
                    }
                    
                    // Extract session info immediately when script loads
                    console.log('🚀 Starting session info extraction...');
                    extractSessionInfo();
                    
                    // Also try after a short delay in case of timing issues
                    setTimeout(extractSessionInfo, 1000);
                </script>
            """)
            
            back_btn = gr.Button("← Back to Country Selection", variant="secondary")
            
            def go_back():
                return gr.HTML("""
                <script>
                    console.log('Back button clicked');
                    const targetUrl = '/country/';
                    
                    if (window.parent && window.parent !== window) {
                        console.log('Sending message to parent for redirect');
                        window.parent.postMessage({
                            type: 'redirect',
                            url: targetUrl
                        }, '*');
                    } else {
                        console.log('Direct redirect to country selection');
                        window.location.href = targetUrl;
                    }
                </script>
                <div style="text-align: center; padding: 20px; color: #198484;">
                    <h3>🔙 Returning to country selection...</h3>
                </div>
                """)
            
            back_output = gr.HTML(visible=False)
            back_btn.click(go_back, outputs=[back_output])
    
    return interface


# Mount the final country selection Gradio app
print("🔧 Setting up final fixed Gradio applications...")

final_country_app = create_final_country_selection_app()
app = gr.mount_gradio_app(
    app, 
    final_country_app, 
    path="/country-gradio"
)

print("✅ Final country selection app mounted at /country-gradio")

# Create and mount the final chat interface
global_chat_app = create_final_chat_interface()
app = gr.mount_gradio_app(
    app,
    global_chat_app,
    path="/chat-gradio"
)

print("✅ Final chat app mounted at /chat-gradio")


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "growbal-intelligence-final-fixed",
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
    
    print("🚀 Starting Growbal Intelligence FastAPI application (Final Fixed Version)...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page")
    print("   - /chat/{session_id}/{country}/ → Chat interface")
    print("   - /country-gradio/ → Country selection Gradio app")
    print("   - /chat-gradio/ → Global chat Gradio app (with query params)")
    print("   - /health → Health check")
    print("   - /debug/sessions → Debug session information")
    print()
    print("🔧 Final fixes implemented:")
    print("   ✅ Immediate auto-redirect (no delays)")
    print("   ✅ Multiple URL parameter extraction methods")
    print("   ✅ Proper iframe src URL construction")
    print("   ✅ Enhanced debugging and console logging")
    print("   ✅ Manual URL parsing as fallback")
    print("   ✅ Real-time parameter display verification")
    
    uvicorn.run(
        "final_fixed_main_app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )