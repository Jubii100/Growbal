# Evolved Human-in-the-Loop System

## Overview

The evolved human-in-the-loop system provides intelligent escalation, seamless handoffs, and quality control mechanisms that adapt based on the conversation flow, ensuring human intervention occurs precisely when needed while maintaining workflow efficiency.

## Intelligent Escalation Framework

### 1. Adaptive Escalation Detection

```python
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

class EscalationReason(Enum):
    """Categorized escalation reasons"""
    USER_REQUEST = "user_request"              # Explicit request for human
    CONFUSION_DETECTED = "confusion_detected"   # User appears confused
    VALIDATION_FAILURES = "validation_failures" # Multiple validation failures
    COMPLEX_SCENARIO = "complex_scenario"       # Scenario too complex for bot
    HIGH_VALUE_CASE = "high_value_case"        # High-value provider/client
    SENTIMENT_NEGATIVE = "sentiment_negative"   # Negative sentiment detected
    TIMEOUT = "timeout"                        # Session taking too long
    TECHNICAL_ERROR = "technical_error"        # System error requiring human
    QUALITY_THRESHOLD = "quality_threshold"    # Quality score below threshold
    REGULATORY_REQUIREMENT = "regulatory"       # Regulatory compliance needs human

@dataclass
class EscalationContext:
    """Context for escalation decision"""
    reason: EscalationReason
    confidence: float
    urgency: str  # low, medium, high, critical
    suggested_action: str
    context_data: Dict[str, Any]
    user_sentiment: Optional[float]
    conversation_summary: str
    pending_items: List[str]
    
class IntelligentEscalationDetector:
    """
    Detects need for human intervention using multiple signals.
    """
    
    def __init__(self, llm, sentiment_analyzer, config):
        self.llm = llm
        self.sentiment = sentiment_analyzer
        self.config = config
        self.escalation_history = []
        
        # Configurable thresholds
        self.thresholds = {
            "confusion_score": 0.7,
            "negative_sentiment": -0.5,
            "validation_failure_limit": 3,
            "session_timeout_minutes": 30,
            "quality_score_minimum": 0.6
        }
    
    async def evaluate_escalation_need(
        self,
        state: Dict[str, Any]
    ) -> Tuple[bool, Optional[EscalationContext]]:
        """
        Evaluate if escalation is needed based on multiple factors.
        
        Args:
            state: Current workflow state
            
        Returns:
            Tuple of (needs_escalation, context)
        """
        escalation_signals = []
        
        # Check explicit user request
        user_request = self._check_user_request(state.get("last_user_message", ""))
        if user_request:
            escalation_signals.append(user_request)
        
        # Analyze confusion level
        confusion = await self._analyze_confusion(state)
        if confusion and confusion.confidence > self.thresholds["confusion_score"]:
            escalation_signals.append(confusion)
        
        # Check validation failures
        validation = self._check_validation_failures(state)
        if validation:
            escalation_signals.append(validation)
        
        # Analyze sentiment
        sentiment = await self._analyze_sentiment(state)
        if sentiment and sentiment.confidence > 0.8:
            escalation_signals.append(sentiment)
        
        # Check complexity
        complexity = await self._assess_complexity(state)
        if complexity:
            escalation_signals.append(complexity)
        
        # Check business rules
        business_rules = self._check_business_rules(state)
        if business_rules:
            escalation_signals.append(business_rules)
        
        # Determine if escalation is needed
        if escalation_signals:
            # Prioritize and select primary reason
            primary_signal = max(escalation_signals, key=lambda x: x.confidence)
            
            # Calculate overall urgency
            urgency = self._calculate_urgency(escalation_signals, state)
            
            context = EscalationContext(
                reason=primary_signal.reason,
                confidence=primary_signal.confidence,
                urgency=urgency,
                suggested_action=self._suggest_action(primary_signal, state),
                context_data=self._gather_context(state),
                user_sentiment=sentiment.confidence if sentiment else None,
                conversation_summary=self._summarize_conversation(state),
                pending_items=self._get_pending_items(state)
            )
            
            return True, context
        
        return False, None
    
    def _check_user_request(self, message: str) -> Optional[EscalationContext]:
        """
        Check for explicit escalation requests.
        """
        escalation_phrases = [
            "speak to human",
            "talk to agent",
            "need help",
            "get me someone",
            "human please",
            "real person",
            "supervisor",
            "manager",
            "escalate"
        ]
        
        message_lower = message.lower()
        for phrase in escalation_phrases:
            if phrase in message_lower:
                return EscalationContext(
                    reason=EscalationReason.USER_REQUEST,
                    confidence=1.0,
                    urgency="high",
                    suggested_action="immediate_handoff",
                    context_data={"trigger_phrase": phrase},
                    user_sentiment=None,
                    conversation_summary="",
                    pending_items=[]
                )
        
        return None
    
    async def _analyze_confusion(self, state: Dict) -> Optional[EscalationContext]:
        """
        Analyze conversation for signs of confusion.
        """
        messages = state.get("messages", [])
        if len(messages) < 4:
            return None
        
        # Get recent messages
        recent = messages[-6:]
        
        # Use LLM to detect confusion
        prompt = f"""
        Analyze this conversation for signs of user confusion:
        
        {self._format_messages(recent)}
        
        Look for:
        1. Repeated questions
        2. Contradictory responses
        3. Expressions of confusion
        4. Off-topic responses
        5. Request for clarification
        
        Return:
        - Confusion score (0-1)
        - Specific indicators found
        - Recommended action
        """
        
        analysis = await self.llm.ainvoke(prompt)
        # Parse analysis
        
        confusion_score = 0.8  # Placeholder
        
        if confusion_score > self.thresholds["confusion_score"]:
            return EscalationContext(
                reason=EscalationReason.CONFUSION_DETECTED,
                confidence=confusion_score,
                urgency="medium",
                suggested_action="clarification_support",
                context_data={"indicators": ["repeated_questions"]},
                user_sentiment=None,
                conversation_summary="",
                pending_items=[]
            )
        
        return None
    
    async def _analyze_sentiment(self, state: Dict) -> Optional[EscalationContext]:
        """
        Analyze user sentiment throughout conversation.
        """
        messages = state.get("messages", [])
        user_messages = [m for m in messages if m.get("role") == "user"]
        
        if not user_messages:
            return None
        
        # Analyze sentiment trajectory
        sentiments = []
        for msg in user_messages[-5:]:  # Last 5 user messages
            score = await self.sentiment.analyze(msg.get("content", ""))
            sentiments.append(score)
        
        # Check for negative trend
        if sentiments and np.mean(sentiments) < self.thresholds["negative_sentiment"]:
            return EscalationContext(
                reason=EscalationReason.SENTIMENT_NEGATIVE,
                confidence=abs(np.mean(sentiments)),
                urgency="high",
                suggested_action="empathy_handoff",
                context_data={"sentiment_scores": sentiments},
                user_sentiment=np.mean(sentiments),
                conversation_summary="",
                pending_items=[]
            )
        
        return None
    
    async def _assess_complexity(self, state: Dict) -> Optional[EscalationContext]:
        """
        Assess if the scenario is too complex for automated handling.
        """
        checklist = state.get("checklist", [])
        
        # Calculate complexity indicators
        blocked_items = sum(1 for item in checklist if item.get("status") == "BLOCKED")
        clarification_needed = sum(1 for item in checklist if item.get("status") == "NEEDS_CLARIFICATION")
        total_items = len(checklist)
        custom_requirements = sum(1 for item in checklist if item.get("source") == "dynamic")
        
        complexity_score = (
            (blocked_items * 0.3) +
            (clarification_needed * 0.2) +
            (custom_requirements * 0.25) +
            (min(total_items / 50, 1) * 0.25)  # Many items indicate complexity
        )
        
        if complexity_score > 0.7:
            return EscalationContext(
                reason=EscalationReason.COMPLEX_SCENARIO,
                confidence=complexity_score,
                urgency="medium",
                suggested_action="expert_consultation",
                context_data={
                    "blocked_items": blocked_items,
                    "clarification_needed": clarification_needed,
                    "custom_requirements": custom_requirements
                },
                user_sentiment=None,
                conversation_summary="",
                pending_items=[]
            )
        
        return None
```

