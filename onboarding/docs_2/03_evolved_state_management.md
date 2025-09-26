# Evolved State Management and Checklist System

## Overview

The evolved state management system provides a robust, event-sourced approach to tracking the onboarding workflow state, with dynamic checklist management that adapts based on user responses, research findings, and profile data.

## Core State Architecture

### 1. Enhanced State Definition

```python
from typing import TypedDict, List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

class WorkflowStatus(Enum):
    """Comprehensive workflow status indicators"""
    # Initialization states
    INITIALIZING = "initializing"
    INTAKE_PHASE = "intake_phase"
    
    # Research states
    RESEARCHING = "researching"
    PARSING_RESEARCH = "parsing_research"
    INDEXING_RESEARCH = "indexing_research"
    
    # Interaction states
    ASKING_QUESTION = "asking_question"
    AWAITING_RESPONSE = "awaiting_response"
    PROCESSING_RESPONSE = "processing_response"
    
    # Decision states
    EVALUATING_CONTINUATION = "evaluating_continuation"
    UPDATING_CHECKLIST = "updating_checklist"
    
    # Completion states
    READY_FOR_CONFIRMATION = "ready_for_confirmation"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    SAVING_RESULTS = "saving_results"
    COMPLETED = "completed"
    
    # Exception states
    ESCALATED = "escalated"
    PAUSED = "paused"
    ABORTED = "aborted"
    ERROR = "error"

class ChecklistItemStatus(Enum):
    """Enhanced checklist item statuses"""
    PENDING = "pending"                    # Not yet addressed
    QUEUED = "queued"                      # Queued for asking
    ASKED = "asked"                        # Question posed
    ANSWERED = "answered"                  # Response received
    VALIDATING = "validating"              # Under validation
    VERIFIED = "verified"                  # Validated successfully
    AUTO_FILLED = "auto_filled"           # Filled from research
    NEEDS_CLARIFICATION = "needs_clarification"  # Requires follow-up
    BLOCKED = "blocked"                    # Cannot proceed
    SKIPPED = "skipped"                   # Not applicable
    NOT_APPLICABLE = "not_applicable"     # Removed as irrelevant

@dataclass
class ChecklistItem:
    """Enhanced checklist item with full tracking"""
    # Core fields
    key: str
    prompt: str
    category: str
    required: bool
    status: ChecklistItemStatus = ChecklistItemStatus.PENDING
    
    # Value and validation
    value: Optional[Any] = None
    value_type: str = "text"
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    validation_errors: List[str] = field(default_factory=list)
    
    # Metadata
    description: Optional[str] = None
    help_text: Optional[str] = None
    placeholder: Optional[str] = None
    
    # Dependencies and priority
    dependencies: List[str] = field(default_factory=list)
    priority: str = "medium"  # critical, high, medium, low
    
    # Source tracking
    source: str = "template"  # template, research, dynamic, user
    confidence: Optional[float] = None
    research_references: List[str] = field(default_factory=list)
    
    # Interaction tracking
    attempts: int = 0
    last_asked_at: Optional[str] = None
    answered_at: Optional[str] = None
    verified_at: Optional[str] = None
    
    # Audit fields
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_by: str = "system"

@dataclass
class ResearchResult:
    """Structured research result"""
    query: str
    source: str
    content: str
    relevance_score: float
    checklist_items: List[str]
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    indexed: bool = False
    index_id: Optional[str] = None
    summary: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class EvolvedOnboardingState(TypedDict):
    """Complete evolved state structure"""
    # Session identification
    session_id: str
    user_id: str
    provider_id: Optional[str]
    parent_session_id: Optional[str]  # For resumed sessions
    
    # Provider and user data
    provider_profile: Dict[str, Any]
    user_profile: Dict[str, Any]
    service_type: Literal["tax", "migration", "business_setup", "other"]
    
    # Workflow status
    workflow_status: WorkflowStatus
    previous_status: Optional[WorkflowStatus]
    status_history: List[Dict[str, Any]]
    
    # Conversation management
    messages: List[Dict[str, Any]]
    message_count: int
    last_bot_message: Optional[str]
    last_user_message: Optional[str]
    conversation_context: Dict[str, Any]
    
    # Question management
    current_question: Optional[ChecklistItem]
    question_queue: List[str]  # Keys of items to ask
    last_question_key: Optional[str]
    awaiting_response: bool
    
    # Checklist state
    checklist: List[ChecklistItem]
    checklist_version: str
    checklist_modifications: List[Dict[str, Any]]  # Audit trail
    completion_metrics: Dict[str, float]
    
    # Research state
    research_needed: bool
    research_results: List[ResearchResult]
    research_queue: List[Dict[str, Any]]
    rag_collection_id: Optional[str]
    last_research_at: Optional[str]
    research_metadata: Dict[str, Any]
    
    # Decision tracking
    decision_points: List[Dict[str, Any]]
    last_decision: Optional[str]
    decision_context: Dict[str, Any]
    
    # Escalation and errors
    escalation_reason: Optional[str]
    escalation_attempts: int
    error_log: List[Dict[str, Any]]
    validation_failures: int
    
    # Performance metrics
    response_times: List[float]
    average_response_time: float
    total_duration_seconds: float
    
    # Feature flags and config
    feature_flags: Dict[str, bool]
    config: Dict[str, Any]
    
    # Timestamps
    created_at: str
    updated_at: str
    completed_at: Optional[str]
    
    # Checkpoints
    last_checkpoint: Optional[str]
    checkpoint_count: int
```

