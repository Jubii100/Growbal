# State Management and Checklist Documentation

## Overview
This module defines the central state structure for the onboarding workflow, including the dynamic checklist system that tracks progress and adapts based on provider type and research findings.

## State Definition

### 1. Core State Structure

```python
from typing import TypedDict, List, Dict, Any, Literal, Optional
from typing_extensions import NotRequired
from datetime import datetime
from enum import Enum

class WorkflowStatus(Enum):
    """Workflow status indicators."""
    ON_TRACK = "ON_TRACK"                # Normal progression
    NEEDS_INFO = "NEEDS_INFO"            # Requires more user input
    RESEARCHING = "RESEARCHING"          # Conducting background research
    ESCALATE = "ESCALATE"                # Needs human intervention
    READY_TO_SAVE = "READY_TO_SAVE"      # All requirements met
    FINALIZE_SAVE = "FINALIZE_SAVE"      # Saving to database
    RESTART = "RESTART"                  # User requested restart
    ABORT = "ABORT"                      # User cancelled process
    COMPLETED = "COMPLETED"               # Successfully completed

class ChecklistStatus(Enum):
    """Individual checklist item status."""
    PENDING = "PENDING"           # Not yet addressed
    ASKED = "ASKED"              # Question posed to user
    ANSWERED = "ANSWERED"        # User provided response
    VERIFIED = "VERIFIED"        # Response validated
    BLOCKED = "BLOCKED"          # Cannot proceed
    SKIPPED = "SKIPPED"          # Not applicable
    AUTO_FILLED = "AUTO_FILLED"  # Filled from research

class ChecklistItem(TypedDict):
    """Structure for individual checklist items."""
    key: str                                    # Unique identifier
    category: str                               # Item category (contact, legal, service, etc.)
    prompt: str                                 # Human-readable prompt
    description: NotRequired[str]               # Detailed description
    required: bool                              # Whether item is mandatory
    status: ChecklistStatus                     # Current status
    value: NotRequired[Any]                     # Collected value
    value_type: str                            # Expected type (text, number, email, etc.)
    validation_rules: NotRequired[Dict]         # Validation criteria
    dependencies: NotRequired[List[str]]        # Other items this depends on
    source: NotRequired[str]                   # Where value came from (user, research, etc.)
    confidence: NotRequired[float]              # Confidence in auto-filled values
    updated_at: NotRequired[str]               # Last update timestamp
    attempts: NotRequired[int]                  # Number of times asked

class ResearchNote(TypedDict):
    """Structure for research findings."""
    query: str                          # Search query used
    source: str                         # Source type (web, wiki, arxiv, etc.)
    content: str                        # Raw content
    summary: NotRequired[str]           # Summarized finding
    relevance_score: NotRequired[float] # Relevance to provider
    timestamp: str                      # When researched
    used_for: NotRequired[List[str]]   # Which checklist items it informed

class OnboardingState(TypedDict):
    """Complete state structure for onboarding workflow."""
    # Core identification
    session_id: str                                  # Unique session identifier
    provider_id: NotRequired[str]                    # Provider UUID (once created)
    
    # Provider information
    provider_profile: Dict[str, Any]                 # Basic provider information
    service_type: Literal["tax", "migration", "business_setup"]
    
    # Conversation management
    messages: List[Dict[str, Any]]                   # Conversation history
    current_turn: int                                 # Current conversation turn
    
    # Checklist tracking
    checklist: List[ChecklistItem]                   # Dynamic checklist
    checklist_version: str                            # Version of checklist template used
    completion_percentage: float                      # Progress indicator
    
    # Research data
    research_notes: List[ResearchNote]               # Research findings
    research_queries_pending: List[str]              # Queries to execute
    vector_store_id: NotRequired[str]               # Chroma collection ID
    
    # Workflow control
    status: WorkflowStatus                           # Current workflow status
    substatus: NotRequired[str]                      # Additional status detail
    status_history: List[Dict[str, Any]]            # Status change log
    
    # Metadata
    started_at: str                                  # Session start time
    last_activity: str                               # Last activity timestamp
    estimated_completion: NotRequired[str]           # Estimated completion time
    escalation_reason: NotRequired[str]             # Why escalated (if applicable)
    
    # Configuration
    config: Dict[str, Any]                          # Runtime configuration
    feature_flags: Dict[str, bool]                  # Feature toggles
```

### 2. State Manager

