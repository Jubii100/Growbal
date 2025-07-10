"""
Search Agent implementation using Claude Haiku 3.5 with streaming support.
This agent is responsible for finding candidate profiles based on user queries.
"""
import os
import time
from typing import Dict, Any, List, Literal, AsyncIterator, Optional, Callable
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler
from ..core.models import (
    SearchAgentInput,
    SearchAgentOutput,
    AgentResponse,
    AgentRole
)
from ..utils.django_interface import search_profiles, search_profiles_by_service_tags, search_profiles_hybrid
from pydantic import BaseModel, Field


class SearchStrategyAnalysis(BaseModel):
    """
    Pydantic model for structured search strategy analysis output.
    """
    strategy: Literal["semantic", "tags", "hybrid"] = Field(
        description="The recommended search strategy based on the query analysis"
    )
    extracted_tags: List[str] = Field(
        default_factory=list,
        description="List of specific service tags or categories mentioned in the query"
    )
    similarity_search_query: str = Field(
        description="The query to use for semantic similarity search. It should mimic the typical service provider profile description (e.g. 'a service provider that provides services such as X, Y, and Z to small businesses')"
    )
    reasoning: str = Field(
        description="Brief explanation of why this strategy is best for the given query"
    )


class StreamingProgressCallback(BaseCallbackHandler):
    """Custom callback handler for streaming progress updates"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        super().__init__()
        self.progress_callback = progress_callback
        self.current_tokens = []
        
    def on_llm_new_token(self, token: str, **kwargs) -> None:
        """Called when a new token is generated"""
        self.current_tokens.append(token)
        if self.progress_callback:
            self.progress_callback(token)
    
    def on_llm_end(self, response, **kwargs) -> None:
        """Called when LLM finishes generating"""
        self.current_tokens = []


class SearchAgent:
    """
    Agent responsible for searching and retrieving candidate profiles from the database.
    Uses Claude Haiku 3.5 for query understanding and search strategy selection.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the search agent with Claude Haiku 3.5.
        
        Args:
            api_key: Anthropic API key. If not provided, will use ANTHROPIC_API_KEY from environment.
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.role = AgentRole.SEARCH
        
        # Initialize output parser for structured response
        self.output_parser = PydanticOutputParser(pydantic_object=SearchAgentOutput)
        
        # Initialize strategy analysis parser
        self.strategy_parser = PydanticOutputParser(pydantic_object=SearchStrategyAnalysis)
    
    def _create_llm(self, streaming: bool = False, callbacks: List[BaseCallbackHandler] = None):
        """Create LLM instance with optional streaming"""
        return ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            anthropic_api_key=self.api_key,
            temperature=0.3,
            max_tokens=1024,
            streaming=streaming,
            callbacks=callbacks or []
        )
    
    def _create_search_strategy_prompt(self) -> ChatPromptTemplate:
        """
        Create a prompt template for determining the best search strategy.
        """
        return ChatPromptTemplate.from_messages([
            ("system", """You are a search strategy expert for a service provider database. 
Your task is to analyze the user's query and determine the best search approach/strategy and extract any specific service tags or categories mentioned in the query.

Consider these search strategies:
1. Semantic similarity search - Best for natural language queries about services or needs
2. Tag-based search - Best when specific service categories or tags are mentioned
3. Hybrid search - Best when both semantic understanding and specific tags are needed

For the similarity_search_query field:
- Transform the user's query into a description that matches how service providers would describe themselves
- Focus on the services, skills, or solutions being sought
- Use professional language that would appear in service provider profiles
- Example: If user asks "I need help with digital marketing", transform to "a service provider that offers digital marketing services including social media management, SEO, and online advertising"

{format_instructions}"""),
            ("human", """Analyze this search query and recommend a search strategy:

Query: {query}""")
        ])
    
    async def search_streaming(
        self, 
        search_input: SearchAgentInput,
        progress_callback: Optional[Callable] = None
    ) -> AsyncIterator[dict]:
        """
        Execute the search operation with streaming progress updates.
        
        Args:
            search_input: SearchAgentInput containing query and parameters
            progress_callback: Optional callback for token-level progress updates
            
        Yields:
            Progress updates as dictionaries
        """
        start_time = time.time()
        
        try:
            # Step 1: Yield search strategy analysis start
            yield {
                "type": "strategy_start",
                "message": "Analyzing query to determine best search strategy..."
            }
            
            # Analyze query to determine search strategy
            strategy_prompt = self._create_search_strategy_prompt()
            
            # Create callbacks for streaming
            callbacks = []
            if progress_callback:
                stream_callback = StreamingProgressCallback(progress_callback)
                callbacks.append(stream_callback)
            
            # Create LLM with streaming if callback provided
            llm = self._create_llm(streaming=bool(progress_callback), callbacks=callbacks)
            
            strategy_chain = strategy_prompt | llm | self.strategy_parser
            
            strategy_analysis = await strategy_chain.ainvoke({
                "query": search_input.query,
                "format_instructions": self.strategy_parser.get_format_instructions()
            })
            
            # Yield strategy analysis complete
            yield {
                "type": "strategy_complete",
                "strategy": strategy_analysis.strategy,
                "extracted_tags": strategy_analysis.extracted_tags,
                "reasoning": strategy_analysis.reasoning,
                "similarity_query": strategy_analysis.similarity_search_query
            }
            
            # Step 2: Execute the appropriate search
            yield {
                "type": "search_start",
                "message": f"Executing {strategy_analysis.strategy} search...",
                "strategy": strategy_analysis.strategy
            }
            
            # Execute search based on structured analysis
            if strategy_analysis.strategy == "tags" and strategy_analysis.extracted_tags:
                search_result = search_profiles_by_service_tags(
                    tags=strategy_analysis.extracted_tags,
                    match_all=False,
                    max_results=search_input.max_results
                )
            elif strategy_analysis.strategy == "hybrid" and strategy_analysis.extracted_tags:
                search_result = search_profiles_hybrid(
                    query=strategy_analysis.similarity_search_query,
                    tags=strategy_analysis.extracted_tags,
                    max_results=search_input.max_results
                )
            else:
                # Use semantic search with the optimized similarity query
                search_result = search_profiles(
                    query=strategy_analysis.similarity_search_query,
                    max_results=search_input.max_results,
                    minimum_similarity=search_input.minimum_similarity
                )
            
            # Yield search progress
            yield {
                "type": "search_progress",
                "found_profiles": len(search_result.candidate_profiles),
                "total_searched": search_result.total_profiles_searched
            }
            
            processing_time = time.time() - start_time
            
            # Yield final result
            yield {
                "type": "complete",
                "response": AgentResponse(
                    success=True,
                    agent_role=self.role,
                    data=search_result,
                    message=f"Successfully found {len(search_result.candidate_profiles)} candidate profiles using {strategy_analysis.strategy} search",
                    processing_time=processing_time,
                    confidence_score=1.0 if search_result.candidate_profiles else 0.0,
                    metadata={
                        "search_strategy": strategy_analysis.strategy,
                        "extracted_tags": strategy_analysis.extracted_tags,
                        "strategy_reasoning": strategy_analysis.reasoning,
                        "similarity_search_query": strategy_analysis.similarity_search_query,
                        "original_query": search_input.query,
                        "total_profiles_searched": search_result.total_profiles_searched
                    }
                )
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            yield {
                "type": "error",
                "response": AgentResponse(
                    success=False,
                    agent_role=self.role,
                    data=None,
                    message=f"Search failed: {str(e)}",
                    processing_time=processing_time,
                    confidence_score=0.0,
                    metadata={"error": str(e)}
                )
            }
    
    async def search(self, search_input: SearchAgentInput, streaming: bool = False) -> AgentResponse:
        """
        Execute the search operation based on the input parameters.
        
        Args:
            search_input: SearchAgentInput containing query and parameters
            streaming: If True, use streaming mode (returns full response at end)
            
        Returns:
            AgentResponse with search results
        """
        if streaming:
            # For backward compatibility, collect all streaming results and return final one
            final_response = None
            async for update in self.search_streaming(search_input):
                if update["type"] == "complete":
                    final_response = update["response"]
                elif update["type"] == "error":
                    final_response = update["response"]
            return final_response
        else:
            # Non-streaming implementation (original)
            return await self._search_non_streaming(search_input)
    
    async def _search_non_streaming(self, search_input: SearchAgentInput) -> AgentResponse:
        """Original non-streaming search implementation"""
        start_time = time.time()
        
        try:
            # Step 1: Analyze query to determine search strategy
            strategy_prompt = self._create_search_strategy_prompt()
            
            # Create non-streaming LLM
            llm = self._create_llm(streaming=False)
            
            strategy_chain = strategy_prompt | llm | self.strategy_parser
            
            strategy_analysis = await strategy_chain.ainvoke({
                "query": search_input.query,
                "format_instructions": self.strategy_parser.get_format_instructions()
            })
            
            # Step 2: Execute the appropriate search based on structured analysis
            if strategy_analysis.strategy == "tags" and strategy_analysis.extracted_tags:
                search_result = search_profiles_by_service_tags(
                    tags=strategy_analysis.extracted_tags,
                    match_all=False,
                    max_results=search_input.max_results
                )
            elif strategy_analysis.strategy == "hybrid" and strategy_analysis.extracted_tags:
                search_result = search_profiles_hybrid(
                    query=strategy_analysis.similarity_search_query,
                    tags=strategy_analysis.extracted_tags,
                    max_results=search_input.max_results
                )
            else:
                # Use semantic search with the optimized similarity query
                search_result = search_profiles(
                    query=strategy_analysis.similarity_search_query,
                    max_results=search_input.max_results,
                    minimum_similarity=search_input.minimum_similarity
                )
            
            processing_time = time.time() - start_time
            
            return AgentResponse(
                success=True,
                agent_role=self.role,
                data=search_result,
                message=f"Successfully found {len(search_result.candidate_profiles)} candidate profiles using {strategy_analysis.strategy} search",
                processing_time=processing_time,
                confidence_score= 1.0 if search_result.candidate_profiles else 0.0,
                metadata={
                    "search_strategy": strategy_analysis.strategy,
                    "extracted_tags": strategy_analysis.extracted_tags,
                    "strategy_reasoning": strategy_analysis.reasoning,
                    "similarity_search_query": strategy_analysis.similarity_search_query,
                    "original_query": search_input.query,
                    "total_profiles_searched": search_result.total_profiles_searched
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return AgentResponse(
                success=False,
                agent_role=self.role,
                data=None,
                message=f"Search failed: {str(e)}",
                processing_time=processing_time,
                confidence_score=0.0,
                metadata={"error": str(e)}
            )
    
    def search_sync(self, search_input: SearchAgentInput, streaming: bool = False) -> AgentResponse:
        """
        Synchronous version of the search method.
        """
        import asyncio
        return asyncio.run(self.search(search_input, streaming=streaming))