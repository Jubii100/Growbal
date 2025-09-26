# Evolved Core Agent Architecture

## System Architecture Overview

The evolved onboarding agent is built on a state-driven, event-sourced architecture that enables dynamic workflow adaptation, intelligent research integration, and seamless human-in-the-loop capabilities. The core enhancement focuses on a **two-part research process** that first customizes the checklist based on industry standards, then answers the customized checklist items.

## Core Components

### 1. Adaptive Workflow Engine

```python
from langgraph.graph import StateGraph, START, END
from typing import Dict, Any, List, Optional
from enum import Enum

class WorkflowDecision(Enum):
    """Workflow decision points"""
    PROCEED_TO_CHECKLIST_RESEARCH = "proceed_to_checklist_research"
    PROCEED_TO_ANSWER_RESEARCH = "proceed_to_answer_research"
    SKIP_RESEARCH = "skip_research"
    ASK_NEXT_QUESTION = "ask_next_question"
    ESCALATE_TO_HUMAN = "escalate_to_human"
    COMPLETE_SESSION = "complete_session"
    UPDATE_CHECKLIST = "update_checklist"
    AUTO_FILL_ANSWERS = "auto_fill_answers"
    REQUEST_CONFIRMATION = "request_confirmation"
    ASK_CLARIFYING_QUESTION = "ask_clarifying_question"

class AdaptiveOnboardingAgent:
    """
    Evolved onboarding agent with two-part research process.
    """
    
    def __init__(self, llm, tools, db_connection, rag_system):
        self.llm = llm
        self.tools = tools
        self.db = db_connection
        self.rag = rag_system
        self.graph = self._build_adaptive_graph()
        
    def _build_adaptive_graph(self) -> StateGraph:
        """
        Construct the adaptive workflow graph with two-part research.
        """
        graph = StateGraph(EvolvedOnboardingState)
        
        # Core workflow nodes
        graph.add_node("intake", self.intake_phase_node)
        graph.add_node("research_decision", self.research_decision_node)
        
        # Two-part research nodes
        graph.add_node("checklist_research", self.checklist_customization_research_node)
        graph.add_node("parse_checklist_research", self.parse_checklist_research_node)
        graph.add_node("answer_research", self.answer_gathering_research_node)
        graph.add_node("parse_answer_research", self.parse_answer_research_node)
        graph.add_node("evaluate_research_results", self.evaluate_research_results_node)
        
        # Answer processing nodes
        graph.add_node("request_answer_confirmation", self.request_answer_confirmation_node)
        graph.add_node("generate_clarifying_question", self.generate_clarifying_question_node)
        graph.add_node("process_confirmation_response", self.process_confirmation_response_node)
        
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
                WorkflowDecision.PROCEED_TO_CHECKLIST_RESEARCH: "research_decision",
                WorkflowDecision.SKIP_RESEARCH: "update_checklist",
                WorkflowDecision.ESCALATE_TO_HUMAN: "escalation"
            }
        )
        
        # Two-part research workflow
        graph.add_conditional_edges(
            "research_decision",
            self.should_conduct_research,
            {
                "checklist_research": "checklist_research",
                "answer_research": "answer_research",
                "skip": "update_checklist"
            }
        )
        
        # Checklist research flow
        graph.add_edge("checklist_research", "parse_checklist_research")
        graph.add_conditional_edges(
            "parse_checklist_research",
            self.after_checklist_research_routing,
            {
                "proceed_to_answer_research": "answer_research",
                "update_checklist": "update_checklist"
            }
        )
        
        # Answer research flow with conditional routing
        graph.add_edge("answer_research", "parse_answer_research")
        graph.add_edge("parse_answer_research", "evaluate_research_results")
        
        # Conditional routing based on research result evaluation
        graph.add_conditional_edges(
            "evaluate_research_results",
            self.route_research_results,
            {
                WorkflowDecision.AUTO_FILL_ANSWERS: "update_checklist",
                WorkflowDecision.REQUEST_CONFIRMATION: "request_answer_confirmation",
                WorkflowDecision.ASK_CLARIFYING_QUESTION: "generate_clarifying_question"
            }
        )
        
        # Answer confirmation flow
        graph.add_edge("request_answer_confirmation", "process_confirmation_response")
        graph.add_conditional_edges(
            "process_confirmation_response",
            self.route_after_confirmation,
            {
                "confirmed": "update_checklist",
                "rejected": "generate_clarifying_question",
                "needs_clarification": "generate_clarifying_question"
            }
        )
        
        # Clarifying question flow
        graph.add_edge("generate_clarifying_question", "process_response")
        # process_response already connects to evaluate_continuation
        
        # Main question loop
        graph.add_edge("update_checklist", "generate_question")
        graph.add_edge("generate_question", "process_response")
        graph.add_edge("process_response", "evaluate_continuation")
        
        # Continuation decision
        graph.add_conditional_edges(
            "evaluate_continuation",
            self.determine_next_action,
            {
                WorkflowDecision.PROCEED_TO_ANSWER_RESEARCH: "research_decision",
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

### 2. Two-Part Research Engine

```python
class TwoPartResearchEngine:
    """
    Intelligent research engine with two distinct phases.
    """
    
    def __init__(self, search_tools, rag_system):
        self.search_tools = search_tools
        self.rag = rag_system
        
    async def checklist_customization_research_node(self, state: EvolvedOnboardingState):
        """
        Part 1: Research industry standards to customize the checklist.
        Focuses on determining what information is needed based on service provider's niche.
        """
        service_type = state["service_type"]
        provider_info = state.get("provider_profile", {})
        
        # Generate queries for industry standards and requirements
        customization_queries = self._generate_checklist_customization_queries(
            service_type=service_type,
            provider_info=provider_info
        )
        
        # Execute research using Wikipedia/ArXiv with clean text parser
        research_results = await self._execute_industry_standards_research(customization_queries)
        
        # Store results for checklist customization
        state["checklist_research_results"] = research_results
        state["checklist_research_timestamp"] = datetime.utcnow().isoformat()
        
        return state
    
    async def answer_gathering_research_node(self, state: EvolvedOnboardingState):
        """
        Part 2: Research specific answers to the customized checklist items.
        Focuses on finding actual answers to tick off checklist items.
        """
        checklist = state["checklist"]
        provider_info = state.get("provider_profile", {})
        
        # Identify pending items that need answers
        pending_items = [item for item in checklist if item["status"] == "PENDING"]
        
        # Generate queries for specific business information
        answer_queries = self._generate_answer_gathering_queries(
            pending_items=pending_items[:5],  # Limit to top 5 priority items
            provider_info=provider_info
        )
        
        # Execute research using web search with business info parser
        research_results = await self._execute_business_info_research(answer_queries)
        
        # Store results for answer extraction
        state["answer_research_results"] = research_results
        state["answer_research_timestamp"] = datetime.utcnow().isoformat()
        
        return state
    
    def _generate_checklist_customization_queries(
        self, 
        service_type: str, 
        provider_info: Dict
    ) -> List[Dict]:
        """
        Generate queries to understand industry-specific requirements.
        """
        queries = []
        
        # Base query for service type standards
        base_query = f"""
        {service_type} service provider industry standards requirements checklist
        regulatory compliance requirements {service_type} providers
        """
        
        queries.append({
            "query": base_query,
            "source": "wikipedia_arxiv",
            "purpose": "industry_standards",
            "priority": "high"
        })
        
        # Location-specific requirements if available
        if provider_info.get("location"):
            location_query = f"""
            {service_type} service provider requirements {provider_info['location']}
            regulatory compliance {provider_info['location']} {service_type}
            """
            queries.append({
                "query": location_query,
                "source": "wikipedia_arxiv",
                "purpose": "location_requirements",
                "priority": "medium"
            })
        
        # Specialization-specific requirements
        if provider_info.get("specialization"):
            specialization_query = f"""
            {provider_info['specialization']} {service_type} specific requirements
            specialized {service_type} provider compliance standards
            """
            queries.append({
                "query": specialization_query,
                "source": "wikipedia_arxiv", 
                "purpose": "specialization_requirements",
                "priority": "medium"
            })
        
        return queries
    
    def _generate_answer_gathering_queries(
        self, 
        pending_items: List[Dict], 
        provider_info: Dict
    ) -> List[Dict]:
        """
        Generate queries to find specific answers to checklist items.
        """
        queries = []
        provider_name = provider_info.get("name", "")
        provider_domain = provider_info.get("website", "")
        
        for item in pending_items:
            # Direct provider information query
            if provider_name:
                query = f"""
                "{provider_name}" {item["prompt"].lower()}
                {provider_name} contact information business details
                """
                queries.append({
                    "query": query,
                    "source": "web_search",
                    "purpose": "direct_answer",
                    "checklist_item": item["key"],
                    "priority": "high" if item.get("required") else "medium"
                })
            
            # Website-specific search if domain available
            if provider_domain:
                domain_query = f"""
                site:{provider_domain} {item["prompt"].lower()}
                """
                queries.append({
                    "query": domain_query,
                    "source": "web_search",
                    "purpose": "website_answer",
                    "checklist_item": item["key"],
                    "priority": "high" if item.get("required") else "medium"
                })
        
        return queries
    
    async def _execute_industry_standards_research(
        self, 
        queries: List[Dict]
    ) -> List[Dict]:
        """
        Execute research using Wikipedia/ArXiv with clean text parsing.
        """
        results = []
        
        for query in queries:
            try:
                # Use Wikipedia/ArXiv search tools
                if query["source"] == "wikipedia_arxiv":
                    raw_result = await self.search_tools.search_wikipedia_arxiv(
                        query["query"]
                    )
                    
                    # Parse and clean the content
                    cleaned_content = self._clean_academic_content(raw_result)
                    
                    results.append({
                        "query": query,
                        "raw_content": raw_result,
                        "cleaned_content": cleaned_content,
                        "timestamp": datetime.utcnow().isoformat(),
                        "success": True
                    })
                    
            except Exception as e:
                results.append({
                    "query": query,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": False
                })
        
        return results
    
    async def _execute_business_info_research(
        self, 
        queries: List[Dict]
    ) -> List[Dict]:
        """
        Execute research using web search with business info parsing.
        """
        results = []
        
        for query in queries:
            try:
                # Use web search tools
                raw_result = await self.search_tools.search_web(query["query"])
                
                # Parse business information using readability parser
                parsed_content = self._parse_business_content(raw_result)
                
                results.append({
                    "query": query,
                    "raw_content": raw_result,
                    "parsed_content": parsed_content,
                    "checklist_item": query.get("checklist_item"),
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True
                })
                
            except Exception as e:
                results.append({
                    "query": query,
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": False
                })
        
        return results
    
    def _clean_academic_content(self, raw_content: str) -> str:
        """
        Clean academic content removing HTML, code, images, keeping only relevant text.
        """
        import re
        from bs4 import BeautifulSoup
        
        # Remove HTML tags
        soup = BeautifulSoup(raw_content, 'html.parser')
        
        # Remove code blocks, images, tables
        for element in soup(['script', 'style', 'img', 'table', 'code', 'pre']):
            element.decompose()
        
        # Get clean text
        clean_text = soup.get_text()
        
        # Remove excessive whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # Focus on business-relevant paragraphs
        paragraphs = clean_text.split('\n')
        relevant_paragraphs = []
        
        business_keywords = [
            'requirement', 'compliance', 'standard', 'regulation',
            'provider', 'service', 'license', 'certification',
            'documentation', 'information', 'business'
        ]
        
        for paragraph in paragraphs:
            if any(keyword in paragraph.lower() for keyword in business_keywords):
                if len(paragraph.strip()) > 50:  # Filter out short fragments
                    relevant_paragraphs.append(paragraph.strip())
        
        return '\n\n'.join(relevant_paragraphs[:10])  # Limit to top 10 relevant paragraphs
    
    def _parse_business_content(self, raw_content: str) -> str:
        """
        Parse business content focusing on contact info, services, etc.
        """
        try:
            from readability import Document
            
            # Use python-readability to extract main content
            doc = Document(raw_content)
            main_content = doc.summary()
            
            # Remove HTML and get clean text
            soup = BeautifulSoup(main_content, 'html.parser')
            clean_text = soup.get_text()
            
            # Extract business-relevant information
            business_info = self._extract_business_patterns(clean_text)
            
            return business_info
            
        except Exception as e:
            # Fallback to simple text extraction
            return self._simple_text_extraction(raw_content)
    
    def _extract_business_patterns(self, text: str) -> str:
        """
        Extract specific business patterns like emails, phones, addresses.
        """
        import re
        
        patterns = {
            'emails': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phones': r'[\+]?[1-9]?[0-9]{7,15}',
            'addresses': r'\d+\s+[A-Za-z0-9\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)',
        }
        
        extracted_info = []
        
        for pattern_name, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                extracted_info.append(f"{pattern_name.title()}: {', '.join(set(matches[:3]))}")
        
        # Add relevant paragraphs
        paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 30]
        business_paragraphs = []
        
        business_keywords = ['service', 'contact', 'about', 'company', 'business', 'location']
        
        for paragraph in paragraphs[:10]:  # Limit paragraphs
            if any(keyword in paragraph.lower() for keyword in business_keywords):
                business_paragraphs.append(paragraph)
        
        result = '\n'.join(extracted_info)
        if business_paragraphs:
            result += '\n\nRelevant Information:\n' + '\n\n'.join(business_paragraphs[:3])
        
        return result
    
    async def parse_checklist_research_node(self, state: EvolvedOnboardingState):
        """
        Parse and apply checklist customization research results.
        """
        research_results = state.get("checklist_research_results", [])
        if not research_results:
            return state
        
        # Extract checklist modifications from research
        checklist_modifications = await self._extract_checklist_modifications(
            research_results, 
            state["service_type"],
            state.get("provider_profile", {})
        )
        
        # Apply modifications to checklist
        current_checklist = state["checklist"]
        modified_checklist = self._apply_checklist_modifications(
            current_checklist, 
            checklist_modifications
        )
        
        state["checklist"] = modified_checklist
        state["checklist_modifications"] = checklist_modifications
        
        return state
    
    async def parse_answer_research_node(self, state: EvolvedOnboardingState):
        """
        Parse and apply answer research results to checklist.
        """
        research_results = state.get("answer_research_results", [])
        if not research_results:
            return state
        
        # Extract answers from research
        extracted_answers = await self._extract_answers_from_research(
            research_results,
            state["checklist"]
        )
        
        # Apply answers to checklist
        updated_checklist = self._apply_research_answers(
            state["checklist"],
            extracted_answers,
            confidence_threshold=0.75
        )
        
        state["checklist"] = updated_checklist
        state["research_answers"] = extracted_answers
        
        return state
    
    async def evaluate_research_results_node(self, state: EvolvedOnboardingState):
        """
        Evaluate research results and decide how to proceed with extracted answers.
        """
        extracted_answers = state.get("research_answers", {})
        
        if not extracted_answers:
            # No answers found, continue with normal questioning
            state["research_evaluation_decision"] = WorkflowDecision.ASK_NEXT_QUESTION
            return state
        
        # Evaluate each extracted answer
        evaluation_results = {}
        high_confidence_count = 0
        medium_confidence_count = 0
        low_confidence_count = 0
        
        for item_key, answer_data in extracted_answers.items():
            confidence = answer_data.get("confidence", 0.0)
            answer_value = answer_data.get("value", "")
            
            if confidence >= 0.9 and self._is_valid_answer_format(answer_value, item_key, state["checklist"]):
                # High confidence, auto-fill
                evaluation_results[item_key] = "auto_fill"
                high_confidence_count += 1
            elif confidence >= 0.7:
                # Medium confidence, request confirmation
                evaluation_results[item_key] = "request_confirmation"
                medium_confidence_count += 1
            elif confidence >= 0.5:
                # Low confidence, ask clarifying question
                evaluation_results[item_key] = "clarifying_question"
                low_confidence_count += 1
            else:
                # Very low confidence, skip
                evaluation_results[item_key] = "skip"
        
        state["answer_evaluation_results"] = evaluation_results
        
        # Determine overall decision based on results
        if high_confidence_count > 0 and medium_confidence_count == 0 and low_confidence_count == 0:
            # All high confidence, auto-fill everything
            decision = WorkflowDecision.AUTO_FILL_ANSWERS
        elif medium_confidence_count > 0:
            # Some medium confidence items, request confirmation
            decision = WorkflowDecision.REQUEST_CONFIRMATION
        elif low_confidence_count > 0:
            # Some low confidence items, ask clarifying questions
            decision = WorkflowDecision.ASK_CLARIFYING_QUESTION
        else:
            # No usable answers, continue with normal questioning
            decision = WorkflowDecision.ASK_NEXT_QUESTION
        
        state["research_evaluation_decision"] = decision
        return state
    
    async def request_answer_confirmation_node(self, state: EvolvedOnboardingState):
        """
        Request user confirmation for medium-confidence research answers.
        """
        evaluation_results = state.get("answer_evaluation_results", {})
        extracted_answers = state.get("research_answers", {})
        checklist = state["checklist"]
        
        # Find items that need confirmation
        confirmation_items = []
        for item_key, evaluation in evaluation_results.items():
            if evaluation == "request_confirmation":
                # Find the checklist item
                item_details = next((item for item in checklist if item.get("key") == item_key), None)
                if item_details and item_key in extracted_answers:
                    confirmation_items.append({
                        "key": item_key,
                        "question": item_details["prompt"],
                        "suggested_answer": extracted_answers[item_key]["value"],
                        "confidence": extracted_answers[item_key]["confidence"],
                        "source": extracted_answers[item_key].get("source", "research")
                    })
        
        if not confirmation_items:
            # No items to confirm, proceed
            state["awaiting_confirmation"] = False
            return state
        
        # Generate confirmation message
        confirmation_message = await self._generate_confirmation_message(confirmation_items)
        
        state["messages"].append({
            "role": "assistant",
            "content": confirmation_message
        })
        state["pending_confirmations"] = confirmation_items
        state["awaiting_confirmation"] = True
        
        return state
    
    async def generate_clarifying_question_node(self, state: EvolvedOnboardingState):
        """
        Generate clarifying questions for low-confidence research results.
        """
        evaluation_results = state.get("answer_evaluation_results", {})
        extracted_answers = state.get("research_answers", {})
        checklist = state["checklist"]
        
        # Find the first item that needs clarification
        clarification_item = None
        for item_key, evaluation in evaluation_results.items():
            if evaluation == "clarifying_question":
                item_details = next((item for item in checklist if item.get("key") == item_key), None)
                if item_details:
                    clarification_item = {
                        "key": item_key,
                        "item": item_details,
                        "research_context": extracted_answers.get(item_key, {})
                    }
                    break
        
        if not clarification_item:
            # No clarification needed, find next pending item normally
            next_item = self._get_next_pending_item(checklist)
            if next_item:
                clarification_item = {
                    "key": next_item["key"],
                    "item": next_item,
                    "research_context": {}
                }
        
        if clarification_item:
            # Generate contextual clarifying question
            clarifying_question = await self._generate_clarifying_question(
                item=clarification_item["item"],
                research_context=clarification_item["research_context"],
                provider_info=state.get("provider_profile", {})
            )
            
            state["messages"].append({
                "role": "assistant", 
                "content": clarifying_question
            })
            state["last_question_key"] = clarification_item["key"]
            state["awaiting_response"] = True
            
            # Mark item as being asked
            for item in checklist:
                if item.get("key") == clarification_item["key"]:
                    item["status"] = "ASKED"
                    break
        
        return state
    
    async def process_confirmation_response_node(self, state: EvolvedOnboardingState):
        """
        Process user's response to answer confirmation requests.
        """
        if not state.get("awaiting_confirmation"):
            return state
        
        last_message = state["messages"][-1]
        if last_message.get("role") != "user":
            return state
        
        user_response = last_message["content"].lower().strip()
        pending_confirmations = state.get("pending_confirmations", [])
        
        # Parse confirmation response
        if any(word in user_response for word in ["yes", "correct", "right", "confirm", "ok", "good"]):
            # User confirmed - apply all pending confirmations
            for confirmation_item in pending_confirmations:
                self._apply_confirmed_answer(state, confirmation_item)
            state["confirmation_result"] = "confirmed"
            
        elif any(word in user_response for word in ["no", "wrong", "incorrect", "fix", "change"]):
            # User rejected - will need clarifying questions
            state["confirmation_result"] = "rejected"
            
        else:
            # Ambiguous response - needs clarification
            state["confirmation_result"] = "needs_clarification"
        
        # Clear confirmation state
        state["awaiting_confirmation"] = False
        state["pending_confirmations"] = []
        
        return state
```

### 3. Research Decision Logic

```python
    def should_conduct_research(self, state: EvolvedOnboardingState) -> str:
        """
        Determine which type of research to conduct.
        """
        # Check if we need to customize checklist first
        if not state.get("checklist_research_completed"):
            return "checklist_research"
        
        # Check if we have pending items that need answers
        checklist = state["checklist"]
        pending_items = [item for item in checklist if item["status"] == "PENDING"]
        
        if len(pending_items) >= 3:  # Threshold for answer research
            return "answer_research"
        
        return "skip"
    
    def after_checklist_research_routing(self, state: EvolvedOnboardingState) -> str:
        """
        Decide next step after checklist research.
        """
        # Mark checklist research as completed
        state["checklist_research_completed"] = True
        
        # Check if we have sufficient provider info for answer research
        provider_info = state.get("provider_profile", {})
        if provider_info.get("name") or provider_info.get("website"):
            return "proceed_to_answer_research"
        else:
            return "update_checklist"
    
    def route_research_results(self, state: EvolvedOnboardingState) -> WorkflowDecision:
        """
        Route based on research result evaluation.
        """
        return state.get("research_evaluation_decision", WorkflowDecision.ASK_NEXT_QUESTION)
    
    def route_after_confirmation(self, state: EvolvedOnboardingState) -> str:
        """
        Route after user responds to confirmation request.
        """
        confirmation_result = state.get("confirmation_result", "")
        
        if confirmation_result == "confirmed":
            return "confirmed"
        elif confirmation_result == "rejected":
            return "rejected" 
        else:
            return "needs_clarification"
    
    async def _extract_checklist_modifications(
        self, 
        research_results: List[Dict], 
        service_type: str,
        provider_info: Dict
    ) -> Dict[str, Any]:
        """
        Use LLM to extract checklist modifications from industry research.
        """
        relevant_content = "\n\n".join([
            result["cleaned_content"] 
            for result in research_results 
            if result.get("success") and result.get("cleaned_content")
        ])
        
        prompt = f"""
        Based on industry research for {service_type} service providers, suggest modifications to the standard onboarding checklist:

        Research Content:
        {relevant_content[:3000]}  # Limit content length

        Current Service Type: {service_type}
        Provider Info: {provider_info}

        Suggest checklist modifications in the following format:
        1. Items to ADD (new requirements specific to this industry/location)
        2. Items to REMOVE (not applicable to this type of provider)
        3. Items to MODIFY (change wording or requirements)

        Focus on:
        - Regulatory requirements specific to this industry
        - Location-specific compliance needs
        - Industry-standard certifications or licenses
        - Typical business information needed for this type of service

        Return practical, actionable modifications that improve the checklist relevance.
        """
        
        llm_response = await self.llm.ainvoke(prompt)
        
        # Parse the response to extract structured modifications
        modifications = {
            "items_to_add": [],
            "items_to_remove": [],
            "items_to_modify": [],
            "reasoning": llm_response.content
        }
        
        return modifications
    
    async def _extract_answers_from_research(
        self, 
        research_results: List[Dict],
        checklist: List[Dict]
    ) -> Dict[str, Any]:
        """
        Extract specific answers from business research results.
        """
        answers = {}
        
        for result in research_results:
            if not result.get("success") or not result.get("checklist_item"):
                continue
            
            checklist_item = result["checklist_item"]
            parsed_content = result.get("parsed_content", "")
            
            # Use LLM to extract specific answer
            answer_extraction = await self._extract_specific_answer(
                content=parsed_content,
                checklist_item=checklist_item,
                checklist=checklist
            )
            
            if answer_extraction.get("confidence", 0) > 0.5:
                answers[checklist_item] = answer_extraction
        
        return answers
    
    async def _extract_specific_answer(
        self, 
        content: str, 
        checklist_item: str,
        checklist: List[Dict]
    ) -> Dict[str, Any]:
        """
        Extract a specific answer for a checklist item from research content.
        """
        # Find the checklist item details
        item_details = next(
            (item for item in checklist if item["key"] == checklist_item), 
            None
        )
        
        if not item_details:
            return {"confidence": 0}
        
        prompt = f"""
        Extract the answer for this checklist item from the provided content:

        Checklist Item: {item_details["prompt"]}
        Expected Answer Type: {item_details.get("value_type", "text")}
        
        Research Content:
        {content[:1000]}

        Extract:
        1. The specific answer to the checklist item
        2. Confidence level (0.0 to 1.0)
        3. Supporting evidence from the content

        If the information is not clearly available or unclear, set confidence to 0.0.
        Only return high confidence answers that directly answer the question.
        """
        
        extraction_result = await self.llm.ainvoke(prompt)
        
        # Parse the extraction result
        return {
            "value": "extracted_value_placeholder",
            "confidence": 0.8,
            "source": "research",
            "evidence": "supporting_evidence_placeholder"
        }
    
    def _is_valid_answer_format(self, answer_value: str, item_key: str, checklist: List[Dict]) -> bool:
        """
        Validate that the extracted answer matches expected format for the checklist item.
        """
        # Find the checklist item
        item_details = next((item for item in checklist if item.get("key") == item_key), None)
        if not item_details:
            return False
        
        expected_type = item_details.get("value_type", "text")
        
        # Basic format validation
        if expected_type == "email":
            import re
            email_pattern = r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}$'
            return re.match(email_pattern, answer_value) is not None
        elif expected_type == "phone":
            # Simple phone validation
            digits = re.sub(r'\D', '', answer_value)
            return 7 <= len(digits) <= 15
        elif expected_type == "website":
            return answer_value.startswith(('http://', 'https://')) or answer_value.startswith('www.')
        else:
            # For text and other types, just check it's not empty
            return len(answer_value.strip()) > 0
    
    async def _generate_confirmation_message(self, confirmation_items: List[Dict]) -> str:
        """
        Generate a user-friendly confirmation message for research findings.
        """
        if len(confirmation_items) == 1:
            item = confirmation_items[0]
            return f"""I found some information that might answer your question about "{item['question']}":

**Suggested Answer:** {item['suggested_answer']}

This information was found through research with {item['confidence']:.0%} confidence. 

Is this correct, or would you like to provide a different answer?"""
        
        else:
            message_parts = ["I found some information that might help answer several of your questions:\n"]
            
            for i, item in enumerate(confirmation_items, 1):
                message_parts.append(f"**{i}. {item['question']}**")
                message_parts.append(f"   Suggested Answer: {item['suggested_answer']}")
                message_parts.append(f"   Confidence: {item['confidence']:.0%}\n")
            
            message_parts.append("Are these answers correct, or would you like to make any changes?")
            return "\n".join(message_parts)
    
    async def _generate_clarifying_question(
        self, 
        item: Dict[str, Any], 
        research_context: Dict[str, Any],
        provider_info: Dict[str, Any]
    ) -> str:
        """
        Generate a clarifying question using research context.
        """
        base_question = item["prompt"]
        
        # If we have research context, use it to create a more informed question
        if research_context and research_context.get("value"):
            suggested_answer = research_context["value"]
            confidence = research_context.get("confidence", 0)
            
            prompt = f"""
            Create a clarifying question for this checklist item, incorporating research findings:
            
            Original Question: {base_question}
            Research Finding: {suggested_answer}
            Research Confidence: {confidence:.0%}
            Provider Info: {provider_info.get('name', 'your business')}
            
            Create a question that:
            1. References the research finding
            2. Asks for confirmation or clarification
            3. Is conversational and helpful
            4. Provides context about why we're asking
            
            Example: "I found that {provider_info.get('name', 'your business')} might be located at {suggested_answer}, but I want to make sure this is correct. Could you confirm your business address?"
            """
            
            response = await self.llm.ainvoke(prompt)
            return response.content
        
        else:
            # Standard question without research context
            return f"Could you please provide information for: {base_question}"
    
    def _apply_confirmed_answer(self, state: EvolvedOnboardingState, confirmation_item: Dict[str, Any]):
        """
        Apply a confirmed answer to the checklist.
        """
        checklist = state["checklist"]
        item_key = confirmation_item["key"]
        
        for item in checklist:
            if item.get("key") == item_key:
                item["value"] = confirmation_item["suggested_answer"]
                item["status"] = "VERIFIED"
                item["source"] = "research_confirmed"
                item["confidence"] = confirmation_item["confidence"]
                item["confirmed_at"] = datetime.utcnow().isoformat()
                break
    
    def _get_next_pending_item(self, checklist: List[Dict]) -> Optional[Dict]:
        """
        Get the next pending checklist item.
        """
        pending_items = [item for item in checklist if item.get("status") == "PENDING"]
        if pending_items:
            # Return highest priority pending item
            required_items = [item for item in pending_items if item.get("required")]
            if required_items:
                return required_items[0]
            else:
                return pending_items[0]
        return None
```

## State Management

```python
class EvolvedOnboardingState(TypedDict):
    """
    Enhanced state for two-part research workflow.
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
    
    # Two-part research system
    checklist_research_results: List[Dict[str, Any]]
    checklist_research_completed: bool
    checklist_modifications: Dict[str, Any]
    answer_research_results: List[Dict[str, Any]]
    research_answers: Dict[str, Any]
    
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
```

## Integration Points

### Research Tool Integration
- **Wikipedia/ArXiv Search**: For industry standards and regulatory requirements
- **Web Search with Readability Parser**: For specific business information
- **Clean Text Processing**: Removes HTML, code, images for focused content
- **Business Pattern Extraction**: Identifies emails, phones, addresses automatically

### Two-Phase Research Flow
1. **Checklist Customization Phase**: 
   - Uses academic/official sources
   - Focuses on industry requirements
   - Modifies checklist structure
   
2. **Answer Gathering Phase**:
   - Uses web search for specific providers
   - Extracts contact information and business details  
   - Auto-fills checklist items with confidence scoring

### Quality Control
- Confidence thresholds for auto-fill decisions
- Source attribution for all research findings
- Fallback to user questions when research is insufficient
- Human review triggers for low-confidence extractions