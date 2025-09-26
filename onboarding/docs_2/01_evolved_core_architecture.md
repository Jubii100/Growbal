# Evolved Core Agent Architecture

## System Architecture Overview

The evolved onboarding agent is built on a state-driven, event-sourced architecture that enables dynamic workflow adaptation, intelligent research integration, and seamless human-in-the-loop capabilities.

## Core Components

### 1. Adaptive Workflow Engine

```python
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any, List, Optional
from enum import Enum

class WorkflowDecision(Enum):
    """Workflow decision points"""
    PROCEED_TO_RESEARCH = "proceed_to_research"
    SKIP_RESEARCH = "skip_research"
    ASK_NEXT_QUESTION = "ask_next_question"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    COMPLETE_SESSION = "complete_session"
    UPDATE_CHECKLIST = "update_checklist"

class AdaptiveOnboardingAgent:
    """
    Evolved onboarding agent with dynamic workflow adaptation.
    """
    
    def __init__(self, llm, tools, db_connection, rag_system):
        self.llm = llm
        self.tools = tools
        self.db = db_connection
        self.rag = rag_system
        self.graph = self._build_adaptive_graph()
        
    def _build_adaptive_graph(self) -> StateGraph:
        """
        Construct the adaptive workflow graph.
        """
        graph = StateGraph(EvolvedOnboardingState)
        
        # Core workflow nodes
        graph.add_node("intake", self.intake_phase_node)
        graph.add_node("research_decision", self.research_decision_node)
        graph.add_node("conduct_research", self.conduct_research_node)
        graph.add_node("parse_and_index", self.parse_and_index_node)
        graph.add_node("update_checklist", self.update_checklist_node)
        graph.add_node("generate_question", self.generate_sequential_question_node)
        graph.add_node("process_response", self.process_user_response_node)
        graph.add_node("evaluate_continuation", self.evaluate_continuation_node)
        graph.add_node("escalation", self.escalation_node)
        graph.add_node("final_confirmation", self.final_confirmation_node)
        graph.add_node("save_results", self.save_results_node)
        
        # Define the adaptive workflow
        graph.add_edge(START, "intake")
        
        # Research decision branch
        graph.add_conditional_edges(
            "intake",
            self.route_after_intake,
            {
                WorkflowDecision.PROCEED_TO_RESEARCH: "research_decision",
                WorkflowDecision.SKIP_RESEARCH: "update_checklist",
                WorkflowDecision.ESCALATE_TO_HUMAN: "escalation"
            }
        )
        
        # Research workflow
        graph.add_conditional_edges(
            "research_decision",
            self.should_conduct_research,
            {
                True: "conduct_research",
                False: "update_checklist"
            }
        )
        graph.add_edge("conduct_research", "parse_and_index")
        graph.add_edge("parse_and_index", "update_checklist")
        
        # Main question loop
        graph.add_edge("update_checklist", "generate_question")
        graph.add_edge("generate_question", "process_response")
        graph.add_edge("process_response", "evaluate_continuation")
        
        # Continuation decision
        graph.add_conditional_edges(
            "evaluate_continuation",
            self.determine_next_action,
            {
                WorkflowDecision.PROCEED_TO_RESEARCH: "research_decision",
                WorkflowDecision.ASK_NEXT_QUESTION: "update_checklist",
                WorkflowDecision.ESCALATE_TO_HUMAN: "escalation",
                WorkflowDecision.COMPLETE_SESSION: "final_confirmation"
            }
        )
        
        # Completion flow
        graph.add_edge("final_confirmation", "save_results")
        graph.add_edge("save_results", END)
        
        # Escalation can return to main flow
        graph.add_conditional_edges(
            "escalation",
            self.route_after_escalation,
            {
                "continue": "update_checklist",
                "complete": "final_confirmation",
                "abort": END
            }
        )
        
        return graph.compile()
```

### 2. Intake Phase Implementation

