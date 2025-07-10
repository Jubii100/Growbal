"""
LangGraph workflow implementation for the Growbal Intelligence system with streaming support.
Orchestrates the search, adjudication, and summarization agents.
"""
import uuid
from datetime import datetime
from typing import Dict, Any, List, AsyncIterator, Optional, Callable
from langgraph.graph import StateGraph, END
from langgraph.graph.graph import CompiledGraph
from .models import (
    WorkflowState,
    SearchAgentInput,
    AdjudicatorAgentInput,
    SummarizerAgentInput,
    ProfileMatch
)
from ..agents.search_agent import SearchAgent
from ..agents.adjudicator_agent import AdjudicatorAgent
from ..agents.summarizer_agent import SummarizerAgent


class GrowbalIntelligenceWorkflow:
    """
    Main workflow orchestrator for the Growbal Intelligence system.
    Uses LangGraph to manage the flow between agents with streaming support.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the workflow with all necessary agents.
        
        Args:
            api_key: Anthropic API key for the agents
        """
        self.search_agent = SearchAgent(api_key=api_key)
        self.adjudicator_agent = AdjudicatorAgent(api_key=api_key)
        self.summarizer_agent = SummarizerAgent(api_key=api_key)
        
        # Build the workflow graph
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> CompiledGraph:
        """
        Build the LangGraph workflow.
        """
        # Create the graph with WorkflowState
        workflow = StateGraph(WorkflowState)
        
        # Add nodes for each agent
        workflow.add_node("search", self._search_node)
        workflow.add_node("adjudicate", self._adjudicate_node)
        workflow.add_node("summarize", self._summarize_node)
        workflow.add_node("no_results", self._no_results_node)
        
        # Define the flow
        workflow.set_entry_point("search")
        
        # Add edges
        workflow.add_edge("search", "adjudicate")
        
        # Add conditional edge after adjudication
        workflow.add_conditional_edges(
            "adjudicate",
            self._check_relevant_results,
            {
                "summarize": "summarize",
                "no_results": "no_results"
            }
        )
        
        workflow.add_edge("summarize", END)
        workflow.add_edge("no_results", END)
        
        # Compile the workflow
        return workflow.compile()
    
    def _check_relevant_results(self, state: WorkflowState) -> str:
        """
        Check if there are any relevant results after adjudication.
        Returns the next node to execute.
        """
        # Check if adjudication was completed and if there are relevant profiles
        if (state.adjudication_completed and 
            state.adjudicator_output and 
            state.adjudicator_output.relevant_profiles):
            return "summarize"
        else:
            return "no_results"
    
    async def run_streaming(
        self, 
        query: str, 
        max_results: int = 5,
        progress_callback: Optional[Callable] = None
    ) -> AsyncIterator[dict]:
        """
        Run the complete workflow with streaming progress updates.
        
        Args:
            query: The user's search query
            max_results: Maximum number of results to return
            progress_callback: Optional callback for token-level progress updates
            
        Yields:
            Progress updates as dictionaries
        """
        # Create initial state
        initial_state = WorkflowState(
            query=query,
            max_results=max_results,
            workflow_id=str(uuid.uuid4()),
            start_time=datetime.now(),
            search_completed=False,
            adjudication_completed=False,
            summary_completed=False,
            errors=[],
            agent_execution_log=[]
        )
        
        try:
            # Step 1: Search with streaming
            yield {
                "type": "workflow_start",
                "workflow_id": initial_state.workflow_id,
                "query": query,
                "message": "Starting intelligent search workflow..."
            }
            
            # Execute search
            search_input = SearchAgentInput(
                query=query,
                max_results=max_results
            )
            
            search_updates = []
            async for update in self.search_agent.search_streaming(search_input, progress_callback):
                # Forward search updates
                yield {
                    "type": "search_update",
                    "agent": "search",
                    **update
                }
                search_updates.append(update)
            
            # Get the final search response
            search_response = None
            for update in search_updates:
                if update["type"] == "complete":
                    search_response = update["response"]
                    break
                elif update["type"] == "error":
                    search_response = update["response"]
                    break
            
            if not search_response or not search_response.success:
                yield {
                    "type": "workflow_error",
                    "agent": "search",
                    "error": "Search failed",
                    "message": search_response.message if search_response else "Unknown error"
                }
                return
            
            # Step 2: Adjudication with streaming
            candidate_profiles = search_response.data.candidate_profiles
            if not candidate_profiles:
                yield {
                    "type": "workflow_complete",
                    "no_results": True,
                    "message": "No candidate profiles found"
                }
                return
            
            adj_input = AdjudicatorAgentInput(
                original_query=query,
                candidate_profiles=candidate_profiles,
                relevance_threshold=0.7
            )
            
            adj_updates = []
            async for update in self.adjudicator_agent.adjudicate_streaming(adj_input, progress_callback):
                # Forward adjudication updates
                yield {
                    "type": "adjudication_update",
                    "agent": "adjudicator",
                    **update
                }
                adj_updates.append(update)
            
            # Get the final adjudication response
            adj_response = None
            for update in adj_updates:
                if update["type"] == "complete":
                    adj_response = update["response"]
                    break
                elif update["type"] == "error":
                    adj_response = update["response"]
                    break
            
            if not adj_response or not adj_response.success:
                yield {
                    "type": "workflow_error",
                    "agent": "adjudicator",
                    "error": "Adjudication failed",
                    "message": adj_response.message if adj_response else "Unknown error"
                }
                return
            
            # Check if we have relevant profiles
            relevant_profiles = adj_response.data.relevant_profiles
            if not relevant_profiles:
                yield {
                    "type": "workflow_complete",
                    "no_results": True,
                    "message": "No relevant profiles found after evaluation",
                    "statistics": {
                        "total_searched": search_response.data.total_profiles_searched,
                        "candidates_found": len(candidate_profiles),
                        "relevant_found": 0
                    }
                }
                return
            
            # Step 3: Summarization with streaming
            sum_input = SummarizerAgentInput(
                original_query=query,
                relevant_profiles=relevant_profiles,
                summary_style="comprehensive"
            )
            
            sum_updates = []
            async for update in self.summarizer_agent.summarize_streaming(sum_input, progress_callback):
                # Forward summarization updates
                yield {
                    "type": "summarization_update",
                    "agent": "summarizer",
                    **update
                }
                sum_updates.append(update)
            
            # Get the final summarization response
            sum_response = None
            for update in sum_updates:
                if update["type"] == "complete":
                    sum_response = update["response"]
                    break
                elif update["type"] == "error":
                    sum_response = update["response"]
                    break
            
            if not sum_response or not sum_response.success:
                yield {
                    "type": "workflow_error",
                    "agent": "summarizer",
                    "error": "Summarization failed",
                    "message": sum_response.message if sum_response else "Unknown error"
                }
                return
            
            # Final workflow complete
            total_time = (datetime.now() - initial_state.start_time).total_seconds()
            
            yield {
                "type": "workflow_complete",
                "workflow_id": initial_state.workflow_id,
                "success": True,
                "total_processing_time": total_time,
                "summary": sum_response.data,
                "statistics": {
                    "total_searched": search_response.data.total_profiles_searched,
                    "candidates_found": len(candidate_profiles),
                    "relevant_found": len(relevant_profiles),
                    "search_time": search_response.processing_time,
                    "adjudication_time": adj_response.processing_time,
                    "summarization_time": sum_response.processing_time
                }
            }
            
        except Exception as e:
            yield {
                "type": "workflow_error",
                "workflow_id": initial_state.workflow_id,
                "error": str(e),
                "message": f"Workflow failed: {str(e)}"
            }
    
    async def _no_results_node(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Handle the case when no relevant results are found.
        """
        # Log execution
        log_entry = {
            "agent": "no_results_handler",
            "start_time": datetime.now().isoformat(),
            "message": "No relevant results found"
        }
        
        # Calculate processing time
        end_time = datetime.now()
        total_time = (end_time - state.start_time).total_seconds()
        
        # Get statistics about what was searched
        total_searched = 0
        total_evaluated = 0
        
        if state.search_output:
            total_searched = state.search_output.total_profiles_searched
            candidate_count = len(state.search_output.candidate_profiles)
            
        if state.adjudicator_output:
            total_evaluated = len(state.adjudicator_output.adjudicated_profiles)
        
        # Create a helpful no-results message
        no_results_summary = {
            "executive_summary": "No relevant service providers found",
            "detailed_summary": f"""Unfortunately, we couldn't find any service providers in our database that match your query: "{state.query}"

Search Statistics:
- Total profiles in database: {total_searched}
- Candidate profiles found: {total_evaluated}
- Relevant profiles: 0

This could be because:
1. Your search criteria are too specific
2. We don't have providers for this particular service in our database yet
3. The service terminology might be different from what's in our system

Suggestions:
- Try using more general terms
- Search for related services
- Check if you're looking for services in a specific location that we might not cover yet
- Try alternative keywords or service categories

Please feel free to modify your search or ask for something else.""",
            "provider_recommendations": [],
            "key_insights": [
                "No matching providers found in the current database",
                f"Searched through {total_searched} total profiles",
                "Consider broadening search criteria or trying alternative terms"
            ],
            "summary_statistics": {
                "total_providers_searched": total_searched,
                "candidates_evaluated": total_evaluated,
                "relevant_providers": 0
            }
        }
        
        log_entry["end_time"] = datetime.now().isoformat()
        
        # Update state with no-results information
        return {
            "summary_completed": True,
            "summarizer_output": no_results_summary,
            "end_time": end_time,
            "total_processing_time": total_time,
            "agent_execution_log": state.agent_execution_log + [log_entry]
        }
    
    async def _search_node(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Execute the search agent node.
        """
        # Log execution
        log_entry = {
            "agent": "search",
            "start_time": datetime.now().isoformat(),
            "input": {"query": state.query, "max_results": state.max_results}
        }
        
        try:
            # Create search input
            search_input = SearchAgentInput(
                query=state.query,
                max_results=state.max_results
            )
            
            # Execute search
            response = await self.search_agent.search(search_input)
            
            # Update log
            log_entry["end_time"] = datetime.now().isoformat()
            log_entry["success"] = response.success
            log_entry["message"] = response.message
            
            if response.success:
                # Parse the response data (now it's a SearchAgentOutput object)
                search_output_data = response.data
                
                # Update state
                return {
                    "search_input": search_input,
                    "search_output": search_output_data,
                    "search_completed": True,
                    "agent_execution_log": state.agent_execution_log + [log_entry]
                }
            else:
                # Handle failure
                return {
                    "search_completed": False,
                    "errors": state.errors + [response.message],
                    "agent_execution_log": state.agent_execution_log + [log_entry]
                }
                
        except Exception as e:
            log_entry["end_time"] = datetime.now().isoformat()
            log_entry["success"] = False
            log_entry["error"] = str(e)
            
            return {
                "search_completed": False,
                "errors": state.errors + [f"Search node error: {str(e)}"],
                "agent_execution_log": state.agent_execution_log + [log_entry]
            }
    
    async def _adjudicate_node(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Execute the adjudicator agent node.
        """
        # Log execution
        log_entry = {
            "agent": "adjudicator",
            "start_time": datetime.now().isoformat()
        }
        
        try:
            # Check if search was successful
            if not state.search_completed or not state.search_output:
                raise ValueError("Search not completed successfully")
            
            # Extract candidate profiles from search output
            candidate_profiles = state.search_output.candidate_profiles
            
            if not candidate_profiles:
                # No profiles to adjudicate
                return {
                    "adjudication_completed": True,
                    "adjudicator_output": {
                        "adjudicated_profiles": [],
                        "relevant_profiles": [],
                        "rejection_summary": "No candidate profiles to evaluate",
                        "adjudication_confidence": 0.0
                    },
                    "agent_execution_log": state.agent_execution_log + [log_entry]
                }
            
            # Create adjudicator input
            adjudicator_input = AdjudicatorAgentInput(
                original_query=state.query,
                candidate_profiles=candidate_profiles
            )
            
            # Execute adjudication
            response = await self.adjudicator_agent.adjudicate(adjudicator_input)
            
            # Update log
            log_entry["end_time"] = datetime.now().isoformat()
            log_entry["success"] = response.success
            log_entry["message"] = response.message
            
            if response.success:
                # Update state
                return {
                    "adjudicator_input": adjudicator_input,
                    "adjudicator_output": response.data,
                    "adjudication_completed": True,
                    "agent_execution_log": state.agent_execution_log + [log_entry]
                }
            else:
                # Handle failure
                return {
                    "adjudication_completed": False,
                    "errors": state.errors + [response.message],
                    "agent_execution_log": state.agent_execution_log + [log_entry]
                }
                
        except Exception as e:
            log_entry["end_time"] = datetime.now().isoformat()
            log_entry["success"] = False
            log_entry["error"] = str(e)
            
            return {
                "adjudication_completed": False,
                "errors": state.errors + [f"Adjudication node error: {str(e)}"],
                "agent_execution_log": state.agent_execution_log + [log_entry]
            }
    
    async def _summarize_node(self, state: WorkflowState) -> Dict[str, Any]:
        """
        Execute the summarizer agent node.
        """
        # Log execution
        log_entry = {
            "agent": "summarizer",
            "start_time": datetime.now().isoformat()
        }
        
        try:
            # Check if adjudication was successful
            if not state.adjudication_completed or not state.adjudicator_output:
                raise ValueError("Adjudication not completed successfully")
            
            # Extract relevant profiles
            relevant_profiles = state.adjudicator_output.relevant_profiles
            
            # This check shouldn't be needed due to conditional routing, but keeping as safety
            if not relevant_profiles:
                # No relevant profiles to summarize
                return {
                    "summary_completed": True,
                    "summarizer_output": {
                        "executive_summary": "No relevant service providers found for your query.",
                        "detailed_summary": f"After evaluating {len(state.adjudicator_output.adjudicated_profiles) if state.adjudicator_output else 0} candidates, none were found to be sufficiently relevant to your query: {state.query}",
                        "provider_recommendations": [],
                        "key_insights": ["Consider broadening your search criteria", "Try different keywords or service categories"],
                        "summary_statistics": {"total_providers": 0, "relevant_providers": 0}
                    },
                    "end_time": datetime.now(),
                    "agent_execution_log": state.agent_execution_log + [log_entry]
                }
            
            # Create summarizer input
            summarizer_input = SummarizerAgentInput(
                original_query=state.query,
                relevant_profiles=relevant_profiles,
                summary_style="comprehensive"
            )
            
            # Execute summarization
            response = await self.summarizer_agent.summarize(summarizer_input)
            
            # Update log
            log_entry["end_time"] = datetime.now().isoformat()
            log_entry["success"] = response.success
            log_entry["message"] = response.message
            
            if response.success:
                # Calculate total processing time
                end_time = datetime.now()
                total_time = (end_time - state.start_time).total_seconds()
                
                # Update state
                return {
                    "summarizer_input": summarizer_input,
                    "summarizer_output": response.data,
                    "summary_completed": True,
                    "end_time": end_time,
                    "total_processing_time": total_time,
                    "agent_execution_log": state.agent_execution_log + [log_entry]
                }
            else:
                # Handle failure
                return {
                    "summary_completed": False,
                    "errors": state.errors + [response.message],
                    "agent_execution_log": state.agent_execution_log + [log_entry]
                }
                
        except Exception as e:
            log_entry["end_time"] = datetime.now().isoformat()
            log_entry["success"] = False
            log_entry["error"] = str(e)
            
            return {
                "summary_completed": False,
                "errors": state.errors + [f"Summarizer node error: {str(e)}"],
                "agent_execution_log": state.agent_execution_log + [log_entry]
            }
    
    async def run(self, query: str, max_results: int = 5, streaming: bool = False) -> WorkflowState:
        """
        Run the complete workflow for a given query.
        
        Args:
            query: The user's search query
            max_results: Maximum number of results to return
            streaming: If True, enables streaming for agents (backward compatibility)
            
        Returns:
            WorkflowState with complete results
        """
        # Create initial state
        initial_state = WorkflowState(
            query=query,
            max_results=max_results,
            workflow_id=str(uuid.uuid4()),
            start_time=datetime.now(),
            search_completed=False,
            adjudication_completed=False,
            summary_completed=False,
            errors=[],
            agent_execution_log=[]
        )
        
        # Run the workflow
        final_state = await self.workflow.ainvoke(initial_state)
        
        return WorkflowState(**final_state)
    
    def run_sync(self, query: str, max_results: int = 5, streaming: bool = False) -> WorkflowState:
        """
        Synchronous version of the run method.
        """
        import asyncio
        return asyncio.run(self.run(query, max_results, streaming))