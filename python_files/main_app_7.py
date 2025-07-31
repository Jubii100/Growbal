"""
ORCHESTRATOR-ENABLED FastAPI application with DYNAMIC SUGGESTIONS
- Uses orchestrator agent to coordinate tool selection
- Integrates with MCP server for service provider search
- Shows only current step and final response (no accumulated agentic history)
- Provides dynamic suggestions based on country, service type, and conversation history
"""

import os
import sys
import asyncio
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import gradio as gr
from dotenv import load_dotenv
from mcp import StdioServerParameters
from session_manager import session_manager
from orchestrator_interface import create_orchestrator_chat_interface, OrchestratorAgent

# Load environment variables
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, 'envs', '1.env')
load_dotenv(env_path)

# Initialize orchestrator
api_key = os.getenv('ANTHROPIC_API_KEY')
orchestrator = OrchestratorAgent(api_key)

# Add the project root to the path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Session manager handles all session operations with database backing
# No longer using in-memory dictionary storage

# MCP Server Configuration
server_params = StdioServerParameters(
    command="python",
    args=[os.path.join(os.path.dirname(__file__), "server.py")],
    env=None
)

# Background task to clean up old sessions
async def cleanup_old_sessions():
    """Periodically deactivate old sessions on a weekly basis"""
    while True:
        try:
            # Deactivate sessions older than 7 days (168 hours)
            deactivated = await session_manager.deactivate_old_sessions(hours=168)
            if deactivated > 0:
                print(f"🧹 Weekly cleanup: Deactivated {deactivated} old sessions")
            else:
                print(f"🧹 Weekly cleanup: No old sessions to deactivate")
        except Exception as e:
            print(f"❌ Error during weekly session cleanup: {e}")
        
        # Run every week (7 days = 604800 seconds)
        await asyncio.sleep(604800)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    cleanup_task = asyncio.create_task(cleanup_old_sessions())
    print("✅ Started weekly session cleanup task")
    
    yield
    
    # Shutdown
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass
    print("🛑 Stopped session cleanup task")

