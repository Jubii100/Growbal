# Growbal

AI-powered platform for service provider discovery, onboarding, and business intelligence. Growbal combines intelligent web crawling, an orchestrated multi-agent reasoning system, and a robust Django backend to help users find, evaluate, and engage with service providers.

## Monorepo Overview

This repository contains multiple coordinated projects. Each subproject has a detailed README with setup and usage instructions.

### Projects

1) Crawler (classic) — `./crawler/`
- AI-assisted web crawling and structured data extraction
- HTML scraping, relevance checking, navigation discovery, and data ingestion

2) Crawler v2 — `./crawler_v2/`
- Notebook-driven pipeline with improved slicing, relevance assessment, and Django integration
- Uses Claude for HTML slicing and structured extraction

3) Chat Application — `./chat/`
- FastAPI-based chat UI with secure authentication, server-side sessions, and streaming responses
- Integrates with Growbal Intelligence for orchestrated tool use and profile discovery

4) Django Backend — `./growbal_django/`
- Core data models: `CustomUser`, `ServiceProviderProfile`, `Service`, `Scrape`, chat sessions
- Vector search (pgvector), tag-based filtering (taggit), REST API endpoints

5) Growbal Intelligence — `./growbal_intelligence/`
- Multi-agent system (search, adjudicator, summarizer) with LangGraph orchestration
- Django integration layer for profile search, hybrid strategies, and streaming updates

6) Onboarding System — `./onboarding/`
- Adaptive, research-driven onboarding flow with state manager and research engine
- Dynamic checklist generation, web research integration, and final validation/summary

7) Auth Implementation Docs — `./authentication_implementation_docs/`
- Step-by-step guide for MySQL-based auth, BCrypt verification, JWT SSO, and server-side sessions

## High-Level Architecture

```
Web Crawlers/AI Agents → Django Backend (PostgreSQL, pgvector) → Intelligence (Agents) → Chat UI
                                       ↑                                 ↓
                                Auth (MySQL)                  Onboarding (Research)
```

### Key Capabilities
- Intelligent crawling with AI-assisted slicing and relevance
- Robust backend with vector similarity search and rich admin
- Orchestrated multi-agent reasoning and streaming outputs
- Secure authentication, session management, and JWT SSO
- Adaptive onboarding with automated research and validation

## Quick Start

Prerequisites
- Python 3.11+
- PostgreSQL 11+ with `pgvector` extension
- (Optional) MySQL 5.7+ for authentication

### 1) Backend Setup
See `growbal_django/README.md` for full details.

```
cd growbal_django
pip install -r ../requirements.txt
createdb growbal_db
psql growbal_db -c "CREATE EXTENSION IF NOT EXISTS vector;"
python manage.py migrate
python manage.py runserver
```

### 2) Chat Application
See `chat/README.md` for full details.

```
cd chat
pip install -r ../requirements.txt
cp ../envs/1.env.example ../envs/1.env
python main.py
```

### 3) Crawler
See `crawler/README.md` or `crawler_v2/README.md` for pipeline details and execution steps.

## Security & Sessions
- Authentication via external MySQL with BCrypt-hashed passwords (see `authentication_implementation_docs/`)
- Server-side sessions with secure cookies and periodic cleanup
- JWT SSO support for partner integrations

## Repository Structure

```
authentication_implementation_docs/  # Auth + session implementation guide
chat/                                # FastAPI chat application
crawler/                             # Classic crawler pipeline
crawler_v2/                          # Enhanced crawler pipeline
growbal_django/                      # Django backend (models, API, admin)
growbal_intelligence/                # Multi-agent intelligence system
onboarding/                          # Adaptive onboarding workflow
```

Refer to each subproject’s README for complete configuration and usage.

## License

This project is proprietary and confidential to the Growbal Platform.