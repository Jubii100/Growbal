# Tools and Utilities Documentation

## Overview
This module contains all tools used by the onboarding agent for research, RAG operations, and data updates.

## Search Tools Implementation

### 1. Multi-Source Search Tool

```python
from langchain.tools import Tool
from langchain_community.utilities import SerpAPIWrapper, ArxivAPIWrapper
from langchain_community.document_loaders import WikipediaLoader
from typing import List, Dict, Any
import asyncio

class SearchTools:
    """
    Unified search tools for the onboarding agent.
    """
    
    def __init__(self, serp_api_key: str):
        self.serp = SerpAPIWrapper(serpapi_api_key=serp_api_key)
        self.arxiv = ArxivAPIWrapper()
        
    def search_web(self, query: str) -> str:
        """
        General web search using SERP API.
        
        Args:
            query: Search query
            
        Returns:
            Formatted search results
        """
        try:
            results = self.serp.run(query)
            return self._format_search_results(results, "web")
        except Exception as e:
            return f"Web search error: {str(e)}"
    
    def search_business_info(self, company_name: str, location: str = "") -> Dict[str, Any]:
        """
        Specialized search for business information.
        
        Args:
            company_name: Name of the business
            location: Optional location filter
            
        Returns:
            Structured business information
        """
        query = f"{company_name} {location} business services contact rating"
        web_results = self.search_web(query)
        
        # Parse and structure the results
        return {
            "raw_results": web_results,
            "structured_data": self._extract_business_info(web_results)
        }
    
    def search_industry_standards(self, service_type: str, region: str = "UAE") -> List[Dict]:
        """
        Search for industry standards and requirements.
        
        Args:
            service_type: Type of service (tax, migration, business setup)
            region: Geographic region for standards
            
        Returns:
            List of relevant standards and requirements
        """
        queries = [
            f"{service_type} requirements {region}",
            f"{service_type} industry standards {region}",
            f"{service_type} best practices {region}"
        ]
        
        results = []
        for query in queries:
            results.append({
                "query": query,
                "results": self.search_web(query)
            })
        
        return results
    
    def search_wikipedia(self, query: str, max_docs: int = 3) -> List[Dict[str, str]]:
        """
        Search Wikipedia for educational/background content.
        
        Args:
            query: Search query
            max_docs: Maximum number of documents to return
            
        Returns:
            List of Wikipedia article contents
        """
        try:
            loader = WikipediaLoader(query=query, load_max_docs=max_docs)
            docs = loader.load()
            return [
                {
                    "title": doc.metadata.get("title", ""),
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "")
                }
                for doc in docs
            ]
        except Exception as e:
            return [{"error": str(e)}]
    
    def search_academic(self, query: str) -> str:
        """
        Search academic papers on ArXiv.
        
        Args:
            query: Academic search query
            
        Returns:
            Relevant paper summaries
        """
        try:
            return self.arxiv.run(query)
        except Exception as e:
            return f"Academic search error: {str(e)}"
    
    async def parallel_search(self, queries: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        """
        Execute multiple searches in parallel.
        
        Args:
            queries: List of {"source": "web|wiki|arxiv", "query": "..."}
            
        Returns:
            List of search results
        """
        tasks = []
        for q in queries:
            if q["source"] == "web":
                tasks.append(self._async_wrapper(self.search_web, q["query"]))
            elif q["source"] == "wiki":
                tasks.append(self._async_wrapper(self.search_wikipedia, q["query"]))
            elif q["source"] == "arxiv":
                tasks.append(self._async_wrapper(self.search_academic, q["query"]))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        return [
            {"query": q, "result": r} 
            for q, r in zip(queries, results)
        ]
    
    async def _async_wrapper(self, func, *args):
        """Wrapper to run sync functions in async context."""
        return await asyncio.get_event_loop().run_in_executor(None, func, *args)
    
    def _format_search_results(self, results: Any, source: str) -> str:
        """Format search results for consistent processing."""
        # Implementation specific to result format
        return str(results)
    
    def _extract_business_info(self, raw_results: str) -> Dict[str, Any]:
        """Extract structured business information from raw search results."""
        # Use regex or LLM to extract structured data
        return {
            "name": "",
            "contact": "",
            "services": [],
            "rating": None
        }
```

### 2. Tool Registration

```python
def create_search_tools() -> List[Tool]:
    """
    Create LangChain Tool objects for the agent.
    """
    search = SearchTools(serp_api_key=os.getenv("SERPER_API_KEY"))
    
    tools = [
        Tool(
            name="search_web",
            func=search.search_web,
            description="Search the web for general information"
        ),
        Tool(
            name="search_business",
            func=search.search_business_info,
            description="Search for specific business information"
        ),
        Tool(
            name="search_standards",
            func=search.search_industry_standards,
            description="Search for industry standards and requirements"
        ),
        Tool(
            name="search_wikipedia",
            func=search.search_wikipedia,
            description="Search Wikipedia for background information"
        )
    ]
    
    return tools
```

## RAG Tools

### 1. Document Processing and Retrieval

