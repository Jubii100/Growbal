# Evolved Tools and Utilities

## Overview

The evolved tools and utilities module provides specialized capabilities for the **two-part research process**: first for checklist customization using academic/official sources, and second for answer gathering using business-focused web search with content parsers.

## Two-Part Research System

### 1. Checklist Customization Research Tools

```python
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum
import asyncio
from datetime import datetime
import re
from bs4 import BeautifulSoup

class ResearchPhase(Enum):
    """Research phases for two-part system"""
    CHECKLIST_CUSTOMIZATION = "checklist_customization"
    ANSWER_GATHERING = "answer_gathering"

@dataclass
class ChecklistResearchQuery:
    """Research query for checklist customization"""
    query_text: str
    service_type: str
    location: Optional[str]
    specialization: Optional[str]
    purpose: str  # "industry_standards", "regulatory_requirements", "compliance_needs"
    priority: str = "medium"

class ChecklistCustomizationEngine:
    """
    Research engine for customizing checklists based on industry standards.
    Uses Wikipedia, ArXiv, and official sources with clean text parsing.
    """
    
    def __init__(self, llm, wikipedia_api, arxiv_api):
        self.llm = llm
        self.wikipedia_api = wikipedia_api
        self.arxiv_api = arxiv_api
        self.content_cleaner = AcademicContentCleaner()
        
    async def research_industry_standards(
        self,
        service_type: str,
        location: Optional[str] = None,
        specialization: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Research industry standards to determine checklist requirements.
        
        Args:
            service_type: Type of service (tax, migration, business_setup, etc.)
            location: Geographic location for local requirements
            specialization: Specific specialization within service type
            
        Returns:
            Industry research results with checklist modifications
        """
        
        # Generate research queries
        queries = self._generate_industry_queries(
            service_type=service_type,
            location=location,
            specialization=specialization
        )
        
        # Execute research across sources
        research_results = await self._execute_parallel_research(queries)
        
        # Clean and process content
        processed_results = self._process_academic_content(research_results)
        
        # Extract checklist modifications
        checklist_modifications = await self._extract_checklist_requirements(
            processed_results, service_type, location, specialization
        )
        
        return {
            "phase": ResearchPhase.CHECKLIST_CUSTOMIZATION,
            "service_type": service_type,
            "location": location,
            "specialization": specialization,
            "raw_results": research_results,
            "processed_content": processed_results,
            "checklist_modifications": checklist_modifications,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _generate_industry_queries(
        self,
        service_type: str,
        location: Optional[str] = None,
        specialization: Optional[str] = None
    ) -> List[ChecklistResearchQuery]:
        """
        Generate targeted queries for industry standards research.
        """
        queries = []
        
        # Core industry standards query
        base_query = ChecklistResearchQuery(
            query_text=f"{service_type} industry standards professional requirements",
            service_type=service_type,
            location=location,
            specialization=specialization,
            purpose="industry_standards",
            priority="high"
        )
        queries.append(base_query)
        
        # Regulatory requirements query
        regulatory_query = ChecklistResearchQuery(
            query_text=f"{service_type} regulatory compliance requirements licensing",
            service_type=service_type,
            location=location,
            specialization=specialization,
            purpose="regulatory_requirements",
            priority="high"
        )
        queries.append(regulatory_query)
        
        # Location-specific query
        if location:
            location_query = ChecklistResearchQuery(
                query_text=f"{service_type} requirements {location} local regulations",
                service_type=service_type,
                location=location,
                specialization=specialization,
                purpose="location_requirements",
                priority="medium"
            )
            queries.append(location_query)
        
        # Specialization query
        if specialization:
            specialization_query = ChecklistResearchQuery(
                query_text=f"{specialization} {service_type} specific requirements standards",
                service_type=service_type,
                location=location,
                specialization=specialization,
                purpose="specialization_requirements",
                priority="medium"
            )
            queries.append(specialization_query)
        
        # Professional certification query
        cert_query = ChecklistResearchQuery(
            query_text=f"{service_type} professional certification qualifications",
            service_type=service_type,
            location=location,
            specialization=specialization,
            purpose="certification_requirements",
            priority="low"
        )
        queries.append(cert_query)
        
        return queries
    
    async def _execute_parallel_research(
        self,
        queries: List[ChecklistResearchQuery]
    ) -> List[Dict[str, Any]]:
        """
        Execute research queries in parallel across Wikipedia and ArXiv.
        """
        tasks = []
        
        for query in queries:
            # Wikipedia search
            wikipedia_task = self._search_wikipedia(query)
            tasks.append(wikipedia_task)
            
            # ArXiv search for academic papers
            arxiv_task = self._search_arxiv(query)
            tasks.append(arxiv_task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and package results
        valid_results = []
        for i, result in enumerate(results):
            if not isinstance(result, Exception) and result:
                valid_results.append(result)
        
        return valid_results
    
    async def _search_wikipedia(self, query: ChecklistResearchQuery) -> Dict[str, Any]:
        """
        Search Wikipedia for industry information.
        """
        try:
            search_results = await self.wikipedia_api.search(
                query=query.query_text,
                limit=5
            )
            
            content = []
            for result in search_results:
                page_content = await self.wikipedia_api.get_page_content(result['title'])
                content.append({
                    'title': result['title'],
                    'url': result.get('url', ''),
                    'content': page_content
                })
            
            return {
                'source': 'wikipedia',
                'query': query,
                'results': content,
                'success': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'source': 'wikipedia',
                'query': query,
                'error': str(e),
                'success': False,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    async def _search_arxiv(self, query: ChecklistResearchQuery) -> Dict[str, Any]:
        """
        Search ArXiv for academic papers related to industry standards.
        """
        try:
            # Modify query for academic context
            academic_query = f"{query.service_type} professional standards regulation"
            
            papers = await self.arxiv_api.search(
                query=academic_query,
                max_results=3
            )
            
            content = []
            for paper in papers:
                content.append({
                    'title': paper.title,
                    'authors': [author.name for author in paper.authors],
                    'abstract': paper.summary,
                    'url': paper.entry_id,
                    'published': paper.published.isoformat()
                })
            
            return {
                'source': 'arxiv',
                'query': query,
                'results': content,
                'success': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'source': 'arxiv',
                'query': query,
                'error': str(e),
                'success': False,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _process_academic_content(
        self,
        raw_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Process and clean academic content for business relevance.
        """
        processed_results = []
        
        for result in raw_results:
            if not result.get('success'):
                continue
            
            processed_content = []
            
            for item in result.get('results', []):
                cleaned_content = self.content_cleaner.clean_academic_text(
                    content=item.get('content', item.get('abstract', '')),
                    focus_keywords=[
                        'requirement', 'standard', 'regulation', 'compliance',
                        'licensing', 'certification', 'professional', 'business'
                    ]
                )
                
                if cleaned_content and len(cleaned_content) > 100:
                    processed_content.append({
                        'title': item.get('title', ''),
                        'url': item.get('url', ''),
                        'cleaned_content': cleaned_content,
                        'relevance_score': self._calculate_business_relevance(cleaned_content)
                    })
            
            if processed_content:
                processed_results.append({
                    'source': result['source'],
                    'query': result['query'],
                    'processed_content': processed_content,
                    'timestamp': result['timestamp']
                })
        
        return processed_results
    
    async def _extract_checklist_requirements(
        self,
        processed_results: List[Dict[str, Any]],
        service_type: str,
        location: Optional[str],
        specialization: Optional[str]
    ) -> Dict[str, Any]:
        """
        Use LLM to extract specific checklist requirements from research.
        """
        # Compile research content
        content_summary = self._compile_research_summary(processed_results)
        
        prompt = f"""
        Based on industry research for {service_type} service providers, identify specific checklist requirements:

        Service Type: {service_type}
        Location: {location or 'Not specified'}
        Specialization: {specialization or 'General'}

        Research Summary:
        {content_summary[:4000]}  # Limit content for LLM processing

        Extract and categorize requirements into:

        1. MANDATORY_ITEMS (Must be collected):
        - Items that are legally required
        - Essential business information for this industry
        - Regulatory compliance requirements

        2. RECOMMENDED_ITEMS (Should be collected):
        - Industry best practices
        - Common business requirements
        - Quality assurance items

        3. OPTIONAL_ITEMS (Nice to have):
        - Additional information that might be useful
        - Competitive advantage items

        4. LOCATION_SPECIFIC (If location provided):
        - Local regulatory requirements
        - Regional compliance needs

        5. ITEMS_TO_REMOVE:
        - Standard checklist items that don't apply to this industry

        Format each item as:
        - Key: unique identifier
        - Question: what to ask the user
        - Type: expected answer type (text, email, phone, etc.)
        - Validation: any validation rules
        - Reason: why this item is needed

        Focus on practical, actionable requirements that improve service quality.
        """
        
        llm_response = await self.llm.ainvoke(prompt)
        
        # Parse LLM response into structured format
        requirements = self._parse_requirements_response(llm_response.content)
        
        return requirements
    
    def _compile_research_summary(
        self,
        processed_results: List[Dict[str, Any]]
    ) -> str:
        """
        Compile research results into a focused summary.
        """
        summary_parts = []
        
        for result in processed_results:
            source = result['source']
            query_purpose = result['query'].purpose
            
            content_snippets = []
            for content in result['processed_content']:
                if content['relevance_score'] > 0.6:  # Only include relevant content
                    snippet = content['cleaned_content'][:500]  # Limit snippet length
                    content_snippets.append(f"- {snippet}")
            
            if content_snippets:
                summary_parts.append(
                    f"\n{source.upper()} - {query_purpose}:\n" + 
                    '\n'.join(content_snippets[:3])  # Max 3 snippets per source
                )
        
        return '\n'.join(summary_parts)
    
    def _parse_requirements_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured checklist modifications.
        """
        # This would implement parsing logic for the LLM response
        # For now, returning a template structure
        
        return {
            "mandatory_items": [],
            "recommended_items": [],
            "optional_items": [],
            "location_specific": [],
            "items_to_remove": [],
            "reasoning": llm_response,
            "confidence": 0.8
        }
```

### 2. Answer Gathering Research Tools

```python
@dataclass
class AnswerResearchQuery:
    """Research query for answer gathering"""
    query_text: str
    provider_name: str
    provider_website: Optional[str]
    checklist_item_key: str
    checklist_question: str
    expected_type: str
    priority: str = "medium"

class AnswerGatheringEngine:
    """
    Research engine for finding specific answers to checklist items.
    Uses web search with business-focused content parsing.
    """
    
    def __init__(self, llm, web_search_api):
        self.llm = llm
        self.web_search = web_search_api
        self.business_parser = BusinessContentParser()
        
    async def research_provider_answers(
        self,
        provider_info: Dict[str, Any],
        pending_checklist_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Research specific answers for pending checklist items.
        
        Args:
            provider_info: Provider information (name, website, etc.)
            pending_checklist_items: Items that need answers
            
        Returns:
            Research results with extracted answers
        """
        
        # Generate targeted queries for each checklist item
        queries = self._generate_answer_queries(
            provider_info=provider_info,
            checklist_items=pending_checklist_items[:8]  # Limit to top 8 items
        )
        
        # Execute web research
        search_results = await self._execute_web_research(queries)
        
        # Parse business content from results
        parsed_results = self._parse_business_content(search_results)
        
        # Extract specific answers
        extracted_answers = await self._extract_specific_answers(
            parsed_results, pending_checklist_items
        )
        
        return {
            "phase": ResearchPhase.ANSWER_GATHERING,
            "provider_info": provider_info,
            "raw_search_results": search_results,
            "parsed_content": parsed_results,
            "extracted_answers": extracted_answers,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _generate_answer_queries(
        self,
        provider_info: Dict[str, Any],
        checklist_items: List[Dict[str, Any]]
    ) -> List[AnswerResearchQuery]:
        """
        Generate specific queries to find answers for checklist items.
        """
        queries = []
        provider_name = provider_info.get("name", "")
        provider_website = provider_info.get("website", "")
        provider_location = provider_info.get("location", "")
        
        for item in checklist_items:
            # Direct provider query
            if provider_name:
                direct_query = AnswerResearchQuery(
                    query_text=f'"{provider_name}" {item["prompt"].lower()}',
                    provider_name=provider_name,
                    provider_website=provider_website,
                    checklist_item_key=item["key"],
                    checklist_question=item["prompt"],
                    expected_type=item.get("value_type", "text"),
                    priority="high" if item.get("required") else "medium"
                )
                queries.append(direct_query)
            
            # Website-specific search
            if provider_website:
                domain = self._extract_domain(provider_website)
                website_query = AnswerResearchQuery(
                    query_text=f'site:{domain} {item["prompt"].lower()}',
                    provider_name=provider_name,
                    provider_website=provider_website,
                    checklist_item_key=item["key"],
                    checklist_question=item["prompt"],
                    expected_type=item.get("value_type", "text"),
                    priority="high" if item.get("required") else "medium"
                )
                queries.append(website_query)
            
            # Location-based search
            if provider_location and provider_name:
                location_query = AnswerResearchQuery(
                    query_text=f'"{provider_name}" {provider_location} {item["prompt"].lower()}',
                    provider_name=provider_name,
                    provider_website=provider_website,
                    checklist_item_key=item["key"],
                    checklist_question=item["prompt"],
                    expected_type=item.get("value_type", "text"),
                    priority="medium"
                )
                queries.append(location_query)
        
        return queries
    
    async def _execute_web_research(
        self,
        queries: List[AnswerResearchQuery]
    ) -> List[Dict[str, Any]]:
        """
        Execute web research queries in parallel.
        """
        tasks = []
        
        for query in queries:
            task = self._search_web(query)
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions
        valid_results = [
            result for result in results 
            if not isinstance(result, Exception) and result.get('success')
        ]
        
        return valid_results
    
    async def _search_web(self, query: AnswerResearchQuery) -> Dict[str, Any]:
        """
        Perform web search for specific answer query.
        """
        try:
            search_results = await self.web_search.search(
                query=query.query_text,
                num_results=5
            )
            
            return {
                'query': query,
                'search_results': search_results,
                'success': True,
                'timestamp': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            return {
                'query': query,
                'error': str(e),
                'success': False,
                'timestamp': datetime.utcnow().isoformat()
            }
    
    def _parse_business_content(
        self,
        search_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Parse business content from search results using readability parser.
        """
        parsed_results = []
        
        for result in search_results:
            query = result['query']
            search_items = result.get('search_results', [])
            
            parsed_items = []
            
            for item in search_items[:3]:  # Limit to top 3 results per query
                try:
                    # Extract business content
                    business_content = self.business_parser.extract_business_info(
                        url=item.get('link', ''),
                        html_content=item.get('content', ''),
                        focus_patterns=self._get_focus_patterns(query.expected_type)
                    )
                    
                    if business_content:
                        parsed_items.append({
                            'url': item.get('link', ''),
                            'title': item.get('title', ''),
                            'business_content': business_content,
                            'relevance_score': self._calculate_answer_relevance(
                                business_content, query.checklist_question
                            )
                        })
                        
                except Exception as e:
                    print(f"Error parsing content from {item.get('link', '')}: {e}")
                    continue
            
            if parsed_items:
                parsed_results.append({
                    'query': query,
                    'parsed_items': parsed_items,
                    'timestamp': datetime.utcnow().isoformat()
                })
        
        return parsed_results
    
    async def _extract_specific_answers(
        self,
        parsed_results: List[Dict[str, Any]],
        checklist_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract specific answers from parsed business content.
        """
        extracted_answers = {}
        
        # Group results by checklist item
        results_by_item = {}
        for result in parsed_results:
            item_key = result['query'].checklist_item_key
            if item_key not in results_by_item:
                results_by_item[item_key] = []
            results_by_item[item_key].extend(result['parsed_items'])
        
        # Extract answers for each item
        for item in checklist_items:
            item_key = item['key']
            if item_key in results_by_item:
                
                # Get best content for this item
                relevant_content = sorted(
                    results_by_item[item_key], 
                    key=lambda x: x['relevance_score'], 
                    reverse=True
                )[:3]  # Top 3 most relevant
                
                # Use LLM to extract specific answer
                answer = await self._llm_extract_answer(
                    item=item,
                    content_items=relevant_content
                )
                
                if answer.get('confidence', 0) > 0.6:
                    extracted_answers[item_key] = answer
        
        return extracted_answers
    
    async def _llm_extract_answer(
        self,
        item: Dict[str, Any],
        content_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Use LLM to extract specific answer from business content.
        """
        content_summary = "\n\n".join([
            f"Source: {content['url']}\n{content['business_content'][:800]}"
            for content in content_items
        ])
        
        prompt = f"""
        Extract the specific answer for this checklist item from the business content:

        Checklist Item: {item['prompt']}
        Expected Type: {item.get('value_type', 'text')}
        Required: {item.get('required', False)}

        Business Content:
        {content_summary[:2000]}

        Extract:
        1. The direct answer to the checklist question
        2. Confidence level (0.0 to 1.0) - how certain are you this is correct?
        3. Source URL where the information was found
        4. Supporting evidence (quote from content)

        Rules:
        - Only return answers you're confident about (>0.6 confidence)
        - If information is unclear or contradictory, set low confidence
        - For contact info, verify format (valid email, phone number, etc.)
        - For addresses, include complete information
        - If no clear answer found, set confidence to 0.0

        Return in format:
        Answer: [the specific answer]
        Confidence: [0.0-1.0]
        Source: [URL]
        Evidence: [supporting quote]
        """
        
        llm_response = await self.llm.ainvoke(prompt)
        
        # Parse LLM response
        return self._parse_answer_response(llm_response.content, content_items)
    
    def _parse_answer_response(
        self, 
        llm_response: str, 
        content_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Parse LLM response into structured answer format.
        """
        # Simple parsing logic - would be more sophisticated in real implementation
        lines = llm_response.split('\n')
        
        answer = ""
        confidence = 0.0
        source = ""
        evidence = ""
        
        for line in lines:
            if line.startswith('Answer:'):
                answer = line.replace('Answer:', '').strip()
            elif line.startswith('Confidence:'):
                try:
                    confidence = float(line.replace('Confidence:', '').strip())
                except:
                    confidence = 0.0
            elif line.startswith('Source:'):
                source = line.replace('Source:', '').strip()
            elif line.startswith('Evidence:'):
                evidence = line.replace('Evidence:', '').strip()
        
        return {
            "value": answer,
            "confidence": confidence,
            "source": source,
            "evidence": evidence,
            "extraction_method": "llm_analysis",
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _get_focus_patterns(self, expected_type: str) -> List[str]:
        """
        Get regex patterns based on expected answer type.
        """
        patterns = {
            'email': [r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'],
            'phone': [r'[\+]?[1-9]?[0-9]{7,15}', r'\(\d{3}\)\s*\d{3}-\d{4}'],
            'address': [r'\d+\s+[A-Za-z0-9\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)'],
            'website': [r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'],
            'text': []  # General text, no specific pattern
        }
        
        return patterns.get(expected_type, [])
```

