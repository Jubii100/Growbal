"""
LLM Wrapper for Onboarding System
Production-ready LangChain + OpenAI implementation
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

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
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
    """Specialized LLM wrapper for onboarding tasks using LangChain and OpenAI."""
    
    def __init__(self, model_name: str = "gpt-5", temperature: float = 0.0, token_limit: int = 32768, timeout: int = 180, max_retries: int = 1):
        self.model_name = model_name
        self.temperature = temperature
        # Add basic reliability controls
        self.chat = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            timeout=timeout,
            max_retries=max_retries,
        )
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

        template_str = self._read_prompt(self._initial_checklist_prompt_path)
        prompt = ChatPromptTemplate.from_template(template_str)
        # Enforce typed output with Pydantic model
        # Use function_calling to reduce schema sensitivity and avoid OpenAI response_format errors
        structured_llm = self.chat.with_structured_output(ChecklistResponse, method="function_calling")
        chain = prompt | structured_llm
        inputs: Dict[str, Any] = {
            "profile_text": profile_text,
            "research_content": research_content,
        }
        inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["research_content", "profile_text"])
        # Retry wrapper for sync invoke
        result_model: Optional[ChecklistResponse] = None
        last_err: Optional[Exception] = None
        for _ in range(1 + 1):  # one extra attempt beyond internal retries
            try:
                result_model = chain.invoke(inputs)
                break
            except Exception as e:
                last_err = e
                try:
                    self._log_llm_error("generate_initial_checklist", e, formatted_text)
                except Exception:
                    pass
                continue
        if result_model is None and last_err is not None:
            # Fallback to empty structure
            result_model = ChecklistResponse(checklist=[])
        # Log the structured response
        self._log_interaction("generate_initial_checklist", formatted_text, result_model.model_dump())
        checklist_items = [item.model_dump() for item in result_model.checklist]
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

        template = (
            "You are crafting a brief, polite clarifying question to collect onboarding info.\n"
            "Original question: {original}\n"
            "Business details: {profile_text}\n"
            "Checklist status (brief): {checklist_summary}\n"
            "Research findings (may be partial): {research_text}\n\n"
            "Write one engaging, inquisitive, conversational question that asks for the information clearly. "
            "If research suggests an answer, acknowledge it briefly and ask the user to confirm or provide the precise details needed. "
            "Keep it to one sentence."
        )
        prompt = ChatPromptTemplate.from_template(template)
        # Ensure we send a meaningful original prompt to the LLM
        original_prompt = item.get("prompt", "").strip()
        if not original_prompt:
            # Derive from key if missing
            key_text = str(item.get("key", "information")).replace("_", " ").strip().title() or "Information"
            original_prompt = f"Please provide your {key_text}."

        inputs = {
            "original": original_prompt,
            "profile_text": profile_text,
            "research_text": research_text or "N/A",
            "checklist_summary": checklist_summary or "N/A",
        }
        # Do not truncate the original question field to avoid empty outputs
        inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["research_text", "profile_text"])
        structured_llm = self.chat.with_structured_output(TextResponse, method="function_calling")
        try:
            # Add timeout protection to prevent hangs
            import asyncio
            result_msg = await asyncio.wait_for(
                (prompt | structured_llm).ainvoke(inputs),
                timeout=25.0  # 25 second timeout for question generation
            )
        except asyncio.TimeoutError:
            print("  Question generation timed out, using fallback")
            result_msg = None
        except Exception as e:
            print(f"  Question generation failed: {str(e)}")
            try:
                self._log_llm_error("generate_clarifying_question", e, formatted_text)
            except Exception:
                pass
            result_msg = None
        content = self._normalize_text_output((getattr(result_msg, 'text', '') if result_msg is not None else '') or ''.strip())
        if not content:
            # Final fallback: synthesize a concise question
            synthesized = original_prompt
            if not synthesized.endswith("?"):
                synthesized = synthesized.rstrip(".") + "?"
            content = synthesized
        self._log_interaction("generate_clarifying_question", formatted_text, content)
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

        template = (
            "You are a strict classifier. Determine if the user ACCEPTS or REJECTS the suggested answers.\n"
            "User response: {user_text}\n"
            "Items (brief): {items_brief}\n\n"
            "Output ONLY minified JSON with keys: decision.\n"
            "Rules: 'accepted' for clear consent (yes/accept/sure/okay). If ambiguous or negative, output 'rejected'."
        )
        prompt = ChatPromptTemplate.from_template(template)
        inputs = {
            "user_text": (user_text or "").strip()[:500],
            "items_brief": json.dumps(brief_items, ensure_ascii=False),
        }
        # Small input; no need for heavy truncation but keep the same utility
        inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["user_text", "items_brief"])
        # Use plain chat model and parse JSON strictly
        try:
            result_msg = await (prompt | self.chat).ainvoke(inputs)
            raw = (getattr(result_msg, "content", "") or "").strip()
        except Exception as e:
            try:
                self._log_llm_error("classify_confirmation_decision", e, formatted_text)
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
        self._log_interaction("classify_confirmation_decision", formatted_text, {"raw": raw, "decision": decision})
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

        template = (
            "You are a strict classifier. Determine if the user ACCEPTS or REJECTS the suggested answers.\n"
            "User response: {user_text}\n"
            "Items (brief): {items_brief}\n\n"
            "Output ONLY minified JSON with keys: decision.\n"
            "Rules: 'accepted' for clear consent (yes/accept/sure/okay). If ambiguous or negative, output 'rejected'."
        )
        prompt = ChatPromptTemplate.from_template(template)
        inputs = {
            "user_text": (user_text or "").strip()[:500],
            "items_brief": json.dumps(brief_items, ensure_ascii=False),
        }
        inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["user_text", "items_brief"])
        try:
            result_msg = (prompt | self.chat).invoke(inputs)
            raw = (getattr(result_msg, "content", "") or "").strip()
        except Exception as e:
            try:
                self._log_llm_error("classify_confirmation_decision_sync", e, formatted_text)
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
        self._log_interaction("classify_confirmation_decision_sync", formatted_text, {"raw": raw, "decision": decision})
        return {"decision": decision}

    async def extract_checklist_modifications(
        self,
        research_content: str,
        location: Optional[str] = None
    ) -> Dict[str, Any]:
        """Extract checklist modifications from research content as structured JSON."""
        template = (
            "Analyze the research then extract checklist modifications based on current checklist and the research content about the business and industry.\n"
            "Content: {content}\n\n"
            "Keep response minimal."
        )
        prompt = ChatPromptTemplate.from_template(template)
        structured_llm = self.chat.with_structured_output(ExtractChecklistModificationsResponse, method="function_calling")
        chain = prompt | structured_llm
        inputs = {
            "content": truncated_content,
        }
        inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["content"])
        # Add timeout and retry protection for async calls
        result = None
        last_err: Optional[Exception] = None
        
        # Shorter timeout for this specific call to prevent workflow hangs
        import asyncio
        for attempt in range(2):  # Only 2 attempts
            try:
                # Use asyncio.wait_for to add an additional timeout layer
                result_model = await asyncio.wait_for(
                    chain.ainvoke(inputs), 
                    timeout=45.0  # 45 second timeout for checklist modifications
                )
                result = result_model.model_dump()
                print(f"  LLM call completed successfully on attempt {attempt + 1}")
                break
            except asyncio.TimeoutError:
                last_err = Exception("LLM call timed out after 20 seconds")
                print(f"  LLM call timed out on attempt {attempt + 1}")
                try:
                    self._log_llm_error("extract_checklist_modifications", last_err, formatted_text)
                except Exception:
                    pass
                continue
            except Exception as e:
                last_err = e
                print(f"  LLM call failed on attempt {attempt + 1}: {str(e)}")
                try:
                    self._log_llm_error("extract_checklist_modifications", e, formatted_text)
                except Exception:
                    pass
                continue
        
        if result is None:
            print(f"  All LLM attempts failed, using fallback empty modifications")
            result = {"mandatory_additions": [], "recommended_additions": [], "items_to_remove": []}
        self._log_interaction("extract_checklist_modifications", formatted_text, result)
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
        template = (
            "Extract a direct answer to the question from the business content.\n"
            "Question: {question}\n\n"
            "Business content (may be truncated):\n{content}\n\n"
        )
        prompt = ChatPromptTemplate.from_template(template)
        structured_llm = self.chat.with_structured_output(ExtractAnswerFromContentResponse, method="function_calling")
        chain = prompt | structured_llm
        inputs = {
            "question": question,
            "content": content,
        }
        # Prefer keeping the question intact; only truncate content
        inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["content"])        
        result = None
        last_err = None
        import asyncio
        for attempt in range(2):  # Only 2 attempts
            try:
                # Add timeout protection
                result_model = await asyncio.wait_for(
                    chain.ainvoke(inputs),
                    timeout=25.0  # 25 second timeout for answer extraction
                )
                result = result_model.model_dump()
                break
            except asyncio.TimeoutError:
                last_err = Exception("extract_answer_from_content timed out")
                print(f"  Answer extraction timed out on attempt {attempt + 1}")
                try:
                    self._log_llm_error("extract_answer_from_content", last_err, formatted_text)
                except Exception:
                    pass
                continue
            except Exception as e:
                last_err = e
                print(f"  Answer extraction failed on attempt {attempt + 1}: {str(e)}")
                try:
                    self._log_llm_error("extract_answer_from_content", e, formatted_text)
                except Exception:
                    pass
                continue
        if result is None:
            result = {"value": "", "confidence": 0.0, "source": "", "evidence": ""}
        self._log_interaction("extract_answer_from_content", formatted_text, result)
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
        template = (
            "Draft a short, friendly confirmation message summarizing these findings and asking the user to confirm.\n"
            "Items:\n{items}\n"
        )
        prompt = ChatPromptTemplate.from_template(template)
        inputs = {"items": items_text}
        inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["items"])
        try:
            import asyncio
            result_msg = await asyncio.wait_for(
                (prompt | self.chat).ainvoke(inputs),
                timeout=20.0  # 20 second timeout for confirmation message
            )
            content = self._normalize_text_output(result_msg.content.strip())
        except asyncio.TimeoutError:
            print("  Confirmation message generation timed out, using fallback")
            content = "Please review the items above and confirm or provide corrections."
        except Exception as e:
            print(f"  Confirmation message generation failed: {str(e)}")
            try:
                self._log_llm_error("generate_confirmation_message", e, formatted_text)
            except Exception:
                pass
            content = "Please review the items above and confirm or provide corrections."
        self._log_interaction("generate_confirmation_message", formatted_text, content)
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
        prompt = ChatPromptTemplate.from_template(template_str)
        
        # Use function calling for structured output
        structured_llm = self.chat.with_structured_output(ProfileSummaryResponse, method="function_calling")
        chain = prompt | structured_llm
        
        inputs = {
            "profile_text": profile_text,
            "checklist_data": checklist_text
        }
        
        # Fit inputs to token limit, prioritizing checklist data over profile text if needed
        inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["profile_text", "checklist_data"])
        
        # Execute with retry logic and timeout protection
        result_model: Optional[ProfileSummaryResponse] = None
        last_err: Optional[Exception] = None
        
        import asyncio
        for attempt in range(2):  # 2 attempts
            try:
                result_model = await asyncio.wait_for(
                    chain.ainvoke(inputs),
                    timeout=60.0  # 60 second timeout for profile summary generation
                )
                print(f"  Profile summary generated successfully on attempt {attempt + 1}")
                break
            except asyncio.TimeoutError:
                last_err = Exception("Profile summary generation timed out after 60 seconds")
                print(f"  Profile summary generation timed out on attempt {attempt + 1}")
                try:
                    self._log_llm_error("generate_profile_summary", last_err, formatted_text)
                except Exception:
                    pass
                continue
            except Exception as e:
                last_err = e
                print(f"  Profile summary generation failed on attempt {attempt + 1}: {str(e)}")
                try:
                    self._log_llm_error("generate_profile_summary", e, formatted_text)
                except Exception:
                    pass
                continue
        
        if result_model is None:
            print("  All profile summary generation attempts failed, using fallback")
            # Provide fallback summary
            completed_count = len(formatted_checklist)
            fallback_summary = f"Profile Summary: Service provider with {completed_count} completed onboarding items. " + \
                             "Please contact the provider directly for detailed information about their services and capabilities."
            result_model = ProfileSummaryResponse(summary=fallback_summary)
        
        # Log the interaction
        response_content = result_model.summary
        self._log_interaction("generate_profile_summary", formatted_text, response_content)
        
        return response_content

    def generate_search_queries(
        self,
        profile_text: str,
        max_queries: int = 3,
    ) -> List[Dict[str, str]]:
        """Generate targeted web search queries for discovering provider pages/results from a single profile_text input."""
        template_str = self._read_prompt(self._generate_search_queries_prompt_path)
        prompt = ChatPromptTemplate.from_template(template_str)
        structured_llm = self.chat.with_structured_output(GenerateSearchQueriesResponse, method="function_calling")
        chain = prompt | structured_llm
        inputs = {"profile_text": profile_text}
        inputs, formatted_text = self._fit_inputs_to_limit(prompt, inputs, keys_to_truncate=["profile_text"])
        try:
            result_model = chain.invoke(inputs)
        except Exception as e:
            try:
                self._log_llm_error("generate_search_queries", e, self._format_prompt(prompt, inputs))
            except Exception:
                pass
            raise
        result = result_model.model_dump()
        self._log_interaction("generate_search_queries", formatted_text, result)
        items = []
        for q in result.get("queries", []):
            try:
                sq = SearchQuery.model_validate(q)
                items.append({"text": sq.text, "intent": sq.intent})
            except Exception:
                if isinstance(q, dict) and q.get("text"):
                    items.append({"text": str(q.get("text")), "intent": str(q.get("intent", "provider_discovery"))})
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

    def _format_prompt(self, prompt: ChatPromptTemplate, inputs: Dict[str, Any]) -> str:
        try:
            # Render to a string view for logging using LangChain formatting
            messages = prompt.format_messages(**inputs)
            rendered = []
            for m in messages:
                role = getattr(m, "type", getattr(m, "role", "message"))
                rendered.append(f"[{role}]\n{getattr(m, 'content', '')}")
            return "\n\n".join(rendered)
        except Exception:
            return json.dumps(inputs, ensure_ascii=False)

    def _fit_inputs_to_limit(
        self,
        prompt: ChatPromptTemplate,
        inputs: Dict[str, Any],
        keys_to_truncate: List[str]
    ) -> Tuple[Dict[str, Any], str]:
        """Ensure the formatted prompt fits within token limit by truncating provided keys."""
        safe_inputs = dict(inputs)
        formatted = self._format_prompt(prompt, safe_inputs)
        if self._count_tokens(formatted) <= self.max_input_tokens:
            return safe_inputs, formatted
        # Iteratively truncate fields in order
        for key in keys_to_truncate:
            if key in safe_inputs and isinstance(safe_inputs[key], str):
                # Gradually shrink until under limit or very small
                for _ in range(6):
                    safe_inputs[key] = self._truncate_to_tokens(str(safe_inputs[key]), int(self.max_input_tokens * 0.6))
                    formatted = self._format_prompt(prompt, safe_inputs)
                    if self._count_tokens(formatted) <= self.max_input_tokens:
                        return safe_inputs, formatted
        # Final fallback: hard truncate the fully formatted text for logging, but send best-effort inputs
        return safe_inputs, formatted[: min(len(formatted), 120000)]

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