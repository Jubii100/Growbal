"""
Adjudicator Agent implementation using Claude Haiku 3.5 with streaming support.
This agent evaluates the relevance of candidate profiles to the original query.
"""
import os
import time
from typing import List, AsyncIterator, Optional, Callable
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler
from ..core.models import (
    AdjudicatorAgentInput,
    AdjudicatorAgentOutput,
    AdjudicationResult,
    AgentResponse,
    AgentRole
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


class AdjudicatorAgent:
    """
    Agent responsible for evaluating the relevance of candidate profiles.
    Uses Claude Haiku 3.5 to analyze each profile against the original query.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the adjudicator agent with Claude Haiku 3.5.
        
        Args:
            api_key: Anthropic API key. If not provided, will use ANTHROPIC_API_KEY from environment.
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.role = AgentRole.ADJUDICATOR
        
        # Initialize output parser for AdjudicationResult
        self.adjudication_parser = PydanticOutputParser(pydantic_object=AdjudicationResult)
    
    def _create_llm(self, streaming: bool = False, callbacks: List[BaseCallbackHandler] = None):
        """Create LLM instance with optional streaming"""
        return ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            anthropic_api_key=self.api_key,
            temperature=0.2,  # Lower temperature for more consistent adjudication
            max_tokens=2048,
            streaming=streaming,
            callbacks=callbacks or []
        )
    
    def _create_adjudication_prompt(self) -> ChatPromptTemplate:
        """
        Create a prompt template for evaluating profile relevance.
        """
        return ChatPromptTemplate.from_messages([
            ("system", """You are an expert evaluator for matching service providers to user queries.
Your task is to carefully analyze each service provider profile against the user's original query and determine its relevance.

Evaluation criteria:
1. Service Match: Do the services offered align with what the user is looking for?
2. Location Relevance: Is the provider's location suitable for the user's needs?
3. Expertise Alignment: Does the provider have the specific expertise requested?
4. Capacity to Serve: Based on the profile, can this provider handle the user's requirements?

For the relevance score:
- 0.9-1.0: Perfect match - provider offers exactly what was requested
- 0.7-0.9: Good match - provider offers most of what was requested
- 0.5-0.7: Partial match - provider offers some relevant services
- 0.3-0.5: Weak match - limited relevance to the query
- 0.0-0.3: Poor match - minimal or no relevance

IMPORTANT: Be strict in your evaluation. Only mark as relevant (is_relevant=true) if the relevance_score is above {relevance_threshold}.

Output your evaluation in this exact JSON format:
{format_instructions}"""),
            ("human", """Original Query: {query}

Profile to Evaluate:
{profile_text}

Similarity Score from Search: {similarity_score}

Evaluate this profile's relevance to the original query.""")
        ])
    
    async def adjudicate_streaming(
        self, 
        adjudicator_input: AdjudicatorAgentInput,
        progress_callback: Optional[Callable] = None
    ) -> AsyncIterator[dict]:
        """
        Evaluate the relevance of candidate profiles with streaming progress.
        
        Args:
            adjudicator_input: AdjudicatorAgentInput containing query and candidate profiles
            progress_callback: Optional callback for progress updates
            
        Yields:
            Progress updates as dictionaries
        """
        start_time = time.time()
        
        try:
            # Create the adjudication prompt
            adjudication_prompt = self._create_adjudication_prompt()
            
            # Get format instructions for the parser
            format_instructions = self.adjudication_parser.get_format_instructions()
            
            # Process each candidate profile
            adjudicated_profiles = []
            relevant_profiles = []
            
            total_profiles = len(adjudicator_input.candidate_profiles)
            
            for idx, profile in enumerate(adjudicator_input.candidate_profiles):
                # Yield progress update for current profile
                yield {
                    "type": "profile_start",
                    "profile_index": idx,
                    "total_profiles": total_profiles,
                    "profile_name": self._extract_profile_name(profile.profile_text),
                    "message": f"Evaluating profile {idx + 1} of {total_profiles}"
                }
                
                try:
                    # Create callbacks for streaming
                    callbacks = []
                    if progress_callback:
                        stream_callback = StreamingProgressCallback(progress_callback)
                        callbacks.append(stream_callback)
                    
                    # Create LLM with streaming if callback provided
                    llm = self._create_llm(streaming=bool(progress_callback), callbacks=callbacks)
                    
                    # Create the chain with structured output
                    chain = adjudication_prompt | llm | self.adjudication_parser
                    
                    # Invoke the chain
                    adjudication_result = await chain.ainvoke({
                        "query": adjudicator_input.original_query,
                        "profile_text": profile.profile_text,
                        "similarity_score": profile.similarity_score,
                        "relevance_threshold": adjudicator_input.relevance_threshold,
                        "format_instructions": format_instructions
                    })
                    
                    # Ensure the profile_match is set correctly
                    adjudication_result.profile_match = profile
                    
                    adjudicated_profiles.append(adjudication_result)
                    
                    # Add to relevant profiles if it passes the threshold
                    if adjudication_result.is_relevant:
                        relevant_profiles.append(profile)
                    
                    # Yield result for this profile
                    yield {
                        "type": "profile_complete",
                        "profile_index": idx,
                        "profile_name": self._extract_profile_name(profile.profile_text),
                        "is_relevant": adjudication_result.is_relevant,
                        "relevance_score": adjudication_result.relevance_score,
                        "reasoning": adjudication_result.reasoning
                    }
                        
                except Exception as e:
                    # If adjudication fails for a profile, create a failed result
                    failed_result = AdjudicationResult(
                        profile_match=profile,
                        relevance_score=0.0,
                        reasoning=f"Failed to evaluate: {str(e)}",
                        is_relevant=False,
                        confidence_level=0.0
                    )
                    adjudicated_profiles.append(failed_result)
                    
                    yield {
                        "type": "profile_error",
                        "profile_index": idx,
                        "profile_name": self._extract_profile_name(profile.profile_text),
                        "error": str(e)
                    }
            
            # Calculate overall confidence
            if adjudicated_profiles:
                avg_confidence = sum(p.confidence_level for p in adjudicated_profiles) / len(adjudicated_profiles)
            else:
                avg_confidence = 0.0
            
            # Generate rejection summary
            rejected_profiles = [p for p in adjudicated_profiles if not p.is_relevant]
            rejection_summary = self._generate_rejection_summary(rejected_profiles)
            
            # Create output
            output = AdjudicatorAgentOutput(
                adjudicated_profiles=adjudicated_profiles,
                relevant_profiles=relevant_profiles,
                rejection_summary=rejection_summary,
                adjudication_confidence=avg_confidence
            )
            
            processing_time = time.time() - start_time
            
            # Yield final result
            yield {
                "type": "complete",
                "response": AgentResponse(
                    success=True,
                    agent_role=self.role,
                    data=output,
                    message=f"Successfully adjudicated {len(adjudicated_profiles)} profiles. {len(relevant_profiles)} found relevant.",
                    processing_time=processing_time,
                    confidence_score=avg_confidence,
                    metadata={
                        "total_evaluated": len(adjudicated_profiles),
                        "total_relevant": len(relevant_profiles),
                        "total_rejected": len(rejected_profiles),
                        "relevance_threshold": adjudicator_input.relevance_threshold
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
                    message=f"Adjudication failed: {str(e)}",
                    processing_time=processing_time,
                    confidence_score=0.0,
                    metadata={"error": str(e)}
                )
            }
    
    def _extract_profile_name(self, profile_text: str) -> str:
        """Extract company name from profile text"""
        lines = profile_text.split('\n')
        for line in lines:
            if "Company Name:" in line:
                return line.split("Company Name:")[1].strip()
        return "Unknown Company"
    
    def _generate_rejection_summary(self, rejected_profiles: List[AdjudicationResult]) -> str:
        """Generate a summary of rejection reasons"""
        if not rejected_profiles:
            return "No profiles were rejected."
        
        # Group by common rejection reasons
        reason_counts = {}
        for profile in rejected_profiles:
            # Extract key phrases from reasoning
            reasoning_lower = profile.reasoning.lower()
            if "location" in reasoning_lower:
                reason_counts["location mismatch"] = reason_counts.get("location mismatch", 0) + 1
            elif "service" in reasoning_lower:
                reason_counts["service mismatch"] = reason_counts.get("service mismatch", 0) + 1
            elif "expertise" in reasoning_lower:
                reason_counts["expertise mismatch"] = reason_counts.get("expertise mismatch", 0) + 1
            else:
                reason_counts["other reasons"] = reason_counts.get("other reasons", 0) + 1
        
        rejection_summary = f"Rejected {len(rejected_profiles)} profiles. Main reasons: " + \
                          ", ".join([f"{reason} ({count})" for reason, count in reason_counts.items()])
        
        return rejection_summary
    
    async def adjudicate(self, adjudicator_input: AdjudicatorAgentInput, streaming: bool = False) -> AgentResponse:
        """
        Evaluate the relevance of candidate profiles.
        
        Args:
            adjudicator_input: AdjudicatorAgentInput containing query and candidate profiles
            streaming: If True, use streaming mode (returns full response at end)
            
        Returns:
            AgentResponse with adjudication results
        """
        if streaming:
            # For backward compatibility, collect all streaming results and return final one
            final_response = None
            async for update in self.adjudicate_streaming(adjudicator_input):
                if update["type"] == "complete":
                    final_response = update["response"]
                elif update["type"] == "error":
                    final_response = update["response"]
            return final_response
        else:
            # Non-streaming implementation (original)
            return await self._adjudicate_non_streaming(adjudicator_input)
    
    async def _adjudicate_non_streaming(self, adjudicator_input: AdjudicatorAgentInput) -> AgentResponse:
        """Original non-streaming adjudication implementation"""
        start_time = time.time()
        
        try:
            # Create the adjudication prompt
            adjudication_prompt = self._create_adjudication_prompt()
            
            # Get format instructions for the parser
            format_instructions = self.adjudication_parser.get_format_instructions()
            
            # Create non-streaming LLM
            llm = self._create_llm(streaming=False)
            
            # Process each candidate profile
            adjudicated_profiles = []
            relevant_profiles = []
            
            for profile in adjudicator_input.candidate_profiles:
                try:
                    # Create the chain with structured output
                    chain = adjudication_prompt | llm | self.adjudication_parser
                    
                    # Invoke the chain
                    adjudication_result = await chain.ainvoke({
                        "query": adjudicator_input.original_query,
                        "profile_text": profile.profile_text,
                        "similarity_score": profile.similarity_score,
                        "relevance_threshold": adjudicator_input.relevance_threshold,
                        "format_instructions": format_instructions
                    })
                    
                    # Ensure the profile_match is set correctly
                    adjudication_result.profile_match = profile
                    
                    adjudicated_profiles.append(adjudication_result)
                    
                    # Add to relevant profiles if it passes the threshold
                    if adjudication_result.is_relevant:
                        relevant_profiles.append(profile)
                        
                except Exception as e:
                    # If adjudication fails for a profile, create a failed result
                    adjudicated_profiles.append(
                        AdjudicationResult(
                            profile_match=profile,
                            relevance_score=0.0,
                            reasoning=f"Failed to evaluate: {str(e)}",
                            is_relevant=False,
                            confidence_level=0.0
                        )
                    )
            
            # Calculate overall confidence
            if adjudicated_profiles:
                avg_confidence = sum(p.confidence_level for p in adjudicated_profiles) / len(adjudicated_profiles)
            else:
                avg_confidence = 0.0
            
            # Generate rejection summary
            rejected_profiles = [p for p in adjudicated_profiles if not p.is_relevant]
            rejection_summary = self._generate_rejection_summary(rejected_profiles)
            
            # Create output
            output = AdjudicatorAgentOutput(
                adjudicated_profiles=adjudicated_profiles,
                relevant_profiles=relevant_profiles,
                rejection_summary=rejection_summary,
                adjudication_confidence=avg_confidence
            )
            
            processing_time = time.time() - start_time
            
            return AgentResponse(
                success=True,
                agent_role=self.role,
                data=output,
                message=f"Successfully adjudicated {len(adjudicated_profiles)} profiles. {len(relevant_profiles)} found relevant.",
                processing_time=processing_time,
                confidence_score=avg_confidence,
                metadata={
                    "total_evaluated": len(adjudicated_profiles),
                    "total_relevant": len(relevant_profiles),
                    "total_rejected": len(rejected_profiles),
                    "relevance_threshold": adjudicator_input.relevance_threshold
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            return AgentResponse(
                success=False,
                agent_role=self.role,
                data=None,
                message=f"Adjudication failed: {str(e)}",
                processing_time=processing_time,
                confidence_score=0.0,
                metadata={"error": str(e)}
            )
    
    def adjudicate_sync(self, adjudicator_input: AdjudicatorAgentInput, streaming: bool = False) -> AgentResponse:
        """
        Synchronous version of the adjudicate method.
        """
        import asyncio
        return asyncio.run(self.adjudicate(adjudicator_input, streaming=streaming))