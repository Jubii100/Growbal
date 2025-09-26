# Implementation Guide for Two-Part Research Onboarding System

## Overview

This implementation guide provides step-by-step instructions for building the evolved onboarding system with the two-part research process: **checklist customization** using industry standards research and **answer gathering** using business-focused web search.

## Quick Start Implementation

### 1. Project Structure

```
growbal-onboarding/
├── src/
│   ├── core/
│   │   ├── evolved_agent.py
│   │   ├── state_manager.py
│   │   └── workflow_engine.py
│   ├── research/
│   │   ├── checklist_customizer.py
│   │   ├── answer_gatherer.py
│   │   ├── content_parser.py
│   │   └── research_orchestrator.py
│   ├── tools/
│   │   ├── wikipedia_search.py
│   │   ├── arxiv_search.py
│   │   ├── web_search.py
│   │   └── readability_parser.py
│   └── api/
│       ├── main.py
│       └── endpoints.py
├── config/
│   ├── settings.py
│   └── checklist_templates.py
├── requirements.txt
└── docker-compose.yml
```

### 2. Dependencies Installation

```txt
# requirements.txt
# Core framework
langgraph>=0.0.40
langchain>=0.1.0
langchain-openai>=0.1.0
fastapi>=0.100.0

# Database and cache
asyncpg>=0.29.0
redis>=5.0.0

# Research tools
wikipedia>=1.4.0
arxiv>=1.4.7
requests>=2.31.0
beautifulsoup4>=4.12.0
readability-lxml>=0.8.1
lxml>=4.9.0

# Content processing
python-readability>=0.3.2
html2text>=2020.1.16
newspaper3k>=0.2.8

# Search APIs
google-search-results>=2.4.2
serpapi>=0.1.5

# Async processing
aiohttp>=3.8.0
aiofiles>=23.0.0

# Utilities
pydantic>=2.0.0
python-multipart>=0.0.6
uvicorn>=0.20.0
```

### 3. Core Configuration

```python
# config/settings.py
from pydantic_settings import BaseSettings
from typing import Dict, Any, Optional

class Settings(BaseSettings):
    """Configuration for two-part research system"""
    
    # Database
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "growbal_onboarding"
    postgres_user: str = "postgres"
    postgres_password: str = ""
    
    # Cache
    redis_url: str = "redis://localhost:6379/0"
    
    # APIs for research
    openai_api_key: str = ""
    serpapi_key: str = ""
    
    # Research configuration
    checklist_research_enabled: bool = True
    answer_research_enabled: bool = True
    max_wikipedia_results: int = 5
    max_arxiv_results: int = 3
    max_web_search_results: int = 5
    
    # Content processing
    readability_min_length: int = 100
    business_relevance_threshold: float = 0.6
    answer_confidence_threshold: float = 0.7
    
    # Performance
    research_timeout_seconds: int = 30
    max_concurrent_searches: int = 10
    
    class Config:
        env_file = ".env"

settings = Settings()
```

## Implementation Steps

### Step 1: Content Processing Foundation

