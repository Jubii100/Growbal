# Human-in-the-Loop Integration Documentation

## Overview
This module implements human intervention points, confirmation mechanisms, and escalation procedures to ensure quality control and handle complex situations during the onboarding process.

## Human Intervention Architecture

### 1. Interrupt Patterns

```python
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint import Checkpoint
from typing import Dict, Any, Optional, List
from enum import Enum
import asyncio

class InterruptType(Enum):
    """Types of interrupts for human intervention."""
    CONFIRMATION = "confirmation"          # Confirm before proceeding
    REVIEW = "review"                      # Review collected data
    ESCALATION = "escalation"              # Complex issue needs human
    APPROVAL = "approval"                  # Approve final submission
    CLARIFICATION = "clarification"        # Human clarifies ambiguity
    OVERRIDE = "override"                  # Human overrides decision

class HumanInTheLoop:
    """
    Manages human intervention in the workflow.
    """
    
    def __init__(self, notification_service=None):
        self.notification_service = notification_service
        self.pending_interventions: Dict[str, Dict] = {}
        self.intervention_history: List[Dict] = []
    
    def create_interrupt(
        self,
        session_id: str,
        interrupt_type: InterruptType,
        context: Dict[str, Any],
        options: Optional[List[str]] = None,
        timeout_minutes: int = 30
    ) -> str:
        """
        Create a human intervention point.
        
        Args:
            session_id: Current session ID
            interrupt_type: Type of intervention needed
            context: Context for the intervention
            options: Available options for human choice
            timeout_minutes: Timeout for human response
            
        Returns:
            Intervention ID
        """
        intervention_id = f"{session_id}_{interrupt_type.value}_{datetime.utcnow().timestamp()}"
        
        intervention = {
            "id": intervention_id,
            "session_id": session_id,
            "type": interrupt_type,
            "context": context,
            "options": options,
            "created_at": datetime.utcnow().isoformat(),
            "timeout_at": (datetime.utcnow() + timedelta(minutes=timeout_minutes)).isoformat(),
            "status": "pending",
            "response": None
        }
        
        self.pending_interventions[intervention_id] = intervention
        
        # Send notification if service is configured
        if self.notification_service:
            self.notification_service.notify_human_needed(intervention)
        
        return intervention_id
    
    async def wait_for_human(
        self,
        intervention_id: str,
        check_interval: int = 5
    ) -> Optional[Dict[str, Any]]:
        """
        Wait for human response to intervention.
        
        Args:
            intervention_id: ID of the intervention
            check_interval: Seconds between checks
            
        Returns:
            Human response or None if timeout
        """
        intervention = self.pending_interventions.get(intervention_id)
        if not intervention:
            return None
        
        timeout_at = datetime.fromisoformat(intervention["timeout_at"])
        
        while datetime.utcnow() < timeout_at:
            # Check if human has responded
            if intervention["status"] == "completed":
                self.intervention_history.append(intervention)
                del self.pending_interventions[intervention_id]
                return intervention["response"]
            
            # Wait before checking again
            await asyncio.sleep(check_interval)
        
        # Timeout reached
        intervention["status"] = "timeout"
        self.intervention_history.append(intervention)
        del self.pending_interventions[intervention_id]
        return None
    
    def submit_human_response(
        self,
        intervention_id: str,
        response: Dict[str, Any]
    ) -> bool:
        """
        Submit human response to intervention.
        
        Args:
            intervention_id: ID of the intervention
            response: Human response
            
        Returns:
            Success boolean
        """
        if intervention_id in self.pending_interventions:
            self.pending_interventions[intervention_id]["response"] = response
            self.pending_interventions[intervention_id]["status"] = "completed"
            self.pending_interventions[intervention_id]["completed_at"] = datetime.utcnow().isoformat()
            return True
        return False
```

### 2. Confirmation Nodes

```python
class ConfirmationNodes:
    """
    Graph nodes requiring human confirmation.
    """
    
    def __init__(self, human_loop: HumanInTheLoop):
        self.human_loop = human_loop
    
    async def confirmation_node(self, state: OnboardingState) -> Dict[str, Any]:
        """
        Request human confirmation before proceeding.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state based on human response
        """
        # Prepare confirmation context
        context = {
            "message": "Please confirm the collected information:",
            "data": self._prepare_confirmation_data(state),
            "checklist_progress": ChecklistValidator.calculate_progress(state["checklist"])
        }
        
        # Create interrupt
        intervention_id = self.human_loop.create_interrupt(
            session_id=state["session_id"],
            interrupt_type=InterruptType.CONFIRMATION,
            context=context,
            options=["Confirm", "Edit", "Cancel"]
        )
        
        # Wait for human response
        response = await self.human_loop.wait_for_human(intervention_id)
        
        if not response:
            # Timeout - escalate
            return {
                "status": WorkflowStatus.ESCALATE,
                "escalation_reason": "Confirmation timeout"
            }
        
        # Process response
        if response["choice"] == "Confirm":
            return {"status": WorkflowStatus.READY_TO_SAVE}
        elif response["choice"] == "Edit":
            return {
                "status": WorkflowStatus.NEEDS_INFO,
                "messages": [AIMessage(content="What would you like to edit?")]
            }
        else:  # Cancel
            return {"status": WorkflowStatus.ABORT}
    
    async def review_research_node(self, state: OnboardingState) -> Dict[str, Any]:
        """
        Human reviews research findings before using them.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state with reviewed research
        """
        # Prepare research for review
        research_summary = self._summarize_research(state["research_notes"])
        
        context = {
            "message": "Review research findings:",
            "research_summary": research_summary,
            "auto_fill_suggestions": self._get_auto_fill_suggestions(state)
        }
        
        intervention_id = self.human_loop.create_interrupt(
            session_id=state["session_id"],
            interrupt_type=InterruptType.REVIEW,
            context=context,
            options=["Approve All", "Review Each", "Skip Research"]
        )
        
        response = await self.human_loop.wait_for_human(intervention_id)
        
        if not response:
            # Continue without research
            return {"feature_flags": {**state["feature_flags"], "enable_auto_fill": False}}
        
        if response["choice"] == "Approve All":
            # Auto-fill from research
            updated_checklist = self._apply_auto_fill(
                state["checklist"],
                state["research_notes"]
            )
            return {"checklist": updated_checklist}
        elif response["choice"] == "Review Each":
            # Create individual confirmations for each auto-fill
            return await self._review_each_auto_fill(state)
        else:
            # Skip research-based auto-fill
            return {"feature_flags": {**state["feature_flags"], "enable_auto_fill": False}}
    
    def _prepare_confirmation_data(self, state: OnboardingState) -> Dict[str, Any]:
        """Prepare data for confirmation display."""
        confirmed_items = {}
        for item in state["checklist"]:
            if item["status"] in [ChecklistStatus.ANSWERED, ChecklistStatus.VERIFIED]:
                confirmed_items[item["prompt"]] = item.get("value", "N/A")
        return confirmed_items
    
    def _summarize_research(self, research_notes: List[ResearchNote]) -> List[str]:
        """Summarize research findings for review."""
        summaries = []
        for note in research_notes[:5]:  # Top 5 findings
            if "summary" in note:
                summaries.append(note["summary"])
        return summaries
    
    def _get_auto_fill_suggestions(self, state: OnboardingState) -> List[Dict]:
        """Get suggestions for auto-filling from research."""
        suggestions = []
        # Logic to match research findings to checklist items
        return suggestions
    
    async def _review_each_auto_fill(self, state: OnboardingState) -> Dict[str, Any]:
        """Review each auto-fill suggestion individually."""
        # Implementation for individual review
        return {}
```

### 3. Escalation Management