```python
async def intake_phase_node(self, state: EvolvedOnboardingState):
    """
    Initial intake phase with intelligent routing.
    """
    # Load user profile from database
    user_profile = await self.db.get_user_profile(state["user_id"])
    
    # Generate initial intake question based on service type and profile
    intake_question = self._generate_intake_question(
        service_type=state["service_type"],
        user_profile=user_profile
    )
    
    # Present question and await response
    state["messages"].append(AIMessage(content=intake_question))
    
    # Store user profile in state
    state["user_profile"] = user_profile
    
    # Initialize checklist based on service type
    state["checklist"] = self._initialize_checklist(
        service_type=state["service_type"],
        user_profile=user_profile
    )
    
    return state

def route_after_intake(self, state: EvolvedOnboardingState) -> WorkflowDecision:
    """
    Determine workflow path after intake response.
    """
    last_message = state["messages"][-1]
    
    # Analyze response quality and completeness
    response_analysis = self._analyze_intake_response(
        response=last_message.content,
        checklist=state["checklist"],
        user_profile=state["user_profile"]
    )
    
    # Decision logic
    if response_analysis["satisfaction_score"] >= 0.8:
        # Response is comprehensive, skip pre-research
        return WorkflowDecision.SKIP_RESEARCH
    elif response_analysis["confusion_detected"]:
        # User seems confused, escalate
        return WorkflowDecision.ESCALATE_TO_HUMAN
    else:
        # Proceed with research to gather context
        return WorkflowDecision.PROCEED_TO_RESEARCH

def _analyze_intake_response(self, response: str, checklist: List, user_profile: Dict) -> Dict:
    """
    Analyze the quality and completeness of intake response.
    """
    analysis = {
        "satisfaction_score": 0.0,
        "confusion_detected": False,
        "items_addressed": [],
        "gaps_identified": []
    }
    
    # Use LLM to analyze response against checklist
    prompt = f"""
    Analyze this intake response against the checklist requirements:
    
    Response: {response}
    
    Checklist items to evaluate:
    {json.dumps([item for item in checklist[:5]], indent=2)}
    
    User Profile Context:
    {json.dumps(user_profile, indent=2)}
    
    Provide:
    1. Satisfaction score (0-1)
    2. Which checklist items were addressed
    3. Information gaps
    4. Signs of confusion (yes/no)
    """
    
    llm_analysis = self.llm.invoke(prompt)
    # Parse LLM response and update analysis dict
    
    return analysis
```

### 3. Dynamic Research Engine

```python
class ResearchEngine:
    """
    Intelligent research engine with adaptive query generation.
    """
    
    def __init__(self, search_tools, rag_system):
        self.search_tools = search_tools
        self.rag = rag_system
        
    async def conduct_research_node(self, state: EvolvedOnboardingState):
        """
        Conduct targeted research based on checklist gaps.
        """
        # Identify information gaps
        gaps = self._identify_research_gaps(
            checklist=state["checklist"],
            user_responses=state["messages"],
            user_profile=state["user_profile"]
        )
        
        # Generate research queries
        queries = self._generate_research_queries(
            gaps=gaps,
            provider_info=state["provider_profile"],
            context=state.get("research_context", {})
        )
        
        # Execute parallel research
        research_results = await self._execute_parallel_research(queries)
        
        # Store raw results
        state["research_notes"] = research_results
        state["research_timestamp"] = datetime.utcnow().isoformat()
        
        return state
    
    async def parse_and_index_node(self, state: EvolvedOnboardingState):
        """
        Parse research results and index in RAG system.
        """
        if not state.get("research_notes"):
            return state
        
        # Parse and structure research findings
        parsed_findings = self._parse_research_findings(state["research_notes"])
        
        # Index in RAG system if significant findings
        if parsed_findings:
            collection_id = await self.rag.index_findings(
                findings=parsed_findings,
                session_id=state["session_id"],
                metadata={
                    "provider_id": state.get("provider_id"),
                    "service_type": state["service_type"],
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            state["rag_collection_id"] = collection_id
            
        # Update state with parsed findings
        state["parsed_research"] = parsed_findings
        
        return state
    
    def _identify_research_gaps(self, checklist: List, user_responses: List, user_profile: Dict) -> List[Dict]:
        """
        Identify what information needs research.
        """
        gaps = []
        
        for item in checklist:
            if item["status"] == "PENDING" and item.get("requires_research"):
                gap = {
                    "checklist_item": item["key"],
                    "information_needed": item["prompt"],
                    "priority": item.get("priority", "medium"),
                    "context": self._extract_relevant_context(item, user_responses)
                }
                gaps.append(gap)
        
        return sorted(gaps, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["priority"]])
    
    def _generate_research_queries(self, gaps: List[Dict], provider_info: Dict, context: Dict) -> List[Dict]:
        """
        Generate optimized research queries.
        """
        queries = []
        
        for gap in gaps[:5]:  # Limit to top 5 gaps
            # Generate contextual query
            query = {
                "query": self._formulate_query(gap, provider_info),
                "source": self._determine_best_source(gap),
                "checklist_item": gap["checklist_item"],
                "priority": gap["priority"]
            }
            queries.append(query)
        
        return queries
    
    async def _execute_parallel_research(self, queries: List[Dict]) -> List[Dict]:
        """
        Execute research queries in parallel.
        """
        tasks = []
        for query in queries:
            if query["source"] == "web":
                tasks.append(self.search_tools.search_web(query["query"]))
            elif query["source"] == "business":
                tasks.append(self.search_tools.search_business_info(query["query"]))
            elif query["source"] == "standards":
                tasks.append(self.search_tools.search_industry_standards(query["query"]))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [
            {
                "query": q,
                "result": r,
                "timestamp": datetime.utcnow().isoformat()
            }
            for q, r in zip(queries, results)
            if not isinstance(r, Exception)
        ]
```