```python
# src/tools/content_parser.py
import re
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from readability import Document

class AcademicContentCleaner:
    """Processes Wikipedia/ArXiv content for business use."""
    
    def __init__(self):
        self.business_keywords = [
            'requirement', 'standard', 'regulation', 'compliance',
            'licensing', 'certification', 'professional', 'business',
            'service', 'provider', 'industry', 'practice'
        ]
    
    def clean_and_extract(self, raw_content: str) -> str:
        """Clean academic content and extract business-relevant sections."""
        # Remove HTML
        soup = BeautifulSoup(raw_content, 'html.parser')
        
        # Remove non-content elements
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'img', 'table']):
            tag.decompose()
        
        text = soup.get_text()
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Extract relevant paragraphs
        paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 50]
        relevant_paragraphs = []
        
        for paragraph in paragraphs:
            score = self._calculate_relevance(paragraph)
            if score > 0.3:
                relevant_paragraphs.append((paragraph, score))
        
        # Sort by relevance and return top paragraphs
        relevant_paragraphs.sort(key=lambda x: x[1], reverse=True)
        return '\n\n'.join([p[0] for p in relevant_paragraphs[:8]])
    
    def _calculate_relevance(self, paragraph: str) -> float:
        """Calculate business relevance of paragraph."""
        paragraph_lower = paragraph.lower()
        matches = sum(1 for keyword in self.business_keywords 
                     if keyword in paragraph_lower)
        return matches / len(self.business_keywords)

class BusinessContentParser:
    """Parses web content for business information."""
    
    def __init__(self):
        self.contact_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'[\+]?[1-9]?[0-9]{7,15}|\(\d{3}\)\s*\d{3}-\d{4}',
            'address': r'\d+\s+[A-Za-z0-9\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd)',
        }
    
    def extract_business_info(self, html_content: str, url: str = "") -> Dict[str, Any]:
        """Extract structured business information."""
        try:
            # Use readability for main content
            doc = Document(html_content)
            main_content = doc.summary()
            
            soup = BeautifulSoup(main_content, 'html.parser')
            clean_text = soup.get_text()
            
            # Extract contact information
            contacts = {}
            for contact_type, pattern in self.contact_patterns.items():
                matches = re.findall(pattern, clean_text, re.IGNORECASE)
                if matches:
                    contacts[contact_type] = list(set(matches[:3]))  # Unique, max 3
            
            # Extract relevant business paragraphs
            business_content = self._extract_business_content(clean_text)
            
            return {
                'contacts': contacts,
                'business_content': business_content,
                'source_url': url,
                'content_length': len(clean_text)
            }
            
        except Exception as e:
            return {
                'error': str(e),
                'contacts': {},
                'business_content': "",
                'source_url': url
            }
    
    def _extract_business_content(self, text: str) -> str:
        """Extract business-relevant content sections."""
        paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 30]
        
        business_keywords = [
            'service', 'contact', 'about', 'company', 'business', 
            'location', 'experience', 'specialization'
        ]
        
        relevant_paragraphs = []
        for paragraph in paragraphs[:20]:  # First 20 paragraphs
            if any(keyword in paragraph.lower() for keyword in business_keywords):
                relevant_paragraphs.append(paragraph)
        
        return '\n\n'.join(relevant_paragraphs[:5])  # Top 5 relevant
```

### Step 2: Research Engines