```python
class EscalationManager:
    """
    Manages escalation to human agents.
    """
    
    def __init__(self, human_loop: HumanInTheLoop):
        self.human_loop = human_loop
        self.escalation_rules = self._load_escalation_rules()
    
    def _load_escalation_rules(self) -> Dict[str, Any]:
        """Load escalation rules and triggers."""
        return {
            "max_attempts": 3,           # Max attempts for any question
            "timeout_minutes": 30,        # Session timeout
            "confusion_threshold": 0.3,   # Confidence threshold
            "keywords": ["help", "confused", "speak to human", "agent"],
            "blocked_items_threshold": 2  # Max blocked items before escalation
        }
    
    def check_escalation_needed(self, state: OnboardingState) -> Optional[str]:
        """
        Check if escalation is needed based on state.
        
        Args:
            state: Current workflow state
            
        Returns:
            Escalation reason or None
        """
        # Check for explicit escalation request
        if state.get("status") == WorkflowStatus.ESCALATE:
            return state.get("escalation_reason", "Explicit escalation request")
        
        # Check max attempts on any item
        for item in state["checklist"]:
            if item.get("attempts", 0) >= self.escalation_rules["max_attempts"]:
                return f"Max attempts reached for {item['prompt']}"
        
        # Check blocked items
        blocked_count = sum(
            1 for item in state["checklist"] 
            if item["status"] == ChecklistStatus.BLOCKED
        )
        if blocked_count >= self.escalation_rules["blocked_items_threshold"]:
            return f"{blocked_count} items blocked"
        
        # Check for confusion in messages
        if self._detect_confusion(state.get("messages", [])):
            return "User appears confused"
        
        # Check session timeout
        started_at = datetime.fromisoformat(state["started_at"])
        if (datetime.utcnow() - started_at).total_seconds() / 60 > self.escalation_rules["timeout_minutes"]:
            return "Session timeout"
        
        return None
    
    def _detect_confusion(self, messages: List[Dict]) -> bool:
        """Detect if user is confused based on messages."""
        if not messages:
            return False
        
        # Check recent messages for confusion keywords
        recent_messages = messages[-5:]  # Last 5 messages
        for msg in recent_messages:
            content = msg.get("content", "").lower()
            for keyword in self.escalation_rules["keywords"]:
                if keyword in content:
                    return True
        
        return False
    
    async def escalate_to_human(
        self,
        state: OnboardingState,
        reason: str
    ) -> Dict[str, Any]:
        """
        Escalate session to human agent.
        
        Args:
            state: Current workflow state
            reason: Reason for escalation
            
        Returns:
            Updated state after escalation
        """
        # Prepare escalation context
        context = {
            "session_id": state["session_id"],
            "provider_profile": state["provider_profile"],
            "checklist_progress": ChecklistValidator.calculate_progress(state["checklist"]),
            "reason": reason,
            "conversation_summary": self._summarize_conversation(state["messages"]),
            "pending_items": [
                item for item in state["checklist"]
                if item["status"] in [ChecklistStatus.PENDING, ChecklistStatus.ASKED]
            ]
        }
        
        # Create escalation interrupt
        intervention_id = self.human_loop.create_interrupt(
            session_id=state["session_id"],
            interrupt_type=InterruptType.ESCALATION,
            context=context,
            options=["Take Over", "Provide Guidance", "Return to Bot"],
            timeout_minutes=60  # Longer timeout for escalations
        )
        
        # Notify human agent
        if self.human_loop.notification_service:
            self.human_loop.notification_service.alert_escalation(context)
        
        # Wait for human response
        response = await self.human_loop.wait_for_human(intervention_id)
        
        if not response:
            # No human available - save and pause
            return {
                "status": WorkflowStatus.ESCALATE,
                "substatus": "awaiting_human",
                "messages": [AIMessage(
                    content="I've notified a human agent who will assist you shortly. "
                            "Your progress has been saved."
                )]
            }
        
        # Process human agent response
        if response["choice"] == "Take Over":
            # Human takes over completely
            return {
                "status": WorkflowStatus.ESCALATE,
                "substatus": "human_handling",
                "human_agent_id": response.get("agent_id"),
                "messages": [AIMessage(
                    content="You've been connected with a human agent who will assist you."
                )]
            }
        elif response["choice"] == "Provide Guidance":
            # Human provides guidance, bot continues
            guidance = response.get("guidance", {})
            return {
                "status": WorkflowStatus.ON_TRACK,
                "messages": [AIMessage(content=guidance.get("message", ""))],
                "checklist": self._apply_human_guidance(state["checklist"], guidance)
            }
        else:  # Return to Bot
            return {
                "status": WorkflowStatus.ON_TRACK,
                "messages": [AIMessage(
                    content="Let's continue with the onboarding process."
                )]
            }
    
    def _summarize_conversation(self, messages: List[Dict]) -> str:
        """Summarize conversation for human agent."""
        # Extract key points from conversation
        summary_points = []
        for msg in messages[-10:]:  # Last 10 messages
            if msg.get("role") == "user":
                summary_points.append(f"User: {msg['content'][:100]}...")
        return "\n".join(summary_points)
    
    def _apply_human_guidance(
        self,
        checklist: List[ChecklistItem],
        guidance: Dict[str, Any]
    ) -> List[ChecklistItem]:
        """Apply human guidance to checklist."""
        # Update checklist based on human input
        if "skip_items" in guidance:
            for item_key in guidance["skip_items"]:
                for item in checklist:
                    if item["key"] == item_key:
                        item["status"] = ChecklistStatus.SKIPPED
        
        if "prefill_items" in guidance:
            for item_key, value in guidance["prefill_items"].items():
                for item in checklist:
                    if item["key"] == item_key:
                        item["value"] = value
                        item["status"] = ChecklistStatus.VERIFIED
                        item["source"] = "human_agent"
        
        return checklist
```

