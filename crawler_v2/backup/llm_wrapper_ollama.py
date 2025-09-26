"""
LLM Wrapper for Onboarding System
Supports both OpenAI and Ollama backends
"""
from typing import Dict, Any, List, Optional, Tuple
import re
from datetime import datetime
from pathlib import Path
import json
import os
import traceback
from dotenv import load_dotenv
try:
    import tiktoken  # OpenAI tokenization
except Exception:  # pragma: no cover - optional dependency safety
    tiktoken = None

# OpenAI imports (commented out for Ollama usage)
# from langchain_openai import ChatOpenAI
# from langchain_core.prompts import ChatPromptTemplate
# from langchain_core.output_parsers import JsonOutputParser
# from pydantic import ValidationError

# Ollama imports
import ollama
import asyncio
from pydantic import ValidationError

from schemas import (
    ChecklistResponse,
    SearchQuery,
    WebSearchResult,
    GenerateSearchQueriesResponse,
    RerankResponse,
    ExtractChecklistModificationsResponse,
    ExtractAnswerFromContentResponse,
    TextResponse,
    ProfileSummaryResponse,
)
from research_tools import OpenAIWebSearchAPI, ScrapingFishClient, BusinessContentParser


class OnboardingLLM:
    """Specialized LLM wrapper for onboarding tasks using Ollama with GPT-OSS."""
    
    def __init__(self, model_name: str = "gpt-oss:20b", temperature: float = 0.0, token_limit: int = 32768, timeout: int = 180, max_retries: int = 1):
        self.model_name = model_name
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        
        # Initialize Ollama client
        self.ollama_client = ollama.Client(host='http://localhost:11434')
        
        # OpenAI/LangChain setup (commented out for Ollama usage)
        # self.chat = ChatOpenAI(
        #     model=self.model_name,
        #     temperature=self.temperature,
        #     timeout=timeout,
        #     max_retries=max_retries,
        # )
        
        self._base_dir = Path(__file__).parent
        self._prompts_dir = self._base_dir / "prompts"
        self._initial_checklist_prompt_path = self._prompts_dir / "initial_checklist.md"
        self._generate_search_queries_prompt_path = self._prompts_dir / "generate_search_queries.md"
        self._rerank_by_title_prompt_path = self._prompts_dir / "rerank_by_title.md"
        self._profile_summary_prompt_path = self._prompts_dir / "profile_summary.md"
        self.max_input_tokens = int(token_limit)
        
        # Logging setup (clear once per process/run)
        self._log_path = self._base_dir / "llm_prompts.txt"
        if not getattr(OnboardingLLM, "_log_initialized", False):
            try:
                with self._log_path.open("w", encoding="utf-8") as f:
                    f.write(f"# Onboarding LLM Prompt Log\n# Model: {self.model_name}\n# Started: {datetime.utcnow().isoformat()}Z\n\n")
            except Exception:
                pass
            OnboardingLLM._log_initialized = True

        # Research and web request logs (refresh per workflow call)
        self._research_log_path = self._base_dir / "research_content.txt"
        self._web_requests_log_path = self._base_dir / "web_requests_log.txt"
        self._html_log_path = self._base_dir / "html.txt"
        self._parsed_html_log_path = self._base_dir / "parsed_html.txt"
        # LLM error log path
        self._llm_error_log_path = self._base_dir / "llm_call.txt"

        # Load envs/1.env non-intrusively so OPENAI_API_KEY is available for LangChain
        try:
            env_path = self._base_dir.parent / "envs" / "1.env"
            if env_path.exists():
                load_dotenv(str(env_path), override=False)
        except Exception:
            pass
    
    def _call_ollama_with_tools(self, messages: List[Dict[str, Any]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Call Ollama with function calling support"""
        try:
            # Prepare the request
            request_data = {
                'model': self.model_name,
                'messages': messages,
                'options': {
                    'temperature': self.temperature
                }
            }
            
            # Add tools if provided
            if tools:
                request_data['tools'] = tools
            
            # Call Ollama
            response = self.ollama_client.chat(**request_data)
            
            # Handle ChatResponse object
            if hasattr(response, 'message'):
                message = response.message
                content = getattr(message, 'content', '') if hasattr(message, 'content') else message.get('content', '')
                tool_calls = getattr(message, 'tool_calls', []) if hasattr(message, 'tool_calls') else message.get('tool_calls', [])
            else:
                # Fallback for dict-like response
                message = response.get('message', {})
                content = message.get('content', '')
                tool_calls = message.get('tool_calls', [])
            
            return {
                'content': content,
                'tool_calls': tool_calls,
                'success': True
            }
            
        except Exception as e:
            return {
                'content': '',
                'tool_calls': [],
                'success': False,
                'error': str(e)
            }
    
    def _call_ollama_structured(self, messages: List[Dict[str, Any]], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Call Ollama with structured output using function calling"""
        # Create a tool for structured output
        tools = [{
            "type": "function",
            "function": {
                "name": "structured_response",
                "description": "Provide a structured response according to the given schema",
                "parameters": schema
            }
        }]
        
        # Add instruction for structured output
        system_message = {
            "role": "system", 
            "content": "You must respond using the structured_response function with the exact schema provided. Do not include any thinking or reasoning in your response."
        }
        
        # Ensure system message is first
        if messages and messages[0].get('role') == 'system':
            messages[0]['content'] += "\n\n" + system_message['content']
        else:
            messages.insert(0, system_message)
        
        response = self._call_ollama_with_tools(messages, tools)
        
        if response['success'] and response['tool_calls']:
            # Extract structured data from tool call
            try:
                tool_call = response['tool_calls'][0]
                function_args = tool_call.get('function', {}).get('arguments', {})
                if isinstance(function_args, str):
                    function_args = json.loads(function_args)
                
                # Apply fixes for different response types based on schema structure
                function_args = self._fix_simplified_response_structure(function_args, schema)
                
                return {
                    'data': function_args,
                    'success': True
                }
            except Exception as e:
                return {
                    'data': {},
                    'success': False,
                    'error': f"Failed to parse structured output: {str(e)}"
                }
        
        return {
            'data': {},
            'success': False,
            'error': response.get('error', 'No tool calls in response')
        }
    
    def _fix_simplified_response_structure(self, function_args: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Fix simplified response structures that GPT-OSS might return"""
        
        # Helper function to normalize enum values (case-insensitive)
        def normalize_enum_value(value: str, valid_values: List[str]) -> str:
            """Normalize enum values to match expected case"""
            if not isinstance(value, str):
                return valid_values[0] if valid_values else value
            
            value_upper = value.upper()
            for valid_val in valid_values:
                if value_upper == valid_val.upper():
                    return valid_val
            
            # Return first valid value as fallback
            return valid_values[0] if valid_values else value
        
        # Fix for GenerateSearchQueriesResponse - queries array of strings
        if 'queries' in function_args and isinstance(function_args['queries'], list):
            queries = function_args['queries']
            formatted_queries = []
            for query in queries:
                if isinstance(query, str):
                    formatted_queries.append({
                        'text': query,
                        'intent': 'provider_discovery'
                    })
                elif isinstance(query, dict):
                    # Ensure intent field is properly set
                    query.setdefault('intent', 'provider_discovery')
                    formatted_queries.append(query)
            function_args['queries'] = formatted_queries
        
        # Fix for ChecklistResponse - checklist array might have simplified items
        if 'checklist' in function_args and isinstance(function_args['checklist'], list):
            checklist = function_args['checklist']
            formatted_checklist = []
            valid_statuses = ['PENDING', 'ASKED', 'VERIFIED', 'AUTO_FILLED']
            
            for i, item in enumerate(checklist):
                if isinstance(item, dict):
                    # Ensure all required fields are present with defaults
                    status = normalize_enum_value(
                        item.get('status', 'PENDING'), 
                        valid_statuses
                    )
                    
                    # Extract the key and prompt, handling various field names
                    key = item.get('key', f"item_{i}")
                    prompt = item.get('prompt', item.get('question', 'Please provide information.'))
                    
                    # Ensure key is lowercase with underscores
                    if key and not key.islower():
                        key = key.lower().replace(' ', '_').replace('-', '_')
                    
                    formatted_item = {
                        'key': key,
                        'prompt': prompt,
                        'required': bool(item.get('required', True)),
                        'status': status,
                        'value': item.get('value', None)
                    }
                    formatted_checklist.append(formatted_item)
                elif isinstance(item, str):
                    # Handle case where model returns just strings
                    formatted_checklist.append({
                        'key': f"item_{i}",
                        'prompt': item,
                        'required': True,
                        'status': 'PENDING',
                        'value': None
                    })
            function_args['checklist'] = formatted_checklist
        
        # Fix for ExtractChecklistModificationsResponse - ensure proper structure
        valid_modification_types = ['required', 'optional', 'mandatory', 'recommended']
        
        for field in ['mandatory_additions', 'recommended_additions', 'items_to_remove']:
            if field in function_args and isinstance(function_args[field], list):
                items = function_args[field]
                formatted_items = []
                for i, item in enumerate(items):
                    if isinstance(item, dict):
                        if field == 'items_to_remove':
                            formatted_item = {
                                'key': item.get('key', f"remove_{i}"),
                                'reason': item.get('reason', 'Suggested by research')
                            }
                        else:
                            # Normalize type field with case handling
                            item_type = normalize_enum_value(
                                item.get('type', 'required'), 
                                valid_modification_types
                            )
                            if field == 'mandatory_additions':
                                item_type = 'required'
                            elif field == 'recommended_additions':
                                item_type = 'optional'
                            
                            key = item.get('key', f"research_item_{i}")
                            if key and not key.islower():
                                key = key.lower().replace(' ', '_').replace('-', '_')
                            
                            formatted_item = {
                                'key': key,
                                'question': item.get('question', item.get('prompt', '')),
                                'type': item_type,
                                'reason': item.get('reason', 'Suggested by research')
                            }
                        formatted_items.append(formatted_item)
                    elif isinstance(item, str):
                        # Handle case where model returns just strings
                        if field == 'items_to_remove':
                            formatted_items.append({
                                'key': item.lower().replace(' ', '_'),
                                'reason': 'Suggested by research'
                            })
                        else:
                            item_type = 'required' if field == 'mandatory_additions' else 'optional'
                            formatted_items.append({
                                'key': f"research_item_{i}",
                                'question': item,
                                'type': item_type,
                                'reason': 'Suggested by research'
                            })
                function_args[field] = formatted_items
        
        # Fix for ExtractAnswerFromContentResponse - ensure all fields are present
        if any(field in function_args for field in ['value', 'confidence', 'source', 'evidence']):
            # This is likely an answer response, ensure all fields exist
            function_args.setdefault('value', function_args.get('answer', function_args.get('text', '')))
            
            # Normalize confidence to float between 0 and 1
            confidence = function_args.get('confidence', 0.7)
            if isinstance(confidence, str):
                try:
                    # Handle percentage strings like "85%" or "0.85"
                    if confidence.endswith('%'):
                        confidence = float(confidence[:-1]) / 100.0
                    else:
                        confidence = float(confidence)
                except ValueError:
                    confidence = 0.7
            function_args['confidence'] = max(0.0, min(1.0, confidence))
            
            function_args.setdefault('source', 'research_content')
            function_args.setdefault('evidence', str(function_args.get('value', ''))[:100])
        
        # Fix for TextResponse - handle various text field names
        if 'text' not in function_args:
            # Check for common alternative field names that might contain text
            text_fields = ['message', 'response', 'question', 'answer', 'content', 'summary']
            for field in text_fields:
                if field in function_args and isinstance(function_args[field], str):
                    function_args['text'] = function_args[field]
                    break
            
            # If still no text field and there's only one string field, use it
            if 'text' not in function_args and len(function_args) == 1:
                for key, value in function_args.items():
                    if isinstance(value, str):
                        function_args['text'] = value
                        break
        
        # Fix for ProfileSummaryResponse - handle various summary field names
        if 'summary' not in function_args:
            # Check for common alternative field names that might contain summary
            summary_fields = ['text', 'content', 'response', 'profile_summary']
            for field in summary_fields:
                if field in function_args and isinstance(function_args[field], str) and len(function_args[field]) > 50:
                    function_args['summary'] = function_args[field]
                    break
            
            # If still no summary field and there's only one long string field, use it
            if 'summary' not in function_args and len(function_args) == 1:
                for key, value in function_args.items():
                    if isinstance(value, str) and len(value) > 50:  # Likely a summary
                        function_args['summary'] = value
                        break
        
        return function_args
    
    async def _call_ollama_structured_async(self, messages: List[Dict[str, Any]], schema: Dict[str, Any]) -> Dict[str, Any]:
        """Async version of Ollama structured call"""
        import asyncio
        
        def sync_call():
            return self._call_ollama_structured(messages, schema)
        
        # Run the sync call in a thread pool to make it async
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, sync_call)

    def generate_initial_checklist_with_research(self, profile_text: str) -> tuple[List[Dict[str, Any]], str]:
        """Generate the initial onboarding checklist and return both checklist and research content.

        Returns:
            tuple: (checklist_items, research_content)
                - checklist_items: List of checklist item dicts with keys: key, prompt, required, status, value
                - research_content: String containing the research content used for generation
        """
        # Reset research logs for this workflow run
        self._reset_research_logs(workflow_label="generate_initial_checklist", profile_text=profile_text)

        # Perform lightweight web research from profile_text
        research_content = self._gather_research_content(profile_text)

        # Prepare prompt for Ollama
        template_str = self._read_prompt(self._initial_checklist_prompt_path)
        formatted_prompt = template_str.format(
            profile_text=profile_text,
            research_content=research_content
        )
        
        # Create schema for ChecklistResponse
        schema = ChecklistResponse.model_json_schema()
        
        messages = [{
            "role": "user",
            "content": formatted_prompt
        }]
        
        # Retry wrapper for Ollama calls
        result_model: Optional[ChecklistResponse] = None
        last_err: Optional[Exception] = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # Call Ollama with structured output
                response = self._call_ollama_structured(messages, schema)
                
                if response['success']:
                    # Parse the structured response
                    result_model = ChecklistResponse(**response['data'])
                    break
                else:
                    last_err = Exception(f"Ollama call failed: {response.get('error', 'Unknown error')}")
                    
            except Exception as e:
                last_err = e
                try:
                    self._log_llm_error("generate_initial_checklist", e, formatted_prompt)
                except Exception:
                    pass
                continue
                
        if result_model is None and last_err is not None:
            # Fallback to empty structure
            result_model = ChecklistResponse(checklist=[])
            
        # Log the structured response
        self._log_interaction("generate_initial_checklist", formatted_prompt, result_model.model_dump())
        
        # Convert to dict and fix enum serialization
        checklist_items = []
        for item in result_model.checklist:
            item_dict = item.model_dump()
            # Fix enum serialization issue - convert ItemStatus enum to string
            if hasattr(item_dict.get('status'), 'value'):
                item_dict['status'] = item_dict['status'].value
            elif str(item_dict.get('status', '')).startswith('ItemStatus.'):
                item_dict['status'] = str(item_dict['status']).replace('ItemStatus.', '')
            checklist_items.append(item_dict)
        
        # Original LangChain implementation (commented out for Ollama usage)
        # template_str = self._read_prompt(self._initial_checklist_prompt_path)
        # prompt = ChatPromptTemplate.from_template(template_str)
        # structured_llm = self.chat.with_structured_output(ChecklistResponse, method="function_calling")
        # chain = prompt | structured_llm
        # inputs: Dict[str, Any] = {
        #     "profile_text": profile_text,
        #     "research_content": research_content,
        # }
        # inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["research_content", "profile_text"])
        # result_model = chain.invoke(inputs)
        
        return checklist_items, research_content

    def _gather_research_content(self, profile_text: str) -> str:
        """Run web search + fetch + parse pipeline and return aggregated natural text content.

        Synchronous implementation using the research tools' sync helpers to fit current call sites.
        """
        # Attempt LLM-generated queries; fall back heuristically on failure
        try:
            queries = self.generate_search_queries(profile_text=profile_text, max_queries=5)
        except Exception as e:
            self._append_to_web_log(f"ERROR generate_search_queries: {type(e).__name__}: {e}")
            queries = []
        # if not queries:
        #     queries = self._heuristic_search_queries(profile_text=profile_text, max_queries=5)
        #     self._append_to_web_log(f"FALLBACK heuristic queries used: {json.dumps(queries, ensure_ascii=False)}")

        if not queries:
            self._append_to_research_log("queries", [])
            self._append_to_research_log("note", "No queries generated; skipping research.")
            return ""
        else:
            self._append_to_research_log("queries", queries)

        web = OpenAIWebSearchAPI()
        fetcher = ScrapingFishClient()
        try:
            self._append_to_web_log(
                f"SCRAPINGFISH key_present={'yes' if bool(getattr(fetcher, 'api_key', '')) else 'no'}"
            )
        except Exception:
            pass
        parser = BusinessContentParser()

        aggregated_snippets: List[str] = []
        all_search_results: List[Dict[str, Any]] = []
        all_reranked_for_query: List[Dict[str, Any]] = []
        fetched_any = False

        for q in queries[:2]:  # Reduced from 3 to 2 to save tokens
            try:
                query_text = q.get("text", "")
                self._append_to_web_log(f"SEARCH q='{query_text}'")
                results = web._search_sync(query_text, num_results=3)  # Reduced from 5 to 3
            except Exception as e:
                self._append_to_web_log(f"ERROR web._search_sync: {type(e).__name__}: {e}")
                results = []

            if not results:
                self._append_to_web_log(f"WARNING: No search results for query: {query_text}")
                continue

            # Normalize for rerank
            normalized = [{"title": r.get("title", ""), "url": r.get("link", ""), "snippet": r.get("snippet", "")} for r in results]
            all_search_results.append({"query": q.get("text", ""), "results": normalized})
            
            # Use simple reranking to avoid token burning
            try:
                reranked = self.rerank_results_by_title(q.get("text", ""), normalized, top_k=2)
                if not reranked:
                    self._append_to_web_log(f"WARNING: Rerank returned empty results, using original")
                    reranked = normalized[:2]
            except Exception as e:
                self._append_to_web_log(f"ERROR rerank_results_by_title: {type(e).__name__}: {e}")
                reranked = normalized[:2]
            all_reranked_for_query.append({"query": q.get("text", ""), "reranked": reranked})

            for r in reranked:
                url = r.get("url")
                if not url:
                    continue
                    
                # Hard limit to prevent excessive fetching
                if len(aggregated_snippets) >= 3:  # Reduced from 4 to 3
                    self._append_to_web_log(f"LIMIT: Reached snippet limit, stopping fetch loop")
                    break
                    
                try:
                    # Strip tracking params to reduce errors
                    try:
                        from urllib.parse import urlparse, urlunparse, parse_qsl
                        pu = urlparse(url)
                        clean_q = [(k, v) for (k, v) in parse_qsl(pu.query) if not k.lower().startswith("utm_")]
                        url = urlunparse((pu.scheme, pu.netloc, pu.path, pu.params, "&".join([f"{k}={v}" for k, v in clean_q]), pu.fragment))
                    except Exception:
                        pass
                    self._append_to_web_log(f"FETCH url='{url}' render_js=True timeout=45")
                    page = fetcher._fetch_sync(url, render_js=True, timeout=45)
                    status = getattr(page, "status_code", None)
                    html = getattr(page, "html", "")
                    
                    if not html or len(html.strip()) < 100:
                        self._append_to_web_log(f"WARNING: Empty or minimal HTML from {url}")
                        continue
                        
                    # Log raw HTML (truncate to keep file reasonable)
                    self._append_to_html_log(url=url, status_code=status, html=html)
                    info = parser.extract_business_info(html, url)
                    content = info.get("business_content", "").strip()
                    title = info.get("title") or r.get("title", "")
                    # Log parsed text
                    self._append_to_parsed_log(url=url, title=title, info=info)
                    if content and len(content) > 50:  # Ensure meaningful content
                        snippet = (title + "\n" if title else "") + content
                        aggregated_snippets.append(snippet[:1500])  # Reduced from 2000 to 1500
                        self._append_to_web_log(f"PARSED url='{url}' content_len={len(content)}")
                        fetched_any = True
                    else:
                        self._append_to_web_log(f"WARNING: No meaningful content from {url}")
                except Exception as e:
                    self._append_to_web_log(f"ERROR fetch/parse url='{url}': {str(e)}")
                    continue

            if len(aggregated_snippets) >= 3:  # Reduced from 4 to 3
                break

        # If nothing aggregated, try a domain-level fallback on first good-looking result
        if not aggregated_snippets and all_search_results:
            try:
                self._append_to_web_log("FALLBACK domain fetch starting")
                seed = None
                for sr in all_search_results:
                    items = sr.get("results", [])
                    for it in items:
                        if it.get("url"):
                            seed = it.get("url")
                            break
                    if seed:
                        break
                if seed:
                    from urllib.parse import urlparse, urlunparse
                    parsed = urlparse(seed)
                    base = urlunparse((parsed.scheme or "https", parsed.netloc, "", "", "", ""))
                    candidates = [base, f"{base}/about", f"{base}/services", f"{base}/contact"]
                    for u in candidates:
                        try:
                            self._append_to_web_log(f"FALLBACK FETCH url='{u}' render_js=True timeout=45")
                            page = fetcher._fetch_sync(u, render_js=True, timeout=45)
                            status = getattr(page, "status_code", None)
                            html = getattr(page, "html", "")
                            self._append_to_html_log(url=u, status_code=status, html=html)
                            info = parser.extract_business_info(html, u)
                            title = info.get("title") or ""
                            self._append_to_parsed_log(url=u, title=title, info=info)
                            content = info.get("business_content", "").strip()
                            if content:
                                snippet = (title + "\n" if title else "") + content
                                aggregated_snippets.append(snippet[:2000])
                                fetched_any = True
                        except Exception:
                            self._append_to_web_log(f"ERROR fallback fetch/parse url='{u}'")
                            continue
            except Exception:
                self._append_to_web_log("ERROR during domain fallback")

        # Persist research details
        self._append_to_research_log("search_results", all_search_results)
        self._append_to_research_log("reranked", all_reranked_for_query)
        joined = "\n\n---\n\n".join(aggregated_snippets)
        self._append_to_research_log("aggregated_content_preview", joined[:2000])
        self._append_to_research_log("aggregated_content_full", joined)
        return joined[:6000]

    async def generate_clarifying_question(
        self,
        item: Dict[str, Any],
        research_context: Optional[Dict[str, Any]] = None,
        provider_profile: Optional[Dict[str, Any]] = None,
        checklist: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Generate a concise clarifying question for a checklist item.

        Incorporates provider profile text and any available research context
        (e.g., preliminary answers or findings) to produce a more insightful,
        engaging, and inquisitive question.
        """
        profile_text = (provider_profile or {}).get("profile_text", "")

        # Prepare a compact research summary if provided
        research_text: str = ""
        if isinstance(research_context, dict) and research_context:
            value = research_context.get("value")
            confidence = research_context.get("confidence")
            source = research_context.get("source")
            evidence = research_context.get("evidence")
            # Build a short, readable summary line
            parts = []
            if value:
                parts.append(f"suggested='{value}'")
            if isinstance(confidence, (int, float)):
                parts.append(f"confidence={float(confidence):.2f}")
            if source:
                parts.append(f"source={source}")
            if evidence:
                # Keep evidence concise
                parts.append(f"evidence={str(evidence)[:160]}")
            research_text = ", ".join(parts)
        elif isinstance(research_context, str):
            research_text = research_context[:1200]  # Increased from 400 to accommodate more context

        # Build a compact checklist status summary to guide context
        checklist_summary = ""
        if isinstance(checklist, list) and checklist:
            try:
                total = len(checklist)
                completed = sum(1 for c in checklist if c.get("status") in ["VERIFIED", "AUTO_FILLED"])
                asked = sum(1 for c in checklist if c.get("status") == "ASKED")
                pending = sum(1 for c in checklist if c.get("status") == "PENDING")
                # Show up to 3 pending keys to avoid token bloat
                pending_keys = [c.get("key") for c in checklist if c.get("status") == "PENDING"][:3]
                checklist_summary = f"total={total}, completed={completed}, asked={asked}, pending={pending}, pending_keys={pending_keys}"
            except Exception:
                checklist_summary = "unavailable"

        # Ensure we send a meaningful original prompt to the LLM
        original_prompt = item.get("prompt", "").strip()
        if not original_prompt:
            # Derive from key if missing
            key_text = str(item.get("key", "information")).replace("_", " ").strip().title() or "Information"
            original_prompt = f"Please provide your {key_text}."

        # Format the prompt
        formatted_prompt = (
            "You are crafting a brief, polite clarifying question to collect onboarding info.\n"
            f"Original question: {original_prompt}\n"
            f"Business details: {profile_text}\n"
            f"Checklist status (brief): {checklist_summary or 'N/A'}\n"
            f"Research findings (may be partial): {research_text or 'N/A'}\n\n"
            "Write one engaging, inquisitive, conversational question that asks for the information clearly. "
            "If research suggests an answer, acknowledge it briefly and ask the user to confirm or provide the precise details needed. "
            "Keep it to one sentence."
        )
        
        messages = [{
            "role": "user",
            "content": formatted_prompt
        }]
        
        # Create schema for TextResponse
        schema = TextResponse.model_json_schema()
        
        try:
            # Add timeout protection to prevent hangs
            import asyncio
            
            async def call_with_timeout():
                response = await self._call_ollama_structured_async(messages, schema)
                if response['success']:
                    result = TextResponse(**response['data'])
                    return result.text
                else:
                    raise Exception(f"Ollama call failed: {response.get('error', 'Unknown error')}")
            
            content = await asyncio.wait_for(
                call_with_timeout(),
                timeout=25.0  # 25 second timeout for question generation
            )
            
        except asyncio.TimeoutError:
            print("  ⚠️ Question generation timed out, using fallback")
            content = None
        except Exception as e:
            print(f"  ⚠️ Question generation failed: {str(e)}")
            try:
                self._log_llm_error("generate_clarifying_question", e, formatted_prompt)
            except Exception:
                pass
            content = None
            
        content = self._normalize_text_output(content or ''.strip())
        if not content:
            # Final fallback: synthesize a concise question
            synthesized = original_prompt
            if not synthesized.endswith("?"):
                synthesized = synthesized.rstrip(".") + "?"
            content = synthesized
            
        self._log_interaction("generate_clarifying_question", formatted_prompt, content)
        
        # Original LangChain implementation (commented out for Ollama usage)
        # template = (
        #     "You are crafting a brief, polite clarifying question to collect onboarding info.\n"
        #     "Original question: {original}\n"
        #     "Business details: {profile_text}\n"
        #     "Checklist status (brief): {checklist_summary}\n"
        #     "Research findings (may be partial): {research_text}\n\n"
        #     "Write one engaging, inquisitive, conversational question that asks for the information clearly. "
        #     "If research suggests an answer, acknowledge it briefly and ask the user to confirm or provide the precise details needed. "
        #     "Keep it to one sentence."
        # )
        # prompt = ChatPromptTemplate.from_template(template)
        # structured_llm = self.chat.with_structured_output(TextResponse, method="function_calling")
        # result_msg = await asyncio.wait_for(
        #     (prompt | structured_llm).ainvoke(inputs),
        #     timeout=25.0
        # )
        
        return content

    async def classify_confirmation_decision(
        self,
        user_text: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Classify a user's confirmation response as accepted or rejected using minimal tokens.

        Returns a dict like {"decision": "accepted"|"rejected"}.
        Defaults to rejected on ambiguity.
        """
        # Compact item summary to reduce token usage
        brief_items: List[Dict[str, Any]] = []
        for it in (items or [])[:4]:
            brief_items.append({
                "key": str(it.get("key", ""))[:40],
                "suggested": str(it.get("suggested_answer", ""))[:80]
            })

        formatted_prompt = (
            "You are a strict classifier. Determine if the user ACCEPTS or REJECTS the suggested answers.\n"
            f"User response: {(user_text or '').strip()[:500]}\n"
            f"Items (brief): {json.dumps(brief_items, ensure_ascii=False)}\n\n"
            "Output ONLY minified JSON with keys: decision.\n"
            "Rules: 'accepted' for clear consent (yes/accept/sure/okay). If ambiguous or negative, output 'rejected'."
        )
        
        messages = [{
            "role": "user",
            "content": formatted_prompt
        }]
        
        # Use plain chat model and parse JSON strictly
        try:
            async def call_with_timeout():
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: self._call_ollama_with_tools(messages, tools=None))
                return response.get('content', '').strip() if response['success'] else "{}"
            
            raw = await asyncio.wait_for(call_with_timeout(), timeout=15.0)
        except Exception as e:
            try:
                self._log_llm_error("classify_confirmation_decision", e, formatted_prompt)
            except Exception:
                pass
            raw = "{}"
        # Attempt to extract JSON
        decision = "rejected"
        try:
            parsed = json.loads(raw)
            cand = str(parsed.get("decision", "")).strip().lower()
            if cand in ("accepted", "rejected"):
                decision = cand
            else:
                decision = "rejected"
        except Exception:
            # Try to find a JSON object substring
            try:
                import re as _re
                m = _re.search(r"\{[\s\S]*\}", raw)
                if m:
                    parsed = json.loads(m.group(0))
                    cand = str(parsed.get("decision", "")).strip().lower()
                    if cand in ("accepted", "rejected"):
                        decision = cand
            except Exception:
                decision = "rejected"
        self._log_interaction("classify_confirmation_decision", formatted_prompt, {"raw": raw, "decision": decision})
        
        # Original LangChain implementation (commented out for Ollama usage)
        # template = (
        #     "You are a strict classifier. Determine if the user ACCEPTS or REJECTS the suggested answers.\n"
        #     "User response: {user_text}\n"
        #     "Items (brief): {items_brief}\n\n"
        #     "Output ONLY minified JSON with keys: decision.\n"
        #     "Rules: 'accepted' for clear consent (yes/accept/sure/okay). If ambiguous or negative, output 'rejected'."
        # )
        # prompt = ChatPromptTemplate.from_template(template)
        # inputs = {
        #     "user_text": (user_text or "").strip()[:500],
        #     "items_brief": json.dumps(brief_items, ensure_ascii=False),
        # }
        # inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["user_text", "items_brief"])
        # result_msg = await (prompt | self.chat).ainvoke(inputs)
        # raw = (getattr(result_msg, "content", "") or "").strip()
        
        return {"decision": decision}

    def classify_confirmation_decision_sync(
        self,
        user_text: str,
        items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Synchronous variant for structured accept/reject classification to be usable in sync routes."""
        brief_items: List[Dict[str, Any]] = []
        for it in (items or [])[:4]:
            brief_items.append({
                "key": str(it.get("key", ""))[:40],
                "suggested": str(it.get("suggested_answer", ""))[:80]
            })

        formatted_prompt = (
            "You are a strict classifier. Determine if the user ACCEPTS or REJECTS the suggested answers.\n"
            f"User response: {(user_text or '').strip()[:500]}\n"
            f"Items (brief): {json.dumps(brief_items, ensure_ascii=False)}\n\n"
            "Output ONLY minified JSON with keys: decision.\n"
            "Rules: 'accepted' for clear consent (yes/accept/sure/okay). If ambiguous or negative, output 'rejected'."
        )
        
        messages = [{
            "role": "user",
            "content": formatted_prompt
        }]
        
        try:
            response = self._call_ollama_with_tools(messages, tools=None)
            raw = response.get('content', '').strip() if response['success'] else "{\"decision\": \"rejected\"}"
        except Exception as e:
            try:
                self._log_llm_error("classify_confirmation_decision_sync", e, formatted_prompt)
            except Exception:
                pass
            raw = "{\"decision\": \"rejected\"}"
            
        decision = "rejected"
        try:
            parsed = json.loads(raw)
            cand = str(parsed.get("decision", "")).strip().lower()
            if cand in ("accepted", "rejected"):
                decision = cand
        except Exception:
            try:
                import re as _re
                m = _re.search(r"\{[\s\S]*\}", raw)
                if m:
                    parsed = json.loads(m.group(0))
                    cand = str(parsed.get("decision", "")).strip().lower()
                    if cand in ("accepted", "rejected"):
                        decision = cand
            except Exception:
                decision = "rejected"
                
        self._log_interaction("classify_confirmation_decision_sync", formatted_prompt, {"raw": raw, "decision": decision})
        
        # Original LangChain implementation (commented out for Ollama usage)
        # template = (
        #     "You are a strict classifier. Determine if the user ACCEPTS or REJECTS the suggested answers.\n"
        #     "User response: {user_text}\n"
        #     "Items (brief): {items_brief}\n\n"
        #     "Output ONLY minified JSON with keys: decision.\n"
        #     "Rules: 'accepted' for clear consent (yes/accept/sure/okay). If ambiguous or negative, output 'rejected'."
        # )
        # prompt = ChatPromptTemplate.from_template(template)
        # inputs = {
        #     "user_text": (user_text or "").strip()[:500],
        #     "items_brief": json.dumps(brief_items, ensure_ascii=False),
        # }
        # inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["user_text", "items_brief"])
        # result_msg = (prompt | self.chat).invoke(inputs)
        # raw = (getattr(result_msg, "content", "") or "").strip()
        
        return {"decision": decision}

    async def extract_checklist_modifications(
        self,
        research_content: str,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract checklist modifications from research content as structured JSON."""
        formatted_prompt = (
            "Analyze the research then extract checklist modifications based on current checklist and the research content about the business and industry.\n"
            f"Content: {research_content}\n\n"
            "Keep response minimal."
        )
        
        messages = [{
            "role": "user",
            "content": formatted_prompt
        }]
        
        # Create schema for ExtractChecklistModificationsResponse
        schema = ExtractChecklistModificationsResponse.model_json_schema()
        
        # Add timeout and retry protection for async calls
        result = None
        last_err: Optional[Exception] = None
        
        # Shorter timeout for this specific call to prevent workflow hangs
        import asyncio
        for attempt in range(2):  # Only 2 attempts
            try:
                # Use asyncio.wait_for to add an additional timeout layer
                async def call_with_timeout():
                    response = await self._call_ollama_structured_async(messages, schema)
                    if response['success']:
                        return ExtractChecklistModificationsResponse(**response['data']).model_dump()
                    else:
                        raise Exception(f"Ollama call failed: {response.get('error', 'Unknown error')}")
                
                result = await asyncio.wait_for(
                    call_with_timeout(), 
                    timeout=45.0  # 45 second timeout for checklist modifications
                )
                print(f"  ✅ LLM call completed successfully on attempt {attempt + 1}")
                break
                
            except asyncio.TimeoutError:
                last_err = Exception("LLM call timed out after 45 seconds")
                print(f"  ⚠️ LLM call timed out on attempt {attempt + 1}")
                try:
                    self._log_llm_error("extract_checklist_modifications", last_err, formatted_prompt)
                except Exception:
                    pass
                continue
            except Exception as e:
                last_err = e
                print(f"  ⚠️ LLM call failed on attempt {attempt + 1}: {str(e)}")
                try:
                    self._log_llm_error("extract_checklist_modifications", e, formatted_prompt)
                except Exception:
                    pass
                continue
        
        if result is None:
            print(f"  ❌ All LLM attempts failed, using fallback empty modifications")
            result = {"mandatory_additions": [], "recommended_additions": [], "items_to_remove": []}
            
        self._log_interaction("extract_checklist_modifications", formatted_prompt, result)
        
        # Original LangChain implementation (commented out for Ollama usage)
        # template = (
        #     "Analyze the research then extract checklist modifications based on current checklist and the research content about the business and industry.\n"
        #     "Content: {content}\n\n"
        #     "Keep response minimal."
        # )
        # prompt = ChatPromptTemplate.from_template(template)
        # structured_llm = self.chat.with_structured_output(ExtractChecklistModificationsResponse, method="function_calling")
        # chain = prompt | structured_llm
        # result_model = await asyncio.wait_for(chain.ainvoke(inputs), timeout=45.0)
        # result = result_model.model_dump()
        return {
            "mandatory_additions": result.get("mandatory_additions", []),
            "recommended_additions": result.get("recommended_additions", []),
            "items_to_remove": result.get("items_to_remove", []),
            "raw_response": json.dumps(result),
        }

    async def extract_answer_from_content(
        self,
        content: str,
        question: str
    ) -> Dict[str, Any]:
        """Extract a specific answer and confidence from provided content."""
        formatted_prompt = (
            "Extract a direct answer to the question from the business content.\n"
            f"Question: {question}\n\n"
            f"Business content (may be truncated):\n{content}\n\n"
        )
        
        messages = [{
            "role": "user",
            "content": formatted_prompt
        }]
        
        # Create schema for ExtractAnswerFromContentResponse
        schema = ExtractAnswerFromContentResponse.model_json_schema()
        
        result = None
        last_err = None
        import asyncio
        
        for attempt in range(2):  # Only 2 attempts
            try:
                # Add timeout protection
                async def call_with_timeout():
                    response = await self._call_ollama_structured_async(messages, schema)
                    if response['success']:
                        return ExtractAnswerFromContentResponse(**response['data']).model_dump()
                    else:
                        raise Exception(f"Ollama call failed: {response.get('error', 'Unknown error')}")
                
                result = await asyncio.wait_for(
                    call_with_timeout(),
                    timeout=25.0  # 25 second timeout for answer extraction
                )
                break
                
            except asyncio.TimeoutError:
                last_err = Exception("extract_answer_from_content timed out")
                print(f"  ⚠️ Answer extraction timed out on attempt {attempt + 1}")
                try:
                    self._log_llm_error("extract_answer_from_content", last_err, formatted_prompt)
                except Exception:
                    pass
                continue
            except Exception as e:
                last_err = e
                print(f"  ⚠️ Answer extraction failed on attempt {attempt + 1}: {str(e)}")
                try:
                    self._log_llm_error("extract_answer_from_content", e, formatted_prompt)
                except Exception:
                    pass
                continue
                
        if result is None:
            result = {"value": "", "confidence": 0.0, "source": "", "evidence": ""}
            
        self._log_interaction("extract_answer_from_content", formatted_prompt, result)
        
        # Original LangChain implementation (commented out for Ollama usage)
        # template = (
        #     "Extract a direct answer to the question from the business content.\n"
        #     "Question: {question}\n\n"
        #     "Business content (may be truncated):\n{content}\n\n"
        # )
        # prompt = ChatPromptTemplate.from_template(template)
        # structured_llm = self.chat.with_structured_output(ExtractAnswerFromContentResponse, method="function_calling")
        # chain = prompt | structured_llm
        # inputs = {
        #     "question": question,
        #     "content": content,
        # }
        # inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["content"])
        # result_model = await asyncio.wait_for(chain.ainvoke(inputs), timeout=25.0)
        # result = result_model.model_dump()
        
        return {
            "value": result.get("value", ""),
            "confidence": float(result.get("confidence", 0.0) or 0.0),
            "source": result.get("source", ""),
            "evidence": result.get("evidence", ""),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def generate_confirmation_message(self, confirmation_items: List[Dict[str, Any]]) -> str:
        """Generate a friendly confirmation message for medium-confidence findings."""
        if not confirmation_items:
            return "No items to confirm."
            
        items_text = "\n".join([
            f"- {item['question']}: {item['suggested_answer']}" for item in confirmation_items
        ])
        
        formatted_prompt = (
            "Draft a short, friendly confirmation message summarizing these findings and asking the user to confirm.\n"
            f"Items:\n{items_text}\n"
        )
        
        messages = [{
            "role": "user",
            "content": formatted_prompt
        }]
        
        try:
            import asyncio
            
            async def call_with_timeout():
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: self._call_ollama_with_tools(messages, tools=None))
                if response['success']:
                    return response['content'].strip()
                else:
                    raise Exception(f"Ollama call failed: {response.get('error', 'Unknown error')}")
            
            content = await asyncio.wait_for(
                call_with_timeout(),
                timeout=20.0  # 20 second timeout for confirmation message
            )
            content = self._normalize_text_output(content)
            
        except asyncio.TimeoutError:
            print("  ⚠️ Confirmation message generation timed out, using fallback")
            content = "Please review the items above and confirm or provide corrections."
        except Exception as e:
            print(f"  ⚠️ Confirmation message generation failed: {str(e)}")
            try:
                self._log_llm_error("generate_confirmation_message", e, formatted_prompt)
            except Exception:
                pass
            content = "Please review the items above and confirm or provide corrections."
            
        self._log_interaction("generate_confirmation_message", formatted_prompt, content)
        
        # Original LangChain implementation (commented out for Ollama usage)
        # template = (
        #     "Draft a short, friendly confirmation message summarizing these findings and asking the user to confirm.\n"
        #     "Items:\n{items}\n"
        # )
        # prompt = ChatPromptTemplate.from_template(template)
        # inputs = {"items": items_text}
        # inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["items"])
        # result_msg = await asyncio.wait_for(
        #     (prompt | self.chat).ainvoke(inputs),
        #     timeout=20.0
        # )
        # content = self._normalize_text_output(result_msg.content.strip())
        
        return content

    async def generate_profile_summary(
        self,
        profile_text: str,
        checklist_data: List[Dict[str, Any]]
    ) -> str:
        """Generate a comprehensive profile summary from checklist responses and profile text.
        
        Args:
            profile_text: Original provider profile information
            checklist_data: List of completed checklist items with questions and answers
            
        Returns:
            Comprehensive profile summary string
        """
        # Format checklist data for the prompt
        formatted_checklist = []
        for item in checklist_data:
            if item.get("status") in ["VERIFIED", "AUTO_FILLED"] and item.get("value"):
                formatted_checklist.append({
                    "question": item.get("prompt", ""),
                    "answer": item.get("value", ""),
                    "key": item.get("key", ""),
                    "status": item.get("status", "")
                })
        
        # Convert to readable format for the prompt
        checklist_text = ""
        for i, item in enumerate(formatted_checklist, 1):
            checklist_text += f"{i}. {item['question']}\n   Answer: {item['answer']}\n\n"
        
        template_str = self._read_prompt(self._profile_summary_prompt_path)
        formatted_prompt = template_str.format(
            profile_text=profile_text,
            checklist_data=checklist_text
        )
        
        messages = [{
            "role": "user",
            "content": formatted_prompt
        }]
        
        # Create schema for ProfileSummaryResponse
        schema = ProfileSummaryResponse.model_json_schema()
        
        # Execute with retry logic and timeout protection
        result_model: Optional[ProfileSummaryResponse] = None
        last_err: Optional[Exception] = None
        
        import asyncio
        for attempt in range(2):  # 2 attempts
            try:
                async def call_with_timeout():
                    response = await self._call_ollama_structured_async(messages, schema)
                    if response['success']:
                        return ProfileSummaryResponse(**response['data'])
                    else:
                        raise Exception(f"Ollama call failed: {response.get('error', 'Unknown error')}")
                
                result_model = await asyncio.wait_for(
                    call_with_timeout(),
                    timeout=60.0  # 60 second timeout for profile summary generation
                )
                print(f"  ✅ Profile summary generated successfully on attempt {attempt + 1}")
                break
                
            except asyncio.TimeoutError:
                last_err = Exception("Profile summary generation timed out after 60 seconds")
                print(f"  ⚠️ Profile summary generation timed out on attempt {attempt + 1}")
                try:
                    self._log_llm_error("generate_profile_summary", last_err, formatted_prompt)
                except Exception:
                    pass
                continue
            except Exception as e:
                last_err = e
                print(f"  ⚠️ Profile summary generation failed on attempt {attempt + 1}: {str(e)}")
                try:
                    self._log_llm_error("generate_profile_summary", e, formatted_prompt)
                except Exception:
                    pass
                continue
        
        if result_model is None:
            print("  ❌ All profile summary generation attempts failed, using fallback")
            # Provide fallback summary
            completed_count = len(formatted_checklist)
            fallback_summary = f"Profile Summary: Service provider with {completed_count} completed onboarding items. " + \
                             "Please contact the provider directly for detailed information about their services and capabilities."
            result_model = ProfileSummaryResponse(summary=fallback_summary)
        
        # Log the interaction
        response_content = result_model.summary
        self._log_interaction("generate_profile_summary", formatted_prompt, response_content)
        
        # Original LangChain implementation (commented out for Ollama usage)
        # template_str = self._read_prompt(self._profile_summary_prompt_path)
        # prompt = ChatPromptTemplate.from_template(template_str)
        # structured_llm = self.chat.with_structured_output(ProfileSummaryResponse, method="function_calling")
        # chain = prompt | structured_llm
        # inputs = {
        #     "profile_text": profile_text,
        #     "checklist_data": checklist_text
        # }
        # inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["profile_text", "checklist_data"])
        # result_model = await asyncio.wait_for(chain.ainvoke(inputs), timeout=60.0)
        
        return response_content

    def generate_search_queries(
        self,
        profile_text: str,
        max_queries: int = 3,
    ) -> List[Dict[str, str]]:
        """Generate targeted web search queries for discovering provider pages/results from a single profile_text input."""
        template_str = self._read_prompt(self._generate_search_queries_prompt_path)
        formatted_prompt = template_str.format(profile_text=profile_text)
        
        messages = [{
            "role": "user",
            "content": formatted_prompt
        }]
        
        # Create schema for GenerateSearchQueriesResponse
        schema = GenerateSearchQueriesResponse.model_json_schema()
        
        try:
            response = self._call_ollama_structured(messages, schema)
            
            if response['success']:
                result_model = GenerateSearchQueriesResponse(**response['data'])
                result = result_model.model_dump()
            else:
                raise Exception(f"Ollama call failed: {response.get('error', 'Unknown error')}")
                
        except Exception as e:
            try:
                self._log_llm_error("generate_search_queries", e, formatted_prompt)
            except Exception:
                pass
            raise
            
        self._log_interaction("generate_search_queries", formatted_prompt, result)
        
        items = []
        for q in result.get("queries", []):
            try:
                sq = SearchQuery.model_validate(q)
                items.append({"text": sq.text, "intent": sq.intent})
            except Exception:
                if isinstance(q, dict) and q.get("text"):
                    items.append({"text": str(q.get("text")), "intent": str(q.get("intent", "provider_discovery"))})
        
        # Original LangChain implementation (commented out for Ollama usage)
        # template_str = self._read_prompt(self._generate_search_queries_prompt_path)
        # prompt = ChatPromptTemplate.from_template(template_str)
        # structured_llm = self.chat.with_structured_output(GenerateSearchQueriesResponse, method="function_calling")
        # chain = prompt | structured_llm
        # inputs = {"profile_text": profile_text}
        # inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["profile_text"])
        # result_model = chain.invoke(inputs)
        # result = result_model.model_dump()
        
        return items[:max_queries]

    def rerank_results_by_title(
        self,
        query: str,
        results: List[Dict[str, Any]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Rerank results by title relevance using LLM guidance.

        Expects results as list of {title, url, snippet} and returns the same list
        ordered by descending relevance. Falls back to simple lexical scoring if LLM fails.
        """
        if not results:
            return []

        # Baseline lexical score for fallback
        def lexical_score(title: str, q: str) -> float:
            title_lower = (title or "").lower()
            words = [w for w in q.lower().split() if len(w) > 2]
            if not words:
                return 0.0
            matches = sum(1 for w in words if w in title_lower)
            return matches / len(words)

        baseline = [
            {**r, "_lex": lexical_score(r.get("title", ""), query)} for r in results
        ]

        # Skip LLM reranking for now to avoid token burning and use simple lexical scoring
        # TODO: Fix LLM reranking later if needed
        ordered = sorted(baseline, key=lambda r: r.get("_lex", 0.0), reverse=True)
        
        # Log the fallback usage
        try:
            self._append_to_web_log(f"RERANK fallback lexical scoring for query='{query}' results={len(results)}")
        except Exception:
            pass

        # Trim and return without internal fields
        trimmed = [{k: v for k, v in r.items() if not k.startswith("_")} for r in ordered[:top_k]]
        return trimmed

    def _read_prompt(self, path: Path) -> str:
        with path.open("r", encoding="utf-8") as f:
            return f.read()

    def _normalize_checklist_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        normalized: Dict[str, Any] = {
            "key": str(item.get("key", "")).strip(),
            "prompt": str(item.get("prompt", "")).strip(),
            "required": bool(item.get("required", True)),
            "status": "PENDING",
            "value": None,
        }
        return normalized

    # ------------------------- Token + Logging Utilities -------------------------
    def _get_token_encoder(self):
        if tiktoken is None:
            return None
        try:
            return tiktoken.encoding_for_model(self.model_name)
        except Exception:
            try:
                return tiktoken.get_encoding("cl100k_base")
            except Exception:
                return None

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken when available; fallback to heuristic."""
        if not text:
            return 0
        enc = self._get_token_encoder()
        if enc is not None:
            try:
                return len(enc.encode(text))
            except Exception:
                pass
        # Heuristic fallback: ~4 chars per token
        return max(1, len(text) // 4)

    def _truncate_to_tokens(self, text: str, max_tokens: int) -> str:
        if not text:
            return text
        # Fast path using length heuristic
        approx_ratio = max_tokens / max(self._count_tokens(text), 1)
        if approx_ratio >= 1.0:
            return text
        new_len = max(200, int(len(text) * approx_ratio))
        return text[:new_len]

    def _format_prompt(self, prompt_template: str, inputs: Dict[str, Any]) -> str:
        """Format prompt template with inputs for logging (Ollama version)"""
        try:
            # Simple string formatting for Ollama
            return prompt_template.format(**inputs)
        except Exception:
            return json.dumps(inputs, ensure_ascii=False)
    
    # Original LangChain _format_prompt method (commented out for Ollama usage)
    # def _format_prompt(self, prompt: ChatPromptTemplate, inputs: Dict[str, Any]) -> str:
    #     try:
    #         # Render to a string view for logging using LangChain formatting
    #         messages = prompt.format_messages(**inputs)
    #         rendered = []
    #         for m in messages:
    #             role = getattr(m, "type", getattr(m, "role", "message"))
    #             rendered.append(f"[{role}]\n{getattr(m, 'content', '')}")
    #         return "\n\n".join(rendered)
    #     except Exception:
    #         return json.dumps(inputs, ensure_ascii=False)

    def _fit_inputs_to_limit(
        self,
        prompt_template: str,
        inputs: Dict[str, Any],
        keys_to_truncate: List[str]
    ) -> Tuple[Dict[str, Any], str]:
        """Ensure the formatted prompt fits within token limit by truncating provided keys (Ollama version)."""
        safe_inputs = dict(inputs)
        formatted = self._format_prompt(prompt_template, safe_inputs)
        if self._count_tokens(formatted) <= self.max_input_tokens:
            return safe_inputs, formatted
        # Iteratively truncate fields in order
        for key in keys_to_truncate:
            if key in safe_inputs and isinstance(safe_inputs[key], str):
                # Gradually shrink until under limit or very small
                for _ in range(6):
                    safe_inputs[key] = self._truncate_to_tokens(str(safe_inputs[key]), int(self.max_input_tokens * 0.6))
                    formatted = self._format_prompt(prompt_template, safe_inputs)
                    if self._count_tokens(formatted) <= self.max_input_tokens:
                        return safe_inputs, formatted
        # Final fallback: hard truncate the fully formatted text for logging, but send best-effort inputs
        return safe_inputs, formatted[: min(len(formatted), 120000)]
    
    # Original LangChain _fit_inputs_to_limit method (commented out for Ollama usage)
    # def _fit_inputs_to_limit(
    #     self,
    #     prompt: ChatPromptTemplate,
    #     inputs: Dict[str, Any],
    #     keys_to_truncate: List[str]
    # ) -> Tuple[Dict[str, Any], str]:
    #     """Ensure the formatted prompt fits within token limit by truncating provided keys."""
    #     safe_inputs = dict(inputs)
    #     formatted = self._format_prompt(prompt, safe_inputs)
    #     if self._count_tokens(formatted) <= self.max_input_tokens:
    #         return safe_inputs, formatted
    #     # Iteratively truncate fields in order
    #     for key in keys_to_truncate:
    #         if key in safe_inputs and isinstance(safe_inputs[key], str):
    #             # Gradually shrink until under limit or very small
    #             for _ in range(6):
    #                 safe_inputs[key] = self._truncate_to_tokens(str(safe_inputs[key]), int(self.max_input_tokens * 0.6))
    #                 formatted = self._format_prompt(prompt, safe_inputs)
    #                 if self._count_tokens(formatted) <= self.max_input_tokens:
    #                     return safe_inputs, formatted
    #     # Final fallback: hard truncate the fully formatted text for logging, but send best-effort inputs
    #     return safe_inputs, formatted[: min(len(formatted), 120000)]

    def _log_interaction(self, label: str, prompt_text: str, response: Any) -> None:
        try:
            with self._log_path.open("a", encoding="utf-8") as f:
                f.write(f"## {label} @ {datetime.utcnow().isoformat()}Z\n")
                f.write("--- PROMPT ---\n")
                f.write(prompt_text if isinstance(prompt_text, str) else json.dumps(prompt_text, ensure_ascii=False))
                f.write("\n\n--- RESPONSE ---\n")
                if hasattr(response, "content"):
                    f.write(str(response.content))
                else:
                    f.write(json.dumps(response, ensure_ascii=False))
                f.write("\n\n==============================\n\n")
        except Exception:
            pass

    def _log_llm_error(self, label: str, error: Exception, context: Optional[str] = None) -> None:
        """Log exceptions from LLM calls to a dedicated file for diagnosis."""
        try:
            with self._llm_error_log_path.open("a", encoding="utf-8") as f:
                f.write(f"## {label} ERROR @ {datetime.utcnow().isoformat()}Z\n")
                f.write(f"model={self.model_name}\n")
                f.write(f"error_type={type(error).__name__}\n")
                try:
                    msg = str(error)
                except Exception:
                    msg = "<unprintable error>"
                f.write(f"error_message={msg}\n")
                if context:
                    # Truncate overly long context to keep file small
                    ctx = context if isinstance(context, str) else json.dumps(context, ensure_ascii=False)
                    f.write("--- CONTEXT ---\n")
                    f.write(ctx[:8000])
                    f.write("\n")
                f.write("--- TRACEBACK ---\n")
                f.write(traceback.format_exc())
                f.write("\n\n")
        except Exception:
            pass

    # ------------------------- Research/Web Logging Helpers -------------------------
    def _reset_research_logs(self, workflow_label: str, profile_text: str) -> None:
        """Refresh the research and web logs for each new workflow run."""
        try:
            with self._research_log_path.open("w", encoding="utf-8") as f:
                f.write(f"# Research Content Log\n# Workflow: {workflow_label}\n# Started: {datetime.utcnow().isoformat()}Z\n\n")
                f.write("[profile_text_preview]\n")
                f.write((profile_text or "")[:1000])
                f.write("\n\n")
        except Exception:
            pass
        try:
            with self._web_requests_log_path.open("w", encoding="utf-8") as f:
                f.write(f"# Web Requests Log\n# Workflow: {workflow_label}\n# Started: {datetime.utcnow().isoformat()}Z\n\n")
        except Exception:
            pass
        try:
            with self._html_log_path.open("w", encoding="utf-8") as f:
                f.write(f"# Raw HTML Log\n# Workflow: {workflow_label}\n# Started: {datetime.utcnow().isoformat()}Z\n\n")
        except Exception:
            pass
        try:
            with self._parsed_html_log_path.open("w", encoding="utf-8") as f:
                f.write(f"# Parsed HTML Log\n# Workflow: {workflow_label}\n# Started: {datetime.utcnow().isoformat()}Z\n\n")
        except Exception:
            pass
        try:
            # Also refresh LLM error log for this workflow run
            with self._llm_error_log_path.open("w", encoding="utf-8") as f:
                f.write(f"# LLM Error Log\n# Workflow: {workflow_label}\n# Started: {datetime.utcnow().isoformat()}Z\n\n")
        except Exception:
            pass

    def _append_to_research_log(self, section: str, data: Any) -> None:
        try:
            with self._research_log_path.open("a", encoding="utf-8") as f:
                f.write(f"## {section} @ {datetime.utcnow().isoformat()}Z\n")
                if isinstance(data, str):
                    f.write(data)
                else:
                    f.write(json.dumps(data, ensure_ascii=False, indent=2))
                f.write("\n\n")
        except Exception:
            pass

    def _append_to_web_log(self, message: str) -> None:
        try:
            with self._web_requests_log_path.open("a", encoding="utf-8") as f:
                f.write(f"{datetime.utcnow().isoformat()}Z | {message}\n")
        except Exception:
            pass

    def _append_to_html_log(self, url: str, status_code: Optional[int], html: str, max_chars: int = 200000) -> None:
        try:
            with self._html_log_path.open("a", encoding="utf-8") as f:
                f.write(f"## URL: {url}\nSTATUS: {status_code}\nLENGTH: {len(html)}\n")
                f.write("--- HTML START ---\n")
                f.write(html[:max_chars])
                f.write("\n--- HTML END ---\n\n")
        except Exception:
            pass

    def _append_to_parsed_log(self, url: str, title: str, info: Dict[str, Any]) -> None:
        try:
            with self._parsed_html_log_path.open("a", encoding="utf-8") as f:
                headings = info.get("headings", [])
                paragraphs = info.get("paragraphs", [])
                text = info.get("business_content", "")
                f.write(f"## URL: {url}\nTITLE: {title}\nHEADINGS: {len(headings)}\nPARAGRAPHS: {len(paragraphs)}\nTEXT_LEN: {len(text)}\n\n")
                preview = text[:2000]
                f.write(preview)
                f.write("\n\n")
        except Exception:
            pass

    def _heuristic_search_queries(self, profile_text: str, max_queries: int = 3) -> List[Dict[str, str]]:
        """Generate simple heuristic queries when LLM-based generation fails."""
        text = profile_text or ""
        # Try to extract company name
        name_match = re.search(r"Company Name:\s*(.+)", text, re.IGNORECASE)
        name = (name_match.group(1).strip() if name_match else "").split("\n")[0]
        if not name:
            # Fallback to first sentence
            name = (text[:120] or "provider").strip()
        # Try to extract domain
        domain_match = re.search(r"https?://([\w\.-]+)", text)
        domain = domain_match.group(1).strip() if domain_match else ""
        candidates: List[str] = []
        if name:
            candidates.append(f'"{name}" official site')
            candidates.append(f"{name} services")
            candidates.append(f"{name} contact")
            candidates.append(f"{name} pricing")
        if domain:
            candidates.append(f"site:{domain} about")
            candidates.append(f"site:{domain} services")
            candidates.append(f"site:{domain} contact")
        # Deduplicate while preserving order
        seen = set()
        queries: List[Dict[str, str]] = []
        for q in candidates:
            if q and q not in seen:
                seen.add(q)
                queries.append({"text": q, "intent": "provider_discovery"})
            if len(queries) >= max_queries:
                break
        return queries

    def _normalize_text_output(self, text: str) -> str:
        """Clean up common formatting artifacts in LLM text outputs.

        - Strip enclosing single or double quotes when the entire content is quoted.
        - Trim whitespace.
        """
        if not text:
            return text
        cleaned = text.strip()
        if (cleaned.startswith('"') and cleaned.endswith('"')) or (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1].strip()
        return cleaned