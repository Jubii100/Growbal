"""
Research Tools for Two-Part Onboarding System
Real implementations using OpenAI Web Search and ScrapingFish for fetching
"""
import os
import asyncio
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import requests
from urllib.parse import urlencode
from bs4 import BeautifulSoup
from pathlib import Path
from dotenv import load_dotenv

from schemas import WebSearchResult, WebSearchResponse, FetchedPage, ParsedPage

# Load env variables from envs/1.env if present (non-intrusive)
try:
    _env_path = Path(__file__).resolve().parents[1] / "envs" / "1.env"
    if _env_path.exists():
        load_dotenv(str(_env_path), override=False)
except Exception:
    pass


class OpenAIWebSearchAPI:
    """OpenAI Web Search via Responses API with web_search tool.

    Requires OPENAI_API_KEY to be set. Returns a normalized list of results.
    """

    def __init__(self, model: str = "gpt-4o"):
        from openai import OpenAI  # Lazy import to avoid import cost if unused
        import os
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model

    async def search(self, query: str, num_results: int = 3) -> List[Dict[str, str]]:
        # The Responses API is synchronous; run in thread to avoid blocking loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._search_sync, query, num_results)

    def _search_sync(self, query: str, num_results: int) -> List[Dict[str, str]]:
        try:
            resp = self.client.responses.create(
                model=self.model,
                input=f"Find relevant links for: {query}",
                tools=[{"type": "web_search"}],
            )
            # Extract citations from response.output -> message.content[].annotations[]
            output = getattr(resp, "output", None) or []
            results: List[Dict[str, str]] = []
            for item in output:
                item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
                if item_type != "message":
                    continue
                content_list = getattr(item, "content", None) or (item.get("content") if isinstance(item, dict) else [])
                for block in content_list or []:
                    annotations = getattr(block, "annotations", None) or (block.get("annotations") if isinstance(block, dict) else [])
                    for ann in annotations or []:
                        ann_type = getattr(ann, "type", None) or (ann.get("type") if isinstance(ann, dict) else None)
                        if ann_type == "url_citation":
                            title = (getattr(ann, "title", None) or ann.get("title") or "").strip()
                            url = (getattr(ann, "url", None) or ann.get("url") or "").strip()
                            if not url:
                                continue
                            results.append({
                                "title": title or url,
                                "link": url,
                                "snippet": "",
                            })
            # Deduplicate by URL, preserve order
            seen = set()
            deduped: List[Dict[str, str]] = []
            for r in results:
                u = r.get("link")
                if u and u not in seen:
                    seen.add(u)
                    deduped.append(r)
            return deduped[:num_results]
        except Exception:
            return []


class AcademicContentCleaner:
    """Cleans academic content for business relevance"""
    
    def __init__(self):
        self.business_keywords = [
            'requirement', 'standard', 'regulation', 'compliance',
            'licensing', 'certification', 'professional', 'business',
            'service', 'provider', 'industry', 'practice'
        ]
    
    def clean_and_extract(self, raw_content: str) -> str:
        """Clean and extract relevant content"""
        # Simple mock cleaning - in production would use BeautifulSoup
        lines = raw_content.strip().split('\n')
        relevant_lines = []
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 20:
                continue
            
            # Check for relevance
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in self.business_keywords):
                relevant_lines.append(line)
        
        return '\n'.join(relevant_lines)