### 4. Approval Workflows

```python
class ApprovalWorkflow:
    """
    Manages approval workflows for final submission.
    """
    
    def __init__(self, human_loop: HumanInTheLoop):
        self.human_loop = human_loop
    
    async def final_approval_node(self, state: OnboardingState) -> Dict[str, Any]:
        """
        Request final approval before saving.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated state based on approval
        """
        # Generate final summary
        summary = self._generate_final_summary(state)
        
        # Check if human approval is required
        if self._requires_human_approval(state):
            context = {
                "summary": summary,
                "provider_data": state["provider_profile"],
                "checklist": state["checklist"],
                "quality_score": self._calculate_quality_score(state)
            }
            
            intervention_id = self.human_loop.create_interrupt(
                session_id=state["session_id"],
                interrupt_type=InterruptType.APPROVAL,
                context=context,
                options=["Approve", "Request Changes", "Reject"]
            )
            
            response = await self.human_loop.wait_for_human(intervention_id)
            
            if not response or response["choice"] == "Reject":
                return {
                    "status": WorkflowStatus.ABORT,
                    "messages": [AIMessage(
                        content="The submission has been rejected. Please contact support."
                    )]
                }
            elif response["choice"] == "Request Changes":
                changes = response.get("requested_changes", [])
                return {
                    "status": WorkflowStatus.NEEDS_INFO,
                    "messages": [AIMessage(
                        content=f"Please address the following: {', '.join(changes)}"
                    )]
                }
            else:  # Approved
                return {
                    "status": WorkflowStatus.FINALIZE_SAVE,
                    "approval": {
                        "approved_by": response.get("approver_id"),
                        "approved_at": datetime.utcnow().isoformat(),
                        "notes": response.get("notes")
                    }
                }
        else:
            # Auto-approve if quality score is high
            return {
                "status": WorkflowStatus.FINALIZE_SAVE,
                "approval": {
                    "auto_approved": True,
                    "approved_at": datetime.utcnow().isoformat()
                }
            }
    
    def _requires_human_approval(self, state: OnboardingState) -> bool:
        """Determine if human approval is required."""
        # Check quality score
        quality_score = self._calculate_quality_score(state)
        if quality_score < 0.8:
            return True
        
        # Check for high-value providers
        if state["provider_profile"].get("tier") == "premium":
            return True
        
        # Check for sensitive service types
        if state["service_type"] in ["legal", "financial"]:
            return True
        
        return False
    
    def _calculate_quality_score(self, state: OnboardingState) -> float:
        """Calculate quality score of the submission."""
        score = 0.0
        total_weight = 0.0
        
        # Completion score
        progress = ChecklistValidator.calculate_progress(state["checklist"])
        score += progress["required_completion_percentage"] * 0.5
        total_weight += 50
        
        # Research depth score
        research_count = len(state.get("research_notes", []))
        research_score = min(research_count / 10, 1.0)  # Max at 10 research items
        score += research_score * 20
        total_weight += 20
        
        # Validation score
        validated_items = sum(
            1 for item in state["checklist"]
            if item["status"] == ChecklistStatus.VERIFIED
        )
        total_items = len(state["checklist"])
        validation_score = validated_items / total_items if total_items > 0 else 0
        score += validation_score * 30
        total_weight += 30
        
        return score / total_weight if total_weight > 0 else 0
    
    def _generate_final_summary(self, state: OnboardingState) -> str:
        """Generate final summary for approval."""
        summary_parts = [
            f"Provider: {state['provider_profile'].get('name', 'Unknown')}",
            f"Service Type: {state['service_type']}",
            f"Completion: {state['completion_percentage']:.1f}%",
            f"Session Duration: {self._calculate_duration(state)}",
            f"Research Items: {len(state.get('research_notes', []))}",
        ]
        
        return "\n".join(summary_parts)
    
    def _calculate_duration(self, state: OnboardingState) -> str:
        """Calculate session duration."""
        started_at = datetime.fromisoformat(state["started_at"])
        duration = datetime.utcnow() - started_at
        minutes = int(duration.total_seconds() / 60)
        return f"{minutes} minutes"
```

