# Implementation Guide for Evolved Onboarding System

## Overview

This guide provides step-by-step instructions for implementing the evolved onboarding agent system, including system requirements, setup procedures, configuration options, and deployment strategies.

## System Requirements

### Infrastructure Requirements

#### Core Services
- **Database**: PostgreSQL 14+ with JSONB support
- **Cache**: Redis 6+ for session management and queuing
- **Vector Database**: ChromaDB or Pinecone for RAG system
- **Search**: Elasticsearch (optional) for advanced search capabilities

#### Compute Requirements
- **Minimum**: 4 CPU cores, 16GB RAM, 100GB storage
- **Recommended**: 8 CPU cores, 32GB RAM, 500GB SSD storage
- **Production**: 16+ CPU cores, 64GB RAM, 1TB+ NVMe storage

#### External APIs
- **LLM Provider**: OpenAI GPT-4 or Anthropic Claude
- **Search APIs**: SerpAPI, Google Custom Search, or similar
- **Notification Services**: Email, Slack, Teams integrations

## Installation and Setup

### 1. Environment Setup

```bash
# Create project directory
mkdir growbal-onboarding
cd growbal-onboarding

# Create Python virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Dependencies Installation

```txt
# requirements.txt
langgraph>=0.0.40
langchain>=0.1.0
langchain-openai>=0.1.0
langchain-community>=0.0.20
asyncpg>=0.29.0
redis>=5.0.0
chromadb>=0.4.0
pydantic>=2.0.0
fastapi>=0.100.0
uvicorn>=0.20.0
python-multipart>=0.0.6
aiofiles>=23.0.0
aioredis>=2.0.0
psycopg2-binary>=2.9.0
sqlalchemy>=2.0.0
alembic>=1.12.0
pytest>=7.0.0
pytest-asyncio>=0.20.0
```

### 3. Database Setup

```sql
-- database_schema.sql
CREATE DATABASE growbal_onboarding;

\c growbal_onboarding;

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    profile_data JSONB DEFAULT '{}',
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Onboarding sessions
CREATE TABLE onboarding_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    session_id VARCHAR(255) UNIQUE NOT NULL,
    state_data JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    service_type VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL
);

-- State checkpoints
CREATE TABLE state_checkpoints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    checkpoint_id VARCHAR(255) UNIQUE NOT NULL,
    checkpoint_data JSONB NOT NULL,
    checkpoint_type VARCHAR(50) DEFAULT 'auto',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Provider profiles
CREATE TABLE provider_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    provider_data JSONB NOT NULL,
    checklist_data JSONB NOT NULL,
    research_notes JSONB DEFAULT '[]',
    completion_metrics JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finalized_at TIMESTAMP NULL
);

-- Human interventions
CREATE TABLE human_interventions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(255) NOT NULL,
    intervention_type VARCHAR(50) NOT NULL,
    reason VARCHAR(100) NOT NULL,
    context_data JSONB NOT NULL,
    agent_id VARCHAR(255) NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL
);

-- Create indexes
CREATE INDEX idx_sessions_user_id ON onboarding_sessions(user_id);
CREATE INDEX idx_sessions_status ON onboarding_sessions(status);
CREATE INDEX idx_checkpoints_session ON state_checkpoints(session_id);
CREATE INDEX idx_profiles_status ON provider_profiles(status);
CREATE INDEX idx_interventions_status ON human_interventions(status);
```

### 4. Configuration Setup

```python
# config/settings.py
from pydantic_settings import BaseSettings
from typing import Dict, Any, Optional

class Settings(BaseSettings):
    """Application configuration"""
    
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "growbal_onboarding"
    postgres_user: str = "postgres"
    postgres_password: str = ""
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # ChromaDB
    chroma_path: str = "./data/chroma_db"
    
    # APIs
    openai_api_key: str = ""
    serper_api_key: str = ""
    
    # Service configuration
    session_timeout_minutes: int = 30
    max_research_queries: int = 10
    confidence_threshold: float = 0.75
    
    # Human-in-the-loop
    escalation_enabled: bool = True
    review_threshold: float = 0.8
    notification_webhook: Optional[str] = None
    
    # Feature flags
    enable_research: bool = True
    enable_auto_fill: bool = True
    enable_validation: bool = True
    enable_caching: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = False