### 3. Content Processing Utilities

```python
class AcademicContentCleaner:
    """
    Cleans academic content removing HTML, code, images, keeping only business-relevant text.
    """
    
    def clean_academic_text(
        self, 
        content: str, 
        focus_keywords: List[str]
    ) -> str:
        """
        Clean academic text content for business relevance.
        """
        # Remove HTML tags
        soup = BeautifulSoup(content, 'html.parser')
        
        # Remove non-content elements
        for element in soup(['script', 'style', 'img', 'table', 'code', 'pre', 'nav', 'header', 'footer']):
            element.decompose()
        
        # Get clean text
        clean_text = soup.get_text()
        
        # Remove excessive whitespace
        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
        
        # Split into paragraphs
        paragraphs = [p.strip() for p in clean_text.split('\n') if p.strip()]
        
        # Filter for business-relevant paragraphs
        relevant_paragraphs = []
        for paragraph in paragraphs:
            if len(paragraph) < 50:  # Skip short fragments
                continue
                
            # Check for focus keywords
            if any(keyword.lower() in paragraph.lower() for keyword in focus_keywords):
                relevance_score = self._calculate_paragraph_relevance(paragraph, focus_keywords)
                if relevance_score > 0.3:
                    relevant_paragraphs.append((paragraph, relevance_score))
        
        # Sort by relevance and return top paragraphs
        relevant_paragraphs.sort(key=lambda x: x[1], reverse=True)
        top_paragraphs = [p[0] for p in relevant_paragraphs[:8]]  # Top 8 paragraphs
        
        return '\n\n'.join(top_paragraphs)
    
    def _calculate_paragraph_relevance(
        self, 
        paragraph: str, 
        focus_keywords: List[str]
    ) -> float:
        """
        Calculate how relevant a paragraph is to business requirements.
        """
        paragraph_lower = paragraph.lower()
        
        # Count keyword matches
        keyword_matches = sum(1 for keyword in focus_keywords if keyword.lower() in paragraph_lower)
        
        # Bonus for business-specific terms
        business_terms = [
            'must', 'required', 'shall', 'should', 'need', 'necessary',
            'compliance', 'regulation', 'standard', 'procedure', 'process',
            'license', 'permit', 'certification', 'qualification'
        ]
        business_matches = sum(1 for term in business_terms if term in paragraph_lower)
        
        # Calculate relevance score
        relevance = (keyword_matches / len(focus_keywords)) * 0.7 + (business_matches / len(business_terms)) * 0.3
        
        return min(relevance, 1.0)  # Cap at 1.0

class BusinessContentParser:
    """
    Parses business content focusing on contact info, services, etc. using readability parser.
    """
    
    def extract_business_info(
        self, 
        url: str, 
        html_content: str,
        focus_patterns: List[str]
    ) -> str:
        """
        Extract business information from HTML content.
        """
        try:
            # Use python-readability to extract main content
            from readability import Document
            
            doc = Document(html_content)
            main_content = doc.summary()
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(main_content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'sidebar']):
                element.decompose()
            
            # Get clean text
            clean_text = soup.get_text()
            
            # Extract structured information
            business_info = self._extract_structured_info(clean_text, focus_patterns)
            
            return business_info
            
        except Exception as e:
            # Fallback to simple text extraction
            return self._fallback_extraction(html_content, focus_patterns)
    
    def _extract_structured_info(
        self, 
        text: str, 
        focus_patterns: List[str]
    ) -> str:
        """
        Extract structured business information using patterns.
        """
        extracted_info = []
        
        # Apply focus patterns if provided
        for pattern in focus_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                pattern_name = self._get_pattern_name(pattern)
                extracted_info.append(f"{pattern_name}: {', '.join(set(matches[:3]))}")
        
        # Always extract common business patterns
        common_patterns = {
            'Email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'Phone': r'[\+]?[1-9]?[0-9]{7,15}|[\(\d{3}\)\s*\d{3}-\d{4}]',
            'Address': r'\d+\s+[A-Za-z0-9\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr)',
            'Website': r'http[s]?://[^\s]+|www\.[^\s]+'
        }
        
        for name, pattern in common_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                extracted_info.append(f"{name}: {', '.join(set(matches[:3]))}")
        
        # Extract relevant paragraphs
        paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 50]
        business_paragraphs = []
        
        business_keywords = [
            'service', 'contact', 'about', 'company', 'business', 'location',
            'experience', 'expertise', 'specialization', 'office', 'hours'
        ]
        
        for paragraph in paragraphs[:15]:  # Limit to first 15 paragraphs
            if any(keyword in paragraph.lower() for keyword in business_keywords):
                business_paragraphs.append(paragraph)
        
        # Combine extracted patterns and relevant content
        result_parts = []
        
        if extracted_info:
            result_parts.append("Extracted Information:\n" + '\n'.join(extracted_info))
        
        if business_paragraphs:
            result_parts.append("Relevant Content:\n" + '\n\n'.join(business_paragraphs[:5]))
        
        return '\n\n'.join(result_parts)
    
    def _get_pattern_name(self, pattern: str) -> str:
        """
        Get human-readable name for regex pattern.
        """
        if 'email' in pattern.lower() or '@' in pattern:
            return "Email"
        elif 'phone' in pattern.lower() or r'\d' in pattern:
            return "Phone"
        elif 'address' in pattern.lower() or 'street' in pattern.lower():
            return "Address"
        elif 'http' in pattern.lower():
            return "Website"
        else:
            return "Pattern Match"
    
    def _fallback_extraction(
        self, 
        html_content: str, 
        focus_patterns: List[str]
    ) -> str:
        """
        Simple fallback extraction when readability fails.
        """
        # Remove HTML tags
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text()
        
        # Extract basic contact information
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'[\+]?[1-9]?[0-9]{7,15}'
        
        emails = re.findall(email_pattern, text)
        phones = re.findall(phone_pattern, text)
        
        result = []
        if emails:
            result.append(f"Emails found: {', '.join(set(emails[:3]))}")
        if phones:
            result.append(f"Phones found: {', '.join(set(phones[:3]))}")
        
        # Add first few paragraphs
        paragraphs = [p.strip() for p in text.split('\n') if len(p.strip()) > 30]
        if paragraphs:
            result.append("Content snippet:\n" + '\n'.join(paragraphs[:3]))
        
        return '\n\n'.join(result) if result else "No extractable business information found."

    def _calculate_business_relevance(self, content: str) -> float:
        """
        Calculate relevance score for business content.
        """
        business_indicators = [
            'contact', 'about', 'service', 'company', 'business',
            'phone', 'email', 'address', 'location', 'office'
        ]
        
        content_lower = content.lower()
        matches = sum(1 for indicator in business_indicators if indicator in content_lower)
        
        return min(matches / len(business_indicators), 1.0)

def _extract_domain(website_url: str) -> str:
    """
    Extract domain from website URL.
    """
    import re
    
    # Remove protocol
    domain = re.sub(r'^https?://', '', website_url)
    # Remove www
    domain = re.sub(r'^www\.', '', domain)
    # Remove path
    domain = domain.split('/')[0]
    
    return domain

def _calculate_answer_relevance(content: str, question: str) -> float:
    """
    Calculate how relevant content is to answering a specific question.
    """
    question_words = question.lower().split()
    content_lower = content.lower()
    
    # Count question word matches
    matches = sum(1 for word in question_words if word in content_lower and len(word) > 3)
    
    # Bonus for specific patterns based on question type
    if 'email' in question.lower() and '@' in content:
        matches += 2
    if 'phone' in question.lower() and re.search(r'\d{3,}', content):
        matches += 2
    if 'address' in question.lower() and any(word in content_lower for word in ['street', 'avenue', 'road']):
        matches += 2
    
    relevance = matches / max(len(question_words), 1)
    return min(relevance, 1.0)
```

