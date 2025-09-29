import os
import json
import asyncio
import re
from typing import Dict, Any, Optional, List, AsyncGenerator
import gradio as gr
from session_manager import session_manager
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

class OrchestratorAgent:
    """Orchestrator agent for tool selection and query summarization"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session_history = []  # Store session history in format compatible with gr.Chatbot
        self.mcp_client = None  # Will be initialized when needed
        self.server_params = StdioServerParameters(
            command="python",
            args=[os.path.join(os.path.dirname(__file__), "server.py")],
            env=None
        )
        
    async def update_session_history(self, session_id: str):
        """Update the session history from database
        
        Args:
            session_id: Session ID to retrieve history for
        """
        if session_id and session_id != "unknown":
            # Get history from database in Gradio format
            db_history = await session_manager.get_session_history_gradio(session_id)
            
            # Convert to ChatInterface format: [[user_msg, bot_msg], ...]
            chatbot_history = []
            for i in range(0, len(db_history), 2):
                if i + 1 < len(db_history):
                    user_msg = db_history[i].get("content", "")
                    bot_msg = db_history[i + 1].get("content", "")
                    chatbot_history.append([user_msg, bot_msg])
            
            self.session_history = chatbot_history
        else:
            self.session_history = []
        
    async def get_mcp_session(self) -> ClientSession:
        """Get or create MCP client session"""
        if self.mcp_client is None:
            self.mcp_client = await self._create_mcp_client()
        return self.mcp_client
    
    async def _create_mcp_client(self) -> ClientSession:
        """Create new MCP client session"""
        async with stdio_client(self.server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                return session
    
    async def analyze_and_route(self, message: str, session_id: str, country: str, service_type: str) -> Dict[str, Any]:
        """Analyze message and history to determine tool usage and create summary using MCP"""
        try:
            # Get conversation history from database
            history = await session_manager.get_session_history_gradio(session_id) if session_id != "unknown" else []
            
            # Convert history to format expected by MCP
            history_dicts = []
            for msg in history[-5:]:  # Last 5 messages for context
                history_dicts.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            # Use MCP server for orchestration
            async with stdio_client(self.server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # Call orchestrator_analyze tool
                    result = await session.call_tool(
                        "orchestrator_analyze",
                        arguments={
                            "message": message,
                            "country": country,
                            "service_type": service_type,
                            "history": history_dicts
                        }
                    )
                    
                    # Handle TextContent object
                    if isinstance(result.content, list) and len(result.content) > 0:
                        content = result.content[0].text if hasattr(result.content[0], 'text') else result.content[0]
                    else:
                        content = result.content.text if hasattr(result.content, 'text') else result.content
                    
                    # Parse JSON if it's a string
                    if isinstance(content, str):
                        return json.loads(content)
                    return content
                    
        except Exception as e:
            print(f"❌ Orchestrator MCP error: {e}")
            # Fallback - check message pattern to decide which tool
            message_lower = message.lower()
            
            # Check for conversational patterns
            conversational_patterns = ["hello", "hi", "hey", "thanks", "thank you", "what", "how", "why"]
            search_patterns = ["find", "search", "looking for", "need", "show me", "locate"]
            
            is_conversational = any(pattern in message_lower for pattern in conversational_patterns)
            is_search = any(pattern in message_lower for pattern in search_patterns)
            
            if is_conversational and not is_search:
                # Use conversational agent
                return {
                    "tool_needed": True,
                    "tool_name": "conversational_agent",
                    "summary": f"Conversational message: {message}",
                    "response": None
                }
            else:
                # Default to search
                return {
                    "tool_needed": True,
                    "tool_name": "search_service_providers",
                    "summary": f"Find {service_type} providers in {country}: {message}",
                    "response": None
                }

    async def generate_suggestions(self, country: str, service_type: str, session_id: str = None) -> List[str]:
        """Generate dynamic suggestions based on context and history using MCP"""
        try:
            # Get conversation history from database
            history = await session_manager.get_session_history_gradio(session_id) if session_id and session_id != "unknown" else []
            
            # Convert history to format expected by MCP
            history_dicts = []
            for msg in history[-3:]:  # Last 3 messages for context
                history_dicts.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
            
            # Use MCP server for suggestions
            async with stdio_client(self.server_params) as (read_stream, write_stream):
                async with ClientSession(read_stream, write_stream) as session:
                    await session.initialize()
                    
                    # Call generate_suggestions tool
                    result = await session.call_tool(
                        "generate_suggestions",
                        arguments={
                            "country": country,
                            "service_type": service_type,
                            "session_history": history_dicts
                        }
                    )
                    
                    # Handle TextContent object
                    if isinstance(result.content, list) and len(result.content) > 0:
                        content = result.content[0].text if hasattr(result.content[0], 'text') else result.content[0]
                    else:
                        content = result.content.text if hasattr(result.content, 'text') else result.content
                    
                    # Parse JSON if it's a string
                    if isinstance(content, str):
                        suggestions = json.loads(content)
                    else:
                        suggestions = content
                    
                    # Ensure we have a list of strings
                    if isinstance(suggestions, list):
                        return suggestions[:3]
                    else:
                        raise ValueError("Invalid suggestions format from MCP")
                        
        except Exception as e:
            print(f"❌ Suggestions MCP error: {e}")
            # Fallback suggestions based on service type
            fallback_suggestions = {
                "Tax Services": [
                    f"Find tax preparers in {country}",
                    f"Compare CPA firms in {country}",
                    f"Search tax advisors in {country}"
                ],
                "Business Setup Services": [
                    f"Find business formation services in {country}",
                    f"Compare company registration services in {country}",
                    f"Search business lawyers in {country}"
                ],
                "Migration/Visa Services": [
                    f"Find immigration lawyers in {country}",
                    f"Compare visa consultants in {country}",
                    f"Search migration advisors in {country}"
                ]
            }
            return fallback_suggestions.get(service_type, [
                f"Find {service_type.lower()} providers in {country}",
                f"Compare {service_type.lower()} options in {country}",
                f"Search professional services in {country}"
            ])

def extract_final_result(chunk: str) -> Optional[str]:
    """Extract the final result from streaming chunks, filtering out agentic updates"""
    # Look for final summary patterns
    final_patterns = [
        r'## Final Summary.*?(?=\n\n|\Z)',
        r'## Summary.*?(?=\n\n|\Z)',
        r'Based on.*?(?=\n\n|\Z)',
        r'Here are.*?(?=\n\n|\Z)',
        r'I found.*?(?=\n\n|\Z)',
    ]
    
    for pattern in final_patterns:
        match = re.search(pattern, chunk, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(0).strip()
    
    # If no specific pattern found, check if it's a substantial response (not just status updates)
    if len(chunk) > 100 and not any(keyword in chunk.lower() for keyword in [
        'searching', 'analyzing', 'processing', 'formulating', 'executing',
        'strategy', 'progress', 'found profiles', 'complete'
    ]):
        return chunk.strip()
    
    return None

def is_status_update(chunk: str) -> bool:
    """Check if chunk is a status update that should be shown temporarily"""
    status_keywords = [
        'searching', 'analyzing', 'processing', 'formulating', 'executing',
        'strategy', 'progress', 'found profiles', 'complete', 'step'
    ]
    
    chunk_lower = chunk.lower()
    return any(keyword in chunk_lower for keyword in status_keywords)

async def call_conversational_agent(orchestrator: OrchestratorAgent, message: str, country: str, service_type: str, session_id: str = None, session_history: list = None):
    """Call the conversational agent using MCP server"""
    try:
        # Use provided session history or fetch from database
        if session_history is None:
            history = await session_manager.get_session_history_gradio(session_id) if session_id and session_id != "unknown" else []
        else:
            # Convert session history format to gradio format
            history = []
            for user_msg, assistant_msg in session_history[-3:]:  # Last 3 exchanges
                if user_msg:
                    history.append({"role": "user", "content": user_msg})
                if assistant_msg:
                    history.append({"role": "assistant", "content": assistant_msg})
        
        # Format history for the agent
        history_text = ""
        for msg in history:
            role = "User" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            # Clean content of any emoji prefixes
            clean_content = content.replace("💬 ", "").replace("🧠 **Orchestrator Analysis**: ", "")
            history_text += f"{role}: {clean_content}\n"
        
        # Use MCP server for conversational agent
        async with stdio_client(orchestrator.server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # Call conversational_agent tool
                result = await session.call_tool(
                    "conversational_agent",
                    arguments={
                        "message": message,
                        "country": country,
                        "service_type": service_type,
                        "history": history_text
                    }
                )
                
                # Handle TextContent object
                if isinstance(result.content, list) and len(result.content) > 0:
                    content = result.content[0].text if hasattr(result.content[0], 'text') else result.content[0]
                else:
                    content = result.content.text if hasattr(result.content, 'text') else result.content
                
                return str(content)
                
    except Exception as e:
        print(f"❌ Conversational agent MCP error: {e}")
        # Fallback responses
        message_lower = message.lower()
        if any(greeting in message_lower for greeting in ["hello", "hi", "hey"]):
            return f"Hello! I'm here to help you find {service_type.lower()} providers in {country}. What specific services are you looking for?"
        elif any(thanks in message_lower for thanks in ["thank", "thanks"]):
            return "You're welcome! Let me know if you need help finding any other service providers."
        else:
            return f"I can help you search for {service_type.lower()} providers in {country}. Just tell me what specific services you need."


async def call_mcp_tool_streaming_clean(orchestrator: OrchestratorAgent, tool_name: str, message: str, system_prompt: str) -> AsyncGenerator[tuple[str, str], None]:
    """Call MCP server tool and stream results with clean status updates"""
    try:
        final_result = ""
        current_status = ""
        
        # Use MCP server for streaming search
        async with stdio_client(orchestrator.server_params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                
                # Get available tools to check if streaming version exists
                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                
                # Use streaming version if available
                if "search_service_providers_streaming" in tool_names:
                    # Call streaming version
                    result = await session.call_tool(
                        "search_service_providers_streaming",
                        arguments={
                            "message": message,
                            "system_prompt": system_prompt
                        }
                    )
                    
                    # Process streaming responses
                    if hasattr(result, 'content'):
                        # Handle TextContent object
                        if isinstance(result.content, list) and len(result.content) > 0:
                            content_str = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                        else:
                            content_str = result.content.text if hasattr(result.content, 'text') else str(result.content)
                        
                        try:
                            responses = json.loads(content_str)
                            if isinstance(responses, list):
                                # Process each response in order
                                for response_dict in responses:
                                    chunk = response_dict.get("response", "")
                                    status = response_dict.get("status", "processing")
                                    
                                    # Handle different status types
                                    if status == "processing":
                                        # This is a status update or intermediate response
                                        if is_status_update(chunk):
                                            current_status = chunk
                                            yield ("status", current_status)
                                        else:
                                            # Check if this contains final result
                                            final_chunk = extract_final_result(chunk)
                                            if final_chunk:
                                                final_result = final_chunk  # Replace, don't append for final results
                                                yield ("final", final_result)
                                            elif len(chunk) > 50:  # Substantial content that's not a status
                                                final_result = chunk  # Replace, don't append
                                                yield ("final", final_result)
                                    elif status in ["success", "no_results"]:
                                        # This is the final successful result
                                        final_result = chunk
                                        yield ("final", final_result)
                                    elif status in ["error", "cancelled"]:
                                        # This is an error or cancellation
                                        yield ("error", chunk)
                                    elif status == "retrying":
                                        # This is a retry status
                                        yield ("status", chunk)
                        except json.JSONDecodeError as e:
                            print(f"❌ Error parsing streaming response: {e}")
                            yield ("error", "Error processing search results")
                else:
                    # Fallback to non-streaming version
                    result = await session.call_tool(
                        "search_service_providers",
                        arguments={
                            "message": message,
                            "system_prompt": system_prompt
                        }
                    )
                    
                    # Handle TextContent object and return the full result as final
                    if isinstance(result.content, list) and len(result.content) > 0:
                        content = result.content[0].text if hasattr(result.content[0], 'text') else str(result.content[0])
                    else:
                        content = result.content.text if hasattr(result.content, 'text') else str(result.content)
                    yield ("final", content)
                        
    except Exception as e:
        print(f"❌ Streaming MCP tool call error: {e}")
        import traceback
        traceback.print_exc()
        yield ("error", f"Error calling search tool: {str(e)}")

def create_orchestrator_chat_interface(orchestrator: OrchestratorAgent):
    """Create chat interface with orchestrator and dynamic suggestions"""
    
    # Session-specific context storage (isolated per tab)
    session_contexts = {}
    
    async def get_dynamic_suggestions(country: str, service_type: str, session_id: str = None) -> List[str]:
        """Get dynamic suggestions from orchestrator"""
        try:
            suggestions = await orchestrator.generate_suggestions(country, service_type, session_id)
            return suggestions
        except Exception as e:
            print(f"❌ Error generating suggestions: {e}")
            # Fallback suggestions
            return [
                f"Find providers in {country}",
                f"Compare {service_type.lower()} options",
                f"Search professional services"
            ]
    
    def orchestrator_chat_wrapper(message: str, history: list, request: gr.Request):
        print(f"request: {request.query_params}")
        """Orchestrator-enabled chat wrapper with dynamic suggestions and history loading"""
        session_id = "unknown"
        country = "unknown"
        service_type = "unknown"
                
        # Extract parameters
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
        
        # Run async function to get session data and history with proper event loop handling
        def run_async_safely(coro):
            """Safely run async function, handling multiple tabs"""
            try:
                # Try to get existing event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running (common in Gradio), use asyncio.run_coroutine_threadsafe
                    import concurrent.futures
                    import threading
                    
                    def run_in_thread():
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        try:
                            return new_loop.run_until_complete(coro)
                        finally:
                            new_loop.close()
                    
                    with concurrent.futures.ThreadPoolExecutor() as executor:
                        future = executor.submit(run_in_thread)
                        return future.result(timeout=30)  # 30 second timeout
                else:
                    return loop.run_until_complete(coro)
            except RuntimeError:
                # No event loop exists, create a new one
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(coro)
                finally:
                    loop.close()
        
        # Load session history for context
        async def load_session_history():
            """Load session history from database"""
            if session_id != "unknown":
                await orchestrator.update_session_history(session_id)
                return orchestrator.session_history
            return []
        
        # Get the session history
        session_history = run_async_safely(load_session_history())
        
        # Update session-specific context (isolated per session)
        session_contexts[session_id] = {
            "country": country,
            "service_type": service_type,
            "session_id": session_id,
            "history": session_history
        }
        
        print(f"🎯 Final parameters: Session={session_id}, Country={country}, Service Type={service_type}, History items={len(session_history)}")
        
        # Orchestrator coordination with clean streaming
        async def orchestrator_response():
            final_assistant_response = ""  # Track the complete assistant response
            
            try:
                # Store user message immediately
                if session_id != "unknown":
                    try:
                        await session_manager.add_message(session_id, "user", message)
                    except Exception as db_error:
                        print(f"❌ Error storing user message: {db_error}")
                
                # Analyze message and determine routing with session history
                analysis = await orchestrator.analyze_and_route(message, session_id, country, service_type)
                
                if analysis.get("tool_needed", False):
                    tool_name = analysis.get("tool_name", "search_service_providers")
                    
                    if tool_name == "conversational_agent":
                        # Handle conversational messages with session history
                        response = await call_conversational_agent(orchestrator, message, country, service_type, session_id, session_history)
                        final_assistant_response = f"💬 {response}"
                        yield final_assistant_response
                        
                    else:  # search_service_providers
                        # Show orchestrator analysis first
                        orchestrator_message = f"🧠 **Orchestrator Analysis**: {analysis.get('summary', message)}"
                        
                        # Format session history for context
                        history_context = ""
                        if session_history and len(session_history) > 0:
                            history_context = "\n\nPREVIOUS CONVERSATION HISTORY:\n"
                            for user_msg, assistant_msg in session_history[-5:]:  # Last 5 exchanges
                                if user_msg:
                                    history_context += f"User: {user_msg}\n"
                                if assistant_msg:
                                    # Clean assistant message of any emoji prefixes
                                    clean_msg = assistant_msg.replace("💬 ", "").replace("🧠 **Orchestrator Analysis**: ", "")
                                    history_context += f"Assistant: {clean_msg}\n"
                            history_context += "\nBased on this conversation history, please provide contextually relevant results.\n"
                        
                        # Create system prompt for streaming tool with history context
                        system_prompt = f"""CRITICAL INSTRUCTIONS:
1. Search ONLY for providers in {country}
2. Search ONLY for {service_type} providers  
3. Query: {analysis.get('summary', message)}{history_context}"""
                        
                        # Track final result
                        final_result = orchestrator_message + "\n\n"
                        
                        # Stream results from the search agent
                        search_agent_final_output = ""  # Track only the search agent's final output
                        async for result_type, content in call_mcp_tool_streaming_clean(
                            orchestrator,
                            tool_name,
                            analysis.get("summary", message),
                            system_prompt
                        ):
                            if result_type == "status":
                                # Show current status temporarily
                                yield orchestrator_message + "\n\n" + content
                            elif result_type == "final":
                                # Update final result and capture search agent output
                                final_result = orchestrator_message + "\n\n" + content
                                search_agent_final_output = content  # Store only the search agent's output
                                final_assistant_response = final_result
                                yield final_result
                            elif result_type == "error":
                                error_response = orchestrator_message + "\n\n" + content
                                search_agent_final_output = content  # Store error as final output
                                final_assistant_response = error_response
                                yield error_response
                        
                        # Use search agent's final output for session storage if available
                        if search_agent_final_output:
                            final_assistant_response = search_agent_final_output
                    
                else:
                    # Direct response without tool (shouldn't happen with updated orchestrator)
                    response = f"💬 {analysis.get('response', 'I can help you find service providers. Please let me know what you need.')}"
                    final_assistant_response = response
                    yield response
                
                # Store assistant response in database
                if session_id != "unknown" and final_assistant_response:
                    try:
                        await session_manager.add_message(session_id, "assistant", final_assistant_response)
                    except Exception as db_error:
                        print(f"❌ Error storing assistant message: {db_error}")
                    
            except Exception as e:
                error_msg = f"❌ Error: {str(e)}"
                print(f"❌ Orchestrator error: {e}")
                yield error_msg
                
                # Store error message as assistant response
                if session_id != "unknown":
                    try:
                        await session_manager.add_message(session_id, "assistant", error_msg)
                    except Exception as db_error:
                        print(f"❌ Error storing error message: {db_error}")
        
        # Run orchestrator with clean streaming using safe async pattern
        gen = orchestrator_response()
        last_response = ""
        try:
            while True:
                response = run_async_safely(gen.__anext__())
                last_response = response  # Don't accumulate, just update
                yield response
        except StopAsyncIteration:
            pass
        
        return last_response
    
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
    
    /* Badge Styling */
    .orchestrator-badge {
        background: #ff6b6b !important;
        color: white !important;
        padding: 2px 6px !important;
        border-radius: 4px !important;
        font-size: 0.7rem !important;
        margin-left: 8px !important;
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
    
    # Function to generate initial suggestions (fallback to static for startup)
    def get_initial_suggestions():
        # Return static suggestions for startup to avoid event loop issues
        # Dynamic suggestions will be generated during conversation
        return [
            "Find providers in your selected country",
            "Compare service options and pricing",
            "Search for specialized professionals"
        ]
    
    # # Create chat interface - we'll handle history loading in the wrapper function
    # history_pairs = orchestrator.session_history if hasattr(orchestrator, 'session_history') else []
    # print(f"history_pairs: {history_pairs}")
    # chatbot_comp = gr.Chatbot(value=[["hello", "world"]])
    
    interface = gr.ChatInterface(
        fn=orchestrator_chat_wrapper,
        # chatbot=chatbot_comp,
        title=f"{logo_html}<div class='app-header'><h1 class='app-title'>Growbal Intelligence</h1><p class='app-description'>AI-powered service provider search</p></div>",
        examples=get_initial_suggestions(),
        cache_examples=False,
        theme=custom_theme,
        css=css,
        textbox=gr.Textbox(
            placeholder="Ask me anything - I'll route to the right agent...",
            container=False,
            scale=7,
            lines=1
        ),
        submit_btn=gr.Button("Send", variant="primary"),
        retry_btn=None,
        undo_btn=None,
        clear_btn=gr.Button("Clear Chat", variant="stop"),
        multimodal=False,
        concurrency_limit=3,
        fill_height=True
    )
    
    return interface