### 4. Adaptive Checklist Manager

```python
class ChecklistManager:
    """
    Manages dynamic checklist updates based on research and responses.
    """
    
    def update_checklist_node(self, state: EvolvedOnboardingState):
        """
        Update checklist based on all available information.
        """
        checklist = state["checklist"]
        
        # Update from user responses
        if state.get("last_user_response"):
            checklist = self._update_from_response(
                checklist=checklist,
                response=state["last_user_response"],
                question_key=state.get("last_question_key")
            )
        
        # Update from research findings
        if state.get("parsed_research"):
            checklist = self._update_from_research(
                checklist=checklist,
                research=state["parsed_research"],
                confidence_threshold=0.7
            )
        
        # Add dynamic items based on discoveries
        checklist = self._add_dynamic_items(
            checklist=checklist,
            user_profile=state["user_profile"],
            research=state.get("parsed_research", {})
        )
        
        # Remove irrelevant items
        checklist = self._remove_irrelevant_items(
            checklist=checklist,
            service_type=state["service_type"],
            provider_profile=state["provider_profile"]
        )
        
        # Reorder based on priority and dependencies
        checklist = self._reorder_checklist(checklist)
        
        # Update completion metrics
        state["completion_metrics"] = self._calculate_completion(checklist)
        state["checklist"] = checklist
        
        return state
    
    def _update_from_response(self, checklist: List, response: str, question_key: str) -> List:
        """
        Update checklist item based on user response.
        """
        for item in checklist:
            if item["key"] == question_key:
                item["value"] = response
                item["status"] = "ANSWERED"
                item["answered_at"] = datetime.utcnow().isoformat()
                
                # Validate response
                validation = self._validate_response(response, item)
                if validation["valid"]:
                    item["status"] = "VERIFIED"
                else:
                    item["validation_errors"] = validation["errors"]
        
        return checklist
    
    def _update_from_research(self, checklist: List, research: Dict, confidence_threshold: float) -> List:
        """
        Auto-fill checklist items from research with confidence scoring.
        """
        for item in checklist:
            if item["status"] == "PENDING":
                # Try to find relevant research finding
                finding = self._find_relevant_finding(item, research)
                
                if finding and finding["confidence"] >= confidence_threshold:
                    item["value"] = finding["value"]
                    item["status"] = "AUTO_FILLED"
                    item["source"] = "research"
                    item["confidence"] = finding["confidence"]
                    item["research_ref"] = finding["reference"]
        
        return checklist
    
    def _add_dynamic_items(self, checklist: List, user_profile: Dict, research: Dict) -> List:
        """
        Add new checklist items based on discoveries.
        """
        new_items = []
        
        # Check if research revealed additional requirements
        if research.get("additional_requirements"):
            for req in research["additional_requirements"]:
                if not any(item["key"] == req["key"] for item in checklist):
                    new_item = {
                        "key": req["key"],
                        "prompt": req["prompt"],
                        "category": req.get("category", "dynamic"),
                        "required": req.get("required", False),
                        "status": "PENDING",
                        "source": "research_discovery",
                        "added_at": datetime.utcnow().isoformat()
                    }
                    new_items.append(new_item)
        
        return checklist + new_items
    
    def _remove_irrelevant_items(self, checklist: List, service_type: str, provider_profile: Dict) -> List:
        """
        Remove items that don't apply to this provider.
        """
        relevant_items = []
        
        for item in checklist:
            # Check relevance based on service type and profile
            if self._is_relevant(item, service_type, provider_profile):
                relevant_items.append(item)
            else:
                # Log removal for audit
                item["status"] = "NOT_APPLICABLE"
                item["removed_at"] = datetime.utcnow().isoformat()
        
        return relevant_items
    
    def _reorder_checklist(self, checklist: List) -> List:
        """
        Reorder checklist based on priority and dependencies.
        """
        # Separate by status
        pending = [i for i in checklist if i["status"] == "PENDING"]
        asked = [i for i in checklist if i["status"] == "ASKED"]
        completed = [i for i in checklist if i["status"] in ["VERIFIED", "AUTO_FILLED"]]
        
        # Sort pending by priority and dependencies
        pending = self._topological_sort(pending)
        
        return completed + asked + pending
```