## Tool Integration Framework

```python
class TwoPartResearchIntegration:
    """
    Integrates checklist customization and answer gathering research tools.
    """
    
    def __init__(self, config: Dict[str, Any]):
        # Initialize checklist customization tools
        self.checklist_engine = ChecklistCustomizationEngine(
            llm=config["llm"],
            wikipedia_api=config["wikipedia_api"],
            arxiv_api=config["arxiv_api"]
        )
        
        # Initialize answer gathering tools  
        self.answer_engine = AnswerGatheringEngine(
            llm=config["llm"],
            web_search_api=config["web_search_api"]
        )
    
    async def execute_two_part_research(
        self,
        service_type: str,
        provider_info: Dict[str, Any],
        current_checklist: List[Dict[str, Any]],
        location: Optional[str] = None,
        specialization: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute complete two-part research process.
        
        Args:
            service_type: Type of service provider
            provider_info: Known provider information
            current_checklist: Current checklist items
            location: Geographic location
            specialization: Provider specialization
            
        Returns:
            Complete research results with checklist modifications and answers
        """
        
        # Phase 1: Checklist Customization Research
        checklist_research = await self.checklist_engine.research_industry_standards(
            service_type=service_type,
            location=location,
            specialization=specialization
        )
        
        # Apply checklist modifications
        modified_checklist = self._apply_checklist_modifications(
            current_checklist=current_checklist,
            modifications=checklist_research["checklist_modifications"]
        )
        
        # Phase 2: Answer Gathering Research (if provider info available)
        answer_research = None
        if provider_info.get("name") or provider_info.get("website"):
            pending_items = [item for item in modified_checklist if item.get("status") == "PENDING"]
            
            if pending_items:
                answer_research = await self.answer_engine.research_provider_answers(
                    provider_info=provider_info,
                    pending_checklist_items=pending_items
                )
                
                # Apply extracted answers
                modified_checklist = self._apply_research_answers(
                    checklist=modified_checklist,
                    answers=answer_research["extracted_answers"]
                )
        
        return {
            "modified_checklist": modified_checklist,
            "checklist_research": checklist_research,
            "answer_research": answer_research,
            "research_summary": self._create_research_summary(
                checklist_research, answer_research
            )
        }
    
    def _apply_checklist_modifications(
        self,
        current_checklist: List[Dict[str, Any]],
        modifications: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Apply checklist modifications from industry research.
        """
        modified_checklist = current_checklist.copy()
        
        # Add new items
        for item in modifications.get("mandatory_items", []):
            modified_checklist.append({
                "key": item["key"],
                "prompt": item["question"],
                "value_type": item["type"],
                "required": True,
                "status": "PENDING",
                "source": "industry_research",
                "validation_rules": item.get("validation", {}),
                "reason": item.get("reason", "")
            })
        
        for item in modifications.get("recommended_items", []):
            modified_checklist.append({
                "key": item["key"], 
                "prompt": item["question"],
                "value_type": item["type"],
                "required": False,
                "status": "PENDING",
                "source": "industry_research",
                "validation_rules": item.get("validation", {}),
                "reason": item.get("reason", "")
            })
        
        # Remove items that don't apply
        items_to_remove = set(modifications.get("items_to_remove", []))
        modified_checklist = [
            item for item in modified_checklist 
            if item.get("key") not in items_to_remove
        ]
        
        return modified_checklist
    
    def _apply_research_answers(
        self,
        checklist: List[Dict[str, Any]],
        answers: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Apply extracted answers to checklist items.
        """
        for item in checklist:
            item_key = item.get("key")
            if item_key in answers:
                answer_data = answers[item_key]
                if answer_data.get("confidence", 0) > 0.6:
                    item["value"] = answer_data["value"]
                    item["status"] = "AUTO_FILLED"
                    item["confidence"] = answer_data["confidence"]
                    item["source"] = "web_research"
                    item["research_evidence"] = answer_data.get("evidence", "")
        
        return checklist
    
    def _create_research_summary(
        self,
        checklist_research: Optional[Dict[str, Any]],
        answer_research: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Create summary of research activities.
        """
        summary = {
            "phases_completed": [],
            "checklist_items_added": 0,
            "checklist_items_removed": 0,
            "answers_found": 0,
            "confidence_scores": {}
        }
        
        if checklist_research:
            summary["phases_completed"].append("checklist_customization")
            modifications = checklist_research.get("checklist_modifications", {})
            summary["checklist_items_added"] = (
                len(modifications.get("mandatory_items", [])) + 
                len(modifications.get("recommended_items", []))
            )
            summary["checklist_items_removed"] = len(modifications.get("items_to_remove", []))
        
        if answer_research:
            summary["phases_completed"].append("answer_gathering")
            answers = answer_research.get("extracted_answers", {})
            summary["answers_found"] = len(answers)
            summary["confidence_scores"] = {
                k: v.get("confidence", 0) for k, v in answers.items()
            }
        
        return summary
```

This evolved tools and utilities system provides:

1. **Specialized Research Engines**: Separate tools for checklist customization vs answer gathering
2. **Source-Specific Parsing**: Wikipedia/ArXiv parser for standards, web search parser for business info
3. **Content Quality Control**: Clean text processing, relevance scoring, confidence thresholds
4. **Structured Integration**: Clear workflow for two-part research with state management
5. **Business-Focused Extraction**: Pattern matching for contacts, addresses, business information