# Load settings
settings = Settings()
```

### 5. Core System Implementation

```python
# main.py - Main application entry point
import asyncio
import asyncpg
import aioredis
from fastapi import FastAPI, HTTPException, BackgroundTasks
from contextlib import asynccontextmanager
from typing import Dict, Any

# Import our evolved components
from src.core.evolved_agent import AdaptiveOnboardingAgent
from src.core.state_manager import EvolvedStateManager
from src.core.checklist_system import DynamicChecklistSystem
from src.tools.research_orchestrator import IntelligentResearchOrchestrator
from src.tools.rag_system import EnhancedRAGSystem
from src.hitl.escalation_detector import IntelligentEscalationDetector
from src.hitl.handoff_manager import SeamlessHandoffManager

class OnboardingSystemManager:
    def __init__(self):
        self.pg_pool = None
        self.redis_pool = None
        self.agent = None
        self.state_manager = None
        self.initialized = False
    
    async def initialize(self):
        """Initialize all system components"""
        
        # Initialize database pools
        self.pg_pool = await asyncpg.create_pool(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
            min_size=5,
            max_size=20
        )
        
        self.redis_pool = aioredis.ConnectionPool.from_url(
            settings.redis_url,
            max_connections=20
        )
        
        # Initialize core components
        await self._initialize_core_components()
        
        self.initialized = True
        print("Onboarding system initialized successfully")
    
    async def _initialize_core_components(self):
        """Initialize core system components"""
        
        # Initialize enhanced RAG system
        rag_system = EnhancedRAGSystem(chroma_path=settings.chroma_path)
        
        # Initialize research orchestrator
        research_orchestrator = IntelligentResearchOrchestrator(
            search_tools=self._create_search_tools(),
            llm=self._create_llm(),
            user_profile_db=self.pg_pool
        )
        
        # Initialize state manager
        self.state_manager = EvolvedStateManager(
            db_connection=self.pg_pool,
            redis_client=self.redis_pool
        )
        
        # Initialize checklist system
        checklist_system = DynamicChecklistSystem(
            llm=self._create_llm(),
            template_service=self._create_template_service(),
            validation_service=self._create_validation_service()
        )
        
        # Initialize human-in-the-loop components
        escalation_detector = IntelligentEscalationDetector(
            llm=self._create_llm(),
            sentiment_analyzer=self._create_sentiment_analyzer(),
            config=settings.dict()
        )
        
        handoff_manager = SeamlessHandoffManager(
            agent_pool=self._create_agent_pool(),
            notification_service=self._create_notification_service()
        )
        
        # Initialize main agent
        self.agent = AdaptiveOnboardingAgent(
            llm=self._create_llm(),
            tools={
                "research": research_orchestrator,
                "rag": rag_system,
                "checklist": checklist_system,
                "state": self.state_manager,
                "escalation": escalation_detector,
                "handoff": handoff_manager
            },
            db_connection=self.pg_pool,
            rag_system=rag_system
        )
    
    def _create_llm(self):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model="gpt-4",
            api_key=settings.openai_api_key,
            temperature=0.1
        )
    
    # ... additional helper methods
    
    async def shutdown(self):
        """Cleanup resources"""
        if self.pg_pool:
            await self.pg_pool.close()
        if self.redis_pool:
            await self.redis_pool.disconnect()

# Global system manager
system_manager = OnboardingSystemManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await system_manager.initialize()
    yield
    # Shutdown
    await system_manager.shutdown()

# Create FastAPI app
app = FastAPI(
    title="Evolved Onboarding System",
    description="Intelligent provider onboarding with adaptive workflows",
    version="2.0.0",
    lifespan=lifespan
)

# API Endpoints
@app.post("/onboarding/start")
async def start_onboarding(request: Dict[str, Any]):
    """Start new onboarding session"""
    if not system_manager.initialized:
        raise HTTPException(status_code=503, detail="System not initialized")
    
    try:
        # Initialize state
        state = await system_manager.state_manager.initialize_state(
            user_id=request["user_id"],
            service_type=request["service_type"],
            provider_info=request.get("provider_info")
        )
        
        # Run first step
        result = await system_manager.agent.run_initial_step(state)
        
        return {
            "session_id": state["session_id"],
            "message": result["message"],
            "next_action": result.get("next_action"),
            "status": "started"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/onboarding/respond")
async def respond_to_question(request: Dict[str, Any]):
    """Process user response"""
    session_id = request["session_id"]
    user_response = request["response"]
    
    try:
        # Get current state
        state = await system_manager.state_manager.get_state(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")
        
        # Process response
        result = await system_manager.agent.process_response(
            state=state,
            user_response=user_response
        )
        
        return {
            "message": result.get("message"),
            "next_action": result.get("next_action"),
            "completion_percentage": result.get("completion_percentage", 0),
            "status": result.get("status")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/onboarding/status/{session_id}")
async def get_session_status(session_id: str):
    """Get current session status"""
    try:
        state = await system_manager.state_manager.get_state(session_id)
        if not state:
            raise HTTPException(status_code=404, detail="Session not found")
        
        progress = system_manager.agent.calculate_progress(state["checklist"])
        
        return {
            "session_id": session_id,
            "status": state["workflow_status"],
            "progress": progress,
            "duration_minutes": state.get("total_duration_seconds", 0) / 60,
            "messages_count": state.get("message_count", 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
```

## Deployment Architecture

### 1. Development Environment

```yaml
# docker-compose.dev.yml
version: '3.8'

services:
  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: growbal_onboarding
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database_schema.sql:/docker-entrypoint-initdb.d/init.sql

  redis:
    image: redis:7
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  app:
    build:
      context: .
      dockerfile: Dockerfile.dev
    ports:
      - "8000:8000"
    environment:
      - POSTGRES_HOST=postgres
      - REDIS_URL=redis://redis:6379/0
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SERPER_API_KEY=${SERPER_API_KEY}
    volumes:
      - .:/app
      - chroma_data:/app/data/chroma_db
    depends_on:
      - postgres
      - redis

volumes:
  postgres_data:
  redis_data:
  chroma_data:
```

### 2. Production Deployment

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: onboarding-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: onboarding-api
  template:
    metadata:
      labels:
        app: onboarding-api
    spec:
      containers:
      - name: api
        image: growbal/onboarding-system:latest
        ports:
        - containerPort: 8000
        env:
        - name: POSTGRES_HOST
          valueFrom:
            secretKeyRef:
              name: db-secret
              key: host
        - name: REDIS_URL
          valueFrom:
            configMapKeyRef:
              name: app-config
              key: redis-url
        resources:
          requests:
            cpu: 500m
            memory: 1Gi
          limits:
            cpu: 2000m
            memory: 4Gi
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /ready
            port: 8000
          initialDelaySeconds: 5
          periodSeconds: 5

---
apiVersion: v1
kind: Service
metadata:
  name: onboarding-service
spec:
  selector:
    app: onboarding-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Configuration Management

### 1. Environment Configuration

```bash
# .env.production
# Database
POSTGRES_HOST=prod-db.company.com
POSTGRES_PORT=5432
POSTGRES_DB=growbal_onboarding_prod
POSTGRES_USER=onboarding_user
POSTGRES_PASSWORD=secure_password_here

# Redis
REDIS_URL=redis://prod-cache.company.com:6379/0

# APIs
OPENAI_API_KEY=sk-xxx
SERPER_API_KEY=xxx

# Performance
SESSION_TIMEOUT_MINUTES=45
MAX_RESEARCH_QUERIES=15
CONFIDENCE_THRESHOLD=0.8

# Features
ENABLE_RESEARCH=true
ENABLE_AUTO_FILL=true
ENABLE_VALIDATION=true
ENABLE_CACHING=true

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
TRACING_ENABLED=true
```

### 2. Feature Flags Configuration

```python
# config/feature_flags.py
from typing import Dict, Any

class FeatureFlags:
    """Dynamic feature flag management"""
    
    def __init__(self, redis_client):
        self.redis = redis_client
        self.default_flags = {
            "enable_research": True,
            "enable_auto_fill": True,
            "enable_human_handoff": True,
            "enable_advanced_validation": True,
            "enable_sentiment_analysis": True,
            "enable_quality_control": True,
            "enable_research_caching": True,
            "enable_parallel_processing": True,
            "beta_features_enabled": False,
            "debug_mode": False
        }
    
    async def get_flag(self, flag_name: str, session_id: str = None) -> bool:
        """Get feature flag value with optional per-session override"""
        
        # Check session-specific override
        if session_id:
            session_flag = await self.redis.get(f"flag:{session_id}:{flag_name}")
            if session_flag is not None:
                return session_flag.decode() == "true"
        
        # Check global override
        global_flag = await self.redis.get(f"flag:global:{flag_name}")
        if global_flag is not None:
            return global_flag.decode() == "true"
        
        # Return default
        return self.default_flags.get(flag_name, False)
    
    async def set_flag(
        self, 
        flag_name: str, 
        value: bool, 
        session_id: str = None,
        ttl: int = None
    ):
        """Set feature flag value"""
        key = f"flag:{session_id or 'global'}:{flag_name}"
        
        if ttl:
            await self.redis.setex(key, ttl, str(value).lower())
        else:
            await self.redis.set(key, str(value).lower())
```

## Monitoring and Observability

### 1. Health Checks

```python
# monitoring/health.py
from fastapi import APIRouter, HTTPException
import asyncio

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check"""
    return {"status": "healthy", "timestamp": datetime.utcnow()}

@router.get("/ready")
async def readiness_check():
    """Readiness check with dependency verification"""
    checks = {
        "database": False,
        "redis": False,
        "llm_api": False,
        "search_api": False
    }
    
    try:
        # Check database
        async with system_manager.pg_pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
            checks["database"] = True
    except Exception:
        pass
    
    try:
        # Check Redis
        async with system_manager.redis_pool as redis:
            await redis.ping()
            checks["redis"] = True
    except Exception:
        pass
    
    # Check APIs (simplified)
    checks["llm_api"] = True  # Would test actual API
    checks["search_api"] = True  # Would test actual API
    
    all_healthy = all(checks.values())
    
    if not all_healthy:
        raise HTTPException(status_code=503, detail=checks)
    
    return {"status": "ready", "checks": checks}
```

### 2. Metrics Collection

```python
# monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time

# Define metrics
session_counter = Counter('onboarding_sessions_total', 'Total sessions created')
session_duration = Histogram('onboarding_session_duration_seconds', 'Session duration')
completion_rate = Gauge('onboarding_completion_rate', 'Session completion rate')
escalation_counter = Counter('onboarding_escalations_total', 'Total escalations', ['reason'])

class MetricsCollector:
    def __init__(self):
        self.active_sessions = {}
    
    def track_session_start(self, session_id: str):
        session_counter.inc()
        self.active_sessions[session_id] = time.time()
    
    def track_session_complete(self, session_id: str, completed: bool):
        if session_id in self.active_sessions:
            duration = time.time() - self.active_sessions[session_id]
            session_duration.observe(duration)
            del self.active_sessions[session_id]
    
    def track_escalation(self, reason: str):
        escalation_counter.labels(reason=reason).inc()

# Global metrics instance
metrics = MetricsCollector()
```

## Testing Strategy

### 1. Unit Tests

```python
# tests/test_checklist_system.py
import pytest
from src.core.checklist_system import DynamicChecklistSystem
from src.core.state_manager import EvolvedStateManager

@pytest.mark.asyncio
async def test_checklist_initialization():
    """Test checklist initialization"""
    system = DynamicChecklistSystem(
        llm=mock_llm,
        template_service=mock_template_service,
        validation_service=mock_validation_service
    )
    
    checklist = await system.initialize_checklist(
        service_type="tax",
        user_profile={"tier": "standard"},
        provider_info={"name": "Test Provider"}
    )
    
    assert len(checklist) > 0
    assert all(item.key for item in checklist)
    assert any(item.required for item in checklist)

@pytest.mark.asyncio
async def test_response_processing():
    """Test user response processing"""
    system = DynamicChecklistSystem(
        llm=mock_llm,
        template_service=mock_template_service,
        validation_service=mock_validation_service
    )
    
    checklist = create_test_checklist()
    
    update_summary = system.update_from_response(
        checklist=checklist,
        response="Test Company LLC",
        question_key="company_name",
        user_profile={}
    )
    
    assert update_summary["validation_status"] == "success"
    assert "company_name" in update_summary["items_updated"]
```

### 2. Integration Tests

```python
# tests/test_workflow_integration.py
@pytest.mark.asyncio
async def test_complete_workflow():
    """Test complete onboarding workflow"""
    
    # Initialize system
    system = await create_test_system()
    
    # Start session
    state = await system.state_manager.initialize_state(
        user_id="test-user",
        service_type="tax",
        provider_info={"name": "Test Provider"}
    )
    
    # Simulate conversation
    responses = [
        "Test Company LLC",
        "test@company.com",
        "+1-555-0123",
        "123 Main St, City, State",
        "5 years"
    ]
    
    for response in responses:
        result = await system.agent.process_response(
            state=state,
            user_response=response
        )
        
        assert result["status"] in ["continuing", "completed"]
        
        if result["status"] == "completed":
            break
    
    # Verify completion
    progress = system.agent.calculate_progress(state["checklist"])
    assert progress["required_completion_percentage"] == 100
```

## Performance Optimization

### 1. Database Optimization

```sql
-- database_indexes.sql
-- Add performance indexes
CREATE INDEX CONCURRENTLY idx_sessions_created_at ON onboarding_sessions(created_at DESC);
CREATE INDEX CONCURRENTLY idx_checkpoints_created_at ON state_checkpoints(created_at DESC);
CREATE INDEX CONCURRENTLY idx_profiles_service_type ON provider_profiles(service_type);

-- Partitioning for large tables
CREATE TABLE onboarding_sessions_2024 PARTITION OF onboarding_sessions
FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
```

### 2. Caching Strategy

```python
# optimization/caching.py
import json
from functools import wraps

class CacheManager:
    def __init__(self, redis_client):
        self.redis = redis_client
    
    def cache_result(self, key_prefix: str, ttl: int = 3600):
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                # Generate cache key
                cache_key = f"{key_prefix}:{hash(str(args) + str(kwargs))}"
                
                # Try to get from cache
                cached = await self.redis.get(cache_key)
                if cached:
                    return json.loads(cached)
                
                # Execute function
                result = await func(*args, **kwargs)
                
                # Store in cache
                await self.redis.setex(
                    cache_key, 
                    ttl, 
                    json.dumps(result, default=str)
                )
                
                return result
            return wrapper
        return decorator

# Usage
cache = CacheManager(redis_client)

@cache.cache_result("research_results", ttl=1800)
async def cached_research_query(query: str, source: str):
    # Expensive research operation
    return await search_api.query(query, source)
```

This implementation guide provides a complete foundation for deploying the evolved onboarding system. The modular architecture ensures scalability, maintainability, and the ability to adapt to changing requirements.