# Create FastAPI app
app = FastAPI(
    title="Growbal Intelligence Platform - Orchestrator v8",
    description="AI-powered service provider search with database-backed sessions",
    version="8.0.0",
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
    """Serve country selection page"""
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
            .orchestrator-badge {{
                background: #ff6b6b;
                color: white;
                padding: 4px 8px;
                border-radius: 8px;
                font-size: 0.75rem;
                margin-left: 10px;
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
    """Handle form submission and redirect to chat interface"""
    if not country or not service_type:
        raise HTTPException(status_code=400, detail="Country and service type are required")
    
    # Check for existing session with same country/service_type
    # This handles duplicate prevention automatically
    session_id, session_data, is_new = await session_manager.get_or_create_session(
        session_id=request.session.get("session_id"),
        country=country,
        service_type=service_type,
        user_id=None  # Anonymous for now
    )
    
    if is_new:
        print(f"🆕 Created new session: {session_id}")
    else:
        print(f"♻️  Reusing existing session: {session_id}")
    
    # Store in FastAPI session
    request.session["session_id"] = session_id
    request.session["country"] = country
    request.session["service_type"] = service_type
    
    print(f"🚀 Redirecting to chat: Session={session_id}, Country={country}, Service Type={service_type}")
    
    # SERVER-SIDE REDIRECT using query parameters
    redirect_url = f"/chat/?session_id={session_id}&country={country}&service_type={service_type}"
    return RedirectResponse(url=redirect_url, status_code=303)

@app.get("/chat/", response_class=HTMLResponse)
async def chat_interface_page(request: Request, session_id: str = None, country: str = None, service_type: str = None):
    """Serve the chat interface page with orchestrator integration"""
    
    # Get or create session in database
    db_session_id, session_data, is_new = await session_manager.get_or_create_session(
        session_id=session_id,
        country=country,
        service_type=service_type,
        user_id=None  # Anonymous for now
    )
    
    # Use the database session ID (in case a different one was returned due to reuse)
    session_id = db_session_id
    
    # Update activity timestamp
    await session_manager.update_activity(session_id)
    
    # Update orchestrator's session history
    await orchestrator.update_session_history(session_id)
    print(orchestrator.session_history)
    
    # Store in FastAPI session
    request.session["session_id"] = session_id
    request.session["country"] = country
    request.session["service_type"] = service_type
    
    print(f"✅ Chat interface loaded: Session={session_id}, Country={country}, Service Type={service_type}")
    
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
            .orchestrator-badge {{
                background: #ff6b6b;
                color: white;
                padding: 2px 6px;
                border-radius: 4px;
                font-size: 0.7rem;
                margin-left: 10px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="session-info">
                <span class="session-info-highlight">🌍 Country:</span> {country} | 
                <span class="session-info-highlight">💼 Service Type:</span> {service_type}
                <a href="/country/" style="margin-left: 20px; color: #198484; text-decoration: none;">← Back to Country Selection</a>
            </div>
            <div class="gradio-container">
                <iframe src="/chat-public/?session_id={session_id}&country={country}&service_type={service_type}" id="chatFrame" allow="camera; microphone; geolocation"></iframe>
            </div>
        </div>
        
        <script>
            console.log('✅ Chat interface loaded with:');
            console.log('  Session ID: {session_id}');
            console.log('  Country: {country}');
            console.log('  Service Type: {service_type}');
            console.log('  URL: ' + window.location.href);
        </script>
    </body>
    </html>
    """

# Mount the orchestrator chat interface
print("🧠 Setting up chat interface with orchestrator...")
orchestrator_chat_app = create_orchestrator_chat_interface(orchestrator)
app = gr.mount_gradio_app(
    app,
    orchestrator_chat_app,
    path="/chat-public"
)
print("✅ Chat app mounted at /chat-public")

# Health check and debug endpoints
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "growbal-intelligence-orchestrator-dynamic",
        "version": "7.0.0",
        "features": ["orchestrator", "dynamic_suggestions", "clean_streaming", "tool_routing"],
        "active_sessions": await session_manager.get_active_sessions_count()
    }

@app.get("/debug/sessions")
async def debug_sessions():
    """Debug endpoint to show active sessions count"""
    active_count = await session_manager.get_active_sessions_count()
    return {
        "total_active_sessions": active_count,
        "note": "Session details are now stored in database for security"
    }

@app.get("/debug/suggestions")
async def debug_suggestions(country: str = "USA", service_type: str = "Tax Services"):
    """Debug endpoint to test suggestion generation"""
    try:
        suggestions = await orchestrator.generate_suggestions(country, service_type, None)
        return {
            "country": country,
            "service_type": service_type,
            "suggestions": suggestions
        }
    except Exception as e:
        return {
            "error": str(e),
            "country": country,
            "service_type": service_type
        }

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Growbal Intelligence FastAPI application...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page")
    print("   - /proceed-to-chat → Form submission handler")
    print("   - /chat/ → Chat interface with orchestrator")
    print("   - /chat-public/ → Public chat interface (free tier)")
    print("   - /health → Health check")
    print("   - /debug/sessions → Debug session information")
    print("   - /debug/suggestions → Debug suggestion generation")
    print()
    print("🧠 Features:")
    print("   ✅ Database-backed session management with duplicate prevention")
    print("   ✅ Intelligent tool routing based on message analysis")
    print("   ✅ Dynamic suggestions generated by orchestrator")
    print("   ✅ Context-aware suggestions (country + service + history)")
    print("   ✅ Clean streaming: shows only current step + final result")
    print("   ✅ Weekly automatic cleanup of old sessions (>7 days)")
    print("   ✅ Persistent chat history storage")
    
    uvicorn.run(
        "main_app_8:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )