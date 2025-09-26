# Database Integration Documentation

## Overview
This module handles PostgreSQL for persistent storage and Chroma for vector similarity search. The integration provides both structured data storage and semantic search capabilities.

## PostgreSQL Integration

### 1. Database Schema

```sql
-- Providers table
CREATE TABLE providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    service_type VARCHAR(50) NOT NULL CHECK (service_type IN ('tax', 'migration', 'business_setup')),
    contact_info JSONB,
    description TEXT,
    rating DECIMAL(3,2),
    location VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(50) DEFAULT 'pending'
);

-- Onboarding sessions table
CREATE TABLE onboarding_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES providers(id),
    checklist JSONB NOT NULL,
    research_notes JSONB,
    conversation_history JSONB,
    workflow_status VARCHAR(50),
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    agent_version VARCHAR(20)
);

-- Checklist templates table
CREATE TABLE checklist_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    service_type VARCHAR(50) NOT NULL,
    version VARCHAR(20) NOT NULL,
    checklist_items JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Vector store metadata table (tracks Chroma collections)
CREATE TABLE vector_collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id UUID REFERENCES providers(id),
    collection_name VARCHAR(255) UNIQUE NOT NULL,
    document_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 2. Database Connection Manager

```python
import psycopg2
from psycopg2.extras import RealDictCursor, Json
from contextlib import contextmanager
from typing import Dict, Any, List, Optional
import os
from datetime import datetime

class PostgresManager:
    """
    Manages PostgreSQL database connections and operations.
    """
    
    def __init__(self, connection_string: Optional[str] = None):
        self.connection_string = connection_string or os.getenv("DATABASE_URL")
        if not self.connection_string:
            raise ValueError("Database connection string not provided")
    
    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.
        """
        conn = psycopg2.connect(self.connection_string)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def save_provider(self, provider_data: Dict[str, Any]) -> str:
        """
        Save or update provider information.
        
        Args:
            provider_data: Provider information dictionary
            
        Returns:
            Provider ID
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO providers (
                        name, service_type, contact_info, 
                        description, rating, location, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (name, service_type) 
                    DO UPDATE SET
                        contact_info = EXCLUDED.contact_info,
                        description = EXCLUDED.description,
                        rating = EXCLUDED.rating,
                        updated_at = CURRENT_TIMESTAMP
                    RETURNING id
                """, (
                    provider_data['name'],
                    provider_data['service_type'],
                    Json(provider_data.get('contact_info', {})),
                    provider_data.get('description'),
                    provider_data.get('rating'),
                    provider_data.get('location'),
                    provider_data.get('status', 'pending')
                ))
                
                provider_id = cur.fetchone()[0]
                return str(provider_id)
    
    def save_onboarding_session(
        self,
        provider_id: str,
        checklist: List[Dict],
        research_notes: List[Dict],
        conversation_history: List[Dict],
        workflow_status: str
    ) -> str:
        """
        Save onboarding session data.
        
        Args:
            provider_id: Provider UUID
            checklist: Completed checklist
            research_notes: Research findings
            conversation_history: Conversation messages
            workflow_status: Final workflow status
            
        Returns:
            Session ID
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO onboarding_sessions (
                        provider_id, checklist, research_notes,
                        conversation_history, workflow_status, completed_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    provider_id,
                    Json(checklist),
                    Json(research_notes),
                    Json(conversation_history),
                    workflow_status,
                    datetime.utcnow() if workflow_status in ['completed', 'saved'] else None
                ))
                
                session_id = cur.fetchone()[0]
                return str(session_id)
    
    def get_provider(self, provider_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve provider information.
        
        Args:
            provider_id: Provider UUID
            
        Returns:
            Provider data dictionary or None
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM providers WHERE id = %s
                """, (provider_id,))
                
                result = cur.fetchone()
                return dict(result) if result else None
    
    def get_checklist_template(self, service_type: str) -> List[Dict]:
        """
        Get the active checklist template for a service type.
        
        Args:
            service_type: Type of service (tax, migration, business_setup)
            
        Returns:
            Checklist items
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT checklist_items FROM checklist_templates
                    WHERE service_type = %s AND is_active = true
                    ORDER BY version DESC
                    LIMIT 1
                """, (service_type,))
                
                result = cur.fetchone()
                return result['checklist_items'] if result else []
    
    def update_provider_status(self, provider_id: str, status: str) -> bool:
        """
        Update provider status.
        
        Args:
            provider_id: Provider UUID
            status: New status
            
        Returns:
            Success boolean
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE providers 
                    SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (status, provider_id))
                
                return cur.rowcount > 0
    
    def search_providers(
        self,
        service_type: Optional[str] = None,
        location: Optional[str] = None,
        min_rating: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for providers with filters.
        
        Args:
            service_type: Filter by service type
            location: Filter by location
            min_rating: Minimum rating filter
            
        Returns:
            List of matching providers
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT * FROM providers WHERE 1=1"
                params = []
                
                if service_type:
                    query += " AND service_type = %s"
                    params.append(service_type)
                
                if location:
                    query += " AND location ILIKE %s"
                    params.append(f"%{location}%")
                
                if min_rating:
                    query += " AND rating >= %s"
                    params.append(min_rating)
                
                query += " ORDER BY rating DESC, created_at DESC"
                
                cur.execute(query, params)
                results = cur.fetchall()
                
                return [dict(row) for row in results]
```

## Chroma Vector Database Integration

### 1. Chroma Manager

```python
import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from typing import List, Dict, Any, Optional
import hashlib
from datetime import datetime

class ChromaManager:
    """
    Manages Chroma vector database for semantic search.
    """
    
    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        embedding_model: str = "text-embedding-ada-002"
    ):
        self.persist_directory = persist_directory
        
        # Initialize Chroma client
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Set up embedding function
        self.embedding_function = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            model_name=embedding_model
        )
    
    def create_provider_collection(self, provider_id: str) -> chromadb.Collection:
        """
        Create a collection for a specific provider.
        
        Args:
            provider_id: Provider UUID
            
        Returns:
            Chroma collection object
        """
        collection_name = f"provider_{provider_id}"
        
        # Delete if exists (for updates)
        try:
            self.client.delete_collection(collection_name)
        except:
            pass
        
        # Create new collection
        collection = self.client.create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"provider_id": provider_id, "created_at": datetime.utcnow().isoformat()}
        )
        
        return collection
    
    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None
    ) -> int:
        """
        Add documents to a collection.
        
        Args:
            collection_name: Name of the collection
            documents: List of document texts
            metadatas: Optional metadata for each document
            ids: Optional IDs for documents
            
        Returns:
            Number of documents added
        """
        collection = self.client.get_collection(
            name=collection_name,
            embedding_function=self.embedding_function
        )
        
        # Generate IDs if not provided
        if ids is None:
            ids = [self._generate_id(doc) for doc in documents]
        
        # Ensure metadatas list matches documents
        if metadatas is None:
            metadatas = [{}] * len(documents)
        
        # Add timestamp to metadata
        for metadata in metadatas:
            metadata["indexed_at"] = datetime.utcnow().isoformat()
        
        # Add documents to collection
        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        return len(documents)
    
    def search(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict] = None,
        where_document: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Search for similar documents in a collection.
        
        Args:
            collection_name: Name of the collection
            query_text: Query string
            n_results: Number of results to return
            where: Metadata filter
            where_document: Document content filter
            
        Returns:
            Search results with documents, metadatas, and distances
        """
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            results = collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where,
                where_document=where_document
            )
            
            # Format results
            formatted_results = {
                "documents": results["documents"][0] if results["documents"] else [],
                "metadatas": results["metadatas"][0] if results["metadatas"] else [],
                "distances": results["distances"][0] if results["distances"] else [],
                "ids": results["ids"][0] if results["ids"] else []
            }
            
            return formatted_results
            
        except Exception as e:
            return {"error": str(e), "documents": [], "metadatas": [], "distances": []}
    
    def update_documents(
        self,
        collection_name: str,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict]] = None
    ) -> bool:
        """
        Update existing documents in a collection.
        
        Args:
            collection_name: Name of the collection
            ids: IDs of documents to update
            documents: New document texts
            metadatas: New metadata
            
        Returns:
            Success boolean
        """
        try:
            collection = self.client.get_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            
            collection.update(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            return True
            
        except Exception as e:
            print(f"Update failed: {e}")
            return False
    
    def delete_collection(self, collection_name: str) -> bool:
        """
        Delete a collection.
        
        Args:
            collection_name: Name of the collection to delete
            
        Returns:
            Success boolean
        """
        try:
            self.client.delete_collection(collection_name)
            return True
        except Exception:
            return False
    
    def list_collections(self) -> List[str]:
        """
        List all collections.
        
        Returns:
            List of collection names
        """
        collections = self.client.list_collections()
        return [col.name for col in collections]
    
    def get_collection_info(self, collection_name: str) -> Dict[str, Any]:
        """
        Get information about a collection.
        
        Args:
            collection_name: Name of the collection
            
        Returns:
            Collection information
        """
        try:
            collection = self.client.get_collection(collection_name)
            
            return {
                "name": collection.name,
                "count": collection.count(),
                "metadata": collection.metadata
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _generate_id(self, document: str) -> str:
        """
        Generate a unique ID for a document.
        
        Args:
            document: Document text
            
        Returns:
            Unique ID string
        """
        return hashlib.md5(document.encode()).hexdigest()
```

## Integrated Database Service

### 1. Unified Database Service

```python
from typing import Dict, Any, List, Optional
import asyncio

class DatabaseService:
    """
    Unified service for both PostgreSQL and Chroma operations.
    """
    
    def __init__(
        self,
        postgres_connection_string: str,
        chroma_persist_directory: str = "./chroma_db"
    ):
        self.postgres = PostgresManager(postgres_connection_string)
        self.chroma = ChromaManager(chroma_persist_directory)
    
    async def initialize_provider(
        self,
        provider_data: Dict[str, Any]
    ) -> Dict[str, str]:
        """
        Initialize a new provider in both databases.
        
        Args:
            provider_data: Provider information
            
        Returns:
            Provider ID and collection name
        """
        # Save to PostgreSQL
        provider_id = self.postgres.save_provider(provider_data)
        
        # Create Chroma collection
        collection = self.chroma.create_provider_collection(provider_id)
        
        # Track in PostgreSQL
        with self.postgres.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO vector_collections (provider_id, collection_name)
                    VALUES (%s, %s)
                """, (provider_id, collection.name))
        
        return {
            "provider_id": provider_id,
            "collection_name": collection.name
        }
    
    async def store_research_results(
        self,
        provider_id: str,
        research_documents: List[Dict[str, Any]]
    ) -> int:
        """
        Store research results in Chroma for RAG.
        
        Args:
            provider_id: Provider UUID
            research_documents: List of research documents with content and metadata
            
        Returns:
            Number of documents stored
        """
        collection_name = f"provider_{provider_id}"
        
        # Extract documents and metadata
        documents = [doc["content"] for doc in research_documents]
        metadatas = [
            {
                "source": doc.get("source", "unknown"),
                "query": doc.get("query", ""),
                "timestamp": doc.get("timestamp", datetime.utcnow().isoformat())
            }
            for doc in research_documents
        ]
        
        # Add to Chroma
        count = self.chroma.add_documents(
            collection_name,
            documents,
            metadatas
        )
        
        # Update count in PostgreSQL
        with self.postgres.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE vector_collections
                    SET document_count = document_count + %s,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE provider_id = %s
                """, (count, provider_id))
        
        return count
    
    async def retrieve_context(
        self,
        provider_id: str,
        query: str,
        n_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a query.
        
        Args:
            provider_id: Provider UUID
            query: Search query
            n_results: Number of results
            
        Returns:
            List of relevant documents with metadata
        """
        collection_name = f"provider_{provider_id}"
        
        results = self.chroma.search(
            collection_name,
            query,
            n_results
        )
        
        # Format results
        formatted_results = []
        for i, doc in enumerate(results.get("documents", [])):
            formatted_results.append({
                "content": doc,
                "metadata": results["metadatas"][i] if i < len(results.get("metadatas", [])) else {},
                "relevance_score": 1 - results["distances"][i] if i < len(results.get("distances", [])) else 0
            })
        
        return formatted_results
    
    async def complete_onboarding(
        self,
        provider_id: str,
        checklist: List[Dict],
        research_notes: List[Dict],
        conversation_history: List[Dict],
        workflow_status: str
    ) -> Dict[str, str]:
        """
        Complete the onboarding process and save all data.
        
        Args:
            provider_id: Provider UUID
            checklist: Completed checklist
            research_notes: Research findings
            conversation_history: Conversation messages
            workflow_status: Final status
            
        Returns:
            Session ID and status
        """
        # Save session to PostgreSQL
        session_id = self.postgres.save_onboarding_session(
            provider_id,
            checklist,
            research_notes,
            conversation_history,
            workflow_status
        )
        
        # Update provider status
        self.postgres.update_provider_status(provider_id, "onboarded")
        
        return {
            "session_id": session_id,
            "status": "completed",
            "provider_id": provider_id
        }
    
    async def cleanup_provider_data(self, provider_id: str) -> bool:
        """
        Clean up provider data from both databases.
        
        Args:
            provider_id: Provider UUID
            
        Returns:
            Success boolean
        """
        collection_name = f"provider_{provider_id}"
        
        # Delete from Chroma
        chroma_deleted = self.chroma.delete_collection(collection_name)
        
        # Delete from PostgreSQL
        with self.postgres.get_connection() as conn:
            with conn.cursor() as cur:
                # Delete vector collection record
                cur.execute("""
                    DELETE FROM vector_collections WHERE provider_id = %s
                """, (provider_id,))
                
                # Delete onboarding sessions
                cur.execute("""
                    DELETE FROM onboarding_sessions WHERE provider_id = %s
                """, (provider_id,))
                
                # Delete provider
                cur.execute("""
                    DELETE FROM providers WHERE id = %s
                """, (provider_id,))
        
        return chroma_deleted
```

## Configuration

```python
# config/database_config.py

import os
from typing import Dict, Any

def get_database_config() -> Dict[str, Any]:
    """
    Get database configuration from environment variables.
    
    Returns:
        Configuration dictionary
    """
    return {
        "postgres": {
            "connection_string": os.getenv(
                "DATABASE_URL",
                "postgresql://user:password@localhost:5432/onboarding_db"
            ),
            "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
            "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10"))
        },
        "chroma": {
            "persist_directory": os.getenv("CHROMA_PERSIST_DIR", "./chroma_db"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
            "collection_prefix": "provider_"
        }
    }

# Initialize database service
def initialize_database_service() -> DatabaseService:
    """
    Initialize the database service with configuration.
    
    Returns:
        Configured DatabaseService instance
    """
    config = get_database_config()
    
    return DatabaseService(
        postgres_connection_string=config["postgres"]["connection_string"],
        chroma_persist_directory=config["chroma"]["persist_directory"]
    )
```