### 5. Sequential Question Generator

```python
class QuestionGenerator:
    """
    Generates contextual, sequential questions.
    """
    
    def generate_sequential_question_node(self, state: EvolvedOnboardingState):
        """
        Generate the next question in sequence.
        """
        # Get next pending item from checklist
        next_item = self._get_next_pending_item(state["checklist"])
        
        if not next_item:
            # No more questions, move to completion
            state["no_more_questions"] = True
            return state
        
        # Retrieve context from RAG if available
        context = ""
        if state.get("rag_collection_id"):
            context = self.rag.retrieve_context(
                query=next_item["prompt"],
                collection_id=state["rag_collection_id"],
                top_k=3
            )
        
        # Generate contextual question
        question = self._formulate_contextual_question(
            item=next_item,
            previous_responses=state["messages"][-5:],  # Last 5 messages
            research_context=context,
            user_profile=state["user_profile"]
        )
        
        # Update state
        state["messages"].append(AIMessage(content=question))
        state["last_question_key"] = next_item["key"]
        state["awaiting_response"] = True
        
        # Mark item as asked
        for item in state["checklist"]:
            if item["key"] == next_item["key"]:
                item["status"] = "ASKED"
                item["asked_at"] = datetime.utcnow().isoformat()
                item["attempts"] = item.get("attempts", 0) + 1
        
        return state
    
    def _get_next_pending_item(self, checklist: List) -> Optional[Dict]:
        """
        Get the next item to ask about.
        """
        # Priority: Required items first, then optional
        for item in checklist:
            if item["status"] == "PENDING" and item["required"]:
                return item
        
        for item in checklist:
            if item["status"] == "PENDING"]:
                return item
        
        return None
    
    def _formulate_contextual_question(self, item: Dict, previous_responses: List, 
                                      research_context: str, user_profile: Dict) -> str:
        """
        Create a contextual, user-friendly question.
        """
        prompt = f"""
        Generate a clear, contextual question for this checklist item:
        
        Item: {json.dumps(item)}
        
        Previous conversation context:
        {self._format_conversation(previous_responses)}
        
        Research context (if relevant):
        {research_context[:500]}
        
        User profile:
        {json.dumps(user_profile, indent=2)}
        
        Requirements:
        1. Be conversational and friendly
        2. Reference previous answers if relevant
        3. Include helpful context from research if available
        4. Be specific about what information is needed
        5. Keep it concise and clear
        """
        
        response = self.llm.invoke(prompt)
        return response.content
```

### 6. Response Processing and Loop Evaluation

