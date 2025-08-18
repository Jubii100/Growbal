"""
Pydantic models for the Growbal Intelligence agentic system.
These models serve as both data structures and prompt schemas for LLM agents.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime


class AgentRole(str, Enum):
    """Enumeration of available agent roles in the system."""
    SEARCH = "search"
    ADJUDICATOR = "adjudicator" 
    SUMMARIZER = "summarizer"
    SUPERVISOR = "supervisor"


class ProfileMatch(BaseModel):
    """
    Represents a service provider profile matched through similarity search.
    Contains the complete profile information as text.
    """
    profile_id: int = Field(
        description="Unique identifier of the service provider profile in the database"
    )
    similarity_score: float = Field(
        description="Cosine similarity score (0-1) indicating how closely this profile matches the search query. Higher scores indicate better matches."
    )
    profile_text: str = Field(
        description="Complete textual representation of the profile obtained from get_profile_text() method, including all company details, services offered, contact information, key personnel, and any other relevant information"
    )


class AdjudicationResult(BaseModel):
    """
    Result of profile relevance assessment by the adjudicator agent.
    Contains the decision and reasoning for profile relevance.
    """
    profile_match: ProfileMatch = Field(
        description="The original profile match that was evaluated for relevance"
    )
    relevance_score: float = Field(
        description="Numerical score (0-1) indicating how relevant this profile is to the original query. 1.0 means highly relevant, 0.0 means not relevant."
    )
    reasoning: str = Field(
        description="Detailed explanation of why this profile was deemed relevant or irrelevant, including specific aspects that influenced the decision"
    )
    is_relevant: bool = Field(
        description="Final binary decision: True if the profile should be included in results, False if it should be filtered out"
    )
    confidence_level: float = Field(
        description="Agent's confidence in this relevance assessment (0-1), where 1.0 indicates very high confidence"
    )


class SearchAgentInput(BaseModel):
    """
    Input specification for the search agent that finds candidate profiles.
    """
    query: str = Field(
        description="Natural language search query describing the type of service provider or services needed"
    )
    max_results: int = Field(
        default=5,
        description="Maximum number of candidate profiles to return from similarity search"
    )
    minimum_similarity: float = Field(
        default=0.0,
        description="Minimum similarity score threshold for including profiles in results"
    )


class AdjudicatorAgentInput(BaseModel):
    """
    Input specification for the adjudicator agent that evaluates profile relevance.
    """
    original_query: str = Field(
        description="The original search query that the user submitted"
    )
    candidate_profiles: List[ProfileMatch] = Field(
        description="List of candidate profiles returned from the similarity search that need relevance evaluation"
    )
    relevance_threshold: float = Field(
        default=0.7,
        description="Minimum relevance score for a profile to be considered relevant (0-1)"
    )


class SummarizerAgentInput(BaseModel):
    """
    Input specification for the summarizer agent that creates final summaries.
    """
    original_query: str = Field(
        description="The original search query that initiated this workflow"
    )
    relevant_profiles: List[ProfileMatch] = Field(
        description="List of profiles that passed the relevance adjudication and should be included in the summary"
    )
    summary_style: str = Field(
        default="comprehensive",
        description="Style of summary to generate: 'brief', 'comprehensive', or 'detailed'"
    )


class SearchAgentOutput(BaseModel):
    """
    Output from the search agent containing candidate profiles.
    """
    candidate_profiles: List[ProfileMatch] = Field(
        description="List of service provider profiles that match the search query, ordered by similarity score"
    )
    total_profiles_searched: int = Field(
        description="Total number of profiles in the database that were searched"
    )
    search_time_seconds: float = Field(
        description="Time taken to complete the similarity search operation"
    )
    search_strategy: str = Field(
        description="Description of the search strategy used (e.g., 'vector similarity', 'text embedding')"
    )


class AdjudicatorAgentOutput(BaseModel):
    """
    Output from the adjudicator agent with relevance assessments.
    """
    adjudicated_profiles: List[AdjudicationResult] = Field(
        description="Complete list of all profiles that were evaluated, including both relevant and irrelevant ones"
    )
    relevant_profiles: List[ProfileMatch] = Field(
        description="Filtered list containing only the profiles deemed relevant to the original query"
    )
    rejection_summary: str = Field(
        description="Brief explanation of why certain profiles were rejected and the common reasons for rejection"
    )
    adjudication_confidence: float = Field(
        description="Overall confidence in the adjudication decisions across all profiles (0-1)"
    )


class SummarizerAgentOutput(BaseModel):
    """
    Output from the summarizer agent with the final summary.
    """
    executive_summary: str = Field(
        description="High-level overview of the search results and key findings"
    )
    # detailed_summary: str = Field(
    #     description="Comprehensive summary of all relevant service providers, their capabilities, and how they address the user's query"
    # )
    provider_recommendations: List[str] = Field(
        description="Specific recommendations for which providers to consider, in order of preference. With clickable titles that are markdown links to the provider's Growbal Link in bold blue font."
    )
    key_insights: List[str] = Field(
        description="Important insights derived from analyzing the relevant profiles"
    )
    summary_statistics: Dict[str, Any] = Field(
        description="Statistical information about the results (e.g., number of providers by country, service types)"
    )


class WorkflowState(BaseModel):
    """
    Complete state object for the LangGraph workflow.
    This tracks the entire processing pipeline from query to final summary.
    """
    # Input
    query: str = Field(
        description="Original user query describing their service provider requirements"
    )
    max_results: int = Field(
        default=5,
        description="Maximum number of results to return"
    )
    
    # Search Phase
    search_input: Optional[SearchAgentInput] = Field(
        default=None,
        description="Input parameters for the search agent"
    )
    search_output: Optional[SearchAgentOutput] = Field(
        default=None,
        description="Results from the search agent"
    )
    search_completed: bool = Field(
        default=False,
        description="Whether the search phase has been completed successfully"
    )
    
    # Adjudication Phase
    adjudicator_input: Optional[AdjudicatorAgentInput] = Field(
        default=None,
        description="Input parameters for the adjudicator agent"
    )
    adjudicator_output: Optional[AdjudicatorAgentOutput] = Field(
        default=None,
        description="Results from the adjudicator agent"
    )
    adjudication_completed: bool = Field(
        default=False,
        description="Whether the adjudication phase has been completed successfully"
    )
    
    # Summarization Phase
    summarizer_input: Optional[SummarizerAgentInput] = Field(
        default=None,
        description="Input parameters for the summarizer agent"
    )
    summarizer_output: Optional[SummarizerAgentOutput] = Field(
        default=None,
        description="Final summary results from the summarizer agent"
    )
    summary_completed: bool = Field(
        default=False,
        description="Whether the summarization phase has been completed successfully"
    )
    
    # Workflow Metadata
    workflow_id: str = Field(
        description="Unique identifier for this workflow execution"
    )
    start_time: datetime = Field(
        default_factory=datetime.now,
        description="Timestamp when the workflow was initiated"
    )
    end_time: Optional[datetime] = Field(
        default=None,
        description="Timestamp when the workflow was completed"
    )
    total_processing_time: Optional[float] = Field(
        default=None,
        description="Total time taken to complete the entire workflow in seconds"
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of any errors or warnings encountered during processing"
    )
    agent_execution_log: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Detailed log of agent executions, timing, and intermediate results"
    )


class AgentResponse(BaseModel):
    """
    Standardized response format for all agents in the system.
    """
    success: bool = Field(
        description="Whether the agent operation completed successfully"
    )
    agent_role: AgentRole = Field(
        description="The role/type of agent that generated this response"
    )
    data: Any = Field(
        description="The main output data from the agent (structure varies by agent type)"
    )
    message: str = Field(
        description="Human-readable message describing the operation result"
    )
    processing_time: float = Field(
        description="Time taken by this agent to complete its operation in seconds"
    )
    confidence_score: Optional[float] = Field(
        default=None,
        description="Agent's confidence in its output quality (0-1), if applicable"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the agent's operation"
    )