```python
# src/research/checklist_customizer.py
import asyncio
import wikipedia
import arxiv
from typing import List, Dict, Any, Optional

class ChecklistCustomizationEngine:
    """Research industry standards to customize checklists."""
    
    def __init__(self, llm, content_cleaner):
        self.llm = llm
        self.cleaner = content_cleaner
        wikipedia.set_lang("en")
    
    async def research_industry_standards(
        self, 
        service_type: str,
        location: Optional[str] = None,
        specialization: Optional[str] = None
    ) -> Dict[str, Any]:
        """Research industry standards for checklist customization."""
        
        # Generate research queries
        queries = self._generate_queries(service_type, location, specialization)
        
        # Execute parallel research
        research_tasks = []
        for query in queries:
            research_tasks.append(self._research_single_query(query))
        
        research_results = await asyncio.gather(*research_tasks, return_exceptions=True)
        
        # Filter successful results
        valid_results = [r for r in research_results 
                        if not isinstance(r, Exception) and r.get('success')]
        
        # Process content
        processed_content = self._process_all_content(valid_results)
        
        # Extract checklist modifications
        modifications = await self._extract_modifications(
            processed_content, service_type, location, specialization
        )
        
        return {
            'service_type': service_type,
            'location': location,
            'specialization': specialization,
            'raw_results': valid_results,
            'processed_content': processed_content,
            'checklist_modifications': modifications,
            'research_count': len(valid_results)
        }
    
    def _generate_queries(
        self, 
        service_type: str, 
        location: Optional[str], 
        specialization: Optional[str]
    ) -> List[Dict[str, str]]:
        """Generate targeted research queries."""
        queries = []
        
        # Base industry query
        queries.append({
            'text': f"{service_type} industry standards professional requirements",
            'type': 'industry_standards',
            'priority': 'high'
        })
        
        # Regulatory query
        queries.append({
            'text': f"{service_type} regulatory compliance requirements",
            'type': 'regulations',
            'priority': 'high'
        })
        
        # Location-specific
        if location:
            queries.append({
                'text': f"{service_type} requirements {location}",
                'type': 'location_specific',
                'priority': 'medium'
            })
        
        # Specialization-specific
        if specialization:
            queries.append({
                'text': f"{specialization} {service_type} specific requirements",
                'type': 'specialization',
                'priority': 'medium'
            })
        
        return queries
    
    async def _research_single_query(self, query: Dict[str, str]) -> Dict[str, Any]:
        """Research a single query across Wikipedia and ArXiv."""
        query_text = query['text']
        results = {'query': query, 'wikipedia': None, 'arxiv': None, 'success': False}
        
        try:
            # Wikipedia search
            wiki_results = await self._search_wikipedia(query_text)
            if wiki_results:
                results['wikipedia'] = wiki_results
                results['success'] = True
        except Exception as e:
            results['wikipedia_error'] = str(e)
        
        try:
            # ArXiv search
            arxiv_results = await self._search_arxiv(query_text)
            if arxiv_results:
                results['arxiv'] = arxiv_results
                results['success'] = True
        except Exception as e:
            results['arxiv_error'] = str(e)
        
        return results
    
    async def _search_wikipedia(self, query: str) -> List[Dict[str, str]]:
        """Search Wikipedia for relevant articles."""
        try:
            # Search for pages
            search_results = wikipedia.search(query, results=5)
            
            articles = []
            for title in search_results[:3]:  # Top 3 results
                try:
                    page = wikipedia.page(title)
                    articles.append({
                        'title': page.title,
                        'url': page.url,
                        'content': page.content[:5000],  # First 5000 chars
                        'summary': page.summary
                    })
                except wikipedia.exceptions.DisambiguationError as e:
                    # Try first option from disambiguation
                    try:
                        page = wikipedia.page(e.options[0])
                        articles.append({
                            'title': page.title,
                            'url': page.url,
                            'content': page.content[:5000],
                            'summary': page.summary
                        })
                    except:
                        continue
                except:
                    continue
            
            return articles
            
        except Exception as e:
            print(f"Wikipedia search error: {e}")
            return []
    
    async def _search_arxiv(self, query: str) -> List[Dict[str, str]]:
        """Search ArXiv for academic papers."""
        try:
            search = arxiv.Search(
                query=query,
                max_results=3,
                sort_by=arxiv.SortCriterion.Relevance
            )
            
            papers = []
            for paper in search.results():
                papers.append({
                    'title': paper.title,
                    'authors': [author.name for author in paper.authors],
                    'summary': paper.summary,
                    'url': paper.entry_id,
                    'published': paper.published.isoformat()
                })
            
            return papers
            
        except Exception as e:
            print(f"ArXiv search error: {e}")
            return []
    
    def _process_all_content(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process all research content."""
        processed = []
        
        for result in results:
            # Process Wikipedia content
            if result.get('wikipedia'):
                for article in result['wikipedia']:
                    clean_content = self.cleaner.clean_and_extract(article['content'])
                    if clean_content:
                        processed.append({
                            'source': 'wikipedia',
                            'title': article['title'],
                            'url': article['url'],
                            'content': clean_content,
                            'query_type': result['query']['type']
                        })
            
            # Process ArXiv content
            if result.get('arxiv'):
                for paper in result['arxiv']:
                    clean_content = self.cleaner.clean_and_extract(paper['summary'])
                    if clean_content:
                        processed.append({
                            'source': 'arxiv',
                            'title': paper['title'],
                            'url': paper['url'],
                            'content': clean_content,
                            'query_type': result['query']['type']
                        })
        
        return processed
    
    async def _extract_modifications(
        self, 
        content: List[Dict[str, Any]], 
        service_type: str,
        location: Optional[str], 
        specialization: Optional[str]
    ) -> Dict[str, Any]:
        """Extract checklist modifications using LLM."""
        
        # Compile content for LLM
        content_summary = "\n\n".join([
            f"SOURCE: {item['source']} - {item['title']}\n{item['content'][:1000]}"
            for item in content[:10]  # Top 10 pieces of content
        ])
        
        prompt = f"""
        Based on industry research, suggest checklist modifications for {service_type} service providers:

        Location: {location or 'Not specified'}
        Specialization: {specialization or 'General'}

        Research Content:
        {content_summary[:6000]}

        Suggest specific checklist modifications:

        1. MANDATORY_ADDITIONS - Items that MUST be added:
        Format: key|question|type|reason
        
        2. RECOMMENDED_ADDITIONS - Items that SHOULD be added:
        Format: key|question|type|reason
        
        3. ITEMS_TO_REMOVE - Standard items that don't apply:
        Format: item_key|reason
        
        Focus on:
        - Legal/regulatory requirements
        - Industry-specific certifications
        - Professional standards
        - Location-specific compliance
        
        Be specific and practical. Each item should improve service quality.
        """
        
        response = await self.llm.ainvoke(prompt)
        return self._parse_modification_response(response.content)
    
    def _parse_modification_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response into structured modifications."""
        lines = response.split('\n')
        
        modifications = {
            'mandatory_additions': [],
            'recommended_additions': [],
            'items_to_remove': [],
            'raw_response': response
        }
        
        current_section = None
        
        for line in lines:
            line = line.strip()
            if 'MANDATORY_ADDITIONS' in line:
                current_section = 'mandatory_additions'
            elif 'RECOMMENDED_ADDITIONS' in line:
                current_section = 'recommended_additions'
            elif 'ITEMS_TO_REMOVE' in line:
                current_section = 'items_to_remove'
            elif '|' in line and current_section:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    if current_section in ['mandatory_additions', 'recommended_additions']:
                        modifications[current_section].append({
                            'key': parts[0],
                            'question': parts[1],
                            'type': parts[2],
                            'reason': parts[3] if len(parts) > 3 else ''
                        })
                    else:  # items_to_remove
                        modifications[current_section].append({
                            'key': parts[0],
                            'reason': parts[1] if len(parts) > 1 else ''
                        })
        
        return modifications
```