### 2. Seamless Handoff Mechanism

```python
class SeamlessHandoffManager:
    """
    Manages smooth transitions between bot and human agents.
    """
    
    def __init__(self, agent_pool, notification_service):
        self.agent_pool = agent_pool
        self.notifications = notification_service
        self.handoff_queue = []
        self.active_handoffs = {}
    
    async def initiate_handoff(
        self,
        session_id: str,
        escalation_context: EscalationContext,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Initiate handoff to human agent.
        
        Args:
            session_id: Session to handoff
            escalation_context: Reason and context for handoff
            state: Current state
            
        Returns:
            Handoff result
        """
        # Package handoff request
        handoff_request = {
            "session_id": session_id,
            "escalation_context": escalation_context,
            "state_snapshot": self._create_state_snapshot(state),
            "priority": self._calculate_priority(escalation_context),
            "requested_at": datetime.utcnow().isoformat(),
            "estimated_wait": None
        }
        
        # Find available agent
        agent = await self._find_suitable_agent(
            escalation_context=escalation_context,
            state=state
        )
        
        if agent:
            # Direct assignment
            return await self._assign_to_agent(
                handoff_request=handoff_request,
                agent=agent
            )
        else:
            # Queue for next available
            return await self._queue_handoff(handoff_request)
    
    async def _find_suitable_agent(
        self,
        escalation_context: EscalationContext,
        state: Dict[str, Any]
    ) -> Optional[Dict]:
        """
        Find the most suitable available agent.
        """
        available_agents = await self.agent_pool.get_available_agents()
        
        if not available_agents:
            return None
        
        # Score agents based on suitability
        scored_agents = []
        for agent in available_agents:
            score = self._calculate_agent_suitability(
                agent=agent,
                escalation_context=escalation_context,
                service_type=state.get("service_type")
            )
            scored_agents.append((agent, score))
        
        # Sort by score and return best match
        scored_agents.sort(key=lambda x: x[1], reverse=True)
        
        if scored_agents[0][1] > 0.5:  # Minimum suitability threshold
            return scored_agents[0][0]
        
        return None
    
    def _calculate_agent_suitability(
        self,
        agent: Dict,
        escalation_context: EscalationContext,
        service_type: str
    ) -> float:
        """
        Calculate how suitable an agent is for this handoff.
        """
        score = 0.0
        
        # Check expertise match
        if service_type in agent.get("expertise", []):
            score += 0.3
        
        # Check language match (if applicable)
        # Check availability status
        if agent.get("status") == "available":
            score += 0.2
        elif agent.get("status") == "busy_low_priority":
            score += 0.1
        
        # Check workload
        current_load = agent.get("current_sessions", 0)
        max_load = agent.get("max_sessions", 5)
        load_ratio = current_load / max_load
        score += (1 - load_ratio) * 0.2
        
        # Check escalation type expertise
        if escalation_context.reason.value in agent.get("specializations", []):
            score += 0.3
        
        return score
    
    async def _assign_to_agent(
        self,
        handoff_request: Dict,
        agent: Dict
    ) -> Dict[str, Any]:
        """
        Assign session to specific agent.
        """
        assignment = {
            "handoff_id": str(uuid.uuid4()),
            "session_id": handoff_request["session_id"],
            "agent_id": agent["id"],
            "agent_name": agent["name"],
            "assigned_at": datetime.utcnow().isoformat(),
            "status": "assigned",
            "handoff_request": handoff_request
        }
        
        # Update agent availability
        await self.agent_pool.assign_session(
            agent_id=agent["id"],
            session_id=handoff_request["session_id"]
        )
        
        # Notify agent
        await self.notifications.notify_agent_assignment(
            agent=agent,
            assignment=assignment
        )
        
        # Store active handoff
        self.active_handoffs[handoff_request["session_id"]] = assignment
        
        # Prepare transition message for user
        transition_message = self._generate_transition_message(
            agent_name=agent["name"],
            estimated_response_time=agent.get("avg_response_time", "shortly")
        )
        
        return {
            "success": True,
            "handoff_id": assignment["handoff_id"],
            "agent": agent,
            "message": transition_message,
            "estimated_response_time": agent.get("avg_response_time", 60)
        }
    
    def _generate_transition_message(
        self,
        agent_name: str,
        estimated_response_time: str
    ) -> str:
        """
        Generate smooth transition message for user.
        """
        return f"""I'm connecting you with {agent_name}, one of our specialists who can better assist you with your specific needs.

They'll review our conversation and continue helping you from here. You can expect a response {estimated_response_time}.

Is there anything specific you'd like me to highlight for them before they take over?"""
```

### 3. Human Review and Override System

```python
class HumanReviewSystem:
    """
    Enables human review and override of bot decisions.
    """
    
    def __init__(self, review_queue, llm):
        self.review_queue = review_queue
        self.llm = llm
        self.review_history = []
    
    async def submit_for_review(
        self,
        session_id: str,
        review_type: str,
        data: Dict[str, Any],
        priority: str = "normal"
    ) -> str:
        """
        Submit item for human review.
        
        Args:
            session_id: Session ID
            review_type: Type of review needed
            data: Data to review
            priority: Review priority
            
        Returns:
            Review ID
        """
        review_id = str(uuid.uuid4())
        
        review_item = {
            "review_id": review_id,
            "session_id": session_id,
            "type": review_type,
            "data": data,
            "priority": priority,
            "status": "pending",
            "submitted_at": datetime.utcnow().isoformat(),
            "reviewed_at": None,
            "reviewer_id": None,
            "decision": None,
            "notes": None
        }
        
        # Add to queue based on priority
        await self.review_queue.add(review_item, priority)
        
        return review_id
    
    async def review_checklist_completion(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Review completed checklist before final save.
        
        Args:
            state: Current state with completed checklist
            
        Returns:
            Review decision
        """
        # Analyze checklist quality
        quality_analysis = await self._analyze_checklist_quality(state)
        
        # Determine if review is needed
        if quality_analysis["requires_review"]:
            review_id = await self.submit_for_review(
                session_id=state["session_id"],
                review_type="checklist_completion",
                data={
                    "checklist": state["checklist"],
                    "quality_analysis": quality_analysis,
                    "provider_profile": state["provider_profile"]
                },
                priority=self._determine_review_priority(quality_analysis)
            )
            
            # Wait for review with timeout
            review_result = await self._wait_for_review(
                review_id=review_id,
                timeout_seconds=300  # 5 minutes
            )
            
            if review_result:
                return self._process_review_decision(review_result)
            else:
                # Timeout - auto-approve with flag
                return {
                    "approved": True,
                    "auto_approved": True,
                    "reason": "Review timeout - auto-approved",
                    "quality_score": quality_analysis["overall_score"]
                }
        else:
            # Auto-approve high quality
            return {
                "approved": True,
                "auto_approved": True,
                "reason": "High quality - no review needed",
                "quality_score": quality_analysis["overall_score"]
            }
    
    async def _analyze_checklist_quality(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Analyze the quality of completed checklist.
        """
        checklist = state["checklist"]
        
        # Calculate quality metrics
        metrics = {
            "completion_rate": self._calculate_completion_rate(checklist),
            "auto_fill_rate": self._calculate_auto_fill_rate(checklist),
            "validation_pass_rate": self._calculate_validation_rate(checklist),
            "confidence_score": self._calculate_confidence_score(checklist),
            "data_consistency": await self._check_data_consistency(checklist),
            "suspicious_patterns": await self._detect_suspicious_patterns(checklist)
        }
        
        # Calculate overall score
        overall_score = (
            metrics["completion_rate"] * 0.3 +
            (1 - metrics["auto_fill_rate"]) * 0.2 +  # Prefer human input
            metrics["validation_pass_rate"] * 0.2 +
            metrics["confidence_score"] * 0.15 +
            metrics["data_consistency"] * 0.15
        )
        
        # Determine if review is needed
        requires_review = (
            overall_score < 0.8 or
            metrics["suspicious_patterns"] or
            metrics["auto_fill_rate"] > 0.7 or
            state.get("provider_profile", {}).get("tier") == "premium"
        )
        
        return {
            "requires_review": requires_review,
            "overall_score": overall_score,
            "metrics": metrics,
            "risk_factors": self._identify_risk_factors(metrics)
        }
    
    async def handle_human_override(
        self,
        session_id: str,
        override_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle human override of bot decisions.
        
        Args:
            session_id: Session being overridden
            override_data: Override instructions
            
        Returns:
            Override result
        """
        override_type = override_data.get("type")
        
        if override_type == "checklist_modification":
            return await self._override_checklist(
                session_id=session_id,
                modifications=override_data["modifications"]
            )
        elif override_type == "skip_verification":
            return await self._skip_verification(
                session_id=session_id,
                items_to_skip=override_data["items"]
            )
        elif override_type == "force_complete":
            return await self._force_completion(
                session_id=session_id,
                reason=override_data.get("reason")
            )
        else:
            return {"error": f"Unknown override type: {override_type}"}
    
    async def _override_checklist(
        self,
        session_id: str,
        modifications: List[Dict]
    ) -> Dict[str, Any]:
        """
        Apply human modifications to checklist.
        """
        results = []
        
        for mod in modifications:
            if mod["action"] == "update_value":
                result = await self._update_item_value(
                    session_id=session_id,
                    item_key=mod["item_key"],
                    new_value=mod["value"],
                    override_validation=True
                )
            elif mod["action"] == "mark_complete":
                result = await self._mark_item_complete(
                    session_id=session_id,
                    item_key=mod["item_key"]
                )
            elif mod["action"] == "skip_item":
                result = await self._skip_item(
                    session_id=session_id,
                    item_key=mod["item_key"],
                    reason=mod.get("reason")
                )
            else:
                result = {"error": f"Unknown action: {mod['action']}"}
            
            results.append(result)
        
        # Log override
        self.review_history.append({
            "session_id": session_id,
            "type": "checklist_override",
            "modifications": modifications,
            "timestamp": datetime.utcnow().isoformat(),
            "results": results
        })
        
        return {
            "success": True,
            "modifications_applied": len(results),
            "results": results
        }
```

