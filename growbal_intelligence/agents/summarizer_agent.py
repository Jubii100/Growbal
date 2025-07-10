"""
Summarizer Agent implementation using Claude Haiku 3.5 with streaming support.
This agent creates comprehensive summaries based on the relevant profiles.
"""
import os
import time
from typing import Dict, List, AsyncIterator, Optional, Callable
from collections import Counter
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain.callbacks.base import BaseCallbackHandler
from ..core.models import (
    SummarizerAgentInput,
    SummarizerAgentOutput,
    ProfileMatch,
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


class SummarizerAgent:
    """
    Agent responsible for creating comprehensive summaries of relevant profiles.
    Uses Claude Haiku 3.5 to analyze and synthesize information.
    """
    
    def __init__(self, api_key: str = None):
        """
        Initialize the summarizer agent with Claude Haiku 3.5.
        
        Args:
            api_key: Anthropic API key. If not provided, will use ANTHROPIC_API_KEY from environment.
        """
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        self.role = AgentRole.SUMMARIZER
        
        # Initialize output parser
        self.output_parser = PydanticOutputParser(pydantic_object=SummarizerAgentOutput)
    
    def _create_llm(self, streaming: bool = False, callbacks: List[BaseCallbackHandler] = None):
        """Create LLM instance with optional streaming"""
        return ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            anthropic_api_key=self.api_key,
            temperature=0.4,  # Slightly higher for more creative summaries
            max_tokens=3000,
            streaming=streaming,
            callbacks=callbacks or []
        )
    
    def _extract_profile_statistics(self, profiles: List[ProfileMatch]) -> Dict[str, any]:
        """
        Extract statistical information from the profiles.
        """
        statistics = {
            "total_providers": len(profiles),
            "countries": {},
            "provider_types": {},
            "services_overview": {}
        }
        
        for profile in profiles:
            profile_text = profile.profile_text
            
            # Extract country (simple parsing - could be improved)
            if "Country:" in profile_text:
                country = profile_text.split("Country:")[1].split("\n")[0].strip()
                statistics["countries"][country] = statistics["countries"].get(country, 0) + 1
            
            # Extract provider type
            if "Provider Type:" in profile_text:
                provider_type = profile_text.split("Provider Type:")[1].split("\n")[0].strip()
                statistics["provider_types"][provider_type] = statistics["provider_types"].get(provider_type, 0) + 1
        
        return statistics
    
    def _extract_profile_name(self, profile_text: str) -> str:
        """Extract company name from profile text"""
        lines = profile_text.split('\n')
        for line in lines:
            if "Company Name:" in line:
                return line.split("Company Name:")[1].strip()
        return "Unknown Company"
    
    def _create_summary_prompt(self) -> ChatPromptTemplate:
        """
        Create a prompt template for generating summaries.
        """
        return ChatPromptTemplate.from_messages([
            ("system", """You are an expert business analyst specializing in service provider summaries.
Your task is to create comprehensive summaries that help users understand their options.

Summary style guidelines based on the requested style:
- 'brief': Focus on key points, 2-3 sentences per provider, executive summary only
- 'comprehensive': Balanced detail, include all sections with moderate depth
- 'detailed': In-depth analysis, extensive information about each provider

Focus on:
1. How well each provider matches the user's query
2. Unique strengths and specializations
3. Geographic coverage and accessibility
4. Service offerings relevant to the query
5. Contact information and next steps

IMPORTANT: Base all recommendations and insights strictly on the information provided in the profiles.

Output your summary in this exact JSON format:
{format_instructions}"""),
            ("human", """Original Query: {query}

Summary Style: {summary_style}

Relevant Service Provider Profiles:
{profiles_text}

Create a comprehensive summary of these service providers that addresses the user's query.""")
        ])
    
    async def summarize_streaming(
        self, 
        summarizer_input: SummarizerAgentInput,
        progress_callback: Optional[Callable] = None
    ) -> AsyncIterator[dict]:
        """
        Create a summary of the relevant profiles with streaming progress.
        
        Args:
            summarizer_input: SummarizerAgentInput containing query and relevant profiles
            progress_callback: Optional callback for token-level progress updates
            
        Yields:
            Progress updates as dictionaries
        """
        start_time = time.time()
        
        try:
            # Yield start of statistics extraction
            yield {
                "type": "statistics_start",
                "message": "Extracting profile statistics...",
                "total_profiles": len(summarizer_input.relevant_profiles)
            }
            
            # Extract statistics first
            statistics = self._extract_profile_statistics(summarizer_input.relevant_profiles)
            
            # Yield statistics complete
            yield {
                "type": "statistics_complete",
                "statistics": statistics,
                "countries": list(statistics["countries"].keys()),
                "provider_types": list(statistics["provider_types"].keys())
            }
            
            # Prepare profiles text with progress
            yield {
                "type": "preparation_start",
                "message": "Preparing profile data for summarization..."
            }
            
            profiles_text = ""
            for i, profile in enumerate(summarizer_input.relevant_profiles):
                profile_name = self._extract_profile_name(profile.profile_text)
                profiles_text += f"\n\n---\n\nProfile {i+1} (Similarity Score: {profile.similarity_score:.2f}):\n{profile.profile_text}"
                
                # Yield profile processing progress
                yield {
                    "type": "profile_prepared",
                    "profile_index": i,
                    "profile_name": profile_name,
                    "total_profiles": len(summarizer_input.relevant_profiles)
                }
            
            # Create the summary prompt
            summary_prompt = self._create_summary_prompt()
            
            # Get format instructions
            format_instructions = self.output_parser.get_format_instructions()
            
            # Yield summarization start
            yield {
                "type": "summarization_start",
                "message": f"Generating {summarizer_input.summary_style} summary...",
                "style": summarizer_input.summary_style
            }
            
            # Create callbacks for streaming
            callbacks = []
            if progress_callback:
                stream_callback = StreamingProgressCallback(progress_callback)
                callbacks.append(stream_callback)
            
            # Create LLM with streaming if callback provided
            llm = self._create_llm(streaming=bool(progress_callback), callbacks=callbacks)
            
            # Create the chain
            chain = summary_prompt | llm | self.output_parser
            
            # Generate the summary
            summary_output = await chain.ainvoke({
                "query": summarizer_input.original_query,
                "summary_style": summarizer_input.summary_style,
                "profiles_text": profiles_text,
                "format_instructions": format_instructions
            })
            
            # Add statistics to the output
            summary_output.summary_statistics = statistics
            
            processing_time = time.time() - start_time
            
            # Calculate confidence based on number of relevant profiles
            confidence = min(0.9, 0.6 + (len(summarizer_input.relevant_profiles) * 0.1))
            
            # Yield final result
            yield {
                "type": "complete",
                "response": AgentResponse(
                    success=True,
                    agent_role=self.role,
                    data=summary_output,
                    message=f"Successfully created {summarizer_input.summary_style} summary for {len(summarizer_input.relevant_profiles)} providers",
                    processing_time=processing_time,
                    confidence_score=confidence,
                    metadata={
                        "summary_style": summarizer_input.summary_style,
                        "profiles_summarized": len(summarizer_input.relevant_profiles),
                        "statistics": statistics
                    }
                )
            }
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            # Try to create a basic summary even if parsing fails
            try:
                basic_summary = self._create_basic_summary(summarizer_input)
                yield {
                    "type": "complete",
                    "response": AgentResponse(
                        success=True,
                        agent_role=self.role,
                        data=basic_summary,
                        message=f"Created basic summary due to parsing error: {str(e)}",
                        processing_time=processing_time,
                        confidence_score=0.5,
                        metadata={"error": str(e), "fallback": True}
                    )
                }
            except:
                yield {
                    "type": "error",
                    "response": AgentResponse(
                        success=False,
                        agent_role=self.role,
                        data=None,
                        message=f"Summarization failed: {str(e)}",
                        processing_time=processing_time,
                        confidence_score=0.0,
                        metadata={"error": str(e)}
                    )
                }
    
    async def summarize(self, summarizer_input: SummarizerAgentInput, streaming: bool = False) -> AgentResponse:
        """
        Create a summary of the relevant profiles.
        
        Args:
            summarizer_input: SummarizerAgentInput containing query and relevant profiles
            streaming: If True, use streaming mode (returns full response at end)
            
        Returns:
            AgentResponse with summary results
        """
        if streaming:
            # For backward compatibility, collect all streaming results and return final one
            final_response = None
            async for update in self.summarize_streaming(summarizer_input):
                if update["type"] == "complete":
                    final_response = update["response"]
                elif update["type"] == "error":
                    final_response = update["response"]
            return final_response
        else:
            # Non-streaming implementation (original)
            return await self._summarize_non_streaming(summarizer_input)
    
    async def _summarize_non_streaming(self, summarizer_input: SummarizerAgentInput) -> AgentResponse:
        """Original non-streaming summarize implementation"""
        start_time = time.time()
        
        try:
            # Extract statistics first
            statistics = self._extract_profile_statistics(summarizer_input.relevant_profiles)
            
            # Prepare profiles text
            profiles_text = "\n\n---\n\n".join([
                f"Profile {i+1} (Similarity Score: {profile.similarity_score:.2f}):\n{profile.profile_text}"
                for i, profile in enumerate(summarizer_input.relevant_profiles)
            ])
            
            # Create the summary prompt
            summary_prompt = self._create_summary_prompt()
            
            # Get format instructions
            format_instructions = self.output_parser.get_format_instructions()
            
            # Create non-streaming LLM
            llm = self._create_llm(streaming=False)
            
            # Create the chain
            chain = summary_prompt | llm | self.output_parser
            
            # Generate the summary
            summary_output = await chain.ainvoke({
                "query": summarizer_input.original_query,
                "summary_style": summarizer_input.summary_style,
                "profiles_text": profiles_text,
                "format_instructions": format_instructions
            })
            
            # Add statistics to the output
            summary_output.summary_statistics = statistics
            
            processing_time = time.time() - start_time
            
            # Calculate confidence based on number of relevant profiles
            confidence = min(0.9, 0.6 + (len(summarizer_input.relevant_profiles) * 0.1))
            
            return AgentResponse(
                success=True,
                agent_role=self.role,
                data=summary_output,
                message=f"Successfully created {summarizer_input.summary_style} summary for {len(summarizer_input.relevant_profiles)} providers",
                processing_time=processing_time,
                confidence_score=confidence,
                metadata={
                    "summary_style": summarizer_input.summary_style,
                    "profiles_summarized": len(summarizer_input.relevant_profiles),
                    "statistics": statistics
                }
            )
            
        except Exception as e:
            processing_time = time.time() - start_time
            
            # Try to create a basic summary even if parsing fails
            try:
                basic_summary = self._create_basic_summary(summarizer_input)
                return AgentResponse(
                    success=True,
                    agent_role=self.role,
                    data=basic_summary,
                    message=f"Created basic summary due to parsing error: {str(e)}",
                    processing_time=processing_time,
                    confidence_score=0.5,
                    metadata={"error": str(e), "fallback": True}
                )
            except:
                return AgentResponse(
                    success=False,
                    agent_role=self.role,
                    data=None,
                    message=f"Summarization failed: {str(e)}",
                    processing_time=processing_time,
                    confidence_score=0.0,
                    metadata={"error": str(e)}
                )
    
    def _create_basic_summary(self, summarizer_input: SummarizerAgentInput) -> dict:
        """
        Create a basic summary as a fallback.
        """
        profiles_info = []
        for i, profile in enumerate(summarizer_input.relevant_profiles):
            # Extract basic info from profile text
            lines = profile.profile_text.split('\n')
            name = "Unknown Provider"
            country = "Unknown"
            
            for line in lines:
                if "Company Name:" in line:
                    name = line.split("Company Name:")[1].strip()
                elif "Country:" in line:
                    country = line.split("Country:")[1].strip()
            
            profiles_info.append(f"{i+1}. {name} ({country})")
        
        return {
            "executive_summary": f"Found {len(summarizer_input.relevant_profiles)} service providers matching your query: {summarizer_input.original_query}",
            "detailed_summary": "Providers found:\n" + "\n".join(profiles_info),
            "provider_recommendations": profiles_info[:3],
            "key_insights": [
                f"Total of {len(summarizer_input.relevant_profiles)} providers identified",
                "Providers span multiple countries and service offerings",
                "Further evaluation recommended based on specific requirements"
            ],
            "summary_statistics": {
                "total_providers": len(summarizer_input.relevant_profiles)
            }
        }
    
    def summarize_sync(self, summarizer_input: SummarizerAgentInput, streaming: bool = False) -> AgentResponse:
        """
        Synchronous version of the summarize method.
        """
        import asyncio
        return asyncio.run(self.summarize(summarizer_input, streaming=streaming))