### Step 3: Answer Gathering Engine

```python
# src/research/answer_gatherer.py
import aiohttp
import asyncio
from typing import List, Dict, Any, Optional

class AnswerGatheringEngine:
    """Research specific answers to checklist items."""
    
    def __init__(self, llm, web_search_api, content_parser):
        self.llm = llm
        self.web_search = web_search_api
        self.parser = content_parser
    
    async def research_answers(
        self,
        provider_info: Dict[str, Any],
        checklist_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Research answers for specific checklist items."""
        
        # Filter to pending items only
        pending_items = [item for item in checklist_items 
                        if item.get('status') == 'PENDING'][:8]  # Max 8 items
        
        if not pending_items:
            return {'extracted_answers': {}, 'research_results': []}
        
        # Generate search queries
        queries = self._generate_answer_queries(provider_info, pending_items)
        
        # Execute web searches
        search_results = await self._execute_searches(queries)
        
        # Parse content
        parsed_content = await self._parse_search_results(search_results)
        
        # Extract specific answers
        answers = await self._extract_answers(parsed_content, pending_items)
        
        return {
            'extracted_answers': answers,
            'research_results': search_results,
            'parsed_content': parsed_content
        }
    
    def _generate_answer_queries(
        self,
        provider_info: Dict[str, Any],
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate targeted search queries for specific answers."""
        queries = []
        provider_name = provider_info.get('name', '')
        provider_website = provider_info.get('website', '')
        
        for item in items:
            # Direct provider search
            if provider_name:
                queries.append({
                    'text': f'"{provider_name}" {item["prompt"].lower()}',
                    'item_key': item['key'],
                    'query_type': 'direct_provider',
                    'priority': 'high' if item.get('required') else 'medium'
                })
            
            # Site-specific search
            if provider_website:
                domain = self._extract_domain(provider_website)
                queries.append({
                    'text': f'site:{domain} {item["prompt"].lower()}',
                    'item_key': item['key'], 
                    'query_type': 'site_specific',
                    'priority': 'high' if item.get('required') else 'medium'
                })
        
        return queries
    
    async def _execute_searches(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute all search queries in parallel."""
        semaphore = asyncio.Semaphore(5)  # Limit concurrent requests
        
        async def search_single(query):
            async with semaphore:
                try:
                    results = await self.web_search.search(
                        query=query['text'],
                        num_results=3
                    )
                    return {
                        'query': query,
                        'results': results,
                        'success': True
                    }
                except Exception as e:
                    return {
                        'query': query,
                        'error': str(e),
                        'success': False
                    }
        
        tasks = [search_single(q) for q in queries]
        results = await asyncio.gather(*tasks)
        
        return [r for r in results if r.get('success')]
    
    async def _parse_search_results(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Parse search results to extract business content."""
        parsed_results = []
        
        for search_result in search_results:
            query = search_result['query']
            results = search_result['results']
            
            for result in results[:3]:  # Top 3 per query
                try:
                    # Fetch page content
                    async with aiohttp.ClientSession() as session:
                        async with session.get(result['link'], timeout=10) as response:
                            if response.status == 200:
                                html_content = await response.text()
                                
                                # Parse business information
                                business_info = self.parser.extract_business_info(
                                    html_content, result['link']
                                )
                                
                                parsed_results.append({
                                    'query': query,
                                    'url': result['link'],
                                    'title': result.get('title', ''),
                                    'business_info': business_info,
                                    'relevance_score': self._calculate_relevance(
                                        business_info, query
                                    )
                                })
                
                except Exception as e:
                    print(f"Error parsing {result.get('link', '')}: {e}")
                    continue
        
        return parsed_results
    
    async def _extract_answers(
        self,
        parsed_content: List[Dict[str, Any]],
        checklist_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract specific answers using LLM analysis."""
        answers = {}
        
        # Group content by item key
        content_by_item = {}
        for content in parsed_content:
            item_key = content['query']['item_key']
            if item_key not in content_by_item:
                content_by_item[item_key] = []
            content_by_item[item_key].append(content)
        
        # Extract answer for each item
        for item in checklist_items:
            item_key = item['key']
            if item_key in content_by_item:
                relevant_content = sorted(
                    content_by_item[item_key],
                    key=lambda x: x['relevance_score'],
                    reverse=True
                )[:3]  # Top 3 most relevant
                
                answer = await self._llm_extract_answer(item, relevant_content)
                if answer.get('confidence', 0) > 0.6:
                    answers[item_key] = answer
        
        return answers
    
    async def _llm_extract_answer(
        self,
        item: Dict[str, Any],
        content_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Use LLM to extract specific answer."""
        
        content_text = "\n\n".join([
            f"URL: {content['url']}\nCONTENT: {content['business_info'].get('business_content', '')[:800]}\nCONTACTS: {content['business_info'].get('contacts', {})}"
            for content in content_items
        ])
        
        prompt = f"""
        Extract the answer for this question from the business content:

        QUESTION: {item['prompt']}
        EXPECTED TYPE: {item.get('value_type', 'text')}
        REQUIRED: {item.get('required', False)}

        BUSINESS CONTENT:
        {content_text[:3000]}

        Extract:
        1. Direct answer to the question
        2. Confidence level (0.0-1.0) - how certain are you?
        3. Source URL where found
        4. Supporting evidence (quote)

        Rules:
        - Only provide answers you're confident about (>0.6)
        - For contact info, verify format is correct
        - If no clear answer, set confidence to 0.0
        - Be precise and factual

        Format:
        ANSWER: [specific answer]
        CONFIDENCE: [0.0-1.0]
        SOURCE: [URL]
        EVIDENCE: [supporting quote]
        """
        
        response = await self.llm.ainvoke(prompt)
        return self._parse_answer_response(response.content)
    
    def _parse_answer_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM answer response."""
        lines = response.split('\n')
        
        answer_data = {
            'value': '',
            'confidence': 0.0,
            'source': '',
            'evidence': ''
        }
        
        for line in lines:
            line = line.strip()
            if line.startswith('ANSWER:'):
                answer_data['value'] = line.replace('ANSWER:', '').strip()
            elif line.startswith('CONFIDENCE:'):
                try:
                    answer_data['confidence'] = float(line.replace('CONFIDENCE:', '').strip())
                except:
                    answer_data['confidence'] = 0.0
            elif line.startswith('SOURCE:'):
                answer_data['source'] = line.replace('SOURCE:', '').strip()
            elif line.startswith('EVIDENCE:'):
                answer_data['evidence'] = line.replace('EVIDENCE:', '').strip()
        
        return answer_data
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL."""
        import re
        domain = re.sub(r'^https?://', '', url)
        domain = re.sub(r'^www\.', '', domain)
        return domain.split('/')[0]
    
    def _calculate_relevance(self, business_info: Dict[str, Any], query: Dict[str, Any]) -> float:
        """Calculate content relevance to query."""
        content = business_info.get('business_content', '')
        question = query.get('text', '')
        
        question_words = question.lower().split()
        content_lower = content.lower()
        
        matches = sum(1 for word in question_words if word in content_lower and len(word) > 3)
        return matches / max(len(question_words), 1)
```

### Step 4: Main Application Integration

```python
# src/api/main.py
import asyncio
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from langchain_openai import ChatOpenAI

# Import our modules
from ..research.checklist_customizer import ChecklistCustomizationEngine
from ..research.answer_gatherer import AnswerGatheringEngine
from ..tools.content_parser import AcademicContentCleaner, BusinessContentParser
from ..tools.web_search import WebSearchAPI

# Global components
app_components = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await initialize_components()
    yield
    # Shutdown
    print("Shutting down...")

async def initialize_components():
    """Initialize all application components."""
    
    # Initialize LLM
    llm = ChatOpenAI(
        model="gpt-4",
        api_key=settings.openai_api_key,
        temperature=0.1
    )
    
    # Initialize content processors
    academic_cleaner = AcademicContentCleaner()
    business_parser = BusinessContentParser()
    
    # Initialize web search
    web_search = WebSearchAPI(api_key=settings.serpapi_key)
    
    # Initialize research engines
    checklist_engine = ChecklistCustomizationEngine(llm, academic_cleaner)
    answer_engine = AnswerGatheringEngine(llm, web_search, business_parser)
    
    app_components.update({
        'llm': llm,
        'checklist_engine': checklist_engine,
        'answer_engine': answer_engine,
        'academic_cleaner': academic_cleaner,
        'business_parser': business_parser,
        'web_search': web_search
    })
    
    print("All components initialized successfully")

# Create FastAPI app
app = FastAPI(
    title="Two-Part Research Onboarding System",
    description="Intelligent onboarding with checklist customization and answer gathering",
    version="1.0.0",
    lifespan=lifespan
)

@app.post("/research/checklist-customization")
async def customize_checklist(request: Dict[str, Any]):
    """Customize checklist based on industry standards."""
    try:
        service_type = request["service_type"]
        location = request.get("location")
        specialization = request.get("specialization")
        
        result = await app_components['checklist_engine'].research_industry_standards(
            service_type=service_type,
            location=location,
            specialization=specialization
        )
        
        return {
            "success": True,
            "research_phase": "checklist_customization",
            "modifications": result["checklist_modifications"],
            "research_count": result["research_count"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/research/answer-gathering")
async def gather_answers(request: Dict[str, Any]):
    """Gather specific answers for checklist items."""
    try:
        provider_info = request["provider_info"]
        checklist_items = request["checklist_items"]
        
        result = await app_components['answer_engine'].research_answers(
            provider_info=provider_info,
            checklist_items=checklist_items
        )
        
        return {
            "success": True,
            "research_phase": "answer_gathering",
            "extracted_answers": result["extracted_answers"],
            "results_count": len(result["research_results"])
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/research/two-part-complete")
async def complete_two_part_research(request: Dict[str, Any]):
    """Execute complete two-part research process."""
    try:
        service_type = request["service_type"]
        provider_info = request["provider_info"]
        current_checklist = request.get("current_checklist", [])
        location = request.get("location")
        specialization = request.get("specialization")
        
        # Phase 1: Checklist Customization
        checklist_result = await app_components['checklist_engine'].research_industry_standards(
            service_type=service_type,
            location=location,
            specialization=specialization
        )
        
        # Apply modifications to checklist
        modified_checklist = apply_checklist_modifications(
            current_checklist,
            checklist_result["checklist_modifications"]
        )
        
        # Phase 2: Answer Gathering (if provider info available)
        answer_result = None
        if provider_info.get("name") or provider_info.get("website"):
            pending_items = [item for item in modified_checklist 
                           if item.get("status") == "PENDING"]
            
            if pending_items:
                answer_result = await app_components['answer_engine'].research_answers(
                    provider_info=provider_info,
                    checklist_items=pending_items
                )
                
                # Apply answers to checklist
                modified_checklist = apply_research_answers(
                    modified_checklist,
                    answer_result["extracted_answers"]
                )
        
        return {
            "success": True,
            "modified_checklist": modified_checklist,
            "checklist_research": {
                "modifications_applied": len(checklist_result["checklist_modifications"].get("mandatory_additions", [])) + 
                                      len(checklist_result["checklist_modifications"].get("recommended_additions", [])),
                "items_removed": len(checklist_result["checklist_modifications"].get("items_to_remove", [])),
                "research_sources": checklist_result["research_count"]
            },
            "answer_research": {
                "answers_found": len(answer_result["extracted_answers"]) if answer_result else 0,
                "confidence_scores": {k: v.get("confidence", 0) for k, v in (answer_result.get("extracted_answers", {})).items()}
            } if answer_result else None
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def apply_checklist_modifications(checklist: List[Dict], modifications: Dict) -> List[Dict]:
    """Apply checklist modifications from research."""
    modified_checklist = checklist.copy()
    
    # Add mandatory items
    for item in modifications.get("mandatory_additions", []):
        modified_checklist.append({
            "key": item["key"],
            "prompt": item["question"],
            "value_type": item["type"],
            "required": True,
            "status": "PENDING",
            "source": "industry_research"
        })
    
    # Add recommended items
    for item in modifications.get("recommended_additions", []):
        modified_checklist.append({
            "key": item["key"],
            "prompt": item["question"],
            "value_type": item["type"],
            "required": False,
            "status": "PENDING",
            "source": "industry_research"
        })
    
    # Remove items
    items_to_remove = {item["key"] for item in modifications.get("items_to_remove", [])}
    modified_checklist = [item for item in modified_checklist 
                         if item.get("key") not in items_to_remove]
    
    return modified_checklist

def apply_research_answers(checklist: List[Dict], answers: Dict) -> List[Dict]:
    """Apply extracted answers to checklist."""
    for item in checklist:
        item_key = item.get("key")
        if item_key in answers:
            answer_data = answers[item_key]
            if answer_data.get("confidence", 0) > 0.7:
                item["value"] = answer_data["value"]
                item["status"] = "AUTO_FILLED"
                item["confidence"] = answer_data["confidence"]
                item["source"] = "web_research"
    
    return checklist

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
```

## Deployment Guide

### Docker Setup

```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - SERPAPI_KEY=${SERPAPI_KEY}
      - POSTGRES_HOST=postgres
      - REDIS_URL=redis://redis:6379/0
    volumes:
      - ./src:/app/src
    depends_on:
      - postgres
      - redis

  postgres:
    image: postgres:14
    environment:
      POSTGRES_DB: growbal_onboarding
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  redis:
    image: redis:7
    volumes:
      - redis_data:/data
    ports:
      - "6379:6379"

volumes:
  postgres_data:
  redis_data:
```

### Environment Configuration

```bash
# .env
OPENAI_API_KEY=sk-your-openai-key
SERPAPI_KEY=your-serpapi-key
POSTGRES_HOST=localhost
POSTGRES_PASSWORD=your-secure-password
REDIS_URL=redis://localhost:6379/0

# Research configuration
MAX_WIKIPEDIA_RESULTS=5
MAX_ARXIV_RESULTS=3
MAX_WEB_SEARCH_RESULTS=5
ANSWER_CONFIDENCE_THRESHOLD=0.7
RESEARCH_TIMEOUT_SECONDS=30
```

## Testing the Implementation

### Basic Test Script

```python
# test_research.py
import asyncio
import aiohttp
import json

async def test_checklist_customization():
    """Test checklist customization research."""
    
    async with aiohttp.ClientSession() as session:
        data = {
            "service_type": "tax",
            "location": "California",
            "specialization": "small business"
        }
        
        async with session.post(
            "http://localhost:8000/research/checklist-customization",
            json=data
        ) as response:
            result = await response.json()
            print("Checklist Customization Result:")
            print(json.dumps(result, indent=2))

async def test_answer_gathering():
    """Test answer gathering research."""
    
    async with aiohttp.ClientSession() as session:
        data = {
            "provider_info": {
                "name": "ABC Tax Services",
                "website": "https://abctax.com"
            },
            "checklist_items": [
                {
                    "key": "contact_email",
                    "prompt": "What is the business email address?",
                    "value_type": "email",
                    "required": True,
                    "status": "PENDING"
                },
                {
                    "key": "phone_number", 
                    "prompt": "What is the business phone number?",
                    "value_type": "phone",
                    "required": True,
                    "status": "PENDING"
                }
            ]
        }
        
        async with session.post(
            "http://localhost:8000/research/answer-gathering",
            json=data
        ) as response:
            result = await response.json()
            print("Answer Gathering Result:")
            print(json.dumps(result, indent=2))

async def test_complete_research():
    """Test complete two-part research process."""
    
    async with aiohttp.ClientSession() as session:
        data = {
            "service_type": "migration",
            "location": "New York",
            "provider_info": {
                "name": "NYC Immigration Law",
                "website": "https://nycimmigration.com"
            },
            "current_checklist": [
                {
                    "key": "business_name",
                    "prompt": "What is your business name?",
                    "value_type": "text",
                    "required": True,
                    "status": "PENDING"
                }
            ]
        }
        
        async with session.post(
            "http://localhost:8000/research/two-part-complete",
            json=data
        ) as response:
            result = await response.json()
            print("Complete Research Result:")
            print(json.dumps(result, indent=2))

if __name__ == "__main__":
    asyncio.run(test_checklist_customization())
    print("\n" + "="*50 + "\n")
    asyncio.run(test_answer_gathering()) 
    print("\n" + "="*50 + "\n")
    asyncio.run(test_complete_research())
```

