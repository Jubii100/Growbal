"""
State Management for the Two-Part Research Onboarding System
"""
from typing import TypedDict, Dict, Any, List, Optional
from enum import Enum
from datetime import datetime
from llm_wrapper import OnboardingLLM


class WorkflowDecision(Enum):
    """Workflow decision points"""
    PROCEED_TO_CHECKLIST_RESEARCH = "proceed_to_checklist_research"
    PROCEED_TO_ANSWER_RESEARCH = "proceed_to_answer_research"
    SKIP_RESEARCH = "skip_research"
    ASK_NEXT_QUESTION = "ask_next_question"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    COMPLETE_SESSION = "complete_session"
    UPDATE_CHECKLIST = "update_checklist"
    REQUEST_CONFIRMATION = "request_confirmation"
    ASK_CLARIFYING_QUESTION = "ask_clarifying_question"


class ResearchPhase(Enum):
    """Research phases for two-part system"""
    CHECKLIST_CUSTOMIZATION = "checklist_customization"
    ANSWER_GATHERING = "answer_gathering"


class ProfileMatch:
    """Profile match data structure for Django integration"""
    def __init__(self, profile_id: int, similarity_score: float, profile_text: str):
        self.profile_id = profile_id
        self.similarity_score = similarity_score
        self.profile_text = profile_text


class EvolvedOnboardingState(TypedDict):
    """
    Enhanced state for two-part research workflow.
    """
    
    # Provider and user data
    provider_profile: Dict[str, Any]
    user_profile: Dict[str, Any]
    
    # Conversation management
    messages: List[Dict[str, Any]]
    last_question: Optional[str]
    last_question_key: Optional[str]
    last_user_response: Optional[str]
    awaiting_response: bool
    
    # Checklist management
    checklist: List[Dict[str, Any]]
    completion_metrics: Dict[str, float]
    
    # Two-part research system
    checklist_research_results: List[Dict[str, Any]]
    checklist_research_completed: bool
    checklist_modifications: Dict[str, Any]
    answer_research_results: List[Dict[str, Any]]
    research_answers: Dict[str, Any]
    research_content: str  # Research content from initial state initialization
    
    # Research evaluation and confirmation
    answer_evaluation_results: Dict[str, str]
    research_evaluation_decision: WorkflowDecision
    awaiting_confirmation: bool
    pending_confirmations: List[Dict[str, Any]]
    confirmation_result: Optional[str]
    
    # Research timestamps
    checklist_research_timestamp: Optional[str]
    answer_research_timestamp: Optional[str]
    
    # RAG system
    rag_collection_id: Optional[str]
    
    # Workflow control
    workflow_status: str
    evaluation: Optional[Dict[str, Any]]
    validation_status: Optional[str]
    validation_errors: Optional[List[str]]
    escalation_reason: Optional[str]
    
    # Metadata
    started_at: str
    last_activity: str
    session_metadata: Dict[str, Any]


def initialize_state(
    provider_profile: Dict[str, Any],
) -> EvolvedOnboardingState:
    """Initialize a new onboarding state with robust retry logic"""
    import time
    
    now = datetime.utcnow().isoformat()

    # Add robust retry and hard failure if checklist is empty
    max_attempts = 3
    last_error = None
    initial_checklist = []
    research_content = ""
    
    for attempt in range(1, max_attempts + 1):
        try:
            initial_checklist, research_content = get_initial_checklist_with_research_from_profile_text(
                provider_profile.get("profile_text", "")
            )
            if initial_checklist and isinstance(initial_checklist, list) and len(initial_checklist) > 0:
                break
            else:
                raise RuntimeError(f"LLM returned empty checklist (attempt {attempt}/{max_attempts})")
        except Exception as e:
            last_error = e
            print(f"⚠️ State initialization attempt {attempt} failed: {e}")
            if attempt < max_attempts:
                time.sleep(1.0)
            continue
    
    if not initial_checklist:
        raise RuntimeError(f"Failed to initialize checklist after {max_attempts} attempts. Last error: {last_error}")
    
    return {
        
        # Provider and user data
        "provider_profile": provider_profile,
        "user_profile": {},
        
        # Conversation management
        "messages": [],
        "last_question": None,
        "last_question_key": None,
        "last_user_response": None,
        "awaiting_response": False,
        
        # Checklist management
        "checklist": initial_checklist,
        "completion_metrics": {"completion_rate": 0.0},
        
        # Two-part research system
        "checklist_research_results": [],
        "checklist_research_completed": False,
        "checklist_modifications": {},
        "answer_research_results": [],
        "research_answers": {},
        "research_content": research_content,  # Captured from initial checklist generation
        
        # Research evaluation and confirmation
        "answer_evaluation_results": {},
        "research_evaluation_decision": WorkflowDecision.SKIP_RESEARCH,
        "awaiting_confirmation": False,
        "pending_confirmations": [],
        "confirmation_result": None,
        
        # Research timestamps
        "checklist_research_timestamp": None,
        "answer_research_timestamp": None,
        
        # RAG system
        "rag_collection_id": None,
        
        # Workflow control
        "workflow_status": "initialized",
        "evaluation": None,
        "validation_status": None,
        "validation_errors": None,
        "escalation_reason": None,
        
        # Metadata
        "started_at": now,
        "last_activity": now,
        "session_metadata": {}
    }


def get_initial_checklist(profile_text: str) -> List[Dict[str, Any]]:
    """Get initial checklist based on profile text using the LLM."""
    return get_initial_checklist_from_profile_text(profile_text)


def get_initial_checklist_from_profile_text(profile_text: str) -> List[Dict[str, Any]]:
    """Invoke the LLM to produce the initial checklist structure.

    The resulting items must adhere to the schema expected by the workflow agent:
    key, prompt, required, status (PENDING), value (None)
    """
    checklist_items, research_content = get_initial_checklist_with_research_from_profile_text(profile_text)
    return checklist_items, research_content


def get_initial_checklist_with_research_from_profile_text(profile_text: str) -> tuple[List[Dict[str, Any]], str]:
    """Invoke the LLM to produce the initial checklist structure and return research content.

    Returns:
        tuple: (checklist_items, research_content)
            - checklist_items: List with schema expected by workflow agent: key, prompt, required, status (PENDING), value (None)
            - research_content: String containing the research content used for generation
    """
    llm = OnboardingLLM()
    checklist_items, research_content = llm.generate_initial_checklist_with_research(profile_text=profile_text)
    
    # Fallback safety: ensure minimal shape
    normalized_items: List[Dict[str, Any]] = []
    for item in checklist_items:
        key = str(item.get("key", "")).strip() or "info"
        prompt = str(item.get("prompt", "")).strip()
        if not prompt:
            # Synthesize a sensible prompt if missing
            key_text = key.replace("_", " ").title()
            prompt = f"Please provide your {key_text}."
        normalized_items.append({
            "key": key,
            "prompt": prompt,
            "required": bool(item.get("required", True)),
            "status": "PENDING",
            "value": None,
        })
    
    return normalized_items, research_content