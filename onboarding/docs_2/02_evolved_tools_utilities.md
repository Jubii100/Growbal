# Evolved Tools and Utilities

## Overview

The evolved tools and utilities module provides enhanced capabilities for intelligent research, dynamic RAG operations, adaptive checklist management, and seamless data updates throughout the onboarding workflow.

## Enhanced Research Tools

### 1. Intelligent Research Orchestrator

```python
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime

class ResearchPriority(Enum):
    """Research priority levels"""
    CRITICAL = "critical"      # Must have for proceeding
    HIGH = "high"              # Important for quality
    MEDIUM = "medium"          # Beneficial but not essential
    LOW = "low"                # Nice to have

@dataclass
class ResearchQuery:
    """Structured research query"""
    query_text: str
    source_type: str
    priority: ResearchPriority
    checklist_items: List[str]
    max_results: int = 5
    timeout: int = 30

class IntelligentResearchOrchestrator:
    """
    Orchestrates research activities with intelligent query optimization.
    """
    
    def __init__(self, search_tools, llm, user_profile_db):
        self.search_tools = search_tools
        self.llm = llm
        self.user_profile_db = user_profile_db
        self.research_cache = {}
        
    async def conduct_adaptive_research(
        self,
        checklist: List[Dict],
        user_profile: Dict,
        provider_info: Dict,
        previous_research: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        Conduct research adaptively based on checklist needs.
        
        Args:
            checklist: Current checklist state
            user_profile: User profile data
            provider_info: Provider information
            previous_research: Previous research results if any
            
        Returns:
            Structured research results
        """
        # Analyze checklist to identify research needs
        research_needs = self._analyze_research_needs(
            checklist=checklist,
            user_profile=user_profile,
            previous_research=previous_research
        )
        
        if not research_needs:
            return {"status": "no_research_needed", "results": []}
        
        # Generate optimized research queries
        queries = self._generate_optimized_queries(
            needs=research_needs,
            provider_info=provider_info,
            user_profile=user_profile
        )
        
        # Execute research with intelligent batching
        results = await self._execute_research_batch(queries)
        
        # Post-process and validate results
        processed_results = self._process_research_results(
            results=results,
            checklist=checklist,
            confidence_threshold=0.7
        )
        
        # Update cache
        self._update_research_cache(processed_results)
        
        return {
            "status": "completed",
            "results": processed_results,
            "queries_executed": len(queries),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _analyze_research_needs(
        self,
        checklist: List[Dict],
        user_profile: Dict,
        previous_research: Optional[List[Dict]]
    ) -> List[Dict]:
        """
        Identify what information needs research.
        """
        needs = []
        
        for item in checklist:
            if item["status"] != "PENDING":
                continue
            
            # Check if research would help
            need_score = self._calculate_research_need_score(
                item=item,
                user_profile=user_profile,
                previous_research=previous_research
            )
            
            if need_score > 0.3:  # Threshold for research
                need = {
                    "checklist_key": item["key"],
                    "information_type": item.get("category", "general"),
                    "prompt": item["prompt"],
                    "priority": self._determine_priority(item, need_score),
                    "need_score": need_score
                }
                needs.append(need)
        
        # Sort by priority and score
        return sorted(needs, key=lambda x: (x["priority"].value, -x["need_score"]))
    
    def _generate_optimized_queries(
        self,
        needs: List[Dict],
        provider_info: Dict,
        user_profile: Dict
    ) -> List[ResearchQuery]:
        """
        Generate optimized research queries using LLM.
        """
        queries = []
        
        # Group similar needs for batch queries
        grouped_needs = self._group_similar_needs(needs)
        
        for group in grouped_needs:
            # Use LLM to generate effective query
            prompt = f"""
            Generate an effective search query for this information need:
            
            Provider: {provider_info.get('name', 'Unknown')}
            Service Type: {provider_info.get('service_type', 'Unknown')}
            Location: {provider_info.get('location', 'Unknown')}
            
            Information needed:
            {json.dumps([n['prompt'] for n in group], indent=2)}
            
            User context:
            {json.dumps(user_profile, indent=2)}
            
            Generate a single, comprehensive search query that would help find this information.
            """
            
            query_text = self.llm.invoke(prompt).content
            
            query = ResearchQuery(
                query_text=query_text,
                source_type=self._determine_source_type(group),
                priority=group[0]["priority"],
                checklist_items=[n["checklist_key"] for n in group],
                max_results=5
            )
            queries.append(query)
        
        return queries[:10]  # Limit to 10 queries
    
    async def _execute_research_batch(
        self,
        queries: List[ResearchQuery]
    ) -> List[Dict]:
        """
        Execute research queries in optimized batches.
        """
        results = []
        
        # Group by priority for batch execution
        critical = [q for q in queries if q.priority == ResearchPriority.CRITICAL]
        high = [q for q in queries if q.priority == ResearchPriority.HIGH]
        other = [q for q in queries if q.priority not in [ResearchPriority.CRITICAL, ResearchPriority.HIGH]]
        
        # Execute critical queries first
        if critical:
            critical_results = await self._execute_query_batch(critical)
            results.extend(critical_results)
        
        # Execute high priority in parallel with others
        if high or other:
            batch_results = await asyncio.gather(
                self._execute_query_batch(high) if high else asyncio.create_task(self._return_empty()),
                self._execute_query_batch(other) if other else asyncio.create_task(self._return_empty())
            )
            for batch in batch_results:
                if batch:
                    results.extend(batch)
        
        return results
    
    async def _execute_query_batch(
        self,
        queries: List[ResearchQuery]
    ) -> List[Dict]:
        """
        Execute a batch of queries in parallel.
        """
        tasks = []
        
        for query in queries:
            # Check cache first
            cache_key = self._get_cache_key(query)
            if cache_key in self.research_cache:
                tasks.append(asyncio.create_task(self._return_cached(cache_key)))
            else:
                # Execute based on source type
                if query.source_type == "web":
                    tasks.append(self.search_tools.search_web_async(query.query_text))
                elif query.source_type == "business":
                    tasks.append(self.search_tools.search_business_async(query.query_text))
                elif query.source_type == "standards":
                    tasks.append(self.search_tools.search_standards_async(query.query_text))
                else:
                    tasks.append(self.search_tools.search_general_async(query.query_text))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Package results with query metadata
        packaged_results = []
        for query, result in zip(queries, results):
            if not isinstance(result, Exception):
                packaged_results.append({
                    "query": query,
                    "result": result,
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": True
                })
            else:
                packaged_results.append({
                    "query": query,
                    "error": str(result),
                    "timestamp": datetime.utcnow().isoformat(),
                    "success": False
                })
        
        return packaged_results
```

### 2. Enhanced RAG System

```python
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
import chromadb
from chromadb.config import Settings
import numpy as np

class EnhancedRAGSystem:
    """
    Enhanced RAG system with intelligent indexing and retrieval.
    """
    
    def __init__(self, chroma_path: str = "./chroma_db"):
        self.embeddings = OpenAIEmbeddings()
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False)
        )
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
    async def index_findings(
        self,
        findings: List[Dict],
        session_id: str,
        metadata: Dict
    ) -> str:
        """
        Index research findings with intelligent chunking.
        
        Args:
            findings: Research findings to index
            session_id: Current session ID
            metadata: Additional metadata
            
        Returns:
            Collection ID
        """
        collection_name = f"session_{session_id}_{datetime.utcnow().timestamp()}"
        
        # Create collection
        collection = self.chroma_client.create_collection(
            name=collection_name,
            embedding_function=self.embeddings
        )
        
        # Process findings
        documents = []
        metadatas = []
        ids = []
        
        for i, finding in enumerate(findings):
            # Extract and chunk content
            content = finding.get("content", "")
            chunks = self.splitter.split_text(content)
            
            for j, chunk in enumerate(chunks):
                documents.append(chunk)
                
                # Create rich metadata
                chunk_metadata = {
                    **metadata,
                    "finding_id": i,
                    "chunk_id": j,
                    "source": finding.get("source", "unknown"),
                    "relevance_score": finding.get("relevance_score", 0.5),
                    "checklist_items": finding.get("checklist_items", []),
                    "timestamp": finding.get("timestamp", datetime.utcnow().isoformat())
                }
                metadatas.append(chunk_metadata)
                ids.append(f"{collection_name}_{i}_{j}")
        
        # Add to collection with embeddings
        if documents:
            embeddings = self.embeddings.embed_documents(documents)
            collection.add(
                documents=documents,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
        
        return collection_name
    
    def retrieve_context(
        self,
        query: str,
        collection_id: str,
        top_k: int = 5,
        relevance_threshold: float = 0.7
    ) -> str:
        """
        Retrieve relevant context with intelligent filtering.
        
        Args:
            query: Search query
            collection_id: Collection to search
            top_k: Number of results
            relevance_threshold: Minimum relevance score
            
        Returns:
            Formatted context string
        """
        try:
            collection = self.chroma_client.get_collection(collection_id)
            
            # Perform similarity search
            results = collection.query(
                query_texts=[query],
                n_results=top_k * 2  # Get more for filtering
            )
            
            # Filter and rank results
            filtered_results = []
            for i, doc in enumerate(results["documents"][0]):
                distance = results["distances"][0][i] if results["distances"] else 1.0
                relevance = 1 - distance  # Convert distance to relevance
                
                if relevance >= relevance_threshold:
                    filtered_results.append({
                        "content": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "relevance": relevance
                    })
            
            # Sort by relevance
            filtered_results.sort(key=lambda x: x["relevance"], reverse=True)
            
            # Format context
            context_parts = []
            for result in filtered_results[:top_k]:
                source = result["metadata"].get("source", "Unknown")
                relevance = result["relevance"]
                content = result["content"]
                
                context_parts.append(
                    f"[Source: {source}, Relevance: {relevance:.2f}]\n{content}"
                )
            
            return "\n\n".join(context_parts)
            
        except Exception as e:
            return f"Error retrieving context: {str(e)}"
    
    def update_collection_with_feedback(
        self,
        collection_id: str,
        query: str,
        selected_chunks: List[str],
        feedback_type: str = "positive"
    ):
        """
        Update collection based on user feedback.
        
        Args:
            collection_id: Collection to update
            query: Original query
            selected_chunks: Chunks that were useful
            feedback_type: Type of feedback
        """
        try:
            collection = self.chroma_client.get_collection(collection_id)
            
            # Update metadata for selected chunks
            for chunk_id in selected_chunks:
                # Get current metadata
                result = collection.get(ids=[chunk_id])
                if result["metadatas"]:
                    metadata = result["metadatas"][0]
                    
                    # Update feedback scores
                    if feedback_type == "positive":
                        metadata["positive_feedback"] = metadata.get("positive_feedback", 0) + 1
                    else:
                        metadata["negative_feedback"] = metadata.get("negative_feedback", 0) + 1
                    
                    # Update the metadata
                    collection.update(
                        ids=[chunk_id],
                        metadatas=[metadata]
                    )
                    
        except Exception as e:
            print(f"Error updating feedback: {str(e)}")
```

