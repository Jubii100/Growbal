import os
import json
import asyncio
import re
from typing import Dict, Any, Optional, List
import gradio as gr
from session_manager import session_manager

class OrchestratorAgent:
    """Orchestrator agent for tool selection and query summarization"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session_history = []  # Store session history in format compatible with gr.Chatbot
        
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
        
    async def analyze_and_route(self, message: str, session_id: str, country: str, service_type: str) -> Dict[str, Any]:
        """Analyze message and history to determine tool usage and create summary"""
        import anthropic
        
        client = anthropic.Anthropic(api_key=self.api_key)
        
        # Get conversation history from database
        history = await session_manager.get_session_history_gradio(session_id) if session_id != "unknown" else []
        
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
   - Use for:
      - explicit search requests to find service providers and services, or professionals
   Parameters: message (search query from user), system_prompt (filtering criteria from system)

2. conversational_agent - Handle general conversation, greetings, questions that are not supported by other tools, and responds to unsupported requests (e.g. "I'm sorry, I don't understand that request.")
   - Use for:
      - greetings 
      - friendly conversation wrapup/closing
      - Ambiguous/unintelligible requests or incomplete requests (ask for clarifications or ask for more information if missing the required parameters for other tools)
      - other questions/general chats/requests that are not supported by other tools and could be answered from the chat history (if it can't be answered from the chat history, then appologize and say you can't help)
   - Parameters: message, country, service_type, history

User Context:
- Country: {country}
- Service Type: {service_type}

Recent Conversation History:
{history_text}

Current Message: {message}

Analyze this request and provide a JSON response with:
{{
  "tool_needed": true/false,
  "tool_name": "search_service_providers" or "conversational_agent" or null,
  "summary": "concise summary of what user is looking for or saying",
  "response": "only used if tool_needed is false"
}}

Guidelines:
- Only set tool_needed to false if you're absolutely certain no tool is appropriate
- Summary should be brief (1-2 sentences) describing the user's intent"""

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

#     async def generate_suggestions(self, country: str, service_type: str, session_id: str = None) -> List[str]:
#         """Generate dynamic suggestions based on context and history"""
#         import anthropic
        
#         client = anthropic.Anthropic(api_key=self.api_key)
        
#         # Get conversation history from database
#         history = await session_manager.get_session_history_gradio(session_id) if session_id and session_id != "unknown" else []
        
#         # Format conversation history
#         history_text = ""
#         for msg in history[-3:]:  # Last 3 messages for context
#             role = "User" if msg.get("role") == "user" else "Assistant"
#             content = msg.get("content", "")
#             history_text += f"{role}: {content}\n"
        
#         # Create suggestions prompt
#         suggestions_prompt = f"""You are generating helpful search suggestions for a service provider search system.

# Context:
# - Country: {country}
# - Service Type: {service_type}
# - Recent Conversation: {history_text}

# Generate exactly 3 concise, actionable search suggestions that would be helpful for someone looking for {service_type} providers in {country}.

# Requirements:
# - NO emojis or icons
# - Each suggestion should be 5-12 words and plausibly a subset of the service type and country
# - If there's conversation history, make suggestions that build on or complement what was discussed
# - Focus on practical, specific searches users might want to make

# Format as a JSON array of exactly 3 strings:
# ["suggestion 1", "suggestion 2", "suggestion 3"]

# Examples for different contexts:
# - For Tax Services in USA: ["Find tax preparers for small businesses", "Compare CPA firms for individuals", "Search tax advisors with IRS experience"]
# - For Migration Services in Canada: ["Find immigration lawyers for work permits", "Search consultants for permanent residency", "Compare services for family sponsorship"]
# - For Business Setup in UAE: ["Find accountants for limited company formation in Dubai", "Search lawyers for business registration in Abu Dhabi", "Compare consultants for VAT registration"]
# """

        try:
            response = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=200,
                messages=[{"role": "user", "content": suggestions_prompt}]
            )
            
            # Get the response text
            response_text = response.content[0].text.strip()
            print(f"🔍 Raw suggestions response: {response_text}")
            
            # Try to extract JSON from response
            try:
                # Look for JSON array pattern
                import re
                json_match = re.search(r'\[.*?\]', response_text, re.DOTALL)
                if json_match:
                    suggestions = json.loads(json_match.group())
                else:
                    # Try parsing the whole response
                    suggestions = json.loads(response_text)
                
                # Ensure we have exactly 3 suggestions
                if isinstance(suggestions, list) and len(suggestions) >= 3:
                    return [str(s).strip() for s in suggestions[:3]]
                else:
                    raise ValueError("Invalid suggestions format")
                    
            except (json.JSONDecodeError, ValueError) as json_error:
                print(f"❌ JSON parsing error: {json_error}")
                print(f"❌ Response text: {response_text}")
                raise json_error
                
        except Exception as e:
            print(f"❌ Suggestions generation error: {e}")
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


async def search_agent_call(message: str, system_prompt: str):
    """Call to search agent with streaming - embedded in orchestrator"""
    try:
        from chat.chat_interface import get_search_agent_response
        
        # Stream the response directly
        async for response_dict in get_search_agent_response(message, system_prompt):
            # Extract response and status from the dictionary
            chunk = response_dict.get("response", "")
            status = response_dict.get("status", "processing")
            
            # Handle different status types
            if status == "processing":
                # This is a status update or intermediate response
                if is_status_update(chunk):
                    yield ("status", chunk)
                else:
                    # Check if this contains final result
                    final_chunk = extract_final_result(chunk)
                    if final_chunk:
                        yield ("final", final_chunk)
                    elif len(chunk) > 50:  # Substantial content that's not a status
                        yield ("final", chunk)
            elif status in ["success", "no_results"]:
                # This is the final successful result
                yield ("final", chunk)
            elif status in ["error", "cancelled"]:
                # This is an error or cancellation
                yield ("error", chunk)
            elif status == "retrying":
                # This is a retry status
                yield ("status", chunk)
                
    except Exception as e:
        print(f"❌ Search agent error: {e}")
        import traceback
        traceback.print_exc()
        yield ("error", f"Search agent error: {str(e)}")


async def conversational_agent_call(message: str, country: str, service_type: str, history_text: str, api_key: str):
    """Call to conversational agent - embedded in orchestrator"""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        # Create conversational prompt
        conversation_prompt = f"""You are a friendly assistant for Growbal Intelligence, a service provider search platform.

User Context:
- Country: {country}
- Service Type: {service_type}
- Recent History: {history_text}

User Message: {message}

Instructions:
- Provide a friendly, helpful response to the user's message
- If they're greeting you (hello, hi, etc.), welcome them warmly and briefly explain how you can help
- If they're asking what you can do, explain that you help find {service_type} providers in {country}
- If they're thanking you, respond graciously
- Keep responses concise and friendly (2-3 sentences max)
- Don't perform searches - just have a conversation
- Suggest they can ask you to find specific providers when they're ready

Response:"""

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=200,
            messages=[{"role": "user", "content": conversation_prompt}]
        )
        
        return response.content[0].text.strip()
        
    except Exception as e:
        print(f"❌ Conversational agent error: {e}")
        import traceback
        traceback.print_exc()
        
        # Fallback responses based on common patterns
        message_lower = message.lower()
        
        if any(greeting in message_lower for greeting in ["hello", "hi", "hey"]):
            return f"Hello! I'm here to help you find {service_type.lower()} providers in {country}. What specific services are you looking for?"
        elif any(thanks in message_lower for thanks in ["thank", "thanks"]):
            return "You're welcome! Let me know if you need help finding any other service providers."
        elif "what" in message_lower or "how" in message_lower:
            return f"I can help you search for {service_type.lower()} providers in {country}. Just tell me what specific services you need, and I'll find the best options for you."
        else:
            return f"I'm here to help you find {service_type.lower()} providers in {country}. What would you like to know?"




async def call_tool_streaming(tool_name: str, message: str, system_prompt: str, orchestrator: OrchestratorAgent = None, country: str = None, service_type: str = None, session_id: str = None, session_history: list = None):
    """Call tools through embedded orchestrator methods"""
    try:
        if tool_name == "conversational_agent":
            # Handle conversational agent with direct call
            if not orchestrator:
                yield ("error", "Orchestrator instance required for conversational agent")
                return
            
            # Format history text from session history
            history_text = ""
            if session_history:
                for user_msg, assistant_msg in session_history[-3:]:  # Last 3 exchanges
                    if user_msg:
                        history_text += f"User: {user_msg}\n"
                    if assistant_msg:
                        # Clean assistant message of any emoji prefixes
                        clean_msg = assistant_msg.replace("**Request Analysis**: ", "")
                        history_text += f"Assistant: {clean_msg}\n"
            
            try:
                # Call conversational agent method
                response = await conversational_agent_call(
                    message=message,
                    country=country,
                    service_type=service_type,
                    history_text=history_text,
                    api_key=orchestrator.api_key
                )
                
                # Yield the final response in streaming format
                yield ("final", response)
                return
                        
            except Exception as e:
                print(f"❌ Conversational agent error: {e}")
                yield ("error", str(e))
            
        elif tool_name == "search_service_providers":
            # Handle search service providers with streaming call
            async for result in search_agent_call(message, system_prompt):
                yield result
                
        else:
            # Unknown tool name
            yield ("error", f"Unknown tool name: {tool_name}")
            
    except Exception as e:
        print(f"❌ Tool call error: {e}")
        import traceback
        traceback.print_exc()
        yield ("error", f"Error calling {tool_name} tool: {str(e)}")

def create_orchestrator_chat_interface(orchestrator: OrchestratorAgent):
    """Create chat interface with orchestrator and dynamic suggestions"""
    
    # Session-specific context storage (isolated per tab)
    session_contexts = {}
    
    # async def get_dynamic_suggestions(country: str, service_type: str, session_id: str = None) -> List[str]:
    #     """Get dynamic suggestions from orchestrator"""
    #     try:
    #         suggestions = await orchestrator.generate_suggestions(country, service_type, session_id)
    #         return suggestions
    #     except Exception as e:
    #         print(f"❌ Error generating suggestions: {e}")
    #         # Fallback suggestions
    #         return [
    #             f"Find providers in {country}",
    #             f"Compare {service_type.lower()} options",
    #             f"Search professional services"
    #         ]
    
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
        async def orchestrator_response(message: str):
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
                        # Handle conversational messages with session history using unified streaming
                        async for result_type, content in call_tool_streaming(
                            tool_name,
                            message,
                            "",  # No system prompt needed for conversational agent
                            orchestrator,
                            country,
                            service_type,
                            session_id,
                            session_history
                        ):
                            if result_type == "final":
                                final_assistant_response = content
                                yield final_assistant_response
                            elif result_type == "error":
                                error_response = content
                                final_assistant_response = error_response
                                yield error_response
                        
                    else:  # search_service_providers
                        # Show orchestrator analysis first
                        orchestrator_message = f"**Request Analysis**: {analysis.get('summary', message)}"
                        
                        # Format session history for context
                        history_context = ""
                        if session_history and len(session_history) > 0:
                            history_context = "\n\nPREVIOUS CONVERSATION HISTORY:\n"
                            for user_msg, assistant_msg in session_history[-5:]:  # Last 5 exchanges
                                if user_msg:
                                    history_context += f"User: {user_msg}\n"
                                if assistant_msg:
                                    # Clean assistant message of any emoji prefixes
                                    clean_msg = assistant_msg.replace("**Request Analysis**: ", "")
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
                        async for result_type, content in call_tool_streaming(
                            tool_name,
                            analysis.get("summary", message),
                            system_prompt,
                            orchestrator,
                            country,
                            service_type,
                            session_id,
                            session_history
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
                    response = analysis.get('response', 'I can help you find service providers. Please let me know what you need.')
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
        gen = orchestrator_response(message)
        last_response = ""
        try:
            while True:
                response = run_async_safely(gen.__anext__())
                last_response = response  # Don't accumulate, just update
                yield response
        except StopAsyncIteration:
            pass
        
        return last_response
    
    # # Read the logo file
    # logo_path = os.path.join(os.path.dirname(__file__), "growbal_logoheader.svg")
    # logo_html = ""
    # if os.path.exists(logo_path):
    #     with open(logo_path, 'r') as f:
    #         logo_content = f.read()
    #         logo_html = f"""
    #         <div style="display: flex; justify-content: center; align-items: center; padding: 10px 0; background: #ffffff; margin-bottom: 10px; border-radius: 15px; box-shadow: 0 8px 32px rgba(43, 85, 86, 0.15);">
    #             <div style="max-width: 200px; height: auto;">
    #                 {logo_content}
    #             </div>
    #         </div>
    #         """
    
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
        title="<div class='app-header'><h1 class='app-title'>Growbal Intelligence</h1><p class='app-description'>AI-powered service provider search</p></div>",
        # examples=get_initial_suggestions(),
        # cache_examples=False,
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