"""
MCP Server implementation for Growbal Intelligence.
Exposes the agentic workflow through Anthropic's Model Context Protocol.
"""
import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from mcp.server import Server, Tool, CallToolResult
from mcp.server.models import InitializationOptions
from mcp.types import TextContent, ImageContent, EmbeddedResource
from ..core.workflow import GrowbalIntelligenceWorkflow
from ..core.models import WorkflowState
from ..utils.django_interface import (
    get_available_service_tags,
    get_profile_by_id,
    search_profiles_by_service_tags
)


class GrowbalIntelligenceMCPServer:
    """
    MCP Server that exposes the Growbal Intelligence agentic system.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the MCP server.
        
        Args:
            api_key: Anthropic API key for the agents
        """
        self.server = Server("growbal-intelligence")
        self.workflow = GrowbalIntelligenceWorkflow(api_key=api_key)
        
        # Setup handlers
        self._setup_handlers()
    
    def _setup_handlers(self):
        """
        Setup all MCP server handlers and tools.
        """
        # Register tools
        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List all available tools."""
            return [
                Tool(
                    name="search_service_providers",
                    description="Search for service providers using natural language queries. The system uses AI agents to find, evaluate, and summarize relevant providers.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Natural language description of the service providers you're looking for"
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of providers to return (default: 5)",
                                "default": 5
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="search_by_tags",
                    description="Search for service providers by specific service tags/categories",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "tags": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of service tags to search for"
                            },
                            "match_all": {
                                "type": "boolean",
                                "description": "If true, only return providers that have ALL tags. If false, return providers with ANY of the tags.",
                                "default": False
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "Maximum number of providers to return",
                                "default": 10
                            }
                        },
                        "required": ["tags"]
                    }
                ),
                Tool(
                    name="get_available_tags",
                    description="Get a list of all available service tags in the system",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_provider_details",
                    description="Get detailed information about a specific service provider by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "provider_id": {
                                "type": "integer",
                                "description": "The database ID of the service provider"
                            }
                        },
                        "required": ["provider_id"]
                    }
                ),
                Tool(
                    name="get_workflow_status",
                    description="Get the status of a previously executed workflow by ID",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workflow_id": {
                                "type": "string",
                                "description": "The UUID of the workflow execution"
                            }
                        },
                        "required": ["workflow_id"]
                    }
                )
            ]
        
        @self.server.call_tool()
        async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
            """Handle tool calls."""
            try:
                if name == "search_service_providers":
                    result = await self._search_service_providers(
                        query=arguments["query"],
                        max_results=arguments.get("max_results", 5)
                    )
                    return CallToolResult(content=[TextContent(text=json.dumps(result, indent=2))])
                
                elif name == "search_by_tags":
                    result = await self._search_by_tags(
                        tags=arguments["tags"],
                        match_all=arguments.get("match_all", False),
                        max_results=arguments.get("max_results", 10)
                    )
                    return CallToolResult(content=[TextContent(text=json.dumps(result, indent=2))])
                
                elif name == "get_available_tags":
                    result = await self._get_available_tags()
                    return CallToolResult(content=[TextContent(text=json.dumps(result, indent=2))])
                
                elif name == "get_provider_details":
                    result = await self._get_provider_details(arguments["provider_id"])
                    return CallToolResult(content=[TextContent(text=json.dumps(result, indent=2))])
                
                elif name == "get_workflow_status":
                    result = await self._get_workflow_status(arguments["workflow_id"])
                    return CallToolResult(content=[TextContent(text=json.dumps(result, indent=2))])
                
                else:
                    return CallToolResult(
                        content=[TextContent(text=f"Unknown tool: {name}")],
                        isError=True
                    )
                    
            except Exception as e:
                return CallToolResult(
                    content=[TextContent(text=f"Error executing tool {name}: {str(e)}")],
                    isError=True
                )
    
    async def _search_service_providers(self, query: str, max_results: int = 5) -> Dict[str, Any]:
        """
        Execute the full AI workflow to search for service providers.
        """
        try:
            # Run the workflow
            workflow_state = await self.workflow.run(query, max_results)
            
            # Prepare the response
            response = {
                "workflow_id": workflow_state.workflow_id,
                "query": workflow_state.query,
                "status": "completed" if workflow_state.summary_completed else "failed",
                "processing_time": workflow_state.total_processing_time,
                "timestamp": datetime.now().isoformat()
            }
            
            # Add results if successful
            if workflow_state.summary_completed and workflow_state.summarizer_output:
                response["results"] = {
                    "executive_summary": workflow_state.summarizer_output.get("executive_summary"),
                    "detailed_summary": workflow_state.summarizer_output.get("detailed_summary"),
                    "recommendations": workflow_state.summarizer_output.get("provider_recommendations", []),
                    "key_insights": workflow_state.summarizer_output.get("key_insights", []),
                    "statistics": workflow_state.summarizer_output.get("summary_statistics", {})
                }
                
                # Add individual provider details if available
                if workflow_state.adjudicator_output and workflow_state.adjudicator_output.get("relevant_profiles"):
                    response["providers"] = []
                    for profile_data in workflow_state.adjudicator_output["relevant_profiles"]:
                        # Handle both ProfileMatch objects and dictionaries
                        if hasattr(profile_data, 'profile_id'):
                            # It's a ProfileMatch object
                            response["providers"].append({
                                "id": profile_data.profile_id,
                                "similarity_score": profile_data.similarity_score,
                                "profile_text": profile_data.profile_text
                            })
                        else:
                            # It's a dictionary
                            response["providers"].append({
                                "id": profile_data.get("profile_id"),
                                "similarity_score": profile_data.get("similarity_score"),
                                "profile_text": profile_data.get("profile_text")
                            })
            else:
                # Add error information
                response["errors"] = workflow_state.errors
                response["status"] = "no_results" if not workflow_state.errors else "failed"
            
            # Add execution log summary
            response["execution_summary"] = {
                "search_completed": workflow_state.search_completed,
                "adjudication_completed": workflow_state.adjudication_completed,
                "summary_completed": workflow_state.summary_completed,
                "agents_executed": len(workflow_state.agent_execution_log)
            }
            
            # Store workflow state for later retrieval
            self._store_workflow_state(workflow_state)
            
            return response
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _search_by_tags(self, tags: List[str], match_all: bool = False, 
                             max_results: int = 10) -> Dict[str, Any]:
        """
        Search for providers by service tags.
        """
        try:
            # Use the django interface to search by tags
            search_result = search_profiles_by_service_tags(
                tags=tags,
                match_all=match_all,
                max_results=max_results
            )
            
            # Format the response
            response = {
                "query_tags": tags,
                "match_mode": "all" if match_all else "any",
                "total_results": len(search_result.candidate_profiles),
                "search_time": search_result.search_time_seconds,
                "providers": []
            }
            
            for profile in search_result.candidate_profiles:
                response["providers"].append({
                    "id": profile.profile_id,
                    "similarity_score": profile.similarity_score,
                    "profile_text": profile.profile_text
                })
            
            return response
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _get_available_tags(self) -> Dict[str, Any]:
        """
        Get all available service tags.
        """
        try:
            tags = get_available_service_tags()
            
            return {
                "total_tags": len(tags),
                "tags": tags,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _get_provider_details(self, provider_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a specific provider.
        """
        try:
            profile = get_profile_by_id(provider_id)
            
            if profile:
                return {
                    "id": profile.profile_id,
                    "profile_text": profile.profile_text,
                    "timestamp": datetime.now().isoformat()
                }
            else:
                return {
                    "status": "not_found",
                    "message": f"No provider found with ID {provider_id}",
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def _get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """
        Get the status of a workflow execution.
        """
        # This would typically fetch from a database or cache
        # For now, return a placeholder
        return {
            "workflow_id": workflow_id,
            "status": "not_implemented",
            "message": "Workflow status retrieval not yet implemented",
            "timestamp": datetime.now().isoformat()
        }
    
    def _store_workflow_state(self, workflow_state: WorkflowState):
        """
        Store workflow state for later retrieval.
        In a production system, this would save to a database or cache.
        """
        # TODO: Implement actual storage mechanism
        pass
    
    async def run(self):
        """
        Run the MCP server.
        """
        # Start the server
        async with self.server.run() as running_server:
            print(f"Growbal Intelligence MCP Server running on stdio")
            await running_server.wait_closed()


async def main():
    """
    Main entry point for the MCP server.
    """
    # Get API key from environment
    api_key = os.getenv('ANTHROPIC_API_KEY')
    
    # Create and run server
    server = GrowbalIntelligenceMCPServer(api_key=api_key)
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())