"""
MCP Server for Growbal Intelligence Search Agent
Provides search functionality for service providers through Model Context Protocol
"""
import asyncio
import os
import sys
from typing import AsyncGenerator, Dict, Any
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

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
async def search_service_providers(
    message: str,
    system_prompt: str
) -> str:
    """AI Search Agent - Searches for service providers matching query with system prompt filtering.
    
    Args:
        message: User's search query
        system_prompt: Filtering criteria for provider selection
        
    Returns:
        Formatted status updates and final analysis results
    """
    
    try:
        # Collect full response with proper error handling
        full_response = ""
        async for chunk in get_search_agent_response(message, system_prompt):
            full_response = chunk  # Last chunk contains complete response
        
        return full_response or "No results found"
        
    except Exception as e:
        print(f"❌ Server search error: {e}")
        import traceback
        traceback.print_exc()
        return f"Search error: {str(e)}"


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


if __name__ == "__main__":
    # For development/testing
    print("🚀 Growbal Search MCP Server")
    print("Tools available:")
    print("  - search_service_providers: Filtered search by country/service")
    print("  - conversational_agent: Handle greetings and general conversation")
    mcp.run()