### 3. Dynamic Checklist Management Tools

```python
class DynamicChecklistManager:
    """
    Advanced checklist management with intelligent updates.
    """
    
    def __init__(self, llm, validation_service):
        self.llm = llm
        self.validation = validation_service
        self.checklist_history = []
        
    def update_checklist_intelligently(
        self,
        checklist: List[Dict],
        user_response: str,
        research_findings: Optional[List[Dict]] = None,
        user_profile: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Intelligently update checklist based on all available information.
        
        Args:
            checklist: Current checklist
            user_response: Latest user response
            research_findings: Research results if available
            user_profile: User profile data
            
        Returns:
            Updated checklist with change summary
        """
        # Snapshot current state
        self.checklist_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "checklist": copy.deepcopy(checklist)
        })
        
        changes = {
            "items_updated": [],
            "items_added": [],
            "items_removed": [],
            "items_reordered": False
        }
        
        # Update from user response
        response_updates = self._process_user_response(
            checklist=checklist,
            response=user_response,
            user_profile=user_profile
        )
        checklist = response_updates["checklist"]
        changes["items_updated"].extend(response_updates["updated"])
        
        # Auto-fill from research
        if research_findings:
            research_updates = self._apply_research_findings(
                checklist=checklist,
                findings=research_findings,
                confidence_threshold=0.75
            )
            checklist = research_updates["checklist"]
            changes["items_updated"].extend(research_updates["auto_filled"])
        
        # Add dynamic items based on discoveries
        dynamic_additions = self._identify_dynamic_items(
            current_checklist=checklist,
            user_response=user_response,
            research=research_findings,
            user_profile=user_profile
        )
        
        for new_item in dynamic_additions:
            checklist.append(new_item)
            changes["items_added"].append(new_item["key"])
        
        # Remove irrelevant items
        relevance_check = self._check_item_relevance(
            checklist=checklist,
            user_profile=user_profile,
            responses_so_far=self._extract_responses(checklist)
        )
        
        checklist = [
            item for item in checklist 
            if item["key"] not in relevance_check["irrelevant"]
        ]
        changes["items_removed"] = relevance_check["irrelevant"]
        
        # Reorder based on dependencies and priority
        reordered_checklist = self._intelligent_reorder(checklist)
        if reordered_checklist != checklist:
            checklist = reordered_checklist
            changes["items_reordered"] = True
        
        return {
            "checklist": checklist,
            "changes": changes,
            "completion_percentage": self._calculate_completion(checklist),
            "next_item": self._get_next_priority_item(checklist)
        }
    
    def _process_user_response(
        self,
        checklist: List[Dict],
        response: str,
        user_profile: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Process user response and update relevant checklist items.
        """
        updated_items = []
        
        # Use LLM to extract information from response
        extraction_prompt = f"""
        Extract information from this user response that matches checklist items:
        
        User Response: {response}
        
        Checklist items to match:
        {json.dumps([{"key": item["key"], "prompt": item["prompt"]} for item in checklist if item["status"] == "ASKED"], indent=2)}
        
        User Profile Context: {json.dumps(user_profile, indent=2) if user_profile else "N/A"}
        
        For each matched item, provide:
        1. The item key
        2. The extracted value
        3. Confidence score (0-1)
        """
        
        extraction_result = self.llm.invoke(extraction_prompt)
        # Parse extraction result
        
        for item in checklist:
            # Check if this item was addressed in the response
            if item["status"] == "ASKED":
                # Validate and update
                validation = self.validation.validate_response(
                    response=response,
                    item=item
                )
                
                if validation["valid"]:
                    item["value"] = validation["extracted_value"]
                    item["status"] = "VERIFIED"
                    item["verified_at"] = datetime.utcnow().isoformat()
                    updated_items.append(item["key"])
                else:
                    item["validation_errors"] = validation["errors"]
                    item["status"] = "NEEDS_CLARIFICATION"
        
        return {
            "checklist": checklist,
            "updated": updated_items
        }
    
    def _apply_research_findings(
        self,
        checklist: List[Dict],
        findings: List[Dict],
        confidence_threshold: float
    ) -> Dict[str, Any]:
        """
        Auto-fill checklist items from research with confidence scoring.
        """
        auto_filled = []
        
        for item in checklist:
            if item["status"] != "PENDING":
                continue
            
            # Find relevant research for this item
            relevant_findings = self._find_relevant_research(
                item=item,
                findings=findings
            )
            
            if relevant_findings:
                # Use LLM to extract value from findings
                extraction = self._extract_value_from_findings(
                    item=item,
                    findings=relevant_findings
                )
                
                if extraction["confidence"] >= confidence_threshold:
                    item["value"] = extraction["value"]
                    item["status"] = "AUTO_FILLED"
                    item["source"] = "research"
                    item["confidence"] = extraction["confidence"]
                    item["research_references"] = extraction["references"]
                    auto_filled.append(item["key"])
        
        return {
            "checklist": checklist,
            "auto_filled": auto_filled
        }
    
    def _identify_dynamic_items(
        self,
        current_checklist: List[Dict],
        user_response: str,
        research: Optional[List[Dict]],
        user_profile: Optional[Dict]
    ) -> List[Dict]:
        """
        Identify new checklist items to add dynamically.
        """
        new_items = []
        
        # Use LLM to identify missing requirements
        prompt = f"""
        Based on the conversation and research, identify any additional information needed:
        
        Current checklist items: {json.dumps([item["key"] for item in current_checklist], indent=2)}
        
        Latest user response: {user_response}
        
        Research findings summary: {self._summarize_research(research) if research else "N/A"}
        
        User profile: {json.dumps(user_profile, indent=2) if user_profile else "N/A"}
        
        Identify any critical missing information that should be collected.
        For each item, provide:
        1. A unique key
        2. The question to ask
        3. Category (contact, legal, service, etc.)
        4. Whether it's required (true/false)
        5. Reason for adding
        """
        
        suggestions = self.llm.invoke(prompt)
        # Parse suggestions and create new items
        
        return new_items
    
    def _intelligent_reorder(self, checklist: List[Dict]) -> List[Dict]:
        """
        Reorder checklist based on dependencies and priority.
        """
        # Separate by status
        completed = [i for i in checklist if i["status"] in ["VERIFIED", "AUTO_FILLED"]]
        in_progress = [i for i in checklist if i["status"] in ["ASKED", "NEEDS_CLARIFICATION"]]
        pending = [i for i in checklist if i["status"] == "PENDING"]
        
        # Sort pending by priority and dependencies
        pending_sorted = self._topological_sort_with_priority(pending)
        
        # Combine in logical order
        return completed + in_progress + pending_sorted
    
    def _topological_sort_with_priority(self, items: List[Dict]) -> List[Dict]:
        """
        Sort items considering both dependencies and priority.
        """
        # Build dependency graph
        graph = {item["key"]: item.get("dependencies", []) for item in items}
        
        # Perform topological sort
        sorted_keys = []
        visited = set()
        
        def visit(key):
            if key in visited:
                return
            visited.add(key)
            for dep in graph.get(key, []):
                if dep in graph:  # Only if dependency is in pending items
                    visit(dep)
            sorted_keys.append(key)
        
        # Visit all nodes
        for item in items:
            visit(item["key"])
        
        # Create sorted list
        key_to_item = {item["key"]: item for item in items}
        sorted_items = [key_to_item[key] for key in sorted_keys if key in key_to_item]
        
        # Further sort by priority within dependency levels
        return sorted(sorted_items, key=lambda x: (
            0 if x.get("required", False) else 1,
            {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(x.get("priority", "medium"), 2)
        ))
```

### 4. State Management and Persistence Tools

```python
import redis
import pickle
from typing import Optional

class StateManagementTools:
    """
    Tools for managing and persisting workflow state.
    """
    
    def __init__(self, redis_client: redis.Redis, db_connection):
        self.redis = redis_client
        self.db = db_connection
        
    async def save_state_checkpoint(
        self,
        session_id: str,
        state: Dict[str, Any],
        checkpoint_type: str = "auto"
    ) -> bool:
        """
        Save a state checkpoint for recovery.
        
        Args:
            session_id: Session identifier
            state: Current state to save
            checkpoint_type: Type of checkpoint (auto, manual, milestone)
            
        Returns:
            Success status
        """
        try:
            checkpoint = {
                "session_id": session_id,
                "state": state,
                "timestamp": datetime.utcnow().isoformat(),
                "type": checkpoint_type,
                "version": state.get("checklist_version", "1.0")
            }
            
            # Save to Redis for quick access
            redis_key = f"checkpoint:{session_id}:{datetime.utcnow().timestamp()}"
            self.redis.setex(
                redis_key,
                3600,  # 1 hour TTL
                pickle.dumps(checkpoint)
            )
            
            # Save to database for persistence
            async with self.db.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO state_checkpoints 
                    (session_id, checkpoint_data, checkpoint_type, created_at)
                    VALUES ($1, $2, $3, $4)
                """, session_id, Json(checkpoint), checkpoint_type, datetime.utcnow())
            
            return True
            
        except Exception as e:
            print(f"Error saving checkpoint: {str(e)}")
            return False
    
    async def load_latest_checkpoint(
        self,
        session_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load the most recent checkpoint for a session.
        
        Args:
            session_id: Session identifier
            
        Returns:
            State checkpoint or None
        """
        try:
            # Try Redis first
            pattern = f"checkpoint:{session_id}:*"
            keys = self.redis.keys(pattern)
            
            if keys:
                # Get most recent
                latest_key = sorted(keys)[-1]
                checkpoint = pickle.loads(self.redis.get(latest_key))
                return checkpoint["state"]
            
            # Fallback to database
            async with self.db.get_connection() as conn:
                result = await conn.fetchone("""
                    SELECT checkpoint_data 
                    FROM state_checkpoints 
                    WHERE session_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, session_id)
                
                if result:
                    return result["checkpoint_data"]["state"]
            
            return None
            
        except Exception as e:
            print(f"Error loading checkpoint: {str(e)}")
            return None
    
    def track_state_transition(
        self,
        session_id: str,
        from_state: str,
        to_state: str,
        trigger: str,
        metadata: Optional[Dict] = None
    ):
        """
        Track state transitions for analytics and debugging.
        
        Args:
            session_id: Session identifier
            from_state: Previous state
            to_state: New state
            trigger: What triggered the transition
            metadata: Additional context
        """
        transition = {
            "session_id": session_id,
            "from_state": from_state,
            "to_state": to_state,
            "trigger": trigger,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        
        # Log to Redis for real-time monitoring
        redis_key = f"transitions:{session_id}"
        self.redis.rpush(redis_key, pickle.dumps(transition))
        self.redis.expire(redis_key, 86400)  # 24 hour TTL
```