```python
class ResponseProcessor:
    """
    Processes user responses and evaluates loop continuation.
    """
    
    def process_user_response_node(self, state: EvolvedOnboardingState):
        """
        Process and validate user response.
        """
        # Get the latest user response
        last_message = state["messages"][-1]
        
        if last_message.role != "user":
            # Waiting for user response
            return state
        
        # Store response
        state["last_user_response"] = last_message.content
        
        # Validate and process response
        validation_result = self._validate_and_process(
            response=last_message.content,
            question_key=state["last_question_key"],
            checklist=state["checklist"]
        )
        
        # Update state based on validation
        if validation_result["valid"]:
            state["validation_status"] = "SUCCESS"
        else:
            state["validation_status"] = "FAILED"
            state["validation_errors"] = validation_result["errors"]
        
        state["awaiting_response"] = False
        
        return state
    
    def evaluate_continuation_node(self, state: EvolvedOnboardingState):
        """
        Evaluate whether to continue the loop or take other actions.
        """
        evaluation = {
            "continue_loop": True,
            "next_action": None,
            "reason": ""
        }
        
        # Check completion
        if self._is_checklist_complete(state["checklist"]):
            evaluation["continue_loop"] = False
            evaluation["next_action"] = WorkflowDecision.COMPLETE_SESSION
            evaluation["reason"] = "All required items completed"
        
        # Check for escalation needs
        elif self._needs_escalation(state):
            evaluation["continue_loop"] = False
            evaluation["next_action"] = WorkflowDecision.ESCALATE_TO_HUMAN
            evaluation["reason"] = state.get("escalation_reason", "Complex situation")
        
        # Check if research would help
        elif self._should_conduct_research(state):
            evaluation["next_action"] = WorkflowDecision.PROCEED_TO_RESEARCH
            evaluation["reason"] = "Additional research needed"
        
        # Continue with next question
        else:
            evaluation["next_action"] = WorkflowDecision.ASK_NEXT_QUESTION
            evaluation["reason"] = "Continue collecting information"
        
        state["evaluation"] = evaluation
        return state
    
    def determine_next_action(self, state: EvolvedOnboardingState) -> WorkflowDecision:
        """
        Route to next action based on evaluation.
        """
        return state["evaluation"]["next_action"]
    
    def _is_checklist_complete(self, checklist: List) -> bool:
        """
        Check if all required items are completed.
        """
        required_items = [i for i in checklist if i["required"]]
        completed_required = [
            i for i in required_items 
            if i["status"] in ["VERIFIED", "AUTO_FILLED"]
        ]
        
        return len(completed_required) == len(required_items)
    
    def _needs_escalation(self, state: EvolvedOnboardingState) -> bool:
        """
        Determine if human escalation is needed.
        """
        # Check explicit request
        if "help" in state.get("last_user_response", "").lower():
            state["escalation_reason"] = "User requested help"
            return True
        
        # Check repeated failures
        for item in state["checklist"]:
            if item.get("attempts", 0) > 3:
                state["escalation_reason"] = f"Multiple attempts on {item['key']}"
                return True
        
        # Check validation failures
        if state.get("validation_status") == "FAILED":
            failure_count = state.get("validation_failure_count", 0) + 1
            state["validation_failure_count"] = failure_count
            if failure_count > 2:
                state["escalation_reason"] = "Repeated validation failures"
                return True
        
        return False
    
    def _should_conduct_research(self, state: EvolvedOnboardingState) -> bool:
        """
        Determine if research would be beneficial.
        """
        # Check if enough pending items warrant research
        pending_count = sum(1 for i in state["checklist"] if i["status"] == "PENDING")
        
        # Research if many items pending and no recent research
        if pending_count > 5:
            last_research = state.get("research_timestamp")
            if not last_research:
                return True
            
            # Check time since last research
            time_since = datetime.utcnow() - datetime.fromisoformat(last_research)
            if time_since.total_seconds() > 600:  # 10 minutes
                return True
        
        return False
```

## State Management

```python
from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

class EvolvedOnboardingState(TypedDict):
    """
    Complete state for the evolved onboarding workflow.
    """
    # Session identification
    session_id: str
    user_id: str
    provider_id: Optional[str]
    
    # Provider and user data
    provider_profile: Dict[str, Any]
    user_profile: Dict[str, Any]
    service_type: str
    
    # Conversation management
    messages: List[Dict[str, Any]]
    last_question_key: Optional[str]
    last_user_response: Optional[str]
    awaiting_response: bool
    
    # Checklist management
    checklist: List[Dict[str, Any]]
    completion_metrics: Dict[str, float]
    
    # Research and RAG
    research_notes: List[Dict[str, Any]]
    parsed_research: Optional[Dict[str, Any]]
    rag_collection_id: Optional[str]
    research_timestamp: Optional[str]
    research_context: Dict[str, Any]
    
    # Workflow control
    workflow_status: str
    evaluation: Optional[Dict[str, Any]]
    validation_status: Optional[str]
    validation_errors: Optional[List[str]]
    validation_failure_count: int
    escalation_reason: Optional[str]
    no_more_questions: bool
    
    # Metadata
    started_at: str
    last_activity: str
    session_metadata: Dict[str, Any]
```

## Integration Points

### Database Integration
- Real-time user profile retrieval
- Session state persistence
- Checklist template management
- Final data storage

### RAG System Integration
- Research document indexing
- Contextual retrieval for questions
- Knowledge base expansion
- Semantic search capabilities

### Human-in-the-Loop Integration
- Escalation triggers and handoff
- Review and approval workflows
- Manual override capabilities
- Quality control checkpoints