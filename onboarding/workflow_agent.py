"""
Adaptive Workflow Agent with LangGraph for Two-Part Research Onboarding
"""
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

from state_manager import (
    EvolvedOnboardingState, WorkflowDecision, initialize_state
)
from research_engine import TwoPartResearchOrchestrator
from llm_wrapper import OnboardingLLM


class AdaptiveOnboardingAgent:
    """
    Evolved onboarding agent with two-part research process using LangGraph
    """
    
    def __init__(self, interactive_mode: bool = True):
        """
        Initialize the agent.
        
        Args:
            interactive_mode: If True, prompts for actual user input.
                            If False, uses simulated responses for testing.
        """
        self.llm = OnboardingLLM()
        self.research_orchestrator = TwoPartResearchOrchestrator()
        self.interactive_mode = interactive_mode
        self.graph = self._build_adaptive_graph()
        
        if self.interactive_mode:
            print("Interactive Mode: ENABLED - User input will be requested")
        else:
            print("Simulation Mode: ENABLED - Using automated responses")
    
    async def run(self, initial_state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Run the compiled graph starting from the provided initial state."""
        import asyncio
        try:
            # Add overall timeout to prevent workflow from hanging indefinitely
            print("⏱️ Starting workflow with 10-minute timeout protection")
            result = await asyncio.wait_for(
                self.graph.ainvoke(initial_state),
                timeout=1200.0  # 20 minute timeout for entire workflow
            )
            print("Workflow completed within timeout")
            return result
        except asyncio.TimeoutError:
            print("Workflow timed out after 10 minutes")
            # Return the current state with error status
            initial_state["workflow_status"] = "timeout_error"
            initial_state["error_message"] = "Workflow timed out after 10 minutes"
            return initial_state
        except Exception as e:
            print(f"Workflow failed with error: {str(e)}")
            # Return the current state with error status
            initial_state["workflow_status"] = "error"
            initial_state["error_message"] = str(e)
            return initial_state
        
    def _build_adaptive_graph(self) -> StateGraph:
        """
        Construct the adaptive workflow graph with two-part research
        """
        graph = StateGraph(EvolvedOnboardingState)
        
        # Core workflow nodes
        graph.add_node("intake", self.intake_phase_node)
        graph.add_node("research_decision", self.research_decision_node)
        
        # Two-part research nodes
        graph.add_node("checklist_research", self.checklist_customization_research_node)
        graph.add_node("answer_research", self.answer_gathering_research_node)
        graph.add_node("evaluate_research", self.evaluate_research_results_node)
        
        # Question and answer nodes
        graph.add_node("generate_question", self.generate_sequential_question_node)
        graph.add_node("process_response", self.process_user_response_node)
        graph.add_node("update_checklist", self.update_checklist_node)
        
        # Confirmation and completion nodes
        graph.add_node("request_confirmation", self.request_answer_confirmation_node)
        graph.add_node("final_confirmation", self.final_confirmation_node)
        graph.add_node("save_results", self.save_results_node)
        
        # Define the adaptive workflow edges
        graph.add_edge(START, "intake")
        graph.add_edge("intake", "research_decision")
        
        # Research decision branching
        graph.add_conditional_edges(
            "research_decision",
            self.should_conduct_research,
            {
                "checklist_research": "checklist_research",
                "answer_research": "answer_research",
                "skip": "generate_question"
            }
        )
        
        # Research flow
        graph.add_edge("checklist_research", "answer_research")
        graph.add_edge("answer_research", "evaluate_research")
        
        # Research evaluation branching
        graph.add_conditional_edges(
            "evaluate_research",
            self.route_research_results,
            {
                WorkflowDecision.REQUEST_CONFIRMATION: "request_confirmation",
                WorkflowDecision.ASK_NEXT_QUESTION: "generate_question"
            }
        )
        
        # Confirmation flow
        graph.add_conditional_edges(
            "request_confirmation",
            self.route_after_confirmation,
            {
                "accepted": "update_checklist",
                "rejected": "generate_question"
            }
        )
        
        # Main question loop
        graph.add_edge("update_checklist", "generate_question")
        graph.add_edge("generate_question", "process_response")
        
        # Process response branching
        graph.add_conditional_edges(
            "process_response",
            self.determine_next_action,
            {
                WorkflowDecision.ASK_NEXT_QUESTION: "update_checklist",
                WorkflowDecision.COMPLETE_SESSION: "final_confirmation"
            }
        )
        
        # Completion flow
        graph.add_edge("final_confirmation", "save_results")
        graph.add_edge("save_results", END)
        
        return graph.compile()
    
    # Node implementations
    async def intake_phase_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Initial intake and setup"""
        print("NODE: Intake Phase")
        state["workflow_status"] = "intake_completed"
        state["last_activity"] = datetime.utcnow().isoformat()
        
        # Add welcome message
        print("  Adding welcome message")
        state["messages"].append({
            "role": "assistant",
            "content": "Welcome! I'll help you complete your service provider profile. Let me gather some information to customize this process for you.",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return state
    
    async def research_decision_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Decide whether to conduct research"""
        print("NODE: Research Decision")
        state["workflow_status"] = "research_decision"
        
        # Skip research for debugging/testing - go straight to questions
        # This allows testing the interactive flow without API issues
        # state["research_evaluation_decision"] = WorkflowDecision.SKIP_RESEARCH
        # print("DEBUG: Skipping research phase, proceeding to questions...")
        
        # Original logic (commented for testing):
        if not state.get("checklist_research_completed"):
            print("  Decision: Proceed to checklist research")
            state["research_evaluation_decision"] = WorkflowDecision.PROCEED_TO_CHECKLIST_RESEARCH
        elif state["provider_profile"].get("profile_text"):
            pending_count = sum(1 for item in state["checklist"] if item["status"] == "PENDING")
            if pending_count >= 3:
                print(f"  Decision: Proceed to answer research ({pending_count} pending items)")
                state["research_evaluation_decision"] = WorkflowDecision.PROCEED_TO_ANSWER_RESEARCH
            else:
                print(f"  Decision: Skip research ({pending_count} pending items)")
                state["research_evaluation_decision"] = WorkflowDecision.SKIP_RESEARCH
        else:
            print("  Decision: Skip research (no profile text)")
            state["research_evaluation_decision"] = WorkflowDecision.SKIP_RESEARCH
        
        return state
    
    async def checklist_customization_research_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Part 1: Research industry standards to customize checklist"""
        print("NODE: Checklist Research")
        state["workflow_status"] = "checklist_research"
        
        # Execute checklist customization research using profile_text
        profile_text = state["provider_profile"].get("profile_text", "")
        print("  Researching industry standards")
        try:
            research_result = await self.research_orchestrator.checklist_engine.research_industry_standards(
                profile_text=profile_text
            )
            print("  Research completed successfully")
        except Exception as e:
            print(f"  Research failed: {str(e)}")
            # Provide fallback result to prevent workflow hang
            research_result = {
                'phase': 'CHECKLIST_CUSTOMIZATION',
                'profile_text': profile_text,
                'raw_results': [],
                'processed_content': [],
                'checklist_modifications': {
                    'mandatory_additions': [],
                    'recommended_additions': [],
                    'items_to_remove': []
                },
                'research_count': 0,
                'timestamp': None
            }
        
        # Store research results
        state["checklist_research_results"] = [research_result]
        state["checklist_research_timestamp"] = datetime.utcnow().isoformat()
        state["checklist_research_completed"] = True
        
        # Apply modifications to checklist
        modifications = research_result.get("checklist_modifications", {})
        state["checklist_modifications"] = modifications
        
        # Update checklist with modifications
        print("  Applying checklist modifications")
        state["checklist"] = self._apply_checklist_modifications(
            state["checklist"], modifications
        )
        
        # Display updated checklist after modifications
        print("  Checklist updated with research modifications:")
        self._display_checklist_status(state)
        
        return state
    
    async def answer_gathering_research_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Part 2: Research specific answers to checklist items"""
        print("🔎 NODE: Answer Research")
        state["workflow_status"] = "answer_research"
        
        # Execute answer gathering research using existing research content
        print("  Researching answers for checklist items using existing research content")
        try:
            research_result = await self.research_orchestrator.answer_engine.research_answers(
                provider_info=state["provider_profile"],
                checklist_items=state["checklist"],
                research_content=state.get("research_content", "")
            )
            print("  Answer research completed successfully")
        except Exception as e:
            print(f"  Answer research failed: {str(e)}")
            # Provide fallback result to prevent workflow hang
            research_result = {
                'phase': 'ANSWER_GATHERING',
                'provider_info': state["provider_profile"],
                'extracted_answers': {},
                'research_results': [],
                'parsed_content': [],
                'timestamp': None
            }
        
        # Store research results
        state["answer_research_results"] = [research_result]
        state["answer_research_timestamp"] = datetime.utcnow().isoformat()
        state["research_answers"] = research_result.get("extracted_answers", {})
        
        # Display checklist status after answer research
        print("  Current checklist status after answer research:")
        self._display_checklist_status(state)
        
        return state
    
    async def evaluate_research_results_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Evaluate research results and decide how to proceed"""
        print("⚖️ NODE: Evaluate Research")
        state["workflow_status"] = "evaluating_research"
        
        extracted_answers = state.get("research_answers", {})
        
        if not extracted_answers:
            state["research_evaluation_decision"] = WorkflowDecision.ASK_NEXT_QUESTION
            return state
        
        # Evaluate confidence levels
        high_confidence_items = []
        medium_confidence_items = []
        low_confidence_items = []
        
        for item_key, answer_data in extracted_answers.items():
            confidence = answer_data.get("confidence", 0.0)
            if confidence >= 0.7:
                high_confidence_items.append(item_key)
            elif confidence >= 0.3:
                medium_confidence_items.append(item_key)
            else:
                low_confidence_items.append(item_key)
        
        state["answer_evaluation_results"] = {
            "high_confidence": high_confidence_items,
            "medium_confidence": medium_confidence_items,
            "low_confidence": low_confidence_items
        }
        
        # Determine decision: confirmation if any usable answers, otherwise ask next question
        if high_confidence_items or medium_confidence_items:
            print(f"  Found {len(high_confidence_items + medium_confidence_items)} usable answers - requesting confirmation")
            state["research_evaluation_decision"] = WorkflowDecision.REQUEST_CONFIRMATION
        else:
            print("  No usable answers found - proceeding to questions")
            state["research_evaluation_decision"] = WorkflowDecision.ASK_NEXT_QUESTION
        
        return state
    
    async def request_answer_confirmation_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Request user confirmation for research findings"""
        print("❓ NODE: Request Confirmation")
        state["workflow_status"] = "requesting_confirmation"
        
        high_confidence = state["answer_evaluation_results"].get("high_confidence", [])
        medium_confidence = state["answer_evaluation_results"].get("medium_confidence", [])
        confirmation_items = []
        
        for item_key in list(high_confidence) + list(medium_confidence):
            answer_data = state["research_answers"].get(item_key, {})
            checklist_item = next((item for item in state["checklist"] if item["key"] == item_key), None)
            
            if checklist_item and answer_data:
                confirmation_items.append({
                    "key": item_key,
                    "question": checklist_item["prompt"],
                    "suggested_answer": answer_data["value"],
                    "confidence": answer_data["confidence"]
                })
        
        if confirmation_items:
            print(f"  Generating confirmation for {len(confirmation_items)} items")
            confirmation_message = await self.llm.generate_confirmation_message(confirmation_items)
            state["messages"].append({
                "role": "assistant",
                "content": confirmation_message,
                "timestamp": datetime.utcnow().isoformat()
            })
            state["pending_confirmations"] = confirmation_items
            state["awaiting_confirmation"] = True
        
        return state
    
    def _display_checklist_status(self, state: EvolvedOnboardingState) -> None:
        """Display current checklist status in an aesthetically pleasing format"""
        checklist = state.get("checklist", [])
        if not checklist:
            return
        
        # Calculate status counts
        total_items = len(checklist)
        completed_items = sum(1 for item in checklist if item["status"] in ["VERIFIED", "AUTO_FILLED"])
        asked_items = sum(1 for item in checklist if item["status"] == "ASKED")
        pending_items = sum(1 for item in checklist if item["status"] == "PENDING")
        
        # Calculate progress percentage
        progress_percentage = (completed_items / total_items * 100) if total_items > 0 else 0
        
        # Create progress bar
        bar_length = 20
        filled_length = int(bar_length * completed_items // total_items) if total_items > 0 else 0
        progress_bar = "█" * filled_length + "░" * (bar_length - filled_length)
        
        # Calculate dynamic width based on longest value
        max_value_length = 0
        for item in checklist:
            if item["status"] in ["VERIFIED", "AUTO_FILLED"] and item.get("value"):
                value = str(item["value"])
                # Add 3 for parentheses and space: " (value)"
                value_length = len(value) + 3
                max_value_length = max(max_value_length, value_length)
        
        # Set minimum value preview width to 8 (original), but allow it to grow
        # Cap at 140 characters to prevent excessively wide displays
        value_preview_width = max(8, min(max_value_length, 140))
        
        # Calculate total border width: 
        # 4 (item number + status) + 45 (prompt) + value_preview_width + 4 (border chars and spaces)
        total_width = 4 + 45 + value_preview_width + 4
        
        # Ensure minimum width for the header
        header_text = "PROFILE PROGRESS"
        min_width_for_header = len(header_text) + 40  # 40 for padding
        total_width = max(total_width, min_width_for_header)
        
        # Calculate padding for centered header
        header_padding = (total_width - len(header_text)) // 2
        header_left_padding = header_padding
        header_right_padding = total_width - len(header_text) - header_left_padding
        
        print("\n" + "╔" + "═" * total_width + "╗")
        print("║" + " " * header_left_padding + header_text + " " * header_right_padding + "║")
        print("╠" + "═" * total_width + "╣")
        
        # Progress line
        progress_text = f"Progress: [{progress_bar}] {progress_percentage:5.1f}%"
        progress_padding = total_width - len(progress_text) - 2
        print(f"║ {progress_text}{' ' * progress_padding} ║")
        
        # Status counts line
        status_text = f"Completed: {completed_items:2d} │ In Progress: {asked_items:2d} │ Remaining: {pending_items:2d}"
        status_padding = total_width - len(status_text) - 2
        print(f"║ {status_text}{' ' * status_padding} ║")
        
        print("╠" + "═" * total_width + "╣")
        
        # Show status for each item (show ALL items, not limited)
        for i, item in enumerate(checklist, 1):
            status_icon = {
                "VERIFIED": "VERIFIED",
                "AUTO_FILLED": "🔄",
                "ASKED": "❓",
                "PENDING": "⏳"
            }.get(item["status"], "❔")
            
            # Truncate prompt if too long
            prompt = item.get("prompt", item.get("key", "Unknown"))
            if len(prompt) > 45:
                prompt = prompt[:42] + "..."
            
            # Show value preview for completed items
            value_preview = ""
            if item["status"] in ["VERIFIED", "AUTO_FILLED"] and item.get("value"):
                value = str(item["value"])
                # If value is too long for the allocated space, truncate with ellipsis
                max_value_chars = value_preview_width - 3  # Account for " (" and ")"
                if len(value) > max_value_chars:
                    value = value[:max_value_chars-3] + "..."
                value_preview = f" ({value})"
            
            print(f"║ {i:2d}. {status_icon} {prompt:<45} {value_preview:<{value_preview_width}} ║")
        
        print("╚" + "═" * total_width + "╝")
        print()

    def _print_final_summary(self, summary: str, state: EvolvedOnboardingState) -> None:
        """Print the final profile summary in an aesthetic, readable format"""
        # Get provider name for header
        provider_name = state["provider_profile"].get("company_name", "Service Provider")
        if not provider_name or provider_name == "Service Provider":
            # Try to extract from profile text
            profile_text = state["provider_profile"].get("profile_text", "")
            if "Company Name:" in profile_text:
                try:
                    provider_name = profile_text.split("Company Name:")[1].split("\n")[0].strip()
                except:
                    provider_name = "Service Provider"
        
        # Calculate completion metrics
        total_items = len(state["checklist"])
        completed_items = sum(1 for item in state["checklist"] if item["status"] in ["VERIFIED", "AUTO_FILLED"])
        completion_rate = (completed_items / total_items * 100) if total_items > 0 else 0
        
        # Create aesthetic border
        header_text = f"FINAL PROFILE SUMMARY - {provider_name.upper()}"
        border_width = max(80, len(header_text) + 10)
        
        print("\n" + "╔" + "═" * border_width + "╗")
        
        # Center the header
        header_padding = (border_width - len(header_text)) // 2
        header_left_padding = header_padding
        header_right_padding = border_width - len(header_text) - header_left_padding
        print("║" + " " * header_left_padding + header_text + " " * header_right_padding + "║")
        
        # Completion status
        status_text = f"Completion: {completed_items}/{total_items} items ({completion_rate:.0f}%)"
        status_padding = border_width - len(status_text) - 2
        print("║ " + status_text + " " * status_padding + " ║")
        
        print("╠" + "═" * border_width + "╣")
        
        # Format and print the summary content
        import textwrap
        summary_lines = summary.split('\n')
        
        for line in summary_lines:
            if line.strip():  # Skip empty lines
                # Wrap long lines
                wrapped_lines = textwrap.wrap(line, width=border_width - 4)
                if not wrapped_lines:  # Handle empty lines after wrapping
                    wrapped_lines = [line]
                
                for wrapped_line in wrapped_lines:
                    line_padding = border_width - len(wrapped_line) - 2
                    print("║ " + wrapped_line + " " * line_padding + " ║")
            else:
                # Print empty line
                print("║" + " " * border_width + "║")
        
        print("╚" + "═" * border_width + "╝")
        print()

    async def generate_sequential_question_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Generate next question from checklist"""
        print("NODE: Generate Question")
        state["workflow_status"] = "generating_question"
        
        # Display current checklist status before asking question
        self._display_checklist_status(state)
        
        # Find next pending item
        pending_items = [item for item in state["checklist"] if item["status"] == "PENDING"]
        
        if pending_items:
            next_item = pending_items[0]
            print(f"  Next item: {next_item['key']}")
            
            # Generate question with explicit named arguments to ensure correct mapping
            try:
                question = await self.llm.generate_clarifying_question(
                    item=next_item,
                    research_context=state.get("research_answers", {}).get(next_item["key"]),
                    provider_profile=state["provider_profile"],
                    checklist=state["checklist"]
                )
            except Exception as e:
                print(f"ERROR: Failed to generate question via LLM: {e}")
                question = ""

            # Ensure non-empty question before proceeding
            if not question or not str(question).strip():
                fallback_prompt = next_item.get("prompt", "Please provide the requested information")
                question = f"{fallback_prompt}"
                print("WARNING: LLM returned empty question. Using fallback based on checklist prompt.")

            # Display the question in a nicely formatted way
            print("┌" + "─" * 58 + "┐")
            print("|" + " " * 22 + "QUESTION" + " " * 23 + "|")
            print("├" + "─" * 58 + "┤")
            
            # Word wrap the question text
            import textwrap
            wrapped_lines = textwrap.wrap(question, width=54)
            for line in wrapped_lines:
                print(f"│ {line:<56} │")
            
            print("└" + "─" * 58 + "┘")
            print()

            state["messages"].append({
                "role": "assistant",
                "content": question,
                "timestamp": datetime.utcnow().isoformat()
            })
            state["last_question"] = question  # Store the actual question
            state["last_question_key"] = next_item["key"]
            state["awaiting_response"] = True
            
            # Update item status
            for item in state["checklist"]:
                if item["key"] == next_item["key"]:
                    item["status"] = "ASKED"
                    break
        else:
            # No more pending items - display final checklist status
            print("  No more pending questions. Final checklist status:")
            self._display_checklist_status(state)
        
        return state
    
    async def process_user_response_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Process user's response to question"""
        print("👤 NODE: Process Response")
        state["workflow_status"] = "processing_response"
        
        # Check if we're waiting for a response
        if not state.get("awaiting_response"):
            print("DEBUG: Not awaiting response, skipping user input")
            return state
        
        # Get user input based on mode
        if self.interactive_mode:
            # Wait for any pending async operations to complete
            import time
            time.sleep(0.5)  # Small delay to ensure question is fully generated
            
            # Get actual user input
            last_question = state.get("last_question", None)
            if not last_question:
                # Recover from state if schema dropped the field: use last assistant message
                last_assistant = None
                for m in reversed(state.get("messages", [])):
                    if m.get("role") == "assistant" and m.get("content"):
                        last_assistant = m
                        break
                if last_assistant:
                    last_question = last_assistant.get("content")
                    state["last_question"] = last_question
            
            if not last_question:
                print("ERROR: No question was generated. Using default.")
                last_question = "Please provide your response:"
            
            last_key = state.get("last_question_key", "unknown")
            
            # Simple input prompt since question is already nicely displayed above
            try:
                # In Jupyter notebook, use input() to get user response
                print("  ⌨️ Waiting for user input...")
                user_response = input("💭 Your answer: ").strip()
                
                if not user_response:
                    user_response = "[No response provided]"
                    print("No response provided, using default")
                
                print(f"  Response captured: {user_response[:50]}..." if len(user_response) > 50 else f"  Response captured: {user_response}")
                print("\n" + "🔵" * 30)  # Visual separator after receiving response
                
            except Exception as e:
                print(f"Error getting user input: {e}")
                user_response = "[Error getting response]"
        else:
            # Use simulated response for testing
            user_response = f"Sample response for {state.get('last_question_key', 'unknown')}"
            print(f"DEBUG: Using simulated response: {user_response}")
        
        state["messages"].append({
            "role": "user",
            "content": user_response,
            "timestamp": datetime.utcnow().isoformat()
        })
        state["last_user_response"] = user_response
        
        # Update checklist item with response
        if state["last_question_key"]:
            for item in state["checklist"]:
                if item["key"] == state["last_question_key"]:
                    item["value"] = user_response
                    item["status"] = "VERIFIED"
                    break
        
        state["awaiting_response"] = False
        
        # Display updated checklist after processing user response
        print("  Checklist updated with user response:")
        self._display_checklist_status(state)
        
        return state
    
    async def update_checklist_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Update checklist with research findings or user responses"""
        print("NODE: Update Checklist")
        state["workflow_status"] = "updating_checklist"
        
        # Apply confirmed research answers if accepted
        if state.get("confirmation_result") == "accepted" and state.get("pending_confirmations"):
            confirmations_count = len(state["pending_confirmations"])
            print(f"  Applying {confirmations_count} confirmed research answers")
            for confirmation in state["pending_confirmations"]:
                item_key = confirmation.get("key")
                for item in state["checklist"]:
                    if item.get("key") == item_key:
                        item["value"] = confirmation.get("suggested_answer")
                        item["status"] = "VERIFIED"
                        item["confidence"] = confirmation.get("confidence")
                        break
            # Clear confirmation state after applying
            state["pending_confirmations"] = []
            state["confirmation_result"] = None
        
        # Calculate completion metrics
        total_items = len(state["checklist"])
        completed_items = sum(1 for item in state["checklist"] 
                             if item["status"] in ["VERIFIED", "AUTO_FILLED"])
        state["completion_metrics"]["completion_rate"] = completed_items / total_items if total_items > 0 else 0
        
        # Display updated checklist after applying confirmations
        if state.get("confirmation_result") == "accepted" and state.get("pending_confirmations"):
            print("  Checklist updated with confirmed research answers:")
            self._display_checklist_status(state)
        
        return state
    
    async def final_confirmation_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Final confirmation before saving"""
        print("NODE: Final Confirmation")
        state["workflow_status"] = "final_confirmation"
        
        # Get completed items and profile information
        completed_items = [item for item in state["checklist"] 
                          if item["status"] in ["VERIFIED", "AUTO_FILLED"]]
        
        print(f"  Generating comprehensive summary for {len(completed_items)} completed items")
        
        # Generate comprehensive profile summary using LLM
        try:
            profile_text = state["provider_profile"].get("profile_text", "")
            summary = await self.llm.generate_profile_summary(
                profile_text=profile_text,
                checklist_data=state["checklist"]
            )
            print("  Profile summary generated successfully")
        except Exception as e:
            print(f"  LLM summary generation failed: {str(e)}, using fallback")
            # Fallback to simple summary
            summary = f"Great! I've collected {len(completed_items)} items for your profile:\n"
            for item in completed_items:  # Show ALL completed items
                summary += f"- {item['prompt']}: {item['value']}\n"
        
        # Print the summary aesthetically for review
        self._print_final_summary(summary, state)
        
        state["messages"].append({
            "role": "assistant",
            "content": summary,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        return state
    
    async def save_results_node(self, state: EvolvedOnboardingState) -> EvolvedOnboardingState:
        """Save results to database"""
        print("💾 NODE: Save Results")
        state["workflow_status"] = "completed"
        state["last_activity"] = datetime.utcnow().isoformat()
        
        # In production, would save to database here
        completion = state['completion_metrics'].get('completion_rate', 0.0)
        print(f"  Onboarding flow completed with {completion:.0%} completion")
        
        return state
    
    # Routing functions
    def should_conduct_research(self, state: EvolvedOnboardingState) -> str:
        """Determine which type of research to conduct"""
        decision = state.get("research_evaluation_decision", WorkflowDecision.SKIP_RESEARCH)
        
        if decision == WorkflowDecision.PROCEED_TO_CHECKLIST_RESEARCH:
            return "checklist_research"
        elif decision == WorkflowDecision.PROCEED_TO_ANSWER_RESEARCH:
            return "answer_research"
        else:
            return "skip"
    
    def route_research_results(self, state: EvolvedOnboardingState) -> WorkflowDecision:
        """Route based on research result evaluation"""
        return state.get("research_evaluation_decision", WorkflowDecision.ASK_NEXT_QUESTION)
    
    def route_after_confirmation(self, state: EvolvedOnboardingState) -> str:
        """Route after user responds to confirmation using LLM classification with structured output."""
        # Present a single prompt to collect a freeform confirmation
        if self.interactive_mode:
            print("\n" + "="*60)
            print("CONFIRMATION REQUIRED")
            print("="*60)
            print("\nWe found suggested answers from research. Please confirm or edit them in brief.")
            # Print the generated confirmation message (from the previous node) before prompting
            try:
                last_assistant_msg = None
                for m in reversed(state.get("messages", [])):
                    if m.get("role") == "assistant" and m.get("content"):
                        last_assistant_msg = m.get("content")
                        break
                if last_assistant_msg:
                    print("\n" + str(last_assistant_msg).strip() + "\n")
            except Exception:
                pass
            print("(Type a short response. We'll classify it as accept or reject.)\n")
            try:
                user_text = input("> ").strip()
            except Exception:
                user_text = ""
        else:
            # In simulation, lightly accept
            user_text = "yes"

        # Use a minimal-token LLM classification with forced JSON output
        items = state.get("pending_confirmations", []) or []
        try:
            result = self.llm.classify_confirmation_decision_sync(user_text=user_text, items=items)
            decision = str(result.get("decision", "rejected")).strip().lower()
        except Exception:
            decision = "rejected"

        if decision == "accepted":
            print("Accepted")
            state["confirmation_result"] = "accepted"
            state["awaiting_confirmation"] = False
            return "accepted"
        else:
            print("Rejected")
            state["confirmation_result"] = "rejected"
            state["awaiting_confirmation"] = False
            return "rejected"
    
    def determine_next_action(self, state: EvolvedOnboardingState) -> WorkflowDecision:
        """Determine next action after processing response"""
        # Check if there are any pending items left to ask
        pending_items = [item for item in state["checklist"] 
                        if item["status"] == "PENDING"]
        
        # Add recursion protection - limit maximum questions
        questions_asked = len([m for m in state.get("messages", []) if m["role"] == "assistant" and "question" in m.get("content", "").lower()])
        max_questions = 20  # Reasonable limit to prevent infinite loops
        
        if not pending_items or questions_asked >= max_questions:
            if questions_asked >= max_questions:
                print(f"Reached maximum questions limit ({max_questions}). Completing session.")
            elif not pending_items:
                print("All questions completed. Proceeding to final confirmation.")
            return WorkflowDecision.COMPLETE_SESSION
        else:
            return WorkflowDecision.ASK_NEXT_QUESTION
    
    def _apply_checklist_modifications(
        self,
        checklist: List[Dict[str, Any]],
        modifications: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply checklist modifications from research"""
        modified_checklist = checklist.copy()
        
        # Add new items
        for item in modifications.get("mandatory_additions", []):
            modified_checklist.append({
                "key": item["key"],
                "prompt": item["question"],
                "required": True,
                "status": "PENDING",
                "value": None
            })
        
        for item in modifications.get("recommended_additions", []):
            modified_checklist.append({
                "key": item["key"],
                "prompt": item["question"],
                "required": False,
                "status": "PENDING",
                "value": None
            })
        
        # Remove items
        items_to_remove = {item["key"] for item in modifications.get("items_to_remove", [])}
        modified_checklist = [
            item for item in modified_checklist 
            if item.get("key") not in items_to_remove
        ]
        
        return modified_checklist