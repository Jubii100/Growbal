"""
ORCHESTRATOR-ENABLED FastAPI application with DYNAMIC SUGGESTIONS
- Uses orchestrator agent to coordinate tool selection
- Provides service provider search with real-time streaming
- Shows only current step and final response (no accumulated agentic history)
- Provides dynamic suggestions based on country, service type, and conversation history
"""

import os
import sys
import asyncio
import json
from fastapi import FastAPI, Request, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from contextlib import asynccontextmanager
import gradio as gr
from dotenv import load_dotenv
from session_manager import session_manager
from orchestrator_interface import create_orchestrator_chat_interface, OrchestratorAgent
from authentication.auth_routes import login_page, process_login, logout
from authentication.dependencies import require_authentication, optional_authentication

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
async def root(request: Request, current_user: dict = Depends(optional_authentication)):
    """Root endpoint that redirects authenticated users to chat, others to login"""
    if current_user:
        # User is authenticated, redirect directly to chat with defaults
        return RedirectResponse(url="/proceed-to-chat")
    else:
        # User not authenticated, redirect to login
        return RedirectResponse(url="/login")

# Authentication routes
app.get("/login", response_class=HTMLResponse)(login_page)
app.post("/login")(process_login)
app.post("/logout")(logout)

# Utility: Generate Growbal logo HTML (shared across views)
def generate_logo_html():
    """Return the Growbal logo wrapped in a styled white container, or an empty string if the file is missing."""
    logo_path = os.path.join(os.path.dirname(__file__), "growbal_logoheader.svg")
    if os.path.exists(logo_path):
        with open(logo_path, "r") as f:
            logo_content = f.read()
        return f"""
        <div style=\"display: flex; justify-content: center; align-items: center; padding: 10px 0; background: #ffffff; margin-bottom: 10px; border-radius: 15px; box-shadow: 0 8px 32px rgba(43, 85, 86, 0.15);\">
            <div style=\"max-width: 200px; height: auto;\">
                {logo_content}
            </div>
        </div>
        """
    return ""

@app.get("/country/", response_class=HTMLResponse)
async def country_selection_page(request: Request, current_user: dict = Depends(require_authentication)):
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
    
    # Prepare logo HTML using shared helper
    logo_html = generate_logo_html()
    # (Previous inline implementation moved to helper above for maintainability)
    
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
    
    # Add user info display
    user_info_html = ""
    if current_user:
        user_name = current_user.get('full_name') or current_user.get('email', 'User')
        user_info_html = f"""
        <div style="text-align: right; padding: 15px; background: #f8f9fa; border-bottom: 1px solid #dee2e6; margin-bottom: 20px; border-radius: 10px;">
            <span style="color: #2b5556;">Welcome, <strong>{user_name}</strong></span> | 
            <form method="post" action="/logout" style="display: inline;">
                <button type="submit" style="background: none; border: none; color: #198484; cursor: pointer; text-decoration: underline; font-weight: 600;">
                    Logout
                </button>
            </form>
        </div>
        """
    
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
            {user_info_html}
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

@app.get("/proceed-to-chat")
@app.post("/proceed-to-chat")
async def proceed_to_chat(
    request: Request, 
    current_user: dict = Depends(require_authentication),
    # Query parameters for GET requests
    country: str = None,
    service_type: str = None,
    session_id: str = None,
    # Form parameters for POST requests (backwards compatibility)
    form_country: str = Form(None),
    form_service_type: str = Form(None)
):
    """Handle both GET and POST requests to proceed to chat interface"""
    
    # Determine country and service_type from either query params or form data
    final_country = country or form_country or "UAE"
    final_service_type = service_type or form_service_type or "Business Setup Services"
    
    # Check for existing session with same country/service_type
    # This handles duplicate prevention automatically
    user_id = current_user.get('user_id') if current_user else None
    
    # Only use session_id if explicitly provided in URL query params
    # Don't reuse from browser session storage to ensure new sessions when needed
    existing_session_id = session_id
    
    final_session_id, session_data, is_new = await session_manager.get_or_create_session(
        session_id=existing_session_id,
        country=final_country,
        service_type=final_service_type,
        user_id=user_id  # Use authenticated user ID if available
    )
    
    if is_new:
        print(f"🆕 Created new session: {final_session_id}")
    else:
        print(f"♻️  Reusing existing session: {final_session_id}")
    
    # Store in FastAPI session
    request.session["session_id"] = final_session_id
    request.session["country"] = final_country
    request.session["service_type"] = final_service_type
    
    print(f"🚀 Redirecting to chat: Session={final_session_id}, Country={final_country}, Service Type={final_service_type}")
    
    # SERVER-SIDE REDIRECT using query parameters
    redirect_url = f"/chat/?session_id={final_session_id}"
    return RedirectResponse(url=redirect_url, status_code=303)