### 5. Summary and Confirmation Tools

```python
class SummaryGenerationTools:
    """
    Tools for generating summaries and confirmation messages.
    """
    
    def __init__(self, llm, template_engine):
        self.llm = llm
        self.templates = template_engine
        
    def generate_adaptive_summary(
        self,
        state: Dict[str, Any],
        summary_type: str = "progress"
    ) -> str:
        """
        Generate contextual summary based on current state.
        
        Args:
            state: Current workflow state
            summary_type: Type of summary (progress, final, confirmation)
            
        Returns:
            Formatted summary
        """
        if summary_type == "progress":
            return self._generate_progress_summary(state)
        elif summary_type == "final":
            return self._generate_final_summary(state)
        elif summary_type == "confirmation":
            return self._generate_confirmation_summary(state)
        else:
            return self._generate_generic_summary(state)
    
    def _generate_final_summary(self, state: Dict[str, Any]) -> str:
        """
        Generate comprehensive final summary for confirmation.
        """
        checklist = state["checklist"]
        completed_items = [i for i in checklist if i["status"] in ["VERIFIED", "AUTO_FILLED"]]
        
        prompt = f"""
        Generate a professional summary of the onboarding session:
        
        Provider Information:
        {json.dumps(state["provider_profile"], indent=2)}
        
        Completed Requirements ({len(completed_items)}/{len(checklist)}):
        {json.dumps([{"prompt": i["prompt"], "value": i.get("value")} for i in completed_items], indent=2)}
        
        Research Findings:
        {self._summarize_research_findings(state.get("research_notes", []))}
        
        Session Metrics:
        - Duration: {self._calculate_duration(state)}
        - Questions Asked: {len([m for m in state["messages"] if m.get("role") == "assistant"])}
        - Completion Rate: {state.get("completion_metrics", {}).get("percentage", 0)}%
        
        Create a clear, structured summary including:
        1. Provider overview
        2. Key services and capabilities
        3. Compliance and requirements status
        4. Next steps (if any)
        """
        
        summary = self.llm.invoke(prompt).content
        
        # Apply template formatting
        return self.templates.format_summary(
            summary=summary,
            provider_name=state["provider_profile"].get("name", "Provider"),
            completion_percentage=state.get("completion_metrics", {}).get("percentage", 0)
        )
```

## Tool Integration Framework

```python
class ToolIntegrationFramework:
    """
    Framework for integrating all tools into the workflow.
    """
    
    def __init__(self, config: Dict[str, Any]):
        # Initialize all tool modules
        self.research = IntelligentResearchOrchestrator(
            search_tools=self._init_search_tools(config),
            llm=config["llm"],
            user_profile_db=config["user_profile_db"]
        )
        
        self.rag = EnhancedRAGSystem(
            chroma_path=config.get("chroma_path", "./chroma_db")
        )
        
        self.checklist_manager = DynamicChecklistManager(
            llm=config["llm"],
            validation_service=config["validation_service"]
        )
        
        self.state_manager = StateManagementTools(
            redis_client=config["redis_client"],
            db_connection=config["db_connection"]
        )
        
        self.summary_tools = SummaryGenerationTools(
            llm=config["llm"],
            template_engine=config["template_engine"]
        )
    
    def get_tool_suite(self) -> Dict[str, Any]:
        """
        Get complete tool suite for agent use.
        """
        return {
            "research": self.research,
            "rag": self.rag,
            "checklist": self.checklist_manager,
            "state": self.state_manager,
            "summary": self.summary_tools
        }
    
    def _init_search_tools(self, config: Dict) -> Any:
        """
        Initialize search tools based on configuration.
        """
        # Implementation depends on specific search APIs
        return SearchTools(config["search_api_keys"])
```