This implementation provides:

1. **Modular Architecture**: Separate engines for each research phase
2. **Clean Content Processing**: Specialized parsers for academic vs business content  
3. **Robust Error Handling**: Graceful failures with fallback mechanisms
4. **Performance Optimization**: Parallel processing, timeouts, and rate limiting
5. **Simple Integration**: FastAPI endpoints for easy testing and integration
6. **Docker Deployment**: Ready-to-deploy containerized setup

Start with this foundation and expand based on your specific requirements!

<function_calls>
<invoke name="TodoWrite">
<parameter name="todos">[{"content": "Read and analyze existing docs_2 directory content", "status": "completed", "activeForm": "Reading and analyzing existing docs_2 directory content"}, {"content": "Create docs_3 directory structure", "status": "completed", "activeForm": "Creating docs_3 directory structure"}, {"content": "Modify 01_evolved_core_architecture.md with two-part research process", "status": "completed", "activeForm": "Modifying 01_evolved_core_architecture.md with two-part research process"}, {"content": "Modify 02_evolved_tools_utilities.md with specific search tools for each part", "status": "completed", "activeForm": "Modifying 02_evolved_tools_utilities.md with specific search tools for each part"}, {"content": "Create implementation guide", "status": "completed", "activeForm": "Creating implementation guide"}]