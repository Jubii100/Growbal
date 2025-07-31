"""
ORCHESTRATOR-ENABLED FastAPI application with MCP Integration
- Uses orchestrator agent to coordinate tool selection
- Integrates with MCP server for service provider search
- Maintains all existing functionality from main_app_4.py
"""

import os
import sys
import uuid
import time
import json
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, Request, HTTPException, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
import gradio as gr
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load environment variables
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, 'envs', '1.env')
load_dotenv(env_path)

# Add the project root to the path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Global storage for session management
session_store: Dict[str, Dict[str, Any]] = {}

# MCP Server Configuration
server_params = StdioServerParameters(
    command="python",
    args=[os.path.join(os.path.dirname(__file__), "server.py")],
    env=None
)

# Create FastAPI app
app = FastAPI(
    title="Growbal Intelligence Platform - Orchestrator",
    description="AI-powered service provider search with orchestrator and MCP integration",
    version="5.0.0"
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

# Import API key for orchestrator
api_key = os.getenv('ANTHROPIC_API_KEY')
if not api_key:
    print("⚠️  WARNING: ANTHROPIC_API_KEY not found in environment!")
    sys.exit(1)

class OrchestratorAgent:
    """Orchestrator agent for tool selection and query summarization"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    async def analyze_and_route(self, message: str, history: List[Dict], country: str, service_type: str) -> Dict[str, Any]:
        """Analyze message and history to determine tool usage and create summary"""
        import anthropic
        
        client = anthropic.Anthropic(api_key=self.api_key)
        
        # Format conversation history
        history_text = ""
        for msg in history[-5:]:  # Last 5 messages for context
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            history_text += f"{role}: {content}\n"
        
        # Create analysis prompt
        analysis_prompt = f"""You are an orchestrator agent for a service provider search system.

Available Tools:
1. search_service_providers - Search for service providers with country/service filtering
   - Use when user wants to find providers, companies, services, or professionals
   - Parameters: message (search query), system_prompt (filtering criteria)

User Context:
- Country: {country}
- Service Type: {service_type}

Recent Conversation History:
{history_text}

Current Message: {message}

Analyze this request and provide a JSON response with:
{{
  "tool_needed": true/false,
  "tool_name": "search_service_providers" or null,
  "summary": "concise summary of what user is looking for",
  "response": "direct response if no tool needed or for conversational messages"
}}

Guidelines:
- Don't use tools for: greetings, thank you, clarifications, general questions
- Summary should be brief (1-2 sentences) combining current message with relevant history
- For conversational messages, provide helpful response directly"""

        try:
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=300,
                messages=[{"role": "user", "content": analysis_prompt}]
            )
            
            # Parse JSON response
            result = json.loads(response.content[0].text)
            return result
            
        except Exception as e:
            print(f"❌ Orchestrator error: {e}")
            # Fallback - assume search needed
            return {
                "tool_needed": True,
                "tool_name": "search_service_providers",
                "summary": f"Find {service_type} providers in {country}: {message}",
                "response": None
            }

# Initialize orchestrator
orchestrator = OrchestratorAgent(api_key)

async def call_mcp_tool_streaming(tool_name: str, message: str, system_prompt: str):
    """Call MCP server tool and stream results in real-time"""
    try:
        # Import the streaming function directly instead of using MCP
        from chat.chat_interface import get_search_agent_response
        
        # Stream the response directly
        async for chunk in get_search_agent_response(message, system_prompt):
            yield chunk
            
    except Exception as e:
        print(f"❌ Streaming tool call error: {e}")
        import traceback
        traceback.print_exc()
        yield f"Error calling search tool: {str(e)}"

# Copy all existing endpoints from main_app_4.py
@app.get("/", response_class=HTMLResponse)
async def root():
    """Root endpoint that redirects to country selection"""
    return RedirectResponse(url="/country/")

@app.get("/country/", response_class=HTMLResponse)
async def country_selection_page():
    """Serve country selection page - same as main_app_4.py"""
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
                <h1 class="app-title">Growbal Intelligence <span class="orchestrator-badge">v5.0 + MCP</span></h1>
                <p class="app-description">AI-powered service provider search with orchestrator agent</p>
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
    
    # SERVER-SIDE REDIRECT using query parameters
    redirect_url = f"/chat/?session_id={session_id}&country={country}&service_type={service_type}"
    return RedirectResponse(url=redirect_url, status_code=303)

@app.get("/chat/", response_class=HTMLResponse)
async def chat_interface_page(request: Request, session_id: str = None, country: str = None, service_type: str = None):
    """Serve the chat interface page with orchestrator integration"""
    
    # Verify session exists
    if session_id not in session_store:
        session_store[session_id] = {
            "country": country,
            "service_type": service_type,
            "created_at": time.time(),
            "active": True,
            "last_activity": time.time()
        }
    
    # Update session
    session_store[session_id]["last_activity"] = time.time()
    
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
                <span class="orchestrator-badge">ORCHESTRATOR</span>
                <a href="/country/" style="margin-left: 20px; color: #198484; text-decoration: none;">← Back to Country Selection</a>
            </div>
            <div class="gradio-container">
                <iframe src="/chat-gradio/?session_id={session_id}&country={country}&service_type={service_type}" id="chatFrame" allow="camera; microphone; geolocation"></iframe>
            </div>
        </div>
        
        <script>
            console.log('✅ Orchestrator Chat interface loaded with:');
            console.log('  Session ID: {session_id}');
            console.log('  Country: {country}');
            console.log('  Service Type: {service_type}');
            console.log('  URL: ' + window.location.href);
        </script>
    </body>
    </html>
    """

def create_orchestrator_chat_interface():
    """Create chat interface with orchestrator and MCP integration"""
    
    def orchestrator_chat_wrapper(message: str, history: list, request: gr.Request):
        """Orchestrator-enabled chat wrapper"""
        session_id = "unknown"
        country = "unknown"
        service_type = "unknown"
        
        print(f"🧠 Orchestrator chat wrapper called with message: {message}")
        
        # Extract parameters (same as main_app_4.py)
        if request and hasattr(request, 'query_params'):
            query_params = dict(request.query_params)
            session_id = query_params.get('session_id', session_id)
            country = query_params.get('country', country)
            service_type = query_params.get('service_type', service_type)
        
        if (session_id == "unknown" or country == "unknown" or service_type == "unknown") and request:
            try:
                fastapi_request = request.request if hasattr(request, 'request') else request
                if hasattr(fastapi_request, 'session'):
                    session_id = fastapi_request.session.get('session_id', session_id)
                    country = fastapi_request.session.get('country', country)
                    service_type = fastapi_request.session.get('service_type', service_type)
            except Exception as e:
                print(f"❌ [FastAPI Session] Error: {e}")
        
        if session_id != "unknown" and session_id in session_store:
            country = session_store[session_id].get("country", country)
            service_type = session_store[session_id].get("service_type", service_type)
        
        print(f"🎯 Final parameters: Session={session_id}, Country={country}, Service Type={service_type}")
        
        # Orchestrator coordination
        async def orchestrator_response():
            try:
                # Analyze message and determine routing
                analysis = await orchestrator.analyze_and_route(message, history, country, service_type)
                
                if analysis.get("tool_needed", False):
                    # Show orchestrator analysis first
                    yield f"🧠 **Orchestrator Analysis**: {analysis.get('summary', message)}\n\n"
                    
                    # Create system prompt for streaming tool
                    system_prompt = f"""CRITICAL INSTRUCTIONS:
1. Search ONLY for providers in {country}
2. Search ONLY for {service_type} providers  
3. Query: {analysis.get('summary', message)}"""
                    
                    # Stream results from the search agent
                    async for chunk in call_mcp_tool_streaming(
                        analysis.get("tool_name", "search_service_providers"),
                        analysis.get("summary", message),
                        system_prompt
                    ):
                        yield chunk
                    
                else:
                    # Direct response without tool
                    yield f"💬 {analysis.get('response', 'I can help you find service providers. Please let me know what you need.')}"
                    
            except Exception as e:
                print(f"❌ Orchestrator error: {e}")
                yield f"❌ Error: {str(e)}"
        
        # Run orchestrator with streaming
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        gen = orchestrator_response()
        last_response = ""
        try:
            while True:
                chunk = loop.run_until_complete(gen.__anext__())
                last_response += chunk
                yield last_response  # Yield accumulated response for real-time updates
        except StopAsyncIteration:
            pass
        
        return last_response
    
    # Same styling as main_app_4.py but with orchestrator branding
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
    
    css = """
    /* Same CSS as main_app_4.py */
    .gradio-container {
        max-width: 1400px !important;
        margin: 0 auto !important;
        background: linear-gradient(135deg, #f8fffe 0%, #f0f9f9 100%) !important;
        padding: 20px !important;
        border-radius: 20px !important;
        box-shadow: 0 10px 50px rgba(25, 132, 132, 0.1) !important;
    }
    
    .chatbot {
        height: 750px !important;
        max-height: 750px !important;
    }
    
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
    
    .orchestrator-badge {
        background: #ff6b6b !important;
        color: white !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-size: 0.7rem !important;
        margin-left: 8px !important;
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
        fn=orchestrator_chat_wrapper,
        type="messages",
        title=f"{logo_html}<div class='app-header'><h1 class='app-title'>Growbal Intelligence <span class='orchestrator-badge'>ORCHESTRATOR</span></h1><p class='app-description'>AI-powered service provider search with intelligent routing</p></div>",
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
            placeholder="🧠 Ask me anything - I'll route to the right agent...",
            container=False,
            scale=7,
            lines=1
        ),
        submit_btn=gr.Button("🚀 Send", variant="primary"),
        retry_btn=None,
        undo_btn=None,
        clear_btn=gr.Button("🗑️ Clear Chat", variant="stop"),
        multimodal=False,
        concurrency_limit=3,
        fill_height=True
    )
    
    return interface

# Mount the orchestrator chat interface
print("🧠 Setting up ORCHESTRATOR chat interface with MCP integration...")
orchestrator_chat_app = create_orchestrator_chat_interface()
app = gr.mount_gradio_app(
    app,
    orchestrator_chat_app,
    path="/chat-gradio"
)
print("✅ Orchestrator chat app mounted at /chat-gradio")

# Same health check and debug endpoints as main_app_4.py
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy", 
        "service": "growbal-intelligence-orchestrator",
        "version": "5.0.0",
        "features": ["orchestrator", "mcp", "tool_routing"],
        "active_sessions": len(session_store)
    }

@app.get("/debug/sessions")
async def debug_sessions():
    """Debug endpoint to show all active sessions"""
    return {
        "total_sessions": len(session_store),
        "sessions": session_store
    }

@app.get("/debug/mcp")
async def debug_mcp():
    """Debug endpoint to test MCP connection"""
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                return {
                    "status": "connected",
                    "tools": [tool.name for tool in tools.tools]
                }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

if __name__ == "__main__":
    import uvicorn
    
    print("🚀 Starting ORCHESTRATOR-ENABLED Growbal Intelligence FastAPI application...")
    print("📍 Available endpoints:")
    print("   - / → Root (redirects to country selection)")
    print("   - /country/ → Country selection page")
    print("   - /proceed-to-chat → Form submission handler")
    print("   - /chat/ → Chat interface with orchestrator")
    print("   - /chat-gradio/ → Orchestrator Gradio app")
    print("   - /health → Health check")
    print("   - /debug/sessions → Debug session information")
    print("   - /debug/mcp → Debug MCP connection")
    print()
    print("🧠 NEW ORCHESTRATOR FEATURES:")
    print("   ✅ Intelligent tool routing based on message analysis")
    print("   ✅ MCP server integration for search agents")
    print("   ✅ Conversation history awareness")
    print("   ✅ Automatic query summarization")
    print("   ✅ Fallback handling for tool failures")
    print("   ✅ Conversational responses for non-search queries")
    
    uvicorn.run(
        "main_app_5:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["."],
        log_level="info"
    )