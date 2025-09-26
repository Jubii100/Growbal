"""
Two-Part Research Engine for Onboarding System
"""
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from research_tools import (
    OpenAIWebSearchAPI, ScrapingFishClient,
    AcademicContentCleaner, BusinessContentParser
)
from llm_wrapper import OnboardingLLM
from state_manager import ResearchPhase


class ChecklistCustomizationEngine:
    """Research engine for customizing checklists based on industry standards"""
    
    def __init__(self, llm: OnboardingLLM):
        self.llm = llm
        self.web_search = OpenAIWebSearchAPI()
        self.fetcher = ScrapingFishClient()
        self.parser = BusinessContentParser()
        self.cleaner = AcademicContentCleaner()
    
    async def research_industry_standards(
        self,
        profile_text: str
    ) -> Dict[str, Any]:
        """Research industry standards for checklist customization using web search.
        
        Uses profile_text to generate appropriate search queries via LLM.
        """
        # Use LLM to generate search queries from profile_text
        queries = self.llm.generate_search_queries(profile_text=profile_text, max_queries=5)

        # Convert LLM queries to our format and execute parallel research
        formatted_queries = []
        for q in queries:
            formatted_queries.append({
                'text': q.get('text', ''),
                'type': q.get('intent', 'general'),
                'priority': 'high'
            })
        
        research_tasks = [self._research_single_query(q) for q in formatted_queries]
        research_results = await asyncio.gather(*research_tasks, return_exceptions=True)

        # Filter successful results
        valid_results = [r for r in research_results if not isinstance(r, Exception) and r.get('success')]

        # Process content
        processed_content = self._process_all_content(valid_results)

        # Extract checklist modifications
        modifications = await self._extract_modifications(processed_content, profile_text)

        return {
            'phase': ResearchPhase.CHECKLIST_CUSTOMIZATION,
            'profile_text': profile_text,
            'raw_results': valid_results,
            'processed_content': processed_content,
            'checklist_modifications': modifications,
            'research_count': len(valid_results),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    
    async def _research_single_query(self, query: Dict[str, str]) -> Dict[str, Any]:
        """Research a single query using web search and fetch/parse top results."""
        query_text = query['text']
        result: Dict[str, Any] = {'query': query, 'pages': [], 'success': False}
        try:
            search_results = await self.web_search.search(query_text, num_results=3)
            # Normalize and pick top 3 by simple lexical score on title
            def lex(title: str) -> float:
                t = (title or '').lower()
                words = [w for w in query_text.lower().split() if len(w) > 2]
                return sum(1 for w in words if w in t) / max(1, len(words))
            ranked = sorted(search_results, key=lambda r: lex(r.get('title', '')), reverse=True)[:2]
            # Fetch and parse
            fetch_tasks = [self.fetcher.fetch(r.get('link', '')) for r in ranked if r.get('link')]
            fetched_pages = await asyncio.gather(*fetch_tasks, return_exceptions=True)
            for r, page in zip(ranked, fetched_pages):
                if isinstance(page, Exception) or not getattr(page, 'html', None):
                    continue
                parsed = self.parser.extract_business_info(page.html, r.get('link', ''))
                if parsed.get('business_content'):
                    result['pages'].append({
                        'title': r.get('title', ''),
                        'url': r.get('link', ''),
                        'content': self.cleaner.clean_and_extract(parsed.get('business_content', '')) or parsed.get('business_content', ''),
                    })
            result['success'] = len(result['pages']) > 0
        except Exception as e:
            result['error'] = str(e)
        return result
    
    def _process_all_content(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process all research content"""
        processed: List[Dict[str, Any]] = []
        for result in results:
            for page in result.get('pages', []):
                if page.get('content'):
                    processed.append({
                        'source': 'web',
                        'title': page.get('title', ''),
                        'url': page.get('url', ''),
                        'content': page.get('content', ''),
                        'query_type': result['query']['type']
                    })
        return processed
    
    async def _extract_modifications(
        self,
        content: List[Dict[str, Any]],
        profile_text: str
    ) -> Dict[str, Any]:
        """Extract checklist modifications using LLM"""
        
        # Compile content for LLM
        content_summary = "\n\n".join([
            f"SOURCE: {item['source']} - {item['title']}\n{item['content'][:500]}"
            for item in content[:5]
        ])
        
        return await self.llm.extract_checklist_modifications(
            content_summary, location=None
        )


class AnswerGatheringEngine:
    """Research engine for finding specific answers to checklist items"""
    
    def __init__(self, llm: OnboardingLLM):
        self.llm = llm
        self.web_search = OpenAIWebSearchAPI()
        self.fetcher = ScrapingFishClient()
        self.parser = BusinessContentParser()
    
    async def research_answers(
        self,
        provider_info: Dict[str, Any],
        checklist_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Research answers for specific checklist items"""
        
        # Filter to pending items only
        pending_items = [item for item in checklist_items 
                        if item.get('status') == 'PENDING'][:5]  # Max 5 items
        
        if not pending_items:
            return {
                'phase': ResearchPhase.ANSWER_GATHERING,
                'extracted_answers': {},
                'research_results': [],
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Generate search queries
        queries = self._generate_answer_queries(provider_info, pending_items)
        
        # Execute web searches
        search_results = await self._execute_searches(queries)
        
        # Parse content
        parsed_content = await self._parse_search_results(search_results)
        
        # Extract specific answers
        answers = await self._extract_answers(parsed_content, pending_items)
        
        return {
            'phase': ResearchPhase.ANSWER_GATHERING,
            'provider_info': provider_info,
            'extracted_answers': answers,
            'research_results': search_results,
            'parsed_content': parsed_content,
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def _generate_answer_queries(
        self,
        provider_info: Dict[str, Any],
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate targeted search queries using profile_text from provider_info.
        
        Uses the profile_text that's passed in provider_info to create
        context-aware queries about the specific company.
        """
        queries = []
        
        # Get the profile_text from provider_info (this is how it's passed from state)
        profile_text = provider_info.get('profile_text', '')
        
        # If we have profile_text, use it to create company-specific queries
        if profile_text:
            # First, add a general search using the entire profile context
            # This helps find information about the specific company
            # Truncate to first 200 chars to avoid overly long queries
            profile_summary = profile_text[:200].replace('\n', ' ').replace('=', '').strip()
            if profile_summary:
                queries.append({
                    'text': profile_summary,
                    'item_key': 'company_profile_search',
                    'query_type': 'profile_based',
                    'priority': 'high'
                })
        
        # Generate queries for each checklist item
        # Combine profile context with the specific question
        for item in items:
            if profile_text:
                # Extract key context from profile_text to prepend to queries
                # This ensures we're searching for the RIGHT company's information
                context_prefix = self._extract_company_context(profile_text)
                if context_prefix:
                    query_text = f"{context_prefix} {item['prompt']}"
                else:
                    query_text = item['prompt']
            else:
                query_text = item['prompt']
                
            queries.append({
                'text': query_text,
                'item_key': item['key'],
                'query_type': 'question_oriented',
                'priority': 'high' if item.get('required') else 'medium'
            })
        
        return queries
    
    def _extract_company_context(self, profile_text: str) -> str:
        """Extract key company identifiers from profile_text for search context."""
        # Look for company name and key details in the profile text
        lines = profile_text.split('\n')
        context_parts = []
        
        for line in lines:
            # Extract company name if present
            if 'Company Name:' in line:
                name = line.split('Company Name:')[1].strip()
                if name:
                    context_parts.append(name)
                    break  # Company name is most important
            # Could also extract other key identifiers if needed
        
        return ' '.join(context_parts[:2])  # Limit context to avoid query bloat
    
    async def _execute_searches(self, queries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute all search queries in parallel"""
        semaphore = asyncio.Semaphore(3)  # Limit concurrent requests
        
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
    
    def _normalize_results_for_rerank(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [{"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")} for r in results]

    async def _parse_search_results(self, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Fetch and parse most relevant search results (by title relevance)."""
        parsed_results: List[Dict[str, Any]] = []

        for search_result in search_results:
            query = search_result['query']
            results = search_result.get('results', [])
            # Rerank by title with LLM guidance
            normalized = self._normalize_results_for_rerank(results)
            reranked = self.llm.rerank_results_by_title(query['text'], normalized, top_k=2)
            # Fetch and parse top reranked
            for item in reranked:
                url = item.get('url', '')
                if not url:
                    continue
                try:
                    fetched = await self.fetcher.fetch(url)
                    business_info = self.parser.extract_business_info(fetched.html, url)
                    parsed_results.append({
                        'query': query,
                        'url': url,
                        'title': item.get('title', ''),
                        'business_info': business_info,
                        'relevance_score': self._title_relevance_score(item.get('title', ''), query.get('text', ''))
                    })
                except Exception:
                    continue

        return parsed_results
    
    async def _extract_answers(
        self,
        parsed_content: List[Dict[str, Any]],
        checklist_items: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract specific answers using LLM analysis"""
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
                )[:2]  # Top 2 most relevant
                
                # Compile content for LLM
                content_text = "\n".join([
                    f"Content: {c['business_info'].get('business_content', '')}"
                    for c in relevant_content
                ])
                
                answer = await self.llm.extract_answer_from_content(
                    content_text,
                    item['prompt']
                )
                
                if answer.get('confidence', 0) > 0.6:
                    answers[item_key] = answer
        
        return answers
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL"""
        import re
        domain = re.sub(r'^https?://', '', url)
        domain = re.sub(r'^www\.', '', domain)
        return domain.split('/')[0]
    
    def _title_relevance_score(self, title: str, query_text: str) -> float:
        """Title relevance scoring for fallback/metrics."""
        if not title or not query_text:
            return 0.0
        title_lower = title.lower()
        words = [w for w in query_text.lower().split() if len(w) > 2]
        if not words:
            return 0.0
        matches = sum(1 for w in words if w in title_lower)
        return min(matches / len(words), 1.0)


class TwoPartResearchOrchestrator:
    """Orchestrates the complete two-part research process"""
    
    def __init__(self):
        self.llm = OnboardingLLM()
        self.checklist_engine = ChecklistCustomizationEngine(self.llm)
        self.answer_engine = AnswerGatheringEngine(self.llm)
    
    def _apply_checklist_modifications(
        self,
        checklist: List[Dict[str, Any]],
        modifications: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply checklist modifications from research"""
        modified_checklist = checklist.copy()
        
        # Add mandatory items
        for item in modifications.get('mandatory_additions', []):
            modified_checklist.append({
                'key': item['key'],
                'prompt': item['question'],
                'required': True,
                'status': 'PENDING',
                'reason': item.get('reason', ''),
                'value': None
            })
        
        # Add recommended items
        for item in modifications.get('recommended_additions', []):
            modified_checklist.append({
                'key': item['key'],
                'prompt': item['question'],
                'required': False,
                'status': 'PENDING',
                'reason': item.get('reason', ''),
                'value': None
            })
        
        # Remove items that don't apply
        items_to_remove = {item['key'] for item in modifications.get('items_to_remove', [])}
        modified_checklist = [
            item for item in modified_checklist 
            if item.get('key') not in items_to_remove
        ]
        
        return modified_checklist
    
    def _apply_research_answers(
        self,
        checklist: List[Dict[str, Any]],
        answers: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply extracted answers to checklist items"""
        for item in checklist:
            item_key = item.get('key')
            if item_key in answers:
                answer_data = answers[item_key]
                if answer_data.get('confidence', 0) > 0.7:
                    item['value'] = answer_data['value']
                    item['status'] = 'AUTO_FILLED'
                    item['confidence'] = answer_data['confidence']
                    item['source'] = 'web_research'
                    item['evidence'] = answer_data.get('evidence', '')
        
        return checklist
    
    def _create_research_summary(
        self,
        checklist_research: Optional[Dict[str, Any]],
        answer_research: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create summary of research activities"""
        summary = {
            'phases_completed': [],
            'checklist_items_added': 0,
            'checklist_items_removed': 0,
            'answers_found': 0,
            'confidence_scores': {}
        }
        
        if checklist_research:
            summary['phases_completed'].append('checklist_customization')
            modifications = checklist_research.get('checklist_modifications', {})
            summary['checklist_items_added'] = (
                len(modifications.get('mandatory_additions', [])) + 
                len(modifications.get('recommended_additions', []))
            )
            summary['checklist_items_removed'] = len(modifications.get('items_to_remove', []))
        
        if answer_research:
            summary['phases_completed'].append('answer_gathering')
            answers = answer_research.get('extracted_answers', {})
            summary['answers_found'] = len(answers)
            summary['confidence_scores'] = {
                k: v.get('confidence', 0) for k, v in answers.items()
            }
        
        return summary