### 5. Notification Service

```python
class NotificationService:
    """
    Service for notifying humans about interventions.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.notification_queue: List[Dict] = []
    
    def notify_human_needed(self, intervention: Dict[str, Any]):
        """
        Send notification that human intervention is needed.
        
        Args:
            intervention: Intervention details
        """
        notification = {
            "type": "intervention_needed",
            "intervention_id": intervention["id"],
            "session_id": intervention["session_id"],
            "intervention_type": intervention["type"].value,
            "priority": self._calculate_priority(intervention),
            "message": self._format_notification_message(intervention),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self._send_notification(notification)
    
    def alert_escalation(self, context: Dict[str, Any]):
        """
        Send urgent alert for escalation.
        
        Args:
            context: Escalation context
        """
        alert = {
            "type": "escalation_alert",
            "session_id": context["session_id"],
            "priority": "high",
            "reason": context["reason"],
            "message": f"ESCALATION: {context['reason']} for session {context['session_id']}",
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self._send_notification(alert)
    
    def _calculate_priority(self, intervention: Dict) -> str:
        """Calculate notification priority."""
        if intervention["type"] == InterruptType.ESCALATION:
            return "high"
        elif intervention["type"] == InterruptType.APPROVAL:
            return "medium"
        else:
            return "low"
    
    def _format_notification_message(self, intervention: Dict) -> str:
        """Format notification message."""
        messages = {
            InterruptType.CONFIRMATION: "User confirmation needed",
            InterruptType.REVIEW: "Research review required",
            InterruptType.ESCALATION: "Session escalated - agent needed",
            InterruptType.APPROVAL: "Final approval required",
            InterruptType.CLARIFICATION: "Clarification needed",
            InterruptType.OVERRIDE: "Override decision required"
        }
        
        return messages.get(intervention["type"], "Human intervention needed")
    
    def _send_notification(self, notification: Dict):
        """Send notification through configured channels."""
        # Implementation would depend on notification channels
        # (email, Slack, webhook, etc.)
        self.notification_queue.append(notification)
        
        # Example: Send to webhook
        if self.config.get("webhook_url"):
            # requests.post(self.config["webhook_url"], json=notification)
            pass
        
        # Example: Send email
        if self.config.get("email_enabled"):
            # send_email(notification)
            pass
```

## Integration Example

```python
# Example of integrating human-in-the-loop with the main agent

def create_agent_with_human_loop():
    """
    Create the onboarding agent with human-in-the-loop capabilities.
    """
    # Initialize services
    notification_service = NotificationService({
        "webhook_url": os.getenv("NOTIFICATION_WEBHOOK"),
        "email_enabled": True
    })
    
    human_loop = HumanInTheLoop(notification_service)
    confirmation_nodes = ConfirmationNodes(human_loop)
    escalation_manager = EscalationManager(human_loop)
    approval_workflow = ApprovalWorkflow(human_loop)
    
    # Build graph with human intervention nodes
    graph = StateGraph(OnboardingState)
    
    # Add regular nodes
    graph.add_node("intake", intake_node)
    graph.add_node("research", research_node)
    
    # Add human intervention nodes
    graph.add_node("confirm", confirmation_nodes.confirmation_node)
    graph.add_node("review_research", confirmation_nodes.review_research_node)
    graph.add_node("escalate", escalation_manager.escalate_to_human)
    graph.add_node("final_approval", approval_workflow.final_approval_node)
    
    # Add conditional edges for human intervention
    graph.add_conditional_edges(
        "research",
        lambda state: "review_research" if state["feature_flags"]["enable_research"] else "intake",
        {
            "review_research": "review_research",
            "intake": "intake"
        }
    )
    
    # Add escalation checks
    graph.add_conditional_edges(
        "intake",
        lambda state: "escalate" if escalation_manager.check_escalation_needed(state) else "confirm",
        {
            "escalate": "escalate",
            "confirm": "confirm"
        }
    )
    
    # Add final approval
    graph.add_edge("confirm", "final_approval")
    graph.add_edge("final_approval", END)
    
    return graph.compile()
```