### 2. State Manager Implementation

```python
import asyncio
from typing import Optional, List, Dict, Any
import json

class EvolvedStateManager:
    """
    Advanced state management with event sourcing and recovery.
    """
    
    def __init__(self, db_connection, redis_client, event_bus=None):
        self.db = db_connection
        self.redis = redis_client
        self.event_bus = event_bus
        self.state_cache = {}
        self.event_log = []
        
    async def initialize_state(
        self,
        user_id: str,
        service_type: str,
        provider_info: Optional[Dict] = None,
        parent_session_id: Optional[str] = None
    ) -> EvolvedOnboardingState:
        """
        Initialize a new onboarding state or resume from parent.
        
        Args:
            user_id: User identifier
            service_type: Type of service
            provider_info: Initial provider information
            parent_session_id: Parent session to resume from
            
        Returns:
            Initialized state
        """
        session_id = str(uuid.uuid4())
        
        # Load user profile
        user_profile = await self._load_user_profile(user_id)
        
        # Initialize or resume state
        if parent_session_id:
            state = await self._resume_from_parent(parent_session_id)
            state["session_id"] = session_id
            state["parent_session_id"] = parent_session_id
        else:
            state = self._create_new_state(
                session_id=session_id,
                user_id=user_id,
                user_profile=user_profile,
                service_type=service_type,
                provider_info=provider_info
            )
        
        # Initialize checklist
        state["checklist"] = await self._initialize_checklist(
            service_type=service_type,
            user_profile=user_profile,
            provider_info=provider_info
        )
        
        # Cache state
        self.state_cache[session_id] = state
        
        # Emit initialization event
        await self._emit_event("state_initialized", {
            "session_id": session_id,
            "user_id": user_id,
            "service_type": service_type
        })
        
        return state
    
    async def update_state(
        self,
        session_id: str,
        updates: Dict[str, Any],
        event_type: str = "state_updated"
    ) -> EvolvedOnboardingState:
        """
        Update state with event sourcing.
        
        Args:
            session_id: Session to update
            updates: Updates to apply
            event_type: Type of event
            
        Returns:
            Updated state
        """
        # Get current state
        state = await self.get_state(session_id)
        if not state:
            raise ValueError(f"State not found for session {session_id}")
        
        # Create event
        event = {
            "session_id": session_id,
            "event_type": event_type,
            "updates": updates,
            "timestamp": datetime.utcnow().isoformat(),
            "sequence": len(self.event_log)
        }
        
        # Apply updates
        old_status = state.get("workflow_status")
        for key, value in updates.items():
            state[key] = value
        
        # Track status changes
        if "workflow_status" in updates and updates["workflow_status"] != old_status:
            state["previous_status"] = old_status
            state["status_history"].append({
                "from": old_status.value if old_status else None,
                "to": updates["workflow_status"].value,
                "timestamp": datetime.utcnow().isoformat(),
                "reason": updates.get("status_reason", "")
            })
        
        # Update timestamps
        state["updated_at"] = datetime.utcnow().isoformat()
        
        # Log event
        self.event_log.append(event)
        
        # Persist to cache
        self.state_cache[session_id] = state
        
        # Async persist to storage
        asyncio.create_task(self._persist_state(session_id, state))
        
        # Emit event
        await self._emit_event(event_type, event)
        
        return state
    
    async def transition_status(
        self,
        session_id: str,
        new_status: WorkflowStatus,
        reason: str = "",
        metadata: Optional[Dict] = None
    ) -> EvolvedOnboardingState:
        """
        Transition workflow status with validation.
        
        Args:
            session_id: Session to transition
            new_status: New status
            reason: Reason for transition
            metadata: Additional context
            
        Returns:
            Updated state
        """
        state = await self.get_state(session_id)
        current_status = state["workflow_status"]
        
        # Validate transition
        if not self._is_valid_transition(current_status, new_status):
            raise ValueError(f"Invalid transition from {current_status} to {new_status}")
        
        # Prepare updates
        updates = {
            "workflow_status": new_status,
            "status_reason": reason
        }
        
        if metadata:
            updates["decision_context"] = metadata
        
        # Apply transition
        return await self.update_state(
            session_id=session_id,
            updates=updates,
            event_type="status_transition"
        )
    
    def _is_valid_transition(
        self,
        from_status: WorkflowStatus,
        to_status: WorkflowStatus
    ) -> bool:
        """
        Validate status transitions.
        """
        # Define valid transitions
        valid_transitions = {
            WorkflowStatus.INITIALIZING: [
                WorkflowStatus.INTAKE_PHASE,
                WorkflowStatus.ERROR
            ],
            WorkflowStatus.INTAKE_PHASE: [
                WorkflowStatus.RESEARCHING,
                WorkflowStatus.UPDATING_CHECKLIST,
                WorkflowStatus.ESCALATED
            ],
            WorkflowStatus.RESEARCHING: [
                WorkflowStatus.PARSING_RESEARCH,
                WorkflowStatus.ERROR
            ],
            WorkflowStatus.PARSING_RESEARCH: [
                WorkflowStatus.INDEXING_RESEARCH,
                WorkflowStatus.UPDATING_CHECKLIST
            ],
            WorkflowStatus.UPDATING_CHECKLIST: [
                WorkflowStatus.ASKING_QUESTION,
                WorkflowStatus.READY_FOR_CONFIRMATION,
                WorkflowStatus.RESEARCHING
            ],
            WorkflowStatus.ASKING_QUESTION: [
                WorkflowStatus.AWAITING_RESPONSE,
                WorkflowStatus.ERROR
            ],
            WorkflowStatus.AWAITING_RESPONSE: [
                WorkflowStatus.PROCESSING_RESPONSE,
                WorkflowStatus.ESCALATED,
                WorkflowStatus.PAUSED
            ],
            WorkflowStatus.PROCESSING_RESPONSE: [
                WorkflowStatus.EVALUATING_CONTINUATION,
                WorkflowStatus.NEEDS_CLARIFICATION,
                WorkflowStatus.ERROR
            ],
            WorkflowStatus.EVALUATING_CONTINUATION: [
                WorkflowStatus.UPDATING_CHECKLIST,
                WorkflowStatus.RESEARCHING,
                WorkflowStatus.READY_FOR_CONFIRMATION,
                WorkflowStatus.ESCALATED
            ],
            WorkflowStatus.READY_FOR_CONFIRMATION: [
                WorkflowStatus.AWAITING_CONFIRMATION,
                WorkflowStatus.UPDATING_CHECKLIST
            ],
            WorkflowStatus.AWAITING_CONFIRMATION: [
                WorkflowStatus.SAVING_RESULTS,
                WorkflowStatus.UPDATING_CHECKLIST,
                WorkflowStatus.ABORTED
            ],
            WorkflowStatus.SAVING_RESULTS: [
                WorkflowStatus.COMPLETED,
                WorkflowStatus.ERROR
            ]
        }
        
        # Allow transitions to error/abort from any state
        if to_status in [WorkflowStatus.ERROR, WorkflowStatus.ABORTED]:
            return True
        
        # Check if transition is valid
        return to_status in valid_transitions.get(from_status, [])
```

