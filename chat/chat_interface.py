"""
Gradio Chat Interface App - Standalone
Features: Chat interface that can be embedded in Django with session and country parameters
"""
import gradio as gr
import asyncio
import sys
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv
from typing import AsyncGenerator, Dict, Any

# Load environment variables
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(project_root, 'envs', '1.env')
load_dotenv(env_path)

# Add the project root to the path
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Change to project root directory to fix import issues
os.chdir(project_root)

# Import the Growbal Intelligence system
try:
    from growbal_intelligence.core.models import WorkflowState, SearchAgentInput, SummarizerAgentInput
    from growbal_intelligence.agents.search_agent import SearchAgent
    from growbal_intelligence.agents.adjudicator_agent import AdjudicatorAgent
    from growbal_intelligence.agents.summarizer_agent import SummarizerAgent
    print("✅ Successfully imported Growbal Intelligence system")
except ImportError as e:
    print(f"❌ Error importing Growbal Intelligence: {e}")
    sys.exit(1)

# Get API key from environment
api_key = os.getenv('ANTHROPIC_API_KEY')
if not api_key:
    print("⚠️  WARNING: ANTHROPIC_API_KEY not found in environment!")
    sys.exit(1)

# Initialize agents
search_agent = SearchAgent(api_key=api_key)
adjudicator_agent = AdjudicatorAgent(api_key=api_key)
summarizer_agent = SummarizerAgent(api_key=api_key)
print("✅ Growbal Intelligence agents initialized")

# Global state for tracking
app_state = {
    "active_workflows": {},
    "conversation_history": [],
    "current_reasoning_streams": {},
    "current_tasks": set(),
    "cancellation_flag": False,
    "session_id": None,
    "selected_country": None
}


def extract_profile_name(profile_text: str) -> str:
    """Extract company name from profile text"""
    if not profile_text:
        return "Unknown Company"
    
    lines = profile_text.split('\n')
    for line in lines:
        if "Company Name:" in line:
            name = line.split("Company Name:")[1].strip()
            if name:
                return name
    
    # Fallback: try to find company name in first few lines
    for line in lines[:5]:
        if line.strip() and not line.startswith("Profile ID:"):
            return line.strip()
    
    return "Unknown Company"


def create_thinking_block(title: str, content: str, status: str = "pending") -> str:
    """Create a collapsible thinking block with status"""
    status_colors = {
        "pending": "#6c757d",
        "processing": "#198484", 
        "completed": "#16a085",
        "error": "#e74c3c"
    }
    
    status_emoji = {
        "pending": "[PENDING]",
        "processing": "[PROCESSING]", 
        "completed": "[COMPLETED]",
        "error": "[ERROR]"
    }
    
    color = status_colors.get(status, "#6c757d")
    emoji = status_emoji.get(status, "[UNKNOWN]")
    
    # If content is empty or just whitespace, don't show the content div
    if not content or content.strip() == "":
        return f"""
<details open style="margin: 4px 0; border: 1px solid {color}; border-radius: 6px; background: #f8f9fa;">
    <summary style="cursor: pointer; font-weight: bold; padding: 8px 12px; background: {color}; color: white; border-radius: 4px; font-size: 14px;">
        {emoji} {title}
    </summary>
</details>
"""
    else:
        return f"""
<details open style="margin: 4px 0; border: 1px solid {color}; border-radius: 6px; background: #f8f9fa;">
    <summary style="cursor: pointer; font-weight: bold; padding: 8px 12px; background: {color}; color: white; border-radius: 4px 4px 0 0; font-size: 14px;">
        {emoji} {title}
    </summary>
    <div style="padding: 12px; background: white; border-radius: 0 0 4px 4px; font-family: monospace; font-size: 12px; max-height: 300px; overflow-y: auto; white-space: pre-wrap;">
        {content}
    </div>
</details>
"""


