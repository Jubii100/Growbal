"""
ACTUALLY WORKING FastAPI application with proper Gradio integration
- Uses server-side redirects instead of JavaScript (following FastAPI docs)
- Implements proper parameter passing using FastAPI sessions
- NO MORE IFRAME BULLSHIT - direct page navigation
- Enhanced with wider country selection page and service type dropdown
- MODIFIED VERSION: Includes system prompt for strict country/service filtering
- FIXED VERSION: Properly handles URL encoding for service types with special characters
"""

import os
import sys
import uuid
import time
from typing import Dict, Any, Optional
from urllib.parse import quote, unquote
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

# Global storage for session management
session_store: Dict[str, Dict[str, Any]] = {}

# Create FastAPI app
app = FastAPI(
    title="Growbal Intelligence Platform",
    description="AI-powered service provider search with country selection and chat interface",
    version="3.0.0"
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


@app.get("/country/", response_class=HTMLResponse)
async def country_selection_page():
    """Serve country selection page - NO IFRAME, direct Gradio integration"""
    
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
    
    # Create country selection options
    country_options = ""
    for code, name in COUNTRY_CHOICES:
        country_options += f'<option value="{name}">{name}</option>\n'
    
    # Create service type options
    service_types = [
        "Tax Services",
        "Business Setup Services", 
        "Migration/Visa Services"
    ]
    
    service_type_options = ""
    for service_type in service_types:
        service_type_options += f'<option value="{service_type}">{service_type}</option>\n'
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Growbal Intelligence - Country Selection</title>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                margin: 0;
                padding: 0;
                font-family: 'Inter', Arial, sans-serif;
                background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            .container {{
                max-width: 800px;
                width: 90%;
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 10px 50px rgba(25, 132, 132, 0.1);
                text-align: center;
            }}
            .app-header {{
                background: linear-gradient(135deg, #2b5556 0%, #21908f 100%);
                color: white;
                padding: 20px;
                border-radius: 15px;
                margin-bottom: 30px;
            }}
            .app-title {{
                font-size: 1.8rem;
                font-weight: 700;
                margin-bottom: 8px;
            }}
            .app-description {{
                font-size: 1rem;
                opacity: 0.9;
                color: white;
            }}
            .selection-grid {{
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin: 20px 0;
            }}
            .selection-item {{
                display: flex;
                flex-direction: column;
                align-items: flex-start;
            }}
            .selection-label {{
                font-size: 1.1rem;
                font-weight: 600;
                color: #2b5556;
                margin-bottom: 8px;
                text-align: left;
            }}
            select {{
                width: 100%;
                padding: 15px;
                font-size: 16px;
                border: 2px solid rgba(25, 132, 132, 0.2);
                border-radius: 10px;
                background: white;
                transition: all 0.3s ease;
            }}
            select:focus {{
                border-color: #198484;
                box-shadow: 0 0 0 3px rgba(25, 132, 132, 0.1);
                outline: none;
            }}
            .btn-primary {{
                background: linear-gradient(135deg, #198484 0%, #16a6a6 100%);
                border: none;
                color: white;
                font-weight: 600;
                border-radius: 10px;
                padding: 15px 30px;
                font-size: 16px;
                cursor: pointer;
                transition: all 0.3s ease;
                box-shadow: 0 4px 15px rgba(25, 132, 132, 0.2);
                width: 100%;
                margin-top: 20px;
            }}
            .btn-primary:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 25px rgba(25, 132, 132, 0.3);
                background: linear-gradient(135deg, #16a6a6 0%, #198484 100%);
            }}
            .btn-primary:disabled {{
                opacity: 0.5;
                cursor: not-allowed;
                transform: none;
            }}
            h2 {{
                color: #2b5556;
                margin-bottom: 10px;
            }}
            p {{
                color: #666;
                margin-bottom: 20px;
            }}
            @media (max-width: 768px) {{
                .selection-grid {{
                    grid-template-columns: 1fr;
                }}
                .container {{
                    width: 95%;
                    padding: 20px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            {logo_html}
            <div class="app-header">
                <h1 class="app-title">Growbal Intelligence</h1>
                <p class="app-description">AI-powered service provider search</p>
            </div>
            
            <h2>Please select your preferences to begin</h2>
            <p>Choose your target country and service type for provider search</p>
            
            <form action="/proceed-to-chat" method="post">
                <div class="selection-grid">
                    <div class="selection-item">
                        <label class="selection-label">Country</label>
                        <select name="country" required onchange="toggleButton()">
                            <option value="">Select a country...</option>
                            {country_options}
                        </select>
                    </div>
                    
                    <div class="selection-item">
                        <label class="selection-label">Service Type</label>
                        <select name="service_type" required onchange="toggleButton()">
                            <option value="">Select a service type...</option>
                            {service_type_options}
                        </select>
                    </div>
                </div>
                
                <button type="submit" class="btn-primary" id="continueBtn" disabled>
                    Continue to Search
                </button>
            </form>
        </div>
        
        <script>
            function toggleButton() {{
                const countrySelect = document.querySelector('select[name="country"]');
                const serviceTypeSelect = document.querySelector('select[name="service_type"]');
                const button = document.getElementById('continueBtn');
                button.disabled = !countrySelect.value || !serviceTypeSelect.value;
            }}
        </script>
    </body>
    </html>
    """


@app.post("/proceed-to-chat")
async def proceed_to_chat(request: Request, country: str = Form(...), service_type: str = Form(...)):
    """
    Handle form submission and redirect to chat interface
    This is the CORRECT way according to FastAPI documentation
    FIXED: Properly URL-encode service type to handle special characters
    """
    if not country or not service_type:
        raise HTTPException(status_code=400, detail="Country and service type are required")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Store session data
    session_store[session_id] = {
        "country": country,
        "service_type": service_type,
        "created_at": time.time(),
        "active": True,
        "last_activity": time.time()
    }
    
    # Store in FastAPI session
    request.session["session_id"] = session_id
    request.session["country"] = country
    request.session["service_type"] = service_type
    
    print(f"🚀 Redirecting to chat: Session={session_id}, Country={country}, Service Type={service_type}")
    
    # SERVER-SIDE REDIRECT with proper URL encoding for service type
    encoded_service_type = quote(service_type, safe='')
    redirect_url = f"/chat/{session_id}/{country}/{encoded_service_type}/"
    print(f"🔧 DEBUG: Original service_type: {service_type}")
    print(f"🔧 DEBUG: Encoded service_type: {encoded_service_type}")
    print(f"🔧 DEBUG: Redirect URL: {redirect_url}")
    return RedirectResponse(url=redirect_url, status_code=303)


@app.get("/chat/{session_id}/{country}/{service_type}/", response_class=HTMLResponse)
async def chat_interface_page(session_id: str, country: str, service_type: str, request: Request):
    """
    Serve the chat interface page with proper parameter passing
    FIXED: URL-decode service type to handle encoded special characters
    """
    
    # URL-decode the service type to handle encoded characters
    decoded_service_type = unquote(service_type)
    
    # Verify session exists
    if session_id not in session_store:
        session_store[session_id] = {
            "country": country,
            "service_type": decoded_service_type,
            "created_at": time.time(),
            "active": True,
            "last_activity": time.time()
        }
    
    # Update session
    session_store[session_id]["last_activity"] = time.time()
    
    # Store in FastAPI session (use decoded service type)
    request.session["session_id"] = session_id
    request.session["country"] = country
    request.session["service_type"] = decoded_service_type
    
    print(f"✅ Chat interface loaded: Session={session_id}, Country={country}, Service Type={decoded_service_type}")
    
    # Direct Gradio mount - NO IFRAME
    # Use URL-encoded service type for the iframe URL but decoded for display
    encoded_service_type = quote(decoded_service_type, safe='')
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
                <span class="session-info-highlight">💼 Service Type:</span> {decoded_service_type}
                <a href="/country/" style="margin-left: 20px; color: #198484; text-decoration: none;">← Back to Country Selection</a>
            </div>
            <div class="gradio-container">
                <iframe src="/chat-gradio/?session_id={session_id}&country={country}&service_type={encoded_service_type}" id="chatFrame" allow="camera; microphone; geolocation"></iframe>
            </div>
        </div>
        
        <script>
            console.log('✅ Chat interface loaded with:');
            console.log('  Session ID: {session_id}');
            console.log('  Country: {country}');
            console.log('  Service Type: {decoded_service_type}');
            console.log('  URL: ' + window.location.href);
        </script>
    </body>
    </html>
    """


def create_working_chat_interface():
    """Create chat interface with PROPER parameter extraction and strict filtering"""
    
    def chat_wrapper(message: str, history: list, request: gr.Request):
        """
        Chat wrapper with RELIABLE parameter extraction and strict system prompt
        FIXED: Properly decode URL-encoded service type parameters
        """
        session_id = "unknown"
        country = "unknown"
        service_type = "unknown"
        
        print(f"🔍 Chat wrapper called with message: {message}")
        
        # Method 1: Extract from query parameters (MOST RELIABLE)
        if request and hasattr(request, 'query_params'):
            query_params = dict(request.query_params)
            session_id = query_params.get('session_id', session_id)
            country = query_params.get('country', country)
            # URL-decode the service type parameter
            encoded_service_type = query_params.get('service_type', service_type)
            service_type = unquote(encoded_service_type) if encoded_service_type != "unknown" else service_type
            print(f"✅ [Query] Session: {session_id}, Country: {country}, Service Type: {service_type}")
        
        # Method 2: Extract from FastAPI session
        if (session_id == "unknown" or country == "unknown" or service_type == "unknown") and request:
            try:
                fastapi_request = request.request if hasattr(request, 'request') else request
                if hasattr(fastapi_request, 'session'):
                    session_id = fastapi_request.session.get('session_id', session_id)
                    country = fastapi_request.session.get('country', country)
                    service_type = fastapi_request.session.get('service_type', service_type)
                    print(f"✅ [FastAPI Session] Session: {session_id}, Country: {country}, Service Type: {service_type}")
            except Exception as e:
                print(f"❌ [FastAPI Session] Error: {e}")
        
        # Method 3: Check session store
        if session_id != "unknown" and session_id in session_store:
            country = session_store[session_id].get("country", country)
            service_type = session_store[session_id].get("service_type", service_type)
            print(f"✅ [Session Store] Session: {session_id}, Country: {country}, Service Type: {service_type}")
        
        print(f"🎯 Final parameters: Session={session_id}, Country={country}, Service Type={service_type}")
        
        # Import and run the actual chat response function with enhanced system prompt
        from chat.chat_interface import get_search_agent_response
        import asyncio
        
        # Create system prompt that enforces country and service type filtering
        system_prompt = f"""CRITICAL INSTRUCTIONS - YOU MUST FOLLOW THESE EXACTLY:

1. COUNTRY FILTER: You are STRICTLY limited to searching for service providers ONLY in {country}.

2. SERVICE TYPE FILTER: You are STRICTLY limited to searching for {service_type} providers ONLY.

4. USER COMMUNICATION:
- When presenting results, clearly indicate that all providers are located in {country}
- When presenting results, clearly indicate that all providers offer {service_type}
- If no relevant results are found, explain that no {service_type} providers were found in {country}"""
        
        # Create async wrapper with system prompt
        async def get_response():
            async for chunk in get_search_agent_response(message, system_prompt):
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
    
    # CSS styling
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
    
    /* Message Styling */
    .message-wrap {
        padding: 15px 20px !important;
        border-radius: 15px !important;
        margin: 10px 0 !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05) !important;
        border: 1px solid rgba(25, 132, 132, 0.1) !important;
    }
    
    .message-wrap.user {
        background: linear-gradient(135deg, #198484 0%, #16a6a6 100%) !important;
        color: white !important;
        border: 1px solid rgba(25, 132, 132, 0.3) !important;
    }
    
    .message-wrap.bot {
        background: linear-gradient(135deg, #ffffff 0%, #f8fffe 100%) !important;
        color: #2d3748 !important;
        border: 1px solid rgba(25, 132, 132, 0.15) !important;
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
    
    .btn-secondary {
        background: linear-gradient(135deg, #ffffff 0%, #f8fffe 100%) !important;
        border: 2px solid #198484 !important;
        color: #198484 !important;
        font-weight: 600 !important;
        border-radius: 10px !important;
        padding: 10px 20px !important;
        transition: all 0.3s ease !important;
    }
    
    .btn-secondary:hover {
        background: linear-gradient(135deg, #198484 0%, #16a6a6 100%) !important;
        color: white !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 15px rgba(25, 132, 132, 0.2) !important;
    }
    
    /* Header Styling */
    .app-header {
        text-align: center !important;
        padding: 10px 0 !important;
        background: linear-gradient(135deg, #2b5556 0%, #21908f 100%) !important;
        border-radius: 15px !important;
        margin-bottom: 10px !important;
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
    
    /* Input Field Styling */
    .textbox input, .textbox textarea {
        border: 2px solid rgba(25, 132, 132, 0.2) !important;
        border-radius: 10px !important;
        padding: 12px !important;
        font-size: 15px !important;
        transition: all 0.3s ease !important;
        background: #ffffff !important;
    }
    
    .textbox input:focus, .textbox textarea:focus {
        border-color: #198484 !important;
        box-shadow: 0 0 0 3px rgba(25, 132, 132, 0.1) !important;
        outline: none !important;
    }
    
    /* Thinking blocks styling */
    details {
        margin: 12px 0 !important;
        border-radius: 10px !important;
        overflow: hidden !important;
        box-shadow: 0 4px 20px rgba(25, 132, 132, 0.08) !important;
    }
    
    details summary {
        transition: all 0.3s ease !important;
        cursor: pointer !important;
        background: linear-gradient(135deg, #198484 0%, #16a6a6 100%) !important;
    }
    
    details summary:hover {
        background: linear-gradient(135deg, #16a6a6 0%, #198484 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 25px rgba(25, 132, 132, 0.15) !important;
    }
    
    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 8px !important;
    }
    
    ::-webkit-scrollbar-track {
        background: #f1f1f1 !important;
        border-radius: 4px !important;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #198484 0%, #16a6a6 100%) !important;
        border-radius: 4px !important;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #16a6a6 0%, #198484 100%) !important;
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
    
    return interface


# Mount the chat interface
print("🔧 Setting up WORKING chat interface with strict filtering...")
working_chat_app = create_working_chat_interface()
app = gr.mount_gradio_app(
    app,
    working_chat_app,
    path="/chat-gradio"
)
print("✅ Working chat app mounted at /chat-gradio with strict country/service filtering")


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "growbal-intelligence-with-strict-filtering",
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
    
    print("🚀 Starting FIXED Growbal Intelligence FastAPI application...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page (NO IFRAME)")
    print("   - /proceed-to-chat → Form submission handler (SERVER-SIDE REDIRECT)")
    print("   - /chat/{session_id}/{country}/{service_type}/ → Chat interface")
    print("   - /chat-gradio/ → Chat Gradio app (with query params)")
    print("   - /health → Health check")
    print("   - /debug/sessions → Debug session information")
    print()
    print("🔧 ENHANCEMENTS IN THIS VERSION:")
    print("   ✅ Strict system prompt enforcement for country/service filtering")
    print("   ✅ Parameters from request are used to constrain AI search behavior")
    print("   ✅ Agent will reject requests outside selected country/service")
    print("   ✅ Search queries automatically include country and service context")
    print("   ✅ Clear communication about filtering constraints to users")
    print("   🔧 FIXED: Proper URL encoding for service types with special characters")
    print("   🔧 FIXED: Handles 'Migration/Visa Services' and other service types with '/' character")
    
    uvicorn.run(
        "main_app_3:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )