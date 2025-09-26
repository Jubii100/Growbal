# LLM Wrapper and Configuration Documentation

## Overview
This module provides a unified interface for LLM interactions, handling model configuration, prompt engineering, and response processing for the onboarding agent.

## LLM Configuration

### 1. Base LLM Wrapper

```python
from langchain_openai import ChatOpenAI
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.callbacks.base import BaseCallbackHandler
from typing import Dict, Any, List, Optional, Union
import os
from enum import Enum
import json
from datetime import datetime

class ModelType(Enum):
    """Available model types for different tasks."""
    RESEARCH = "gpt-4o-mini"  # Fast, cost-effective for research
    CONVERSATION = "gpt-4o"    # High quality for user interactions
    ANALYSIS = "gpt-4o-mini"   # Balanced for analysis tasks
    SUMMARY = "gpt-4o"         # High quality for final summaries

class LLMConfig:
    """Configuration for LLM models."""
    
    DEFAULT_TEMPERATURE = {
        ModelType.RESEARCH: 0.3,
        ModelType.CONVERSATION: 0.7,
        ModelType.ANALYSIS: 0.2,
        ModelType.SUMMARY: 0.4
    }
    
    DEFAULT_MAX_TOKENS = {
        ModelType.RESEARCH: 1000,
        ModelType.CONVERSATION: 1500,
        ModelType.ANALYSIS: 800,
        ModelType.SUMMARY: 2000
    }
    
    @classmethod
    def get_model_config(cls, model_type: ModelType) -> Dict[str, Any]:
        """
        Get configuration for a specific model type.
        
        Args:
            model_type: Type of model to configure
            
        Returns:
            Configuration dictionary
        """
        return {
            "model": model_type.value,
            "temperature": cls.DEFAULT_TEMPERATURE[model_type],
            "max_tokens": cls.DEFAULT_MAX_TOKENS[model_type],
            "api_key": os.getenv("OPENAI_API_KEY"),
            "request_timeout": 30,
            "max_retries": 3
        }
```

### 2. Enhanced LLM Wrapper

```python
class LLMWrapper:
    """
    Unified wrapper for LLM interactions with specialized methods.
    """
    
    def __init__(self, model_type: ModelType = ModelType.CONVERSATION):
        self.model_type = model_type
        self.config = LLMConfig.get_model_config(model_type)
        self.llm = self._initialize_llm()
        self.conversation_history: List[BaseMessage] = []
        
    def _initialize_llm(self) -> ChatOpenAI:
        """
        Initialize the LLM with configuration.
        
        Returns:
            Configured ChatOpenAI instance
        """
        return ChatOpenAI(
            model=self.config["model"],
            temperature=self.config["temperature"],
            max_tokens=self.config["max_tokens"],
            api_key=self.config["api_key"],
            request_timeout=self.config["request_timeout"],
            max_retries=self.config["max_retries"],
            callbacks=[TokenUsageCallback()]  # Track token usage
        )
    
    def generate_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        use_history: bool = False
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User prompt
            system_message: Optional system message
            context: Optional context dictionary
            use_history: Whether to include conversation history
            
        Returns:
            LLM response
        """
        messages = []
        
        # Add system message
        if system_message:
            messages.append(SystemMessage(content=system_message))
        
        # Add conversation history if requested
        if use_history:
            messages.extend(self.conversation_history[-10:])  # Last 10 messages
        
        # Add context if provided
        if context:
            context_str = self._format_context(context)
            messages.append(SystemMessage(content=f"Context: {context_str}"))
        
        # Add user prompt
        messages.append(HumanMessage(content=prompt))
        
        # Generate response
        response = self.llm.invoke(messages)
        
        # Update history
        if use_history:
            self.conversation_history.append(HumanMessage(content=prompt))
            self.conversation_history.append(response)
        
        return response.content
    
    def generate_structured_response(
        self,
        prompt: str,
        output_schema: Dict[str, Any],
        system_message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate a structured response following a schema.
        
        Args:
            prompt: User prompt
            output_schema: Expected output schema
            system_message: Optional system message
            
        Returns:
            Structured response dictionary
        """
        schema_str = json.dumps(output_schema, indent=2)
        
        enhanced_prompt = f"""
        {prompt}
        
        Please provide your response in the following JSON format:
        {schema_str}
        
        Ensure your response is valid JSON that matches this schema exactly.
        """
        
        response = self.generate_response(
            enhanced_prompt,
            system_message=system_message or "You are a helpful assistant that provides structured JSON responses."
        )
        
        # Parse JSON response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Fallback: extract JSON from response
            return self._extract_json(response)
    
    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dictionary for prompt."""
        formatted_parts = []
        for key, value in context.items():
            if isinstance(value, list):
                value_str = "\n".join([f"  - {item}" for item in value[:5]])  # Limit to 5 items
            elif isinstance(value, dict):
                value_str = json.dumps(value, indent=2)[:500]  # Limit length
            else:
                value_str = str(value)
            
            formatted_parts.append(f"{key}:\n{value_str}")
        
        return "\n\n".join(formatted_parts)
    
    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Extract JSON from text response."""
        # Try to find JSON block
        import re
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
        return {}
    
    def clear_history(self):
        """Clear conversation history."""
        self.conversation_history = []
```

### 3. Specialized LLM Methods

```python
class OnboardingLLM(LLMWrapper):
    """
    Specialized LLM wrapper for onboarding tasks.
    """
    
    def __init__(self):
        super().__init__(ModelType.CONVERSATION)
        self.research_llm = LLMWrapper(ModelType.RESEARCH)
        self.analysis_llm = LLMWrapper(ModelType.ANALYSIS)
        self.summary_llm = LLMWrapper(ModelType.SUMMARY)
    
    def generate_clarifying_questions(
        self,
        provider_profile: Dict[str, Any],
        missing_items: List[Dict[str, Any]],
        research_context: Optional[List[str]] = None
    ) -> List[str]:
        """
        Generate intelligent clarifying questions.
        
        Args:
            provider_profile: Current provider information
            missing_items: Items missing from checklist
            research_context: Optional research findings
            
        Returns:
            List of clarifying questions
        """
        prompt = f"""
        Based on the following provider profile and missing information,
        generate 2-3 concise, specific questions to gather the required details.
        
        Provider Profile:
        {json.dumps(provider_profile, indent=2)}
        
        Missing Information:
        {json.dumps(missing_items, indent=2)}
        
        {"Research Context: " + str(research_context[:3]) if research_context else ""}
        
        Guidelines:
        - Ask direct, specific questions
        - Avoid redundancy with already collected information
        - Prioritize critical business information
        - Be professional and conversational
        """
        
        response = self.generate_structured_response(
            prompt,
            output_schema={
                "questions": ["question1", "question2", "question3"]
            }
        )
        
        return response.get("questions", [])
    
    def analyze_research_results(
        self,
        query: str,
        search_results: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Analyze research results for relevant information.
        
        Args:
            query: Original search query
            search_results: List of search results
            
        Returns:
            Analyzed and extracted information
        """
        prompt = f"""
        Analyze the following search results for the query: "{query}"
        
        Search Results:
        {json.dumps(search_results[:5], indent=2)}
        
        Extract and summarize:
        1. Key facts relevant to the query
        2. Industry standards or requirements mentioned
        3. Common practices or recommendations
        4. Any specific regulations or compliance needs
        
        Focus on actionable information for service provider onboarding.
        """
        
        response = self.analysis_llm.generate_structured_response(
            prompt,
            output_schema={
                "key_facts": ["fact1", "fact2"],
                "standards": ["standard1", "standard2"],
                "practices": ["practice1", "practice2"],
                "regulations": ["regulation1", "regulation2"],
                "summary": "brief summary"
            }
        )
        
        return response
    
    def generate_provider_summary(
        self,
        provider_data: Dict[str, Any],
        checklist: List[Dict[str, Any]],
        research_notes: List[Dict[str, Any]]
    ) -> str:
        """
        Generate comprehensive provider summary.
        
        Args:
            provider_data: Complete provider information
            checklist: Completed checklist
            research_notes: Research findings
            
        Returns:
            Professional summary
        """
        prompt = f"""
        Create a professional summary for this service provider:
        
        Provider Information:
        {json.dumps(provider_data, indent=2)}
        
        Completed Checklist Items:
        {self._format_checklist(checklist)}
        
        Key Research Findings:
        {self._format_research(research_notes[:3])}
        
        Generate a comprehensive summary including:
        1. Provider Overview (2-3 sentences)
        2. Core Services Offered
        3. Key Qualifications and Expertise
        4. Client Requirements for Service Delivery
        5. Unique Value Propositions
        6. Recommended Next Steps
        
        Keep the tone professional and informative.
        """
        
        return self.summary_llm.generate_response(
            prompt,
            system_message="You are a professional business analyst creating provider summaries."
        )
    
    def validate_response(
        self,
        user_response: str,
        expected_format: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate and parse user responses.
        
        Args:
            user_response: Raw user response
            expected_format: Expected data format
            
        Returns:
            Validated and structured response
        """
        prompt = f"""
        Parse and validate the following user response according to the expected format:
        
        User Response: "{user_response}"
        
        Expected Format:
        {json.dumps(expected_format, indent=2)}
        
        Extract the relevant information and structure it according to the format.
        If information is missing or unclear, mark it as null.
        """
        
        return self.analysis_llm.generate_structured_response(
            prompt,
            output_schema=expected_format
        )
    
    def generate_follow_up_prompt(
        self,
        conversation_history: List[Dict[str, str]],
        current_status: str
    ) -> str:
        """
        Generate contextual follow-up prompts.
        
        Args:
            conversation_history: Recent conversation
            current_status: Current workflow status
            
        Returns:
            Follow-up prompt
        """
        prompt = f"""
        Based on the conversation history and current status,
        generate an appropriate follow-up message.
        
        Recent Conversation:
        {json.dumps(conversation_history[-3:], indent=2)}
        
        Current Status: {current_status}
        
        Generate a brief, friendly follow-up that:
        - Acknowledges what was discussed
        - Guides the next step
        - Maintains conversational flow
        """
        
        return self.generate_response(
            prompt,
            system_message="You are a friendly onboarding assistant."
        )
    
    def _format_checklist(self, checklist: List[Dict]) -> str:
        """Format checklist for prompts."""
        items = []
        for item in checklist:
            if item.get("status") == "VERIFIED":
                items.append(f"- {item['prompt']}: {item.get('value', 'Completed')}")
        return "\n".join(items) if items else "No items completed"
    
    def _format_research(self, research_notes: List[Dict]) -> str:
        """Format research notes for prompts."""
        notes = []
        for note in research_notes:
            if "summary" in note:
                notes.append(f"- {note['summary']}")
        return "\n".join(notes) if notes else "No research notes"
```

### 4. Prompt Templates

```python
class PromptTemplates:
    """
    Centralized prompt templates for consistent interactions.
    """
    
    SYSTEM_PROMPTS = {
        "onboarding_assistant": """
        You are a professional onboarding assistant for a platform connecting 
        service providers with clients. Your role is to:
        1. Gather essential information from service providers
        2. Ask clarifying questions based on research
        3. Maintain a friendly, professional tone
        4. Guide providers through the onboarding process efficiently
        """,
        
        "research_analyst": """
        You are a research analyst specializing in business services.
        Focus on extracting actionable information about:
        - Industry standards and requirements
        - Common practices and procedures
        - Regulatory compliance needs
        - Service delivery expectations
        """,
        
        "data_validator": """
        You are a data validation specialist. Your role is to:
        - Parse user inputs accurately
        - Identify missing or incomplete information
        - Validate data against expected formats
        - Flag potential issues or inconsistencies
        """
    }
    
    CONVERSATION_TEMPLATES = {
        "greeting": """
        Welcome! I'm here to help complete your service provider profile.
        Based on your {service_type} services, I'll need to gather some 
        information to match you with the right clients.
        """,
        
        "missing_info": """
        I notice we still need the following information:
        {missing_items}
        
        Could you please provide these details?
        """,
        
        "confirmation": """
        Thank you for providing that information. Let me confirm:
        {confirmation_items}
        
        Is this correct?
        """,
        
        "completion": """
        Excellent! Your profile is now complete. Here's a summary:
        {summary}
        
        You can now start receiving client inquiries matching your services.
        """
    }
    
    @classmethod
    def get_prompt(
        cls,
        template_type: str,
        template_name: str,
        **kwargs
    ) -> str:
        """
        Get a formatted prompt template.
        
        Args:
            template_type: Type of template (system or conversation)
            template_name: Name of the template
            **kwargs: Variables to format in the template
            
        Returns:
            Formatted prompt string
        """
        if template_type == "system":
            template = cls.SYSTEM_PROMPTS.get(template_name, "")
        elif template_type == "conversation":
            template = cls.CONVERSATION_TEMPLATES.get(template_name, "")
        else:
            return ""
        
        return template.format(**kwargs) if kwargs else template
```

### 5. Token Usage Tracking

```python
class TokenUsageCallback(BaseCallbackHandler):
    """
    Callback handler to track token usage.
    """
    
    def __init__(self):
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0
    
    def on_llm_end(self, response, **kwargs):
        """
        Called when LLM call ends.
        
        Args:
            response: LLM response object
        """
        if hasattr(response, 'llm_output') and response.llm_output:
            token_usage = response.llm_output.get('token_usage', {})
            
            self.prompt_tokens += token_usage.get('prompt_tokens', 0)
            self.completion_tokens += token_usage.get('completion_tokens', 0)
            self.total_tokens += token_usage.get('total_tokens', 0)
            self.request_count += 1
            
            # Calculate cost (example rates)
            model = response.llm_output.get('model_name', '')
            if 'gpt-4' in model:
                prompt_cost = self.prompt_tokens * 0.00003
                completion_cost = self.completion_tokens * 0.00006
            else:  # gpt-3.5-turbo
                prompt_cost = self.prompt_tokens * 0.0000005
                completion_cost = self.completion_tokens * 0.0000015
            
            self.total_cost += prompt_cost + completion_cost
    
    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get token usage statistics.
        
        Returns:
            Usage statistics dictionary
        """
        return {
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_cost": round(self.total_cost, 4),
            "request_count": self.request_count,
            "average_tokens_per_request": (
                self.total_tokens // self.request_count 
                if self.request_count > 0 else 0
            )
        }
    
    def reset(self):
        """Reset usage statistics."""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_cost = 0.0
        self.request_count = 0
```

## Configuration and Initialization

```python
# config/llm_config.py

def initialize_onboarding_llm() -> OnboardingLLM:
    """
    Initialize the onboarding LLM with environment configuration.
    
    Returns:
        Configured OnboardingLLM instance
    """
    # Ensure API key is set
    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY environment variable not set")
    
    # Create and return LLM instance
    return OnboardingLLM()

# Usage example
def example_usage():
    """Example of using the LLM wrapper."""
    llm = initialize_onboarding_llm()
    
    # Generate clarifying questions
    questions = llm.generate_clarifying_questions(
        provider_profile={"name": "ABC Tax Services", "type": "tax"},
        missing_items=[{"key": "license_number", "prompt": "Professional license number"}]
    )
    
    # Analyze research results
    analysis = llm.analyze_research_results(
        query="UAE tax requirements",
        search_results=[{"content": "UAE requires VAT registration..."}]
    )
    
    # Generate summary
    summary = llm.generate_provider_summary(
        provider_data={"name": "ABC Tax Services"},
        checklist=[],
        research_notes=[]
    )
    
    return questions, analysis, summary
```