def format_streaming_update(update: Dict[str, Any]) -> str:
    """Enhanced format function that handles real-time reasoning streams"""
    # Handle the workflow-level updates first
    if "workflow_id" in update and "query" in update:
        return f"**Starting AI Analysis**\n\n*Processing: {update.get('query', 'Unknown query')}*"
    
    # Check for agent-specific updates by looking at the agent field
    agent = update.get("agent", "unknown")
    
    if agent == "search":
        # Search agent updates
        if "strategy" in update:
            strategy = update.get("strategy", "unknown")
            return f"**Search Agent** - Strategy selected: **{strategy}**\n\n*Executing search...*"
        
        elif "found_profiles" in update:
            found = update.get("found_profiles", 0)
            return f"**Search Agent** - Found **{found} candidates**\n\n*Continuing search...*"
        
        elif "response" in update:
            response = update.get("response", {})
            if hasattr(response, 'data') and response.data:
                candidates = len(response.data.candidate_profiles)
                return f"**Search Complete** - Found **{candidates} candidates**\n\n*Moving to evaluation phase...*"
        
        else:
            # Fallback for search updates
            return f"**Search Agent** - {update.get('message', 'Processing...')}"
    
    elif agent == "adjudicator":
        # Enhanced adjudication agent updates with real-time reasoning
        update_type = update.get("type", "unknown")
        
        if update_type == "profile_start":
            idx = update.get("profile_index", 0)
            total = update.get("total_profiles", "?")
            profile_name = update.get("profile_name", "Unknown Company")
            
            # Initialize thinking block for this profile
            thinking_block = create_thinking_block(
                f"Evaluating: {profile_name} ({idx + 1}/{total})",
                "",
                "processing"
            )
            
            return f"**Adjudicator Agent** - Starting evaluation\n\n{thinking_block}"
        
        elif update_type == "profile_complete":
            # Final profile evaluation result
            profile_name = update.get("profile_name", "Unknown Company")
            is_relevant = update.get("is_relevant", False)
            relevance_score = update.get("relevance_score", 0)
            reasoning = update.get("reasoning", "No reasoning provided")
            
            # Show the full reasoning
            status = "RELEVANT" if is_relevant else "NOT RELEVANT"
            
            thinking_block = create_thinking_block(
                f"Final Result: {profile_name} - {status} ({relevance_score:.2f})",
                reasoning,
                "completed"
            )
            
            return f"**Adjudicator Agent** - Evaluation complete\n\n{thinking_block}"
        
        elif update_type == "profile_streaming":
            # Streaming LLM output during evaluation
            profile_name = update.get("profile_name", "Unknown Company")
            profile_index = update.get("profile_index", 0)
            total_profiles = update.get("total_profiles", "?")
            streaming_content = update.get("streaming_content", "")
            
            thinking_block = create_thinking_block(
                f"Evaluating: {profile_name} ({profile_index + 1}/{total_profiles})",
                streaming_content,
                "processing"
            )
            
            return f"**Adjudicator Agent** - AI reasoning in progress...\n\n{thinking_block}"
        
        elif "response" in update:
            response = update.get("response", {})
            if hasattr(response, 'data') and response.data:
                relevant = len(response.data.relevant_profiles)
                total = len(response.data.adjudicated_profiles)
                return f"**Adjudication Complete** - **{relevant}/{total} relevant** profiles\n\n*Generating summary...*"
        
        else:
            return f"**Adjudicator Agent** - {update.get('message', 'Processing...')}"
    
    elif agent == "summarizer":
        # Summarization agent updates
        if "progress" in update:
            progress = update.get("progress", "")
            return f"**Summarizer Agent** - {progress}\n\n*Finalizing analysis...*"
        
        elif "response" in update:
            response = update.get("response", {})
            if hasattr(response, 'data') and response.data:
                return f"**Summary Complete** - Analysis generated\n\n*Preparing final results...*"
        
        else:
            return f"**Summarizer Agent** - {update.get('message', 'Processing...')}"
    
    # Handle workflow completion and error updates
    elif "success" in update and "summary" in update:
        summary = update.get("summary", {})
        stats = update.get("statistics", {})
        
        # Handle both dict and Pydantic model cases
        if hasattr(summary, 'executive_summary'):
            exec_summary = summary.executive_summary
            recommendations = summary.provider_recommendations
            insights = summary.key_insights
        else:
            exec_summary = summary.get("executive_summary", "Analysis complete")
            recommendations = summary.get("provider_recommendations", [])
            insights = summary.get("key_insights", [])
        
        result = f"""## **Analysis Complete!**

### **Executive Summary**
{exec_summary}

### **Top Recommendations**
"""
        
        for i, rec in enumerate(recommendations, 1):
            result += f"{i}. {rec}\n"
        
        result += f"""
### **Key Insights**
"""
        
        for insight in insights:
            result += f"• {insight}\n"
        
        result += f"""
### **Processing Statistics**
- **Total Searched**: {stats.get('total_searched', 0)}
- **Relevant Profiles**: {stats.get('relevant_found', 0)}
"""
        
        return result
    
    elif "no_results" in update:
        return f"**No Results Found**\n\n{update.get('message', 'No relevant providers found for your query.')}"
    
    elif "error" in update:
        error_msg = update.get("message", "Unknown error occurred")
        return f"**Error**: {error_msg}\n\nPlease try again or rephrase your query."
    
    # Default fallback
    update_type = update.get("type", "unknown")
    return f"Processing... ({update_type})"


