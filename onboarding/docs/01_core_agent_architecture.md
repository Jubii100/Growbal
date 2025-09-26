# Core Onboarding Agent Architecture

## Overview
The onboarding agent is a stateful, multi-behavioral system built with LangGraph that conducts provider onboarding through conversational interactions, background research, and administrative tasks.

## Agent Components

### 1. Main Agent Graph Structure

```python
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from typing import Annotated, List, Dict, Any, Literal
from langgraph.graph.message import add_messages

class OnboardingAgent:
    """
    Main onboarding agent orchestrating the complete workflow.
    Combines research, conversation, and administrative capabilities.
    """
    
    def __init__(self, llm: ChatOpenAI, tools: List):
        self.llm = llm
        self.tools = tools
        self.graph = self._build_graph()
        
    def _build_graph(self) -> StateGraph:
        """
        Construct the agent workflow graph with all nodes and edges.
        """
        graph = StateGraph(OnboardingState)
        
        # Add main behavior nodes
        graph.add_node("intake", self.intake_node)
        graph.add_node("research", self.research_node)
        graph.add_node("clarify", self.clarification_node)
        graph.add_node("validate", self.validation_node)
        graph.add_node("summarize", self.summarization_node)
        graph.add_node("human_review", self.human_review_node)
        
        # Define workflow edges
        graph.add_edge(START, "intake")
        graph.add_conditional_edges(
            "intake",
            self.route_after_intake,
            {
                "research": "research",
                "clarify": "clarify",
                "validate": "validate"
            }
        )
        graph.add_edge("research", "clarify")
        graph.add_conditional_edges(
            "clarify",
            self.check_completion_status,
            {
                "more_info": "intake",
                "ready": "validate",
                "human": "human_review"
            }
        )
        graph.add_edge("validate", "summarize")
        graph.add_edge("summarize", END)
        graph.add_edge("human_review", "clarify")
        
        return graph.compile()
```

### 2. Agent Behaviors

#### Research Behavior
Conducts background research using multiple search tools to gather context about the provider and their services.

```python
async def research_node(self, state: OnboardingState):
    """
    Execute background research based on provider profile and gaps.
    """
    provider = state["provider_profile"]
    gaps = self._identify_information_gaps(state["checklist"])
    
    # Create targeted research queries
    queries = self._generate_research_queries(provider, gaps)
    
    # Execute parallel searches
    research_tasks = []
    for query in queries:
        research_tasks.append(self._execute_research(query))
    
    results = await asyncio.gather(*research_tasks)
    
    # Store results for RAG processing
    return {
        "research_notes": results,
        "messages": [AIMessage(content="Background research completed")]
    }
```

#### Conversational Behavior
Manages the dialogue with the provider, asking targeted questions based on research findings and checklist requirements.

```python
def clarification_node(self, state: OnboardingState):
    """
    Generate intelligent follow-up questions based on research and checklist.
    """
    # Analyze what information is still needed
    missing_items = [
        item for item in state["checklist"]
        if item["status"] in ["PENDING", "ASKED"] and item["required"]
    ]
    
    # Use RAG to find relevant context from research
    context = self._retrieve_relevant_context(
        missing_items, 
        state["research_notes"]
    )
    
    # Generate targeted questions
    questions = self._generate_smart_questions(missing_items, context)
    
    return {
        "messages": [AIMessage(content=questions)],
        "checklist": self._update_checklist_status(state["checklist"], "ASKED")
    }
```

#### Administrative Behavior
Handles data validation, persistence, and workflow status management.

```python
def validation_node(self, state: OnboardingState):
    """
    Validate collected information and update statuses.
    """
    checklist = state["checklist"]
    
    # Validate required fields
    validation_results = self._validate_checklist_items(checklist)
    
    # Determine workflow status
    if all(item["valid"] for item in validation_results if item["required"]):
        status = "READY_TO_SAVE"
    elif self._needs_escalation(validation_results):
        status = "ESCALATE"
    else:
        status = "NEEDS_INFO"
    
    return {
        "status": status,
        "checklist": self._update_with_validation(checklist, validation_results)
    }
```

### 3. Routing Logic

```python
def route_after_intake(self, state: OnboardingState) -> str:
    """
    Determine next step based on current state completeness.
    """
    checklist = state["checklist"]
    pending_required = sum(
        1 for item in checklist 
        if item["required"] and item["status"] == "PENDING"
    )
    
    if pending_required > 3:
        return "research"  # Need background research first
    elif pending_required > 0:
        return "clarify"   # Ask specific questions
    else:
        return "validate"  # Ready for validation
        
def check_completion_status(self, state: OnboardingState) -> str:
    """
    Check if we have enough information to proceed.
    """
    if state["status"] == "ESCALATE":
        return "human"
    elif self._is_checklist_complete(state["checklist"]):
        return "ready"
    else:
        return "more_info"
```

## Integration with React Agent

For more complex tool orchestration, integrate with LangGraph's create_react_agent:

```python
from langgraph.prebuilt import create_react_agent

def create_research_subagent(llm, tools):
    """
    Create a ReAct agent for research tasks.
    """
    return create_react_agent(
        llm,
        tools,
        state_modifier="You are a research assistant gathering information about service providers."
    )

# Use within main agent
class OnboardingAgent:
    def __init__(self, llm, tools):
        self.research_agent = create_research_subagent(llm, tools)
        # ... rest of initialization
    
    async def research_node(self, state):
        # Delegate complex research to ReAct agent
        research_state = {
            "messages": [HumanMessage(content=f"Research {state['provider_profile']['name']}")],
            "context": state["provider_profile"]
        }
        result = await self.research_agent.ainvoke(research_state)
        return {"research_notes": result["messages"][-1].content}
```

## Execution Flow

1. **Intake Phase**: Collect initial provider information
2. **Research Phase**: Conduct background research if needed
3. **Clarification Loop**: Ask targeted questions based on research
4. **Validation Phase**: Verify all required information is present
5. **Human Review**: Escalate if needed (human-in-the-loop)
6. **Summarization**: Generate final provider profile

## Key Design Principles

- **State-driven**: All decisions based on current state
- **Modular behaviors**: Separate research, conversation, and admin logic
- **Parallel processing**: Execute multiple searches concurrently
- **RAG integration**: Use vector search for contextual question generation
- **Human-in-the-loop**: Escalation paths for complex cases
- **Progressive disclosure**: Only ask necessary questions based on research