```python
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

class StateManager:
    """
    Manages the onboarding state throughout the workflow.
    """
    
    def __init__(self, initial_provider_data: Dict[str, Any] = None):
        self.state = self._initialize_state(initial_provider_data)
        self.state_snapshots: List[OnboardingState] = []  # For rollback
    
    def _initialize_state(
        self, 
        provider_data: Optional[Dict[str, Any]] = None
    ) -> OnboardingState:
        """
        Initialize a new onboarding state.
        
        Args:
            provider_data: Initial provider information
            
        Returns:
            Initialized state
        """
        now = datetime.utcnow().isoformat()
        service_type = provider_data.get("service_type", "business_setup") if provider_data else "business_setup"
        
        return OnboardingState(
            session_id=str(uuid.uuid4()),
            provider_profile=provider_data or {},
            service_type=service_type,
            messages=[],
            current_turn=0,
            checklist=self._get_initial_checklist(service_type),
            checklist_version="1.0",
            completion_percentage=0.0,
            research_notes=[],
            research_queries_pending=[],
            status=WorkflowStatus.ON_TRACK,
            status_history=[{
                "status": WorkflowStatus.ON_TRACK.value,
                "timestamp": now,
                "reason": "Session initialized"
            }],
            started_at=now,
            last_activity=now,
            config={
                "max_questions_per_turn": 3,
                "research_depth": "standard",
                "auto_fill_enabled": True
            },
            feature_flags={
                "enable_research": True,
                "enable_auto_fill": True,
                "enable_validation": True,
                "enable_escalation": True
            }
        )
    
    def update_status(
        self,
        new_status: WorkflowStatus,
        reason: Optional[str] = None,
        substatus: Optional[str] = None
    ) -> None:
        """
        Update the workflow status.
        
        Args:
            new_status: New workflow status
            reason: Reason for status change
            substatus: Additional status detail
        """
        self.state["status"] = new_status
        if substatus:
            self.state["substatus"] = substatus
        
        # Log status change
        self.state["status_history"].append({
            "status": new_status.value,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason or "Status update",
            "substatus": substatus
        })
        
        self.state["last_activity"] = datetime.utcnow().isoformat()
        
        # Update estimated completion
        self._update_estimated_completion()
    
    def update_checklist_item(
        self,
        item_key: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Update a specific checklist item.
        
        Args:
            item_key: Checklist item key
            updates: Updates to apply
            
        Returns:
            Success boolean
        """
        for item in self.state["checklist"]:
            if item["key"] == item_key:
                # Update fields
                for key, value in updates.items():
                    if key in item:
                        item[key] = value
                
                # Update timestamp and attempts
                item["updated_at"] = datetime.utcnow().isoformat()
                if "status" in updates and updates["status"] == ChecklistStatus.ASKED:
                    item["attempts"] = item.get("attempts", 0) + 1
                
                # Recalculate completion
                self._update_completion_percentage()
                return True
        
        return False
    
    def batch_update_checklist(
        self,
        updates: List[Dict[str, Any]]
    ) -> int:
        """
        Batch update multiple checklist items.
        
        Args:
            updates: List of updates with item_key and changes
            
        Returns:
            Number of items updated
        """
        updated_count = 0
        for update in updates:
            if self.update_checklist_item(
                update["item_key"],
                update["changes"]
            ):
                updated_count += 1
        
        return updated_count
    
    def add_research_note(
        self,
        note: ResearchNote
    ) -> None:
        """
        Add a research finding to the state.
        
        Args:
            note: Research note to add
        """
        note["timestamp"] = datetime.utcnow().isoformat()
        self.state["research_notes"].append(note)
        self.state["last_activity"] = datetime.utcnow().isoformat()
    
    def snapshot_state(self) -> None:
        """Create a snapshot of the current state for potential rollback."""
        import copy
        self.state_snapshots.append(copy.deepcopy(self.state))
        
        # Keep only last 5 snapshots
        if len(self.state_snapshots) > 5:
            self.state_snapshots.pop(0)
    
    def rollback_state(self) -> bool:
        """
        Rollback to the previous state snapshot.
        
        Returns:
            Success boolean
        """
        if self.state_snapshots:
            self.state = self.state_snapshots.pop()
            return True
        return False
    
    def _update_completion_percentage(self) -> None:
        """Calculate and update completion percentage."""
        total_required = sum(1 for item in self.state["checklist"] if item["required"])
        completed_required = sum(
            1 for item in self.state["checklist"] 
            if item["required"] and item["status"] in [
                ChecklistStatus.VERIFIED,
                ChecklistStatus.AUTO_FILLED
            ]
        )
        
        if total_required > 0:
            self.state["completion_percentage"] = (completed_required / total_required) * 100
        else:
            self.state["completion_percentage"] = 0.0
    
    def _update_estimated_completion(self) -> None:
        """Update estimated completion time based on progress."""
        completion_pct = self.state["completion_percentage"]
        
        if completion_pct < 30:
            estimated_minutes = 15
        elif completion_pct < 60:
            estimated_minutes = 10
        elif completion_pct < 90:
            estimated_minutes = 5
        else:
            estimated_minutes = 2
        
        estimated_time = datetime.utcnow() + timedelta(minutes=estimated_minutes)
        self.state["estimated_completion"] = estimated_time.isoformat()
    
    def _get_initial_checklist(self, service_type: str) -> List[ChecklistItem]:
        """
        Get the initial checklist based on service type.
        
        Args:
            service_type: Type of service provider
            
        Returns:
            Initial checklist items
        """
        # This would normally load from database
        # For now, return a template based on service type
        return ChecklistTemplates.get_template(service_type)
```