### 4. Quality Control and Confirmation

```python
class QualityControlSystem:
    """
    Ensures quality through strategic confirmation points.
    """
    
    def __init__(self, llm, confirmation_templates):
        self.llm = llm
        self.templates = confirmation_templates
        self.confirmation_points = []
    
    async def determine_confirmation_need(
        self,
        state: Dict[str, Any],
        checkpoint_type: str
    ) -> bool:
        """
        Determine if confirmation is needed at this checkpoint.
        
        Args:
            state: Current state
            checkpoint_type: Type of checkpoint
            
        Returns:
            Whether confirmation is needed
        """
        if checkpoint_type == "pre_research":
            # Confirm before conducting extensive research
            return self._should_confirm_research(state)
        elif checkpoint_type == "post_research":
            # Confirm research findings before using
            return self._should_confirm_research_findings(state)
        elif checkpoint_type == "critical_update":
            # Confirm critical checklist updates
            return self._should_confirm_critical_update(state)
        elif checkpoint_type == "pre_save":
            # Always confirm before final save
            return True
        
        return False
    
    async def request_confirmation(
        self,
        state: Dict[str, Any],
        confirmation_type: str
    ) -> Dict[str, Any]:
        """
        Request user confirmation at key points.
        
        Args:
            state: Current state
            confirmation_type: Type of confirmation
            
        Returns:
            Confirmation result
        """
        # Generate confirmation message
        confirmation_message = await self._generate_confirmation_message(
            state=state,
            confirmation_type=confirmation_type
        )
        
        # Create confirmation request
        confirmation_request = {
            "session_id": state["session_id"],
            "type": confirmation_type,
            "message": confirmation_message,
            "options": self._get_confirmation_options(confirmation_type),
            "data_summary": self._create_data_summary(state, confirmation_type),
            "requested_at": datetime.utcnow().isoformat()
        }
        
        # Log confirmation point
        self.confirmation_points.append(confirmation_request)
        
        return confirmation_request
    
    async def _generate_confirmation_message(
        self,
        state: Dict[str, Any],
        confirmation_type: str
    ) -> str:
        """
        Generate contextual confirmation message.
        """
        if confirmation_type == "final_save":
            return await self._generate_final_confirmation(state)
        elif confirmation_type == "research_findings":
            return await self._generate_research_confirmation(state)
        elif confirmation_type == "critical_update":
            return await self._generate_update_confirmation(state)
        
        return "Please confirm to proceed."
    
    async def _generate_final_confirmation(
        self,
        state: Dict[str, Any]
    ) -> str:
        """
        Generate comprehensive final confirmation message.
        """
        checklist = state["checklist"]
        completed_items = [i for i in checklist if i.get("status") in ["VERIFIED", "AUTO_FILLED"]]
        
        prompt = f"""
        Generate a clear, professional confirmation message for the user to review before saving:
        
        Provider Information:
        {json.dumps(state["provider_profile"], indent=2)}
        
        Completed Information ({len(completed_items)}/{len(checklist)} items):
        {json.dumps([{
            "question": item["prompt"],
            "answer": item.get("value"),
            "source": item.get("source", "user")
        } for item in completed_items[:10]], indent=2)}
        
        Session Metrics:
        - Duration: {state.get("total_duration_seconds", 0) / 60:.1f} minutes
        - Questions Asked: {state.get("message_count", 0)}
        - Auto-filled Items: {sum(1 for i in checklist if i.get("source") == "research")}
        
        Create a confirmation message that:
        1. Summarizes key information collected
        2. Highlights any auto-filled items for review
        3. Asks for explicit confirmation to save
        4. Mentions ability to edit if needed
        """
        
        message = await self.llm.ainvoke(prompt)
        return message.content
    
    async def process_confirmation_response(
        self,
        session_id: str,
        response: str,
        confirmation_type: str
    ) -> Dict[str, Any]:
        """
        Process user's confirmation response.
        
        Args:
            session_id: Session ID
            response: User's response
            confirmation_type: Type of confirmation
            
        Returns:
            Processing result
        """
        if response == "confirm":
            return {
                "action": "proceed",
                "confirmed": True,
                "timestamp": datetime.utcnow().isoformat()
            }
        elif response == "edit":
            return {
                "action": "edit_requested",
                "confirmed": False,
                "next_step": "collect_edit_requirements"
            }
        elif response == "cancel":
            return {
                "action": "cancelled",
                "confirmed": False,
                "next_step": "handle_cancellation"
            }
        else:
            # Handle custom response
            return await self._handle_custom_response(
                session_id=session_id,
                response=response,
                confirmation_type=confirmation_type
            )
```

## Integration with Main Workflow

```python
class EvolvedHumanInTheLoopIntegration:
    """
    Integrates human-in-the-loop capabilities with main workflow.
    """
    
    def __init__(self, config: Dict):
        self.escalation_detector = IntelligentEscalationDetector(
            llm=config["llm"],
            sentiment_analyzer=config["sentiment_analyzer"],
            config=config["escalation_config"]
        )
        
        self.handoff_manager = SeamlessHandoffManager(
            agent_pool=config["agent_pool"],
            notification_service=config["notification_service"]
        )
        
        self.review_system = HumanReviewSystem(
            review_queue=config["review_queue"],
            llm=config["llm"]
        )
        
        self.quality_control = QualityControlSystem(
            llm=config["llm"],
            confirmation_templates=config["templates"]
        )
    
    async def check_intervention_needed(
        self,
        state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Check if any human intervention is needed.
        
        Args:
            state: Current workflow state
            
        Returns:
            Intervention decision
        """
        # Check for escalation
        needs_escalation, escalation_context = await self.escalation_detector.evaluate_escalation_need(state)
        
        if needs_escalation:
            # Initiate handoff
            handoff_result = await self.handoff_manager.initiate_handoff(
                session_id=state["session_id"],
                escalation_context=escalation_context,
                state=state
            )
            
            return {
                "intervention_needed": True,
                "type": "escalation",
                "handoff_result": handoff_result,
                "next_action": "await_human_takeover"
            }
        
        # Check for confirmation points
        checkpoint_type = self._determine_checkpoint_type(state)
        if await self.quality_control.determine_confirmation_need(state, checkpoint_type):
            confirmation_request = await self.quality_control.request_confirmation(
                state=state,
                confirmation_type=checkpoint_type
            )
            
            return {
                "intervention_needed": True,
                "type": "confirmation",
                "confirmation_request": confirmation_request,
                "next_action": "await_confirmation"
            }
        
        # Check for review requirements
        if self._needs_review(state):
            review_id = await self.review_system.submit_for_review(
                session_id=state["session_id"],
                review_type="quality_check",
                data=state,
                priority="normal"
            )
            
            return {
                "intervention_needed": True,
                "type": "review",
                "review_id": review_id,
                "next_action": "continue_with_flag"
            }
        
        return {
            "intervention_needed": False,
            "next_action": "continue_workflow"
        }
    
    def _determine_checkpoint_type(self, state: Dict) -> str:
        """
        Determine what type of checkpoint we're at.
        """
        status = state.get("workflow_status")
        
        if status == "READY_FOR_CONFIRMATION":
            return "final_save"
        elif status == "PARSING_RESEARCH":
            return "research_findings"
        elif state.get("critical_update_pending"):
            return "critical_update"
        
        return "standard"
    
    def _needs_review(self, state: Dict) -> bool:
        """
        Determine if state needs review.
        """
        # Check various review triggers
        return (
            state.get("auto_fill_count", 0) > 5 or
            state.get("validation_failures", 0) > 2 or
            state.get("provider_profile", {}).get("tier") == "premium"
        )
```