```python
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
import chromadb
from chromadb.config import Settings
from typing import List, Optional

class RAGTools:
    """
    Tools for document processing and retrieval-augmented generation.
    """
    
    def __init__(self, chroma_path: str = "./chroma_db"):
        self.embeddings = OpenAIEmbeddings()
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=1200,
            chunk_overlap=150,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        self.chroma_client = chromadb.PersistentClient(
            path=chroma_path,
            settings=Settings(anonymized_telemetry=False)
        )
    
    def process_and_index_documents(
        self, 
        documents: List[str], 
        collection_name: str,
        metadata: Optional[List[Dict]] = None
    ) -> str:
        """
        Process documents and index them in Chroma.
        
        Args:
            documents: List of document contents
            collection_name: Name for the Chroma collection
            metadata: Optional metadata for documents
            
        Returns:
            Collection ID
        """
        # Split documents into chunks
        all_chunks = []
        all_metadatas = []
        
        for i, doc in enumerate(documents):
            chunks = self.splitter.split_text(doc)
            all_chunks.extend(chunks)
            
            # Add metadata for each chunk
            doc_metadata = metadata[i] if metadata else {}
            all_metadatas.extend([
                {**doc_metadata, "chunk_index": j}
                for j in range(len(chunks))
            ])
        
        # Create or get collection
        collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embeddings
        )
        
        # Generate embeddings and add to collection
        embeddings = self.embeddings.embed_documents(all_chunks)
        
        collection.add(
            documents=all_chunks,
            embeddings=embeddings,
            metadatas=all_metadatas,
            ids=[f"{collection_name}_{i}" for i in range(len(all_chunks))]
        )
        
        return collection_name
    
    def retrieve_relevant_chunks(
        self,
        query: str,
        collection_name: str,
        top_k: int = 6,
        filter_dict: Optional[Dict] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant document chunks.
        
        Args:
            query: Search query
            collection_name: Chroma collection to search
            top_k: Number of results to return
            filter_dict: Optional metadata filters
            
        Returns:
            List of relevant chunks with metadata
        """
        try:
            collection = self.chroma_client.get_collection(collection_name)
            
            # Perform similarity search
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
                where=filter_dict
            )
            
            # Format results
            chunks = []
            for i, doc in enumerate(results["documents"][0]):
                chunks.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None
                })
            
            return chunks
            
        except Exception as e:
            return [{"error": str(e)}]
    
    def update_collection(
        self,
        collection_name: str,
        new_documents: List[str],
        new_metadata: Optional[List[Dict]] = None
    ):
        """
        Update an existing collection with new documents.
        
        Args:
            collection_name: Name of collection to update
            new_documents: New documents to add
            new_metadata: Metadata for new documents
        """
        collection = self.chroma_client.get_collection(collection_name)
        
        # Process new documents
        chunks = []
        metadatas = []
        for i, doc in enumerate(new_documents):
            doc_chunks = self.splitter.split_text(doc)
            chunks.extend(doc_chunks)
            
            doc_meta = new_metadata[i] if new_metadata else {}
            metadatas.extend([doc_meta] * len(doc_chunks))
        
        # Add to collection
        if chunks:
            embeddings = self.embeddings.embed_documents(chunks)
            
            # Generate unique IDs
            existing_count = collection.count()
            ids = [f"{collection_name}_{existing_count + i}" for i in range(len(chunks))]
            
            collection.add(
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )
```

## Data Update Tools

### 1. State and Database Update Tools

```python
from typing import Dict, Any, List
import json
from datetime import datetime

class DataUpdateTools:
    """
    Tools for updating agent state and database records.
    """
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def update_checklist_item(
        self,
        checklist: List[Dict],
        item_key: str,
        updates: Dict[str, Any]
    ) -> List[Dict]:
        """
        Update a specific checklist item.
        
        Args:
            checklist: Current checklist state
            item_key: Key of item to update
            updates: Dictionary of updates to apply
            
        Returns:
            Updated checklist
        """
        for item in checklist:
            if item["key"] == item_key:
                item.update(updates)
                item["updated_at"] = datetime.utcnow().isoformat()
        
        return checklist
    
    def batch_update_checklist(
        self,
        checklist: List[Dict],
        updates: List[Dict[str, Any]]
    ) -> List[Dict]:
        """
        Batch update multiple checklist items.
        
        Args:
            checklist: Current checklist
            updates: List of {"key": "...", "updates": {...}}
            
        Returns:
            Updated checklist
        """
        for update in updates:
            checklist = self.update_checklist_item(
                checklist,
                update["key"],
                update["updates"]
            )
        
        return checklist
    
    def save_provider_profile(
        self,
        provider_data: Dict[str, Any],
        checklist: List[Dict],
        research_notes: List[Dict]
    ) -> str:
        """
        Save complete provider profile to database.
        
        Args:
            provider_data: Provider information
            checklist: Completed checklist
            research_notes: Research findings
            
        Returns:
            Provider ID
        """
        # Prepare data for storage
        profile = {
            "provider_info": provider_data,
            "checklist": checklist,
            "research_notes": research_notes,
            "created_at": datetime.utcnow().isoformat(),
            "status": "completed"
        }
        
        # Save to database (implementation depends on DB choice)
        provider_id = self._save_to_db(profile)
        
        return provider_id
    
    def update_workflow_status(
        self,
        state: Dict,
        new_status: str,
        reason: Optional[str] = None
    ) -> Dict:
        """
        Update the workflow status in state.
        
        Args:
            state: Current state
            new_status: New status value
            reason: Optional reason for status change
            
        Returns:
            Updated state
        """
        state["status"] = new_status
        state["status_history"] = state.get("status_history", [])
        state["status_history"].append({
            "status": new_status,
            "timestamp": datetime.utcnow().isoformat(),
            "reason": reason
        })
        
        return state
    
    def _save_to_db(self, data: Dict) -> str:
        """Internal method to save to database."""
        # PostgreSQL implementation would go here
        # For now, return a mock ID
        return f"provider_{datetime.utcnow().timestamp()}"
```

## Conclusion and Summary Tools

```python
class SummarizationTools:
    """
    Tools for generating summaries and conclusions.
    """
    
    def __init__(self, llm):
        self.llm = llm
    
    def generate_provider_summary(
        self,
        provider_data: Dict,
        checklist: List[Dict],
        research_notes: List[Dict]
    ) -> str:
        """
        Generate a comprehensive provider summary.
        
        Args:
            provider_data: Provider information
            checklist: Completed checklist
            research_notes: Research findings
            
        Returns:
            Formatted summary
        """
        prompt = f"""
        Generate a professional summary for this service provider:
        
        Provider Info: {json.dumps(provider_data, indent=2)}
        
        Completed Requirements:
        {self._format_checklist(checklist)}
        
        Key Research Findings:
        {self._format_research(research_notes)}
        
        Create a concise summary including:
        1. Provider overview
        2. Services offered
        3. Key qualifications
        4. Client requirements
        5. Notable findings
        """
        
        response = self.llm.invoke(prompt)
        return response.content
    
    def generate_quotation_template(
        self,
        provider_type: str,
        checklist: List[Dict]
    ) -> Dict[str, Any]:
        """
        Generate a quotation template based on provider type and requirements.
        
        Args:
            provider_type: Type of service provider
            checklist: Completed checklist with requirements
            
        Returns:
            Quotation template structure
        """
        required_fields = [
            item for item in checklist
            if item["required"] and item["status"] == "VERIFIED"
        ]
        
        template = {
            "provider_type": provider_type,
            "required_client_info": [
                {
                    "field": item["key"],
                    "description": item["prompt"],
                    "value_type": item.get("value_type", "text")
                }
                for item in required_fields
            ],
            "quotation_sections": self._get_standard_sections(provider_type)
        }
        
        return template
    
    def _format_checklist(self, checklist: List[Dict]) -> str:
        """Format checklist for summary."""
        completed = [item for item in checklist if item["status"] == "VERIFIED"]
        return "\n".join([f"- {item['prompt']}: {item.get('value', 'N/A')}" for item in completed])
    
    def _format_research(self, research_notes: List[Dict]) -> str:
        """Format research notes for summary."""
        # Extract key findings
        return "\n".join([note.get("summary", "") for note in research_notes[:5]])
    
    def _get_standard_sections(self, provider_type: str) -> List[str]:
        """Get standard quotation sections by provider type."""
        sections_map = {
            "tax": ["Tax Planning", "Filing Services", "Compliance", "Advisory"],
            "migration": ["Visa Processing", "Documentation", "Legal Support", "Relocation Services"],
            "business_setup": ["Company Formation", "Licensing", "Bank Account", "Office Setup"]
        }
        return sections_map.get(provider_type, ["Services", "Timeline", "Costs"])
```

## Tool Integration

```python
def create_all_tools(config: Dict) -> List[Tool]:
    """
    Create and configure all tools for the agent.
    
    Args:
        config: Configuration dictionary with API keys and settings
        
    Returns:
        List of configured Tool objects
    """
    # Initialize tool classes
    search_tools = SearchTools(config["serper_api_key"])
    rag_tools = RAGTools(config.get("chroma_path", "./chroma_db"))
    data_tools = DataUpdateTools(config.get("db_connection"))
    summary_tools = SummarizationTools(config["llm"])
    
    # Create tool list
    tools = []
    
    # Add search tools
    tools.extend(create_search_tools())
    
    # Add RAG tools
    tools.append(Tool(
        name="index_documents",
        func=rag_tools.process_and_index_documents,
        description="Process and index documents for retrieval"
    ))
    
    tools.append(Tool(
        name="retrieve_context",
        func=rag_tools.retrieve_relevant_chunks,
        description="Retrieve relevant context from indexed documents"
    ))
    
    # Add data update tools
    tools.append(Tool(
        name="update_checklist",
        func=data_tools.batch_update_checklist,
        description="Update checklist items with new information"
    ))
    
    tools.append(Tool(
        name="save_profile",
        func=data_tools.save_provider_profile,
        description="Save completed provider profile to database"
    ))
    
    # Add summary tools
    tools.append(Tool(
        name="generate_summary",
        func=summary_tools.generate_provider_summary,
        description="Generate comprehensive provider summary"
    ))
    
    return tools
```