## Checklist Templates

### 1. Dynamic Checklist System

```python
class ChecklistTemplates:
    """
    Manages checklist templates for different service types.
    """
    
    BASE_ITEMS = [
        ChecklistItem(
            key="company_name",
            category="basic",
            prompt="What is your company's legal name?",
            required=True,
            status=ChecklistStatus.PENDING,
            value_type="text",
            validation_rules={"min_length": 2, "max_length": 200}
        ),
        ChecklistItem(
            key="contact_email",
            category="contact",
            prompt="Primary contact email address",
            required=True,
            status=ChecklistStatus.PENDING,
            value_type="email",
            validation_rules={"pattern": r"^[^\s@]+@[^\s@]+\.[^\s@]+$"}
        ),
        ChecklistItem(
            key="contact_phone",
            category="contact",
            prompt="Primary contact phone number",
            required=True,
            status=ChecklistStatus.PENDING,
            value_type="phone",
            validation_rules={"min_length": 10}
        ),
        ChecklistItem(
            key="business_address",
            category="contact",
            prompt="Business address",
            required=True,
            status=ChecklistStatus.PENDING,
            value_type="text"
        ),
        ChecklistItem(
            key="years_in_business",
            category="basic",
            prompt="How many years have you been in business?",
            required=True,
            status=ChecklistStatus.PENDING,
            value_type="number",
            validation_rules={"min": 0, "max": 100}
        )
    ]
    
    SERVICE_SPECIFIC_ITEMS = {
        "tax": [
            ChecklistItem(
                key="tax_license",
                category="legal",
                prompt="Tax consultant license number",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="text"
            ),
            ChecklistItem(
                key="tax_services",
                category="service",
                prompt="Which tax services do you offer? (VAT, Corporate Tax, Personal Tax, etc.)",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="list"
            ),
            ChecklistItem(
                key="tax_software",
                category="service",
                prompt="Which tax software/platforms do you use?",
                required=False,
                status=ChecklistStatus.PENDING,
                value_type="list"
            ),
            ChecklistItem(
                key="industry_focus",
                category="service",
                prompt="Which industries do you specialize in?",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="list"
            ),
            ChecklistItem(
                key="client_size",
                category="service",
                prompt="What size businesses do you typically serve?",
                description="Small (1-50), Medium (51-500), Large (500+)",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="list"
            )
        ],
        "migration": [
            ChecklistItem(
                key="migration_license",
                category="legal",
                prompt="Immigration consultant license/registration number",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="text"
            ),
            ChecklistItem(
                key="visa_types",
                category="service",
                prompt="Which visa types do you handle?",
                description="Work, Residence, Visit, Student, etc.",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="list"
            ),
            ChecklistItem(
                key="countries_covered",
                category="service",
                prompt="Which countries/regions do you cover?",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="list"
            ),
            ChecklistItem(
                key="additional_services",
                category="service",
                prompt="Additional services offered",
                description="Document attestation, PRO services, relocation assistance",
                required=False,
                status=ChecklistStatus.PENDING,
                value_type="list"
            ),
            ChecklistItem(
                key="processing_time",
                category="service",
                prompt="Average visa processing time",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="text"
            )
        ],
        "business_setup": [
            ChecklistItem(
                key="business_license",
                category="legal",
                prompt="Business consultant license number",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="text"
            ),
            ChecklistItem(
                key="company_types",
                category="service",
                prompt="Types of companies you can set up",
                description="LLC, Free Zone, Mainland, Offshore",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="list"
            ),
            ChecklistItem(
                key="jurisdictions",
                category="service",
                prompt="Which jurisdictions do you operate in?",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="list"
            ),
            ChecklistItem(
                key="setup_timeline",
                category="service",
                prompt="Typical company setup timeline",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="text"
            ),
            ChecklistItem(
                key="banking_support",
                category="service",
                prompt="Do you provide bank account opening support?",
                required=True,
                status=ChecklistStatus.PENDING,
                value_type="boolean"
            )
        ]
    }
    
    @classmethod
    def get_template(cls, service_type: str) -> List[ChecklistItem]:
        """
        Get checklist template for a service type.
        
        Args:
            service_type: Type of service
            
        Returns:
            Complete checklist template
        """
        import copy
        
        # Start with base items
        checklist = copy.deepcopy(cls.BASE_ITEMS)
        
        # Add service-specific items
        if service_type in cls.SERVICE_SPECIFIC_ITEMS:
            service_items = copy.deepcopy(cls.SERVICE_SPECIFIC_ITEMS[service_type])
            checklist.extend(service_items)
        
        # Add timestamp to each item
        for item in checklist:
            item["updated_at"] = datetime.utcnow().isoformat()
            item["attempts"] = 0
        
        return checklist
    
    @classmethod
    def add_dynamic_items(
        cls,
        checklist: List[ChecklistItem],
        research_findings: List[Dict[str, Any]]
    ) -> List[ChecklistItem]:
        """
        Add dynamic checklist items based on research.
        
        Args:
            checklist: Current checklist
            research_findings: Research results
            
        Returns:
            Updated checklist with dynamic items
        """
        # Analyze research to identify additional requirements
        dynamic_items = []
        
        for finding in research_findings:
            # Example: If research mentions specific certification
            if "certification" in finding.get("content", "").lower():
                if not any(item["key"] == "certifications" for item in checklist):
                    dynamic_items.append(ChecklistItem(
                        key="certifications",
                        category="legal",
                        prompt="Professional certifications held",
                        required=False,
                        status=ChecklistStatus.PENDING,
                        value_type="list",
                        source="research",
                        updated_at=datetime.utcnow().isoformat(),
                        attempts=0
                    ))
            
            # Example: If research mentions insurance requirements
            if "insurance" in finding.get("content", "").lower():
                if not any(item["key"] == "insurance" for item in checklist):
                    dynamic_items.append(ChecklistItem(
                        key="insurance",
                        category="legal",
                        prompt="Professional liability insurance details",
                        required=False,
                        status=ChecklistStatus.PENDING,
                        value_type="text",
                        source="research",
                        updated_at=datetime.utcnow().isoformat(),
                        attempts=0
                    ))
        
        checklist.extend(dynamic_items)
        return checklist
```

### 2. Checklist Validation and Progress Tracking

```python
class ChecklistValidator:
    """
    Validates checklist items and tracks progress.
    """
    
    @staticmethod
    def validate_item(
        item: ChecklistItem,
        value: Any
    ) -> Dict[str, Any]:
        """
        Validate a checklist item value.
        
        Args:
            item: Checklist item
            value: Value to validate
            
        Returns:
            Validation result
        """
        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        # Check required
        if item["required"] and not value:
            validation_result["valid"] = False
            validation_result["errors"].append("This field is required")
            return validation_result
        
        # Type validation
        if not ChecklistValidator._validate_type(value, item["value_type"]):
            validation_result["valid"] = False
            validation_result["errors"].append(f"Invalid type. Expected {item['value_type']}")
        
        # Rules validation
        if "validation_rules" in item and item["validation_rules"]:
            rules_result = ChecklistValidator._validate_rules(
                value, 
                item["validation_rules"],
                item["value_type"]
            )
            if not rules_result["valid"]:
                validation_result["valid"] = False
                validation_result["errors"].extend(rules_result["errors"])
        
        # Dependency validation
        if "dependencies" in item and item["dependencies"]:
            deps_result = ChecklistValidator._validate_dependencies(
                item["dependencies"]
            )
            if not deps_result["valid"]:
                validation_result["warnings"].append(
                    "Some dependent fields are not yet completed"
                )
        
        return validation_result
    
    @staticmethod
    def _validate_type(value: Any, expected_type: str) -> bool:
        """Validate value type."""
        type_validators = {
            "text": lambda v: isinstance(v, str),
            "number": lambda v: isinstance(v, (int, float)),
            "email": lambda v: isinstance(v, str) and "@" in v,
            "phone": lambda v: isinstance(v, str) and len(v) >= 10,
            "boolean": lambda v: isinstance(v, bool),
            "list": lambda v: isinstance(v, list),
            "date": lambda v: isinstance(v, str)  # Could add date parsing
        }
        
        validator = type_validators.get(expected_type, lambda v: True)
        return validator(value)
    
    @staticmethod
    def _validate_rules(
        value: Any,
        rules: Dict[str, Any],
        value_type: str
    ) -> Dict[str, Any]:
        """Validate against specific rules."""
        result = {"valid": True, "errors": []}
        
        # Text/String rules
        if value_type in ["text", "email", "phone"]:
            if "min_length" in rules and len(value) < rules["min_length"]:
                result["valid"] = False
                result["errors"].append(f"Minimum length is {rules['min_length']}")
            
            if "max_length" in rules and len(value) > rules["max_length"]:
                result["valid"] = False
                result["errors"].append(f"Maximum length is {rules['max_length']}")
            
            if "pattern" in rules:
                import re
                if not re.match(rules["pattern"], value):
                    result["valid"] = False
                    result["errors"].append("Invalid format")
        
        # Number rules
        elif value_type == "number":
            if "min" in rules and value < rules["min"]:
                result["valid"] = False
                result["errors"].append(f"Minimum value is {rules['min']}")
            
            if "max" in rules and value > rules["max"]:
                result["valid"] = False
                result["errors"].append(f"Maximum value is {rules['max']}")
        
        # List rules
        elif value_type == "list":
            if "min_items" in rules and len(value) < rules["min_items"]:
                result["valid"] = False
                result["errors"].append(f"At least {rules['min_items']} items required")
            
            if "max_items" in rules and len(value) > rules["max_items"]:
                result["valid"] = False
                result["errors"].append(f"Maximum {rules['max_items']} items allowed")
        
        return result
    
    @staticmethod
    def _validate_dependencies(dependencies: List[str]) -> Dict[str, Any]:
        """Check if dependencies are met."""
        # This would check the actual state in a real implementation
        return {"valid": True}
    
    @staticmethod
    def calculate_progress(checklist: List[ChecklistItem]) -> Dict[str, Any]:
        """
        Calculate detailed progress metrics.
        
        Args:
            checklist: Current checklist
            
        Returns:
            Progress metrics
        """
        total = len(checklist)
        required = sum(1 for item in checklist if item["required"])
        
        completed_statuses = [
            ChecklistStatus.VERIFIED,
            ChecklistStatus.AUTO_FILLED
        ]
        
        completed_total = sum(
            1 for item in checklist 
            if item["status"] in completed_statuses
        )
        
        completed_required = sum(
            1 for item in checklist 
            if item["required"] and item["status"] in completed_statuses
        )
        
        pending = sum(
            1 for item in checklist 
            if item["status"] == ChecklistStatus.PENDING
        )
        
        in_progress = sum(
            1 for item in checklist 
            if item["status"] in [ChecklistStatus.ASKED, ChecklistStatus.ANSWERED]
        )
        
        blocked = sum(
            1 for item in checklist 
            if item["status"] == ChecklistStatus.BLOCKED
        )
        
        return {
            "total_items": total,
            "required_items": required,
            "completed_total": completed_total,
            "completed_required": completed_required,
            "pending": pending,
            "in_progress": in_progress,
            "blocked": blocked,
            "completion_percentage": (completed_total / total * 100) if total > 0 else 0,
            "required_completion_percentage": (completed_required / required * 100) if required > 0 else 0,
            "can_proceed": completed_required == required and blocked == 0
        }
```

## State Persistence

```python
class StatePersistence:
    """
    Handles state persistence and recovery.
    """
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def save_state(self, state: OnboardingState) -> bool:
        """
        Save state to database.
        
        Args:
            state: Current state
            
        Returns:
            Success boolean
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO onboarding_states 
                        (session_id, state_data, updated_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (session_id) 
                        DO UPDATE SET 
                            state_data = EXCLUDED.state_data,
                            updated_at = EXCLUDED.updated_at
                    """, (
                        state["session_id"],
                        Json(state),
                        datetime.utcnow()
                    ))
            return True
        except Exception as e:
            print(f"Failed to save state: {e}")
            return False
    
    def load_state(self, session_id: str) -> Optional[OnboardingState]:
        """
        Load state from database.
        
        Args:
            session_id: Session ID
            
        Returns:
            State or None
        """
        try:
            with self.db.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT state_data 
                        FROM onboarding_states 
                        WHERE session_id = %s
                    """, (session_id,))
                    
                    result = cur.fetchone()
                    return result["state_data"] if result else None
        except Exception as e:
            print(f"Failed to load state: {e}")
            return None
```