async def enhanced_workflow_streaming(query: str, max_results: int = 7) -> AsyncGenerator[str, None]:
    """Enhanced workflow that uses the streaming adjudicator for real-time reasoning display"""
    workflow_id = f"workflow_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    try:
        # Check cancellation flag before starting
        if app_state["cancellation_flag"]:
            yield "**Process Cancelled** - Search was interrupted."
            return
            
        # Step 1: Search
        yield format_streaming_update({
            "workflow_id": workflow_id,
            "query": query
        })
        
        search_input = SearchAgentInput(query=query, max_results=max_results, minimum_similarity=0.5)
        
        # Stream through the search agent
        search_response = None
        search_data = None
        
        # Check if search_agent has search_streaming method
        if hasattr(search_agent, 'search_streaming'):
            async for search_update in search_agent.search_streaming(search_input):
                # Check cancellation flag
                if app_state["cancellation_flag"]:
                    yield "**Process Cancelled** - Search was interrupted."
                    return
                    
                # Add agent field to match format
                search_update["agent"] = "search"
                
                # Handle the different update types
                if search_update.get("type") == "strategy_complete":
                    search_update["strategy"] = search_update.get("strategy", "unknown")
                elif search_update.get("type") == "search_progress":
                    search_update["found_profiles"] = search_update.get("found_profiles", 0)
                elif search_update.get("type") == "complete":
                    search_response = search_update.get("response")
                    search_update["response"] = search_response
                elif search_update.get("type") == "error":
                    yield f"Search failed: {search_update.get('message', 'Unknown error')}"
                    return
                
                # Format and yield the update
                formatted = format_streaming_update(search_update)
                yield formatted
                
                # Small delay for UX
                await asyncio.sleep(0.05)
        else:
            # Fallback to non-streaming search
            search_response = await search_agent.search(search_input)
            
            if not search_response.success or not search_response.data:
                yield "Search failed. Please try again."
                return
            
            # Show search results
            yield format_streaming_update({
                "agent": "search",
                "response": search_response
            })
        
        # Check cancellation flag before adjudication
        if app_state["cancellation_flag"]:
            yield "**Process Cancelled** - Search was interrupted."
            return
        
        # Extract search data
        if search_response and search_response.data:
            search_data = search_response.data
        else:
            yield "No search results found."
            return
        
        # Step 2: Enhanced Adjudication with real-time streaming
        from growbal_intelligence.core.models import AdjudicatorAgentInput
        
        adj_input = AdjudicatorAgentInput(
            original_query=query,
            candidate_profiles=search_data.candidate_profiles,
            relevance_threshold=0.7
        )
        
        # Use the adjudicator agent with streaming
        adj_response = None
        current_profile_index = 0
        current_profile_name = "Unknown"
        streaming_content = ""
        token_buffer = []
        
        # Progress callback to capture streaming tokens
        def token_callback(token: str):
            nonlocal token_buffer
            token_buffer.append(token)
        
        async for adj_update in adjudicator_agent.adjudicate_streaming(adj_input, token_callback):
            # Check cancellation flag
            if app_state["cancellation_flag"]:
                yield "**Process Cancelled** - Evaluation was interrupted."
                return
                
            # Track current profile for streaming
            if adj_update.get("type") == "profile_start":
                current_profile_index = adj_update.get("profile_index", 0)
                current_profile_name = adj_update.get("profile_name", "Unknown")
                streaming_content = ""
                token_buffer = []
            
            # Check if we have new tokens to stream
            if token_buffer:
                # Add new tokens to streaming content
                new_tokens = "".join(token_buffer)
                streaming_content += new_tokens
                token_buffer = []
                
                # Yield streaming update
                streaming_update = {
                    "type": "profile_streaming",
                    "agent": "adjudicator",
                    "profile_name": current_profile_name,
                    "profile_index": current_profile_index,
                    "total_profiles": len(search_data.candidate_profiles),
                    "streaming_content": streaming_content
                }
                formatted = format_streaming_update(streaming_update)
                yield formatted
            
            # Add agent identifier and forward all updates
            adj_update["agent"] = "adjudicator"
            formatted = format_streaming_update(adj_update)
            yield formatted
            
            # Capture the final response
            if adj_update.get("type") == "complete":
                adj_response = adj_update.get("response")
            
            # Small delay for better UX
            await asyncio.sleep(0.05)
        
        if not adj_response or not adj_response.success:
            yield "Evaluation failed. Please try again."
            return
        
        # Check cancellation flag before summarization
        if app_state["cancellation_flag"]:
            yield "❌ **Process Cancelled** - Process was interrupted."
            return
        
        # Check if we have relevant profiles
        relevant_profiles = adj_response.data.relevant_profiles
        if not relevant_profiles:
            yield "**No Relevant Profiles Found**\n\nNo providers met the relevance criteria after detailed evaluation."
            return
        
        # Step 3: Summarization
        sum_input = SummarizerAgentInput(
            original_query=query,
            relevant_profiles=relevant_profiles,
            summary_style="comprehensive"
        )
        
        sum_response = await summarizer_agent.summarize(sum_input)
        
        if not sum_response.success or not sum_response.data:
            yield "Summary generation failed. Please try again."
            return
        
        # Final workflow complete
        yield format_streaming_update({
            "success": True,
            "summary": sum_response.data,
            "statistics": {
                "total_searched": search_data.total_profiles_searched,
                "candidates_found": len(search_data.candidate_profiles),
                "relevant_found": len(relevant_profiles)
            }
        })
        
    except Exception as e:
        if app_state["cancellation_flag"]:
            yield "**Process Cancelled** - Search was interrupted."
        else:
            yield f"**System Error**: {str(e)}\n\nPlease try again later."


async def get_search_agent_response(message: str, system_prompt: str) -> AsyncGenerator[Dict[str, str], None]:
    """
    Main function that MCP server calls - Enhanced workflow with system prompt support
    Returns dict with 'response' and 'status' fields
    """
    if not message.strip():
        yield {"response": "Please enter a search query.", "status": "error"}
        return
    
    # Reset cancellation flag when starting new request
    app_state["cancellation_flag"] = False
    
    # Apply system prompt to the query
    enhanced_query = f"{system_prompt}\n\nUser Query: {message}"
    
    # Retry logic for API overload
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            final_response = ""
            async for response in enhanced_workflow_streaming(enhanced_query):
                # Check if process was cancelled
                if app_state["cancellation_flag"]:
                    yield {"response": "**Process Cancelled** - Search was interrupted.", "status": "cancelled"}
                    return
                
                # Determine status based on response content
                if "**Analysis Complete!**" in response:
                    final_response = response
                    yield {"response": response, "status": "success"}
                elif "**No Results Found**" in response or "**No Relevant Profiles Found**" in response:
                    final_response = response
                    yield {"response": response, "status": "no_results"}
                elif "**Error**" in response or "**System Error**" in response:
                    final_response = response
                    yield {"response": response, "status": "error"}
                elif "**Process Cancelled**" in response:
                    final_response = response
                    yield {"response": response, "status": "cancelled"}
                else:
                    # This is a status update or intermediate response
                    yield {"response": response, "status": "processing"}
            return  # Success, exit retry loop
            
        except Exception as e:
            error_str = str(e)
            if "overloaded" in error_str.lower() or "529" in error_str:
                if attempt < max_retries - 1:
                    yield {"response": f"**API Overloaded** - Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})", "status": "retrying"}
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    yield {"response": f"**API Overloaded** - Please try again in a few minutes.", "status": "error"}
                    return
            else:
                yield {"response": f"**Error**: {error_str}\n\nPlease try again later.", "status": "error"}
                return


async def chat_response(message: str, history: list) -> AsyncGenerator[str, None]:
    """Enhanced chat response with retry logic and real-time reasoning streaming - for Gradio interface"""
    if not message.strip():
        yield "Please enter a search query."
        return
    
    # Reset cancellation flag when starting new request
    app_state["cancellation_flag"] = False
    
    # Retry logic for API overload
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            async for response in enhanced_workflow_streaming(message):
                # Check if process was cancelled
                if app_state["cancellation_flag"]:
                    yield "**Process Cancelled** - Search was interrupted."
                    return
                yield response
            return  # Success, exit retry loop
            
        except Exception as e:
            error_str = str(e)
            if "overloaded" in error_str.lower() or "529" in error_str:
                if attempt < max_retries - 1:
                    yield f"**API Overloaded** - Retrying in {retry_delay} seconds... (Attempt {attempt + 1}/{max_retries})"
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                else:
                    yield f"**API Overloaded** - Please try again in a few minutes."
                    return
            else:
                yield f"**Error**: {error_str}\n\nPlease try again later."
                return


def reset_app_state():
    """Reset the application to initial state"""
    # Set cancellation flag to halt any running processes
    app_state["cancellation_flag"] = True
    
    # Clear all tracking data
    app_state["active_workflows"].clear()
    app_state["conversation_history"].clear()
    app_state["current_reasoning_streams"].clear()
    app_state["current_tasks"].clear()
    
    # Reset cancellation flag after a brief delay
    asyncio.create_task(reset_cancellation_flag())


async def reset_cancellation_flag():
    """Reset the cancellation flag after a brief delay"""
    await asyncio.sleep(0.5)  # Give time for processes to see the flag
    app_state["cancellation_flag"] = False


def create_chat_interface_app(session_id: str = None, country: str = None):
    """Create the chat interface with session and country context"""
    
    # Store session info in app state
    app_state["session_id"] = session_id or str(uuid.uuid4())
    app_state["selected_country"] = country or "Not specified"
    
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
    
    /* Session info styling */
    .session-info {
        background: white !important;
        padding: 15px !important;
        border-radius: 10px !important;
        margin-bottom: 15px !important;
        box-shadow: 0 4px 15px rgba(25, 132, 132, 0.08) !important;
        text-align: center !important;
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
    
    # Create custom theme
    custom_theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.emerald,
        secondary_hue=gr.themes.colors.teal,
        neutral_hue=gr.themes.colors.gray,
        font=[gr.themes.GoogleFont("Inter"), "Arial", "sans-serif"]
    )
    
    # Custom clear function that resets state before clearing chat
    def custom_clear():
        reset_app_state()
        return []
    
    # Create session info HTML
    session_info = f"""
    <div class="session-info">
        <strong>Session:</strong> {app_state["session_id"]} | 
        <strong>Country:</strong> {app_state["selected_country"]}
    </div>
    """
    
    # Create back button functionality
    def go_back():
        return gr.HTML("""
        <script>
            // Send message to parent Django window
            if (window.parent && window.parent !== window) {
                window.parent.postMessage({
                    type: 'redirect',
                    url: '/country/'
                }, '*');
            } else {
                // Fallback for standalone mode
                window.location.href = '/country/';
            }
        </script>
        <div style="text-align: center; padding: 20px; color: #198484;">
            <h3>🔙 Returning to country selection...</h3>
        </div>
        """)
    
    # Create interface
    interface = gr.ChatInterface(
        fn=chat_response,
        type="messages",
        title=f"{logo_html}<div class='app-header'><h1 class='app-title'>Growbal Intelligence</h1><p class='app-description'>AI-powered service provider search</p></div>",
        description=session_info,
        examples=[
            "🏢 I need immigration services for business migration to UAE",
            "💼 Find accounting firms in Dubai for tech startups", 
            "💻 Looking for IT consulting with cloud expertise",
            "⚖️ Need legal services for fintech company setup",
            "📈 Find B2B marketing agencies with AI experience"
        ],
        cache_examples=False,
        theme=custom_theme,
        css=css,
        textbox=gr.Textbox(
            placeholder="🔍 Ask me about service providers and watch the AI reasoning...",
            container=False,
            scale=7,
            lines=1
        ),
        submit_btn=gr.Button("Search Providers", variant="primary"),
        retry_btn=None,
        undo_btn=None,
        clear_btn=gr.Button("🗑️ Clear Chat", variant="stop"),
        additional_inputs=[],
        multimodal=False,
        concurrency_limit=3,
        fill_height=True
    )
    
    # Add back button
    with interface:
        with gr.Row():
            back_btn = gr.Button("← Back to Country Selection", variant="secondary")
            back_output = gr.HTML(visible=False)
            
        back_btn.click(go_back, outputs=[back_output])
    
    # Try to override the clear button functionality
    try:
        if hasattr(interface, 'clear_btn') and interface.clear_btn:
            interface.clear_btn.click(
                fn=custom_clear,
                outputs=interface.chatbot,
                queue=False,
                show_progress=False
            )
    except Exception:
        pass
    
    return interface


def main():
    """Main function to launch the chat interface app"""
    # Parse command line arguments
    session_id = None
    country = None
    port = 7861
    
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print("Invalid port number, using default 7861")
    
    if len(sys.argv) > 2:
        session_id = sys.argv[2]
    
    if len(sys.argv) > 3:
        country = sys.argv[3]
    
    # Create and launch interface
    interface = create_chat_interface_app(session_id, country)
    
    launch_config = {
        "server_port": port,
        "share": False,
        "debug": True,
        "inbrowser": not ('--no-browser' in sys.argv),
        "quiet": False,
        "favicon_path": None
    }
    
    print(f"🚀 Launching Chat Interface App on port {port}")
    print(f"   Session: {session_id or 'Generated'}")
    print(f"   Country: {country or 'Not specified'}")
    
    interface.launch(**launch_config)


if __name__ == "__main__":
    main()