@app.get("/chat/", response_class=HTMLResponse)
async def chat_interface_page(request: Request, session_id: str = None, current_user: dict = Depends(require_authentication)):
    """Serve the chat interface page with orchestrator integration"""
    
    # Get or create session in database
    session = await session_manager.get_session(session_id)
    if session is None:
        # either 404 or redirect back to /country/
        raise HTTPException(404, "Invalid session")
    
    # Use the database session ID (in case a different one was returned due to reuse)
    session_id = str(session.get("session_id"))
    country = str(session.get("country"))
    service_type = str(session.get("service_type"))
    print(f"🚀 Chat interface loaded: Session={session_id}, Country={country}, Service Type={service_type}")

    # Update activity timestamp
    await session_manager.update_activity(session_id)
    
    # Get all user sessions for the sidebar
    user_id = current_user.get('user_id') if current_user else None
    user_sessions = []
    if user_id:
        user_sessions = await session_manager.get_user_sessions(user_id, active_only=True)
    
    # Update orchestrator's session history
    await orchestrator.update_session_history(session_id)
    print(orchestrator.session_history)
    
    # Get session history for display
    session_history = orchestrator.session_history if hasattr(orchestrator, 'session_history') else []
    
    # Determine if there is any chat history
    has_history = bool(session_history)

    # Pre-serialise history for JavaScript (empty array when none)
    history_json = json.dumps(session_history) if has_history else "[]"

    # Build the chat-history HTML (and its accompanying <script>) only when
    # history exists.  Otherwise, render an empty string so that **no trace**
    # of the component appears in the final page.
    if has_history:
        history_section = f"""
            <!-- Chat History Component -->
            <div id=\"chatHistoryContainer\" class=\"chat-history-container collapsed\">
                <div class=\"chat-history-header\" onclick=\"toggleChatHistory()\">
                    <span class=\"chat-history-title\">
                        <span id=\"toggleIcon\" class=\"chat-history-toggle collapsed\">⌃</span>
                        Previous Chat History
                    </span>
                </div>
                <div id=\"chatHistoryContent\" class=\"chat-history-content\">
                    <!-- History will be populated by JavaScript -->
                </div>
            </div>

            <!-- Include Markdown parser (marked.js) and sanitizer (DOMPurify) -->
            <script src=\"https://cdn.jsdelivr.net/npm/marked/marked.min.js\"></script>
            <script src=\"https://cdn.jsdelivr.net/npm/dompurify@2.4.4/dist/purify.min.js\"></script>
            <script>
                // Session history data
                const sessionHistory = {history_json};
                
                // Toggle chat history visibility
                function toggleChatHistory() {{
                    const container = document.getElementById('chatHistoryContainer');
                    const toggleIcon  = document.getElementById('toggleIcon');
                    
                    if (container.classList.contains('collapsed')) {{
                        container.classList.remove('collapsed');
                        container.classList.add('expanded');
                        toggleIcon.classList.remove('collapsed');
                    }} else {{
                        container.classList.remove('expanded');
                        container.classList.add('collapsed');
                        toggleIcon.classList.add('collapsed');
                    }}
                }}
                
                // Convert Markdown to safe HTML
                function renderMarkdown(text) {{
                    if (!text) return '';
                    const cleanedText = String(text).trim();
                    // marked.parse adds a trailing newline; trim again after parsing
                    const rawHtml = marked.parse(cleanedText).trim();
                    return DOMPurify.sanitize(rawHtml);
                }}
                
                // Populate chat history UI
                function populateChatHistory() {{
                    const contentDiv = document.getElementById('chatHistoryContent');
                    
                    if (!sessionHistory || sessionHistory.length === 0) {{
                        contentDiv.innerHTML = '<div class=\"no-history\">No previous chat history for this session</div>';
                        return;
                    }}
                    
                    let historyHTML = '';
                    sessionHistory.forEach(([userMsg, assistantMsg]) => {{
                        // User message
                        if (userMsg) {{
                            historyHTML += `
                                <div class=\"chat-message user\">
                                    <div class=\"message-role user\">You</div>
                                    <div class=\"message-content\">${{renderMarkdown(userMsg)}}</div>
                                </div>
                            `;
                        }}
                        // Assistant message
                        if (assistantMsg) {{
                            historyHTML += `
                                <div class=\"chat-message assistant\">
                                    <div class=\"message-role assistant\">Growbal Intelligence</div>
                                    <div class=\"message-content\">${{renderMarkdown(assistantMsg)}}</div>
                                </div>
                            `;
                        }}
                    }});
                    contentDiv.innerHTML = historyHTML;
                }}
                
                // Simple HTML-escape helper
                function escapeHtml(text) {{
                    const div = document.createElement('div');
                    div.textContent = text;
                    return div.innerHTML;
                }}
                
                // Initialise after page load and automatically expand history panel
                document.addEventListener('DOMContentLoaded', () => {{
                    populateChatHistory();
                    // Auto-expand when history exists
                    if (sessionHistory && sessionHistory.length > 0) {{
                        toggleChatHistory();
                    }}
                }});
                
                // Debug output
                console.log('✅ Chat interface loaded with:');
                console.log('  Session ID: {session_id}');
                console.log('  Country: {country}');
                console.log('  Service Type: {service_type}');
                console.log('  History items:', sessionHistory.length);
                console.log('  URL: ' + window.location.href);
            </script>
        """
    else:
        # Display Growbal logo placeholder when no chat history exists
        history_section = generate_logo_html()

    # Store in FastAPI session
    request.session["session_id"] = session_id
    request.session["country"] = country
    request.session["service_type"] = service_type
    
    print(f"✅ Chat interface loaded: Session={session_id}, Country={country}, Service Type={service_type}")
    
    # (history_json and history_section prepared above, only if history exists)
    
    # Prepare sessions list HTML
    sessions_list_html = ""
    if user_sessions:
        from datetime import datetime
        import time
        
        for sess in user_sessions:
            sess_id = sess.get('session_id')
            sess_title = sess.get('title', 'Untitled Session')
            sess_country = sess.get('country')
            sess_service = sess.get('service_type')
            last_activity = sess.get('last_activity')
            
            # Format last activity time
            if last_activity:
                last_activity_dt = datetime.fromtimestamp(last_activity)
                now = datetime.now()
                time_diff = now - last_activity_dt
                
                # Format time difference
                if time_diff.days > 0:
                    time_str = f"{time_diff.days}d ago"
                elif time_diff.seconds >= 3600:
                    hours = time_diff.seconds // 3600
                    time_str = f"{hours}h ago"
                elif time_diff.seconds >= 60:
                    minutes = time_diff.seconds // 60
                    time_str = f"{minutes}m ago"
                else:
                    time_str = "just now"
            else:
                time_str = ""
            
            is_current = str(sess_id) == str(session_id)
            active_class = 'active' if is_current else ''
            sessions_list_html += f'''
                <a href="/chat/?session_id={sess_id}" class="session-item {active_class}">
                    <div class="session-title">{sess_title}</div>
                    <div class="session-meta">{sess_service} • {sess_country} • {time_str}</div>
                </a>
            '''
    else:
        sessions_list_html = '<div class="no-sessions">No active sessions</div>'
    
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
            
            .main-content {{
                flex: 1;
                display: flex;
                position: relative;
                overflow: hidden;
            }}
            
            /* Sessions Sidebar Styles */
            .sessions-sidebar {{
                width: 350px;
                background: white;
                border-right: 1px solid rgba(25, 132, 132, 0.15);
                display: flex;
                flex-direction: column;
                transition: margin-left 0.3s ease;
                position: relative;
                z-index: 10;
            }}
            
            .sessions-sidebar.collapsed {{
                margin-left: -350px;
            }}
            
            .sessions-header {{
                padding: 20px;
                background: linear-gradient(135deg, #f8fffe 0%, #ffffff 100%);
                border-bottom: 1px solid rgba(25, 132, 132, 0.1);
                position: relative;
            }}
            
            .sessions-title {{
                font-weight: 600;
                color: #2b5556;
                font-size: 1.1rem;
                margin-bottom: 5px;
            }}
            
            .sessions-subtitle {{
                font-size: 0.85rem;
                color: #718096;
            }}
            
            .toggle-sidebar {{
                position: absolute;
                right: -40px;
                top: 20px;
                width: 40px;
                height: 60px;
                background: white;
                border: 1px solid rgba(25, 132, 132, 0.15);
                border-left: none;
                border-radius: 0 8px 8px 0;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.3s ease;
                box-shadow: 2px 0 8px rgba(0, 0, 0, 0.05);
                z-index: 15;
            }}
            
            .toggle-sidebar:hover {{
                background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%);
                box-shadow: 3px 0 12px rgba(25, 132, 132, 0.1);
                transform: translateX(5px);
            }}
            
            .toggle-icon {{
                color: #198484;
                font-size: 1.2rem;
                transition: transform 0.3s ease;
            }}
            
            .sessions-sidebar.collapsed .toggle-icon {{
                transform: rotate(180deg);
            }}
            
            .sessions-list {{
                flex: 1;
                overflow-y: auto;
                padding: 10px;
            }}
            
            .session-item {{
                display: block;
                padding: 12px 15px;
                margin-bottom: 8px;
                background: #fafbfc;
                border: 1px solid rgba(25, 132, 132, 0.1);
                border-radius: 8px;
                text-decoration: none;
                transition: all 0.2s ease;
                cursor: pointer;
                min-height: 60px;
            }}
            
            .session-item:hover {{
                background: linear-gradient(135deg, #f0f9f9 0%, #f8fffe 100%);
                border-color: rgba(25, 132, 132, 0.2);
                transform: translateX(2px);
            }}
            
            .session-item.active {{
                background: linear-gradient(135deg, #198484 0%, #16a6a6 100%);
                border-color: transparent;
                color: white;
            }}
            
            .session-title {{
                font-weight: 600;
                font-size: 0.85rem;
                color: #2b5556;
                margin-bottom: 4px;
                line-height: 1.3;
                display: -webkit-box;
                -webkit-line-clamp: 2;
                -webkit-box-orient: vertical;
                overflow: hidden;
                word-break: break-word;
            }}
            
            .session-item.active .session-title {{
                color: white;
            }}
            
            .session-meta {{
                font-size: 0.75rem;
                color: #718096;
                margin-top: 2px;
            }}
            
            .session-item.active .session-meta {{
                color: rgba(255, 255, 255, 0.9);
            }}
            
            .no-sessions {{
                padding: 20px;
                text-align: center;
                color: #718096;
                font-size: 0.9rem;
            }}
            
            .content-area {{
                flex: 1;
                display: flex;
                flex-direction: column;
                position: relative;
                padding-left: 20px;
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
            
            /* Chat History Styles */
            .chat-history-container {{
                background: white;
                border: 1px solid rgba(25, 132, 132, 0.15); /* subtle outline */
                border-radius: 12px;                       /* rounded corners */
                box-shadow: 0 4px 14px rgba(25, 132, 132, 0.08); /* soft shadow for separation */
                margin-bottom: 24px;                       /* space before chat UI */
                transition: max-height 0.3s ease-in-out;
                overflow: hidden;
            }}
            
            .chat-history-header {{
                padding: 12px 20px;
                background: linear-gradient(135deg, #f8fffe 0%, #ffffff 100%);
                border-bottom: 1px solid rgba(25, 132, 132, 0.1);
                cursor: pointer;
                display: flex;
                justify-content: space-between;
                align-items: center;
                user-select: none;
                border-radius: 12px 12px 0 0; /* match container rounding */
            }}
            
            .chat-history-header:hover {{
                background: linear-gradient(135deg, #f0f9f9 0%, #f8fffe 100%);
            }}
            
            .chat-history-title {{
                font-weight: 600;
                color: #2b5556;
                font-size: 0.95rem;
                display: flex;
                align-items: center;
                gap: 6px;
            }}
            
            .chat-history-toggle {{
                color: #198484;
                font-size: 1.4rem;
                transition: transform 0.3s ease;
                /* Arrow points downward (expanded state) */
                transform: rotate(180deg);
            }}
            
            /* Arrow points right when collapsed */
            .chat-history-toggle.collapsed {{
                transform: rotate(90deg);
            }}
            
            .chat-history-content {{
                max-height: 300px;
                overflow-y: auto;
                padding: 0;
                background: #fafbfc;
                border-radius: 0 0 12px 12px; /* match container rounding */
            }}
            
            .chat-history-content::-webkit-scrollbar {{
                width: 8px;
            }}
            
            .chat-history-content::-webkit-scrollbar-track {{
                background: #f1f1f1;
                border-radius: 4px;
            }}
            
            .chat-history-content::-webkit-scrollbar-thumb {{
                background: linear-gradient(135deg, #198484 0%, #16a6a6 100%);
                border-radius: 4px;
            }}
            
            .chat-history-content::-webkit-scrollbar-thumb:hover {{
                background: linear-gradient(135deg, #16a6a6 0%, #198484 100%);
            }}
            
            .chat-message {{
                padding: 6px 30px;             /* tighter vertical padding */
                border-bottom: 1px solid rgba(25, 132, 132, 0.05);
            }}
            
            .chat-message:last-child {{
                border-bottom: none;
            }}
            
            .chat-message.user {{
                background: linear-gradient(135deg, #f0f9f9 0%, #f8fffe 100%);
            }}
            
            .chat-message.assistant {{
                background: white;
            }}
            
            .message-role {{
                font-weight: 600;
                font-size: 0.85rem;
                margin-bottom: 4px;
            }}
            
            .message-role.user {{
                color: #198484;
            }}
            
            .message-role.assistant {{
                color: #2b5556;
            }}
            
            .message-content {{
                font-size: 0.9rem;
                line-height: 1.5;
                color: #4a5568;
                white-space: normal;  /* prevent extra line breaks from trailing \n */
                word-wrap: break-word;
            }}

            /* Reduce Markdown element spacing inside chat history */
            .message-content h1,
            .message-content h2,
            .message-content h3,
            .message-content h4,
            .message-content h5,
            .message-content h6 {{
                margin: 4px 0;
            }}

            .message-content p {{
                margin: 4px 0;
            }}

            .message-content ul,
            .message-content ol {{
                margin: 4px 0 4px 20px; /* tighten vertical gap, maintain indentation */
                padding-left: 18px;
            }}

            .message-content li {{
                margin: 2px 0;
            }}
            
            .no-history {{
                padding: 30px;
                text-align: center;
                color: #718096;
                font-size: 0.9rem;
            }}
            
            /* Collapsed state */
            .chat-history-container.collapsed {{
                max-height: 48px;
            }}
            
            .chat-history-container.expanded {{
                max-height: 348px; /* header (48px) + content (300px) */
            }}
            
            /* Responsive design */
            @media (max-width: 768px) {{
                .sessions-sidebar {{
                    display: none;
                }}
                
                .content-area {{
                    width: 100%;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="session-info">
                <span class="session-info-highlight">🌍 Country:</span> {country} | 
                <span class="session-info-highlight">💼 Service Type:</span> {service_type}
                <a href="/proceed-to-chat" style="margin-left: 20px; color: #198484; text-decoration: none;">← New Session</a>
            </div>
            
            <div class="main-content">
                <div class="sessions-sidebar" id="sessionsSidebar">
                    <div class="sessions-header">
                        <div class="sessions-title">Your Sessions</div>
                        <div class="sessions-subtitle">Click to switch between chats</div>
                        <button class="toggle-sidebar" onclick="toggleSidebar()">
                            <span class="toggle-icon">‹</span>
                        </button>
                    </div>
                    <div class="sessions-list">
                        {sessions_list_html}
                    </div>
                </div>
                
                <div class="content-area">
                    {history_section}
                    
                    <div class="gradio-container">
                        <iframe src="/chat-public/?session_id={session_id}&country={country}&service_type={service_type}" id="chatFrame" allow="camera; microphone; geolocation"></iframe>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Toggle sessions sidebar
            function toggleSidebar() {{
                const sidebar = document.getElementById('sessionsSidebar');
                sidebar.classList.toggle('collapsed');
            }}
            
            // Optional: Add keyboard shortcut (Ctrl/Cmd + B) to toggle sidebar
            document.addEventListener('keydown', (e) => {{
                if ((e.ctrlKey || e.metaKey) && e.key === 'b') {{
                    e.preventDefault();
                    toggleSidebar();
                }}
            }});
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

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting Growbal Intelligence FastAPI application...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page")
    print("   - /proceed-to-chat → Form submission handler")
    print("   - /chat/ → Chat interface with orchestrator")
    print("   - /chat-public/ → Public chat interface (free tier)")
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
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )