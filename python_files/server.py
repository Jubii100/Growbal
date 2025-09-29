"""
MCP Server for Growbal Intelligence Search Agent
Provides search functionality for service providers through Model Context Protocol
"""
import asyncio
import os
import sys
from typing import AsyncGenerator, Dict, Any, List
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv
import json

# Load environment variables
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, 'envs', '1.env')
load_dotenv(env_path)

# Add project root to path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import the search agent function
from chat.chat_interface import get_search_agent_response

# Create MCP server
mcp = FastMCP("growbal-search")


@mcp.tool()
async def search_service_providers_streaming(
    message: str,
    system_prompt: str
) -> AsyncGenerator[str, None]:
    """AI Search Agent with Streaming - Searches for service providers with real-time status updates.
    
    Args:
        message: User's search query
        system_prompt: Filtering criteria for provider selection
        
    Yields:
        JSON strings with response and status fields
    """
    
    try:
        # Stream responses from the search agent
        async for response_dict in get_search_agent_response(message, system_prompt):
            # Yield each response as a JSON string
            yield json.dumps(response_dict)
        
    except Exception as e:
        print(f"❌ Server search error: {e}")
        import traceback
        traceback.print_exc()
        yield json.dumps({"response": f"Search error: {str(e)}", "status": "error"})


@mcp.tool()
async def search_service_providers(
    message: str,
    system_prompt: str
) -> str:
    """AI Search Agent - Searches for service providers matching query with system prompt filtering.
    
    Args:
        message: User's search query
        system_prompt: Filtering criteria for provider selection
        
    Returns:
        Formatted final analysis results
    """
    
    try:
        # Collect full response with proper error handling
        full_response = ""
        final_status = "processing"
        
        async for response_dict in get_search_agent_response(message, system_prompt):
            full_response = response_dict.get("response", "")
            final_status = response_dict.get("status", "processing")
            
            # Only keep the final response
            if final_status in ["success", "no_results", "error", "cancelled"]:
                break
        
        return full_response or "No results found"
        
    except Exception as e:
        print(f"❌ Server search error: {e}")
        import traceback
        traceback.print_exc()
        return f"Search error: {str(e)}"


@mcp.tool()
async def orchestrator_analyze(
    message: str,
    country: str,
    service_type: str,
    history: List[Dict[str, str]] = None
) -> Dict[str, Any]:
    """Orchestrator Agent - Analyzes messages to determine tool usage and create summaries.
    
    Args:
        message: User's message
        country: User's selected country
        service_type: User's selected service type
        history: Recent conversation history as list of dicts with 'role' and 'content'
        
    Returns:
        Dictionary with tool routing decision
    """
    
    try:
        # Get API key
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return {
                "tool_needed": False,
                "tool_name": None,
                "summary": "System unavailable",
                "response": "I apologize, but I'm unable to process requests at the moment."
            }
        
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        # Format conversation history
        history_text = ""
        if history:
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

2. conversational_agent - Handle general conversation, greetings, questions that are not supported by other tools, and responds to unsupported requests (e.g. "I'm sorry, I don't understand that request.")
   - Use for: greetings (hello, hi), thank you, general questions, system inquiries
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
- Use conversational_agent for: greetings, thank you, general questions, system inquiries
- Use search_service_providers for: explicit search requests, finding providers
- Only set tool_needed to false if you're absolutely certain no tool is appropriate
- Summary should be brief (1-2 sentences) describing the user's intent"""

        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=300,
            messages=[{"role": "user", "content": analysis_prompt}]
        )
        
        # Parse JSON response
        result = json.loads(response.content[0].text)
        return result
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parse error: {e}")
        # Fallback logic
        return fallback_orchestrator_analysis(message, country, service_type)
    except Exception as e:
        print(f"❌ Orchestrator error: {e}")
        # Fallback logic
        return fallback_orchestrator_analysis(message, country, service_type)


def fallback_orchestrator_analysis(message: str, country: str, service_type: str) -> Dict[str, Any]:
    """Fallback orchestrator logic when API fails"""
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


@mcp.tool()
async def conversational_agent(
    message: str,
    country: str,
    service_type: str,
    history: str = ""
) -> str:
    """Conversational Agent - Handles general conversation, greetings, and questions about the system.
    
    Args:
        message: User's message
        country: User's selected country for context
        service_type: User's selected service type for context
        history: Recent conversation history
        
    Returns:
        Friendly conversational response
    """
    
    try:
        # Get API key
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return "I apologize, but I'm unable to respond at the moment. Please try again later."
        
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        # Create conversational prompt
        conversation_prompt = f"""You are a friendly assistant for Growbal Intelligence, a service provider search platform.

User Context:
- Country: {country}
- Service Type: {service_type}
- Recent History: {history}

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


@mcp.tool()
async def generate_suggestions(
    country: str,
    service_type: str,
    session_history: List[Dict[str, str]] = None
) -> List[str]:
    """Generate dynamic suggestions based on context and history.
    
    Args:
        country: User's selected country
        service_type: User's selected service type
        session_history: Recent conversation history
        
    Returns:
        List of 3 suggestion strings
    """
    
    try:
        # Get API key
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if not api_key:
            return fallback_suggestions(country, service_type)
        
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        
        # Format conversation history
        history_text = ""
        if session_history:
            for msg in session_history[-3:]:  # Last 3 messages for context
                role = "User" if msg.get("role") == "user" else "Assistant"
                content = msg.get("content", "")
                history_text += f"{role}: {content}\n"
        
        # Create suggestions prompt
        suggestions_prompt = f"""You are generating helpful search suggestions for a service provider search system.

Context:
- Country: {country}
- Service Type: {service_type}
- Recent Conversation: {history_text}

Generate exactly 3 concise, actionable search suggestions that would be helpful for someone looking for {service_type} providers in {country}.

Requirements:
- NO emojis or icons
- Each suggestion should be 5-12 words and plausibly a subset of the service type and country
- If there's conversation history, make suggestions that build on or complement what was discussed
- Focus on practical, specific searches users might want to make

Format as a JSON array of exactly 3 strings:
["suggestion 1", "suggestion 2", "suggestion 3"]

Examples for different contexts:
- For Tax Services in USA: ["Find tax preparers for small businesses", "Compare CPA firms for individuals", "Search tax advisors with IRS experience"]
- For Migration Services in Canada: ["Find immigration lawyers for work permits", "Search consultants for permanent residency", "Compare services for family sponsorship"]
- For Business Setup in UAE: ["Find accountants for limited company formation in Dubai", "Search lawyers for business registration in Abu Dhabi", "Compare consultants for VAT registration"]
"""

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
            return fallback_suggestions(country, service_type)
            
    except Exception as e:
        print(f"❌ Suggestions generation error: {e}")
        return fallback_suggestions(country, service_type)


def fallback_suggestions(country: str, service_type: str) -> List[str]:
    """Fallback suggestions when API fails"""
    fallback_map = {
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
    return fallback_map.get(service_type, [
        f"Find {service_type.lower()} providers in {country}",
        f"Compare {service_type.lower()} options in {country}",
        f"Search professional services in {country}"
    ])


if __name__ == "__main__":
    # For development/testing
    print("🚀 Growbal Search MCP Server")
    print("Tools available:")
    print("  - search_service_providers: Filtered search by country/service")
    print("  - search_service_providers_streaming: Search with real-time updates")
    print("  - conversational_agent: Handle greetings and general conversation")
    print("  - orchestrator_analyze: Analyze messages for tool routing")
    print("  - generate_suggestions: Generate dynamic search suggestions")
    mcp.run()