### 3. Dynamic Checklist System

```python
class DynamicChecklistSystem:
    """
    Advanced checklist management with intelligent adaptation.
    """
    
    def __init__(self, llm, template_service, validation_service):
        self.llm = llm
        self.templates = template_service
        self.validation = validation_service
        self.modification_log = []
        
    async def initialize_checklist(
        self,
        service_type: str,
        user_profile: Dict,
        provider_info: Optional[Dict] = None
    ) -> List[ChecklistItem]:
        """
        Initialize checklist with intelligent customization.
        
        Args:
            service_type: Type of service
            user_profile: User profile data
            provider_info: Initial provider information
            
        Returns:
            Customized checklist
        """
        # Load base template
        base_template = await self.templates.get_template(service_type)
        
        # Convert to ChecklistItem objects
        checklist = [
            ChecklistItem(**item) for item in base_template
        ]
        
        # Customize based on user profile
        checklist = self._customize_for_user(checklist, user_profile)
        
        # Pre-fill from provider info if available
        if provider_info:
            checklist = self._prefill_from_provider(checklist, provider_info)
        
        # Analyze and add dynamic items
        dynamic_items = await self._generate_dynamic_items(
            base_checklist=checklist,
            service_type=service_type,
            user_profile=user_profile
        )
        checklist.extend(dynamic_items)
        
        # Sort by priority and dependencies
        checklist = self._optimize_order(checklist)
        
        return checklist
    
    def update_from_response(
        self,
        checklist: List[ChecklistItem],
        response: str,
        question_key: str,
        user_profile: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Update checklist based on user response.
        
        Args:
            checklist: Current checklist
            response: User response
            question_key: Key of answered question
            user_profile: User profile for context
            
        Returns:
            Update summary
        """
        update_summary = {
            "items_updated": [],
            "items_added": [],
            "validation_status": "pending",
            "follow_up_needed": False
        }
        
        # Find and update the answered item
        for item in checklist:
            if item.key == question_key:
                # Validate response
                validation = self.validation.validate(
                    value=response,
                    rules=item.validation_rules,
                    value_type=item.value_type
                )
                
                if validation["valid"]:
                    item.value = validation["normalized_value"]
                    item.status = ChecklistItemStatus.VERIFIED
                    item.verified_at = datetime.utcnow().isoformat()
                    update_summary["validation_status"] = "success"
                else:
                    item.value = response
                    item.status = ChecklistItemStatus.NEEDS_CLARIFICATION
                    item.validation_errors = validation["errors"]
                    update_summary["validation_status"] = "failed"
                    update_summary["follow_up_needed"] = True
                
                item.answered_at = datetime.utcnow().isoformat()
                item.updated_at = datetime.utcnow().isoformat()
                update_summary["items_updated"].append(item.key)
                
                # Check for dependent items to update
                self._update_dependent_items(checklist, item)
                
                # Check if response triggers new items
                new_items = self._check_for_triggered_items(
                    response=response,
                    item=item,
                    user_profile=user_profile
                )
                
                if new_items:
                    for new_item in new_items:
                        checklist.append(new_item)
                        update_summary["items_added"].append(new_item.key)
                
                break
        
        # Log modification
        self.modification_log.append({
            "type": "response_update",
            "timestamp": datetime.utcnow().isoformat(),
            "question_key": question_key,
            "summary": update_summary
        })
        
        return update_summary
    
    def apply_research_findings(
        self,
        checklist: List[ChecklistItem],
        research_results: List[ResearchResult],
        confidence_threshold: float = 0.75
    ) -> Dict[str, Any]:
        """
        Auto-fill checklist from research findings.
        
        Args:
            checklist: Current checklist
            research_results: Research findings
            confidence_threshold: Minimum confidence for auto-fill
            
        Returns:
            Application summary
        """
        application_summary = {
            "items_auto_filled": [],
            "items_enriched": [],
            "confidence_scores": {}
        }
        
        for item in checklist:
            if item.status != ChecklistItemStatus.PENDING:
                continue
            
            # Find relevant research
            relevant_findings = self._find_relevant_research(
                item=item,
                research_results=research_results
            )
            
            if not relevant_findings:
                continue
            
            # Extract value using LLM
            extraction = self._extract_value_from_research(
                item=item,
                findings=relevant_findings
            )
            
            if extraction["confidence"] >= confidence_threshold:
                item.value = extraction["value"]
                item.status = ChecklistItemStatus.AUTO_FILLED
                item.source = "research"
                item.confidence = extraction["confidence"]
                item.research_references = extraction["references"]
                item.updated_at = datetime.utcnow().isoformat()
                
                application_summary["items_auto_filled"].append(item.key)
                application_summary["confidence_scores"][item.key] = extraction["confidence"]
            elif extraction["confidence"] >= 0.5:
                # Add as suggestion/enrichment
                item.help_text = f"Research suggests: {extraction['value']}"
                application_summary["items_enriched"].append(item.key)
        
        # Log modification
        self.modification_log.append({
            "type": "research_application",
            "timestamp": datetime.utcnow().isoformat(),
            "summary": application_summary
        })
        
        return application_summary
    
    def _extract_value_from_research(
        self,
        item: ChecklistItem,
        findings: List[ResearchResult]
    ) -> Dict[str, Any]:
        """
        Extract value from research findings using LLM.
        """
        prompt = f"""
        Extract information for this checklist item from research findings:
        
        Checklist Item:
        - Key: {item.key}
        - Question: {item.prompt}
        - Expected Type: {item.value_type}
        - Description: {item.description or "N/A"}
        
        Research Findings:
        {json.dumps([{
            "source": f.source,
            "content": f.content[:500],
            "relevance": f.relevance_score
        } for f in findings[:3]], indent=2)}
        
        Extract:
        1. The value for this checklist item
        2. Confidence score (0-1)
        3. Which findings support this value
        
        If the information is not clearly available, return confidence 0.
        """
        
        result = self.llm.invoke(prompt)
        # Parse LLM response
        
        return {
            "value": "extracted_value",
            "confidence": 0.8,
            "references": ["ref1", "ref2"]
        }
    
    def get_next_question(
        self,
        checklist: List[ChecklistItem]
    ) -> Optional[ChecklistItem]:
        """
        Get the next question to ask based on priority and dependencies.
        
        Args:
            checklist: Current checklist
            
        Returns:
            Next item to ask about or None
        """
        # Filter to pending items
        pending = [
            item for item in checklist 
            if item.status == ChecklistItemStatus.PENDING
        ]
        
        if not pending:
            return None
        
        # Check dependencies
        available = []
        for item in pending:
            if self._dependencies_met(item, checklist):
                available.append(item)
        
        if not available:
            # No items with met dependencies, might need escalation
            return None
        
        # Sort by priority
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        available.sort(key=lambda x: (
            0 if x.required else 1,
            priority_order.get(x.priority, 2),
            x.attempts
        ))
        
        return available[0]
    
    def _dependencies_met(
        self,
        item: ChecklistItem,
        checklist: List[ChecklistItem]
    ) -> bool:
        """
        Check if item dependencies are satisfied.
        """
        if not item.dependencies:
            return True
        
        checklist_keys = {i.key: i for i in checklist}
        
        for dep_key in item.dependencies:
            if dep_key in checklist_keys:
                dep_item = checklist_keys[dep_key]
                if dep_item.status not in [
                    ChecklistItemStatus.VERIFIED,
                    ChecklistItemStatus.AUTO_FILLED,
                    ChecklistItemStatus.SKIPPED
                ]:
                    return False
        
        return True
    
    def calculate_progress(
        self,
        checklist: List[ChecklistItem]
    ) -> Dict[str, Any]:
        """
        Calculate detailed progress metrics.
        
        Args:
            checklist: Current checklist
            
        Returns:
            Progress metrics
        """
        total = len(checklist)
        
        # Count by status
        status_counts = {}
        for status in ChecklistItemStatus:
            status_counts[status.value] = sum(
                1 for item in checklist if item.status == status
            )
        
        # Calculate completion
        completed = sum(
            1 for item in checklist 
            if item.status in [
                ChecklistItemStatus.VERIFIED,
                ChecklistItemStatus.AUTO_FILLED,
                ChecklistItemStatus.SKIPPED,
                ChecklistItemStatus.NOT_APPLICABLE
            ]
        )
        
        # Required items
        required_total = sum(1 for item in checklist if item.required)
        required_completed = sum(
            1 for item in checklist 
            if item.required and item.status in [
                ChecklistItemStatus.VERIFIED,
                ChecklistItemStatus.AUTO_FILLED
            ]
        )
        
        # Calculate percentages
        overall_percentage = (completed / total * 100) if total > 0 else 0
        required_percentage = (required_completed / required_total * 100) if required_total > 0 else 0
        
        # Identify blockers
        blocked_items = [
            item.key for item in checklist 
            if item.status == ChecklistItemStatus.BLOCKED
        ]
        
        needs_clarification = [
            item.key for item in checklist 
            if item.status == ChecklistItemStatus.NEEDS_CLARIFICATION
        ]
        
        return {
            "total_items": total,
            "completed_items": completed,
            "overall_percentage": round(overall_percentage, 2),
            "required_total": required_total,
            "required_completed": required_completed,
            "required_percentage": round(required_percentage, 2),
            "status_breakdown": status_counts,
            "blocked_items": blocked_items,
            "needs_clarification": needs_clarification,
            "can_complete": len(blocked_items) == 0 and required_completed == required_total,
            "estimated_remaining": total - completed
        }
```

### 4. State Persistence and Recovery

```python
import aioredis
import asyncpg
from typing import Optional

class StatePersistenceLayer:
    """
    Handles state persistence and recovery with multiple storage backends.
    """
    
    def __init__(self, postgres_pool, redis_pool):
        self.pg_pool = postgres_pool
        self.redis_pool = redis_pool
        
    async def save_checkpoint(
        self,
        state: EvolvedOnboardingState,
        checkpoint_type: str = "auto"
    ) -> str:
        """
        Save a state checkpoint.
        
        Args:
            state: State to checkpoint
            checkpoint_type: Type of checkpoint
            
        Returns:
            Checkpoint ID
        """
        checkpoint_id = f"checkpoint_{state['session_id']}_{datetime.utcnow().timestamp()}"
        
        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "session_id": state["session_id"],
            "state": state,
            "type": checkpoint_type,
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": {
                "message_count": state["message_count"],
                "completion": state["completion_metrics"],
                "duration": state["total_duration_seconds"]
            }
        }
        
        # Save to Redis for quick access
        async with self.redis_pool as redis:
            await redis.setex(
                f"checkpoint:{checkpoint_id}",
                86400,  # 24 hour TTL
                json.dumps(checkpoint_data)
            )
            
            # Track latest checkpoint
            await redis.set(
                f"latest_checkpoint:{state['session_id']}",
                checkpoint_id
            )
        
        # Save to PostgreSQL for durability
        async with self.pg_pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO state_checkpoints 
                (checkpoint_id, session_id, state_data, checkpoint_type, created_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (checkpoint_id) DO UPDATE
                SET state_data = EXCLUDED.state_data,
                    updated_at = CURRENT_TIMESTAMP
            """, checkpoint_id, state["session_id"], json.dumps(checkpoint_data), 
                checkpoint_type, datetime.utcnow())
        
        # Update state
        state["last_checkpoint"] = checkpoint_id
        state["checkpoint_count"] = state.get("checkpoint_count", 0) + 1
        
        return checkpoint_id
    
    async def load_checkpoint(
        self,
        checkpoint_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Optional[EvolvedOnboardingState]:
        """
        Load a checkpoint.
        
        Args:
            checkpoint_id: Specific checkpoint to load
            session_id: Session to load latest checkpoint for
            
        Returns:
            Loaded state or None
        """
        # Determine checkpoint to load
        if not checkpoint_id and session_id:
            async with self.redis_pool as redis:
                checkpoint_id = await redis.get(f"latest_checkpoint:{session_id}")
                if checkpoint_id:
                    checkpoint_id = checkpoint_id.decode()
        
        if not checkpoint_id:
            return None
        
        # Try Redis first
        async with self.redis_pool as redis:
            data = await redis.get(f"checkpoint:{checkpoint_id}")
            if data:
                checkpoint = json.loads(data)
                return checkpoint["state"]
        
        # Fallback to PostgreSQL
        async with self.pg_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT state_data 
                FROM state_checkpoints 
                WHERE checkpoint_id = $1
            """, checkpoint_id)
            
            if row:
                checkpoint = json.loads(row["state_data"])
                return checkpoint["state"]
        
        return None
    
    async def list_checkpoints(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict]:
        """
        List available checkpoints for a session.
        
        Args:
            session_id: Session ID
            limit: Maximum checkpoints to return
            
        Returns:
            List of checkpoint metadata
        """
        async with self.pg_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT checkpoint_id, checkpoint_type, created_at,
                       (state_data->>'metrics')::jsonb as metrics
                FROM state_checkpoints
                WHERE session_id = $1
                ORDER BY created_at DESC
                LIMIT $2
            """, session_id, limit)
            
            return [
                {
                    "checkpoint_id": row["checkpoint_id"],
                    "type": row["checkpoint_type"],
                    "created_at": row["created_at"].isoformat(),
                    "metrics": row["metrics"]
                }
                for row in rows
            ]
    
    async def cleanup_old_checkpoints(
        self,
        session_id: str,
        keep_count: int = 5
    ):
        """
        Clean up old checkpoints, keeping only recent ones.
        
        Args:
            session_id: Session ID
            keep_count: Number of checkpoints to keep
        """
        async with self.pg_pool.acquire() as conn:
            # Get checkpoints to delete
            rows = await conn.fetch("""
                SELECT checkpoint_id 
                FROM state_checkpoints
                WHERE session_id = $1
                ORDER BY created_at DESC
                OFFSET $2
            """, session_id, keep_count)
            
            if rows:
                checkpoint_ids = [row["checkpoint_id"] for row in rows]
                
                # Delete from PostgreSQL
                await conn.execute("""
                    DELETE FROM state_checkpoints
                    WHERE checkpoint_id = ANY($1)
                """, checkpoint_ids)
                
                # Delete from Redis
                async with self.redis_pool as redis:
                    for checkpoint_id in checkpoint_ids:
                        await redis.delete(f"checkpoint:{checkpoint_id}")
```

## Integration Example

```python
async def create_evolved_state_system(config: Dict) -> Dict:
    """
    Create complete evolved state management system.
    """
    # Initialize database pools
    pg_pool = await asyncpg.create_pool(**config["postgres"])
    redis_pool = aioredis.ConnectionPool.from_url(config["redis_url"])
    
    # Initialize services
    state_manager = EvolvedStateManager(
        db_connection=pg_pool,
        redis_client=redis_pool,
        event_bus=config.get("event_bus")
    )
    
    checklist_system = DynamicChecklistSystem(
        llm=config["llm"],
        template_service=config["template_service"],
        validation_service=config["validation_service"]
    )
    
    persistence_layer = StatePersistenceLayer(
        postgres_pool=pg_pool,
        redis_pool=redis_pool
    )
    
    return {
        "state_manager": state_manager,
        "checklist_system": checklist_system,
        "persistence": persistence_layer
    }
```