class BusinessContentParser:
    """Parses web content for business information"""

    def _strip_html_to_text(self, html: str) -> ParsedPage:
        """Extract headings and paragraphs (no scripts/styles)."""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        title = None
        if soup.title and soup.title.string:
            title = soup.title.string.strip()

        headings: List[str] = []
        for h in ["h1", "h2", "h3", "h4", "h5", "h6"]:
            for tag in soup.find_all(h):
                text = tag.get_text(" ", strip=True)
                if text:
                    headings.append(text)

        paragraphs: List[str] = []
        for p in soup.find_all("p"):
            text = p.get_text(" ", strip=True)
            if text and len(text) > 30:
                paragraphs.append(text)

        text = "\n\n".join(headings + paragraphs)
        return ParsedPage(url="", title=title, text=text, headings=headings, paragraphs=paragraphs, word_count=len(text.split()))

    def extract_business_info(self, html_content: str, url: str = "") -> Dict[str, Any]:
        """Extract business information from content"""
        parsed = self._strip_html_to_text(html_content)

        contacts = {}
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, html_content)
        if emails:
            contacts['email'] = list(set(emails))[:3]

        phone_pattern = r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}'
        phones = re.findall(phone_pattern, html_content)
        if phones:
            contacts['phone'] = list(set(phones))[:3]

        address_pattern = r'\d+\s+[A-Za-z0-9\s,.-]+(?:Street|St|Avenue|Ave|Road|Rd|Suite|Ste)'
        addresses = re.findall(address_pattern, html_content, re.IGNORECASE)
        if addresses:
            contacts['address'] = list(set(addresses))[:3]

        return {
            'contacts': contacts,
            'business_content': parsed.text,
            'headings': parsed.headings,
            'paragraphs': parsed.paragraphs,
            'title': parsed.title,
            'source_url': url,
            'content_length': len(html_content)
        }


class ScrapingFishClient:
    """Minimal ScrapingFish client for rendered content fetching."""

    def __init__(self, api_key: Optional[str] = None):
        # Prefer SCRAPING_API_KEY from 1.env, fall back to SCRAPINGFISH_API_KEY
        self.api_key = api_key or os.getenv("SCRAPING_API_KEY") or os.getenv("SCRAPINGFISH_API_KEY", "")
        # ScrapingFish returns the fetched page body. Correct endpoint root doesn't include /v1
        self.base_url = os.getenv("SCRAPINGFISH_BASE_URL", "https://api.scrapingfish.com/")

    async def fetch(self, url: str, render_js: bool = True, timeout: int = 30) -> FetchedPage:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_sync, url, render_js, timeout)

    def _fetch_sync(self, url: str, render_js: bool, timeout: int) -> FetchedPage:
        # Realistic headers
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
            ),
        }

        def _ok(resp: requests.Response) -> bool:
            try:
                if not resp or resp.status_code is None:
                    return False
                if int(resp.status_code) >= 400:
                    return False
                body = resp.text or ""
                return len(body.strip()) > 0
            except Exception:
                return False

        # 1) ScrapingFish (prefer JS render), if API key present
        if self.api_key:
            for base in [self.base_url.rstrip("/"), "https://api.scrapingfish.com"]:
                try:
                    endpoint = base if base.endswith("/") else base + "/"
                    params = {
                        "api_key": self.api_key,
                        "url": url,
                        "render_js": "true" if render_js else "false",
                    }
                    resp = requests.get(endpoint, params=params, headers=headers, timeout=timeout)
                    if _ok(resp):
                        return FetchedPage(url=url, status_code=resp.status_code, html=resp.text, fetched_at=datetime.utcnow().isoformat())
                    # Try without JS once if JS render gave empty/failed
                    if render_js:
                        params["render_js"] = "false"
                        resp2 = requests.get(endpoint, params=params, headers=headers, timeout=timeout)
                        if _ok(resp2):
                            return FetchedPage(url=url, status_code=resp2.status_code, html=resp2.text, fetched_at=datetime.utcnow().isoformat())
                except Exception:
                    continue

        # 2) Direct HTTP(S) fallback without ScrapingFish
        try:
            resp_direct = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            if _ok(resp_direct):
                return FetchedPage(url=url, status_code=resp_direct.status_code, html=resp_direct.text, fetched_at=datetime.utcnow().isoformat())
        except Exception:
            pass

        # Final fallback: empty response marker
        return FetchedPage(url=url, status_code=0, html="", fetched_at=datetime.utcnow().isoformat())


# Backwards-compatibility alias for existing imports
MockWebSearchAPI = OpenAIWebSearchAPI