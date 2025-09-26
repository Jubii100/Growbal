import os
import glob
import requests
from bs4 import BeautifulSoup, Comment
import justext
import json

import re
from urllib.parse import urlparse, unquote
from pathlib import Path


class HtmlScraper:
    def __init__(self, scraping_api_key, save_directory="saved_html"):
        self.scraping_api_key = scraping_api_key
        self.save_directory = save_directory
        os.makedirs(self.save_directory, exist_ok=True)
        self.KEYWORD_PATTERNS: dict[str, list[re.Pattern]] = {
            "about": [
                re.compile(r"\babout(?:\s+us)?\b", re.I),
                re.compile(r"\bwho\s+(?:we|i)\s+are\b", re.I),
                re.compile(r"\bcompany\s+info(?:rmation)?\b", re.I),
                re.compile(r"\bour\s+(?:story|mission|vision)\b", re.I),
            ],
            "services": [
                re.compile(r"\bservices?\b", re.I),
                re.compile(r"\bour\s+services?\b", re.I),
                re.compile(r"\bwhat\s+we\s+(?:do|offer)\b", re.I),
                re.compile(r"\bsolutions?\b", re.I),
                re.compile(r"\bproducts?\b", re.I),
            ],
            "contact": [
                re.compile(r"\bcontact(?:\s+us)?\b", re.I),
                re.compile(r"\bget\s+in\s+touch\b", re.I),
                re.compile(r"\bsupport\b", re.I),
                re.compile(r"\bhelp(?:\s+center)?\b", re.I),
            ],
            "team": [
                re.compile(r"\bteam\b", re.I),
                re.compile(r"\bmeet\s+(?:the\s+)?team\b", re.I),
                re.compile(r"\bleadership\b", re.I),
                re.compile(r"\bmanagement\b", re.I),
            ],
            "careers": [
                re.compile(r"\bcareers?\b", re.I),
                re.compile(r"\bjobs?\b", re.I),
                re.compile(r"\bjoin\s+us\b", re.I),
            ],
            # ➜ add more categories & patterns as your crawler evolves
        }

        # compile once for speed
        self.JUNK_HREF = re.compile(
            r"""
            ^\s*(?:javascript:|mailto:|tel:|\#|$)   # empty, anchors, js:, mailto:, tel:, etc.
            """, re.I | re.X
        )


    def scrape_html_base(
        self,
        link: str,
        scroll_rounds: int = 12,
        px_per_scroll: int = 2500,
        wait_ms: int = 1200,
    ) -> str:
        """
        Scrolls the page several times with built-in 'scroll' steps,
        saves the fully rendered HTML to <save_directory>/<slug>.html,
        and returns the HTML string.
        """
        # ── 1 Build the JS-scenario ──────────────────────────────────────────────
        steps = [{"wait": 1500}]
        for _ in range(scroll_rounds):
            steps.append({"scroll": px_per_scroll})
            steps.append({"wait": wait_ms})
        steps.append({"wait": 800})
        scenario = {"steps": steps}

        # ── 2 Call Scraping Fish ────────────────────────────────────────────────
        payload = {
            "api_key": self.scraping_api_key,
            "url": link,
            "js_scenario": json.dumps(scenario),
            "trial_timeout_ms": 45_000,
            "total_timeout_ms": 60_000,
            "render_js": "true",
        }
        resp = requests.get("https://scraping.narf.ai/api/v1/", params=payload, timeout=90)
        resp.raise_for_status()
        return resp.content.decode()

    def scrape_html_about(self, link):
        # html_content_list = []

        # for result in relevant_results:
        # Define a JS scenario to simulate user interactions if needed
        scenario_steps = [
            {"wait": 3000},  # wait 5 seconds (your comment says 1s, should match actual value)
            {"click_if_exists": ".menu-toggle"},  # click menu if present
            {"wait_for": {"selector": "a[href*='about']", "state": "attached"}},  # wait for "about" link to load
            {"wait": 1000}  # wait 5 seconds (your comment says 1s, should match actual value)
        ]

        # Prepare the API request parameters correctly for ScrapingFish
        params = {
            "api_key": self.scraping_api_key,
            "url": link,
            "render_js": "true",
            "js_scenario": json.dumps({"steps": scenario_steps})
        }

        response = requests.get("https://scraping.narf.ai/api/v1/", params=params)
        if response.status_code == 200:
            return response.content.decode()
        else:
            print(f"Failed to fetch {link}: Status code {response.status_code}")
            return None

    def scrape_html_contact(self, link):
        # html_content_list = []

        # for result in relevant_results:
        # Define a JS scenario to simulate user interactions if needed
        scenario_steps = [
            {"wait": 3000},  # wait 5 seconds (your comment says 1s, should match actual value)
            {"click_if_exists": ".menu-toggle"},  # click menu if present
            {"wait_for": {"selector": "a[href*='contact']", "state": "attached"}},  # wait for "contact" link to load
            {"wait": 1000}  # wait 5 seconds (your comment says 1s, should match actual value)
        ]

        # Prepare the API request parameters correctly for ScrapingFish
        params = {
            "api_key": self.scraping_api_key,
            "url": link,
            "render_js": "true",
            "js_scenario": json.dumps({"steps": scenario_steps})
        }

        response = requests.get("https://scraping.narf.ai/api/v1/", params=params)
        if response.status_code == 200:
            return response.content.decode()
        else:
            print(f"Failed to fetch {link}: Status code {response.status_code}")
            return None

    def scrape_and_save_html(self, relevant_results):
        saved_files = []

        for result in relevant_results:
            if 'link' in result:
                payload = {
                    "api_key": self.scraping_api_key,
                    "url": result['link'],
                    "render_js": "true"
                }

                response = requests.get("https://scraping.narf.ai/api/v1/", params=payload)
                if response.status_code == 200:
                    filename = f"{result.get('id', hash(result['link']))}.html"
                    filepath = os.path.join(self.save_directory, filename)
                    with open(filepath, 'w', encoding='utf-8') as file:
                        file.write(response.content.decode())
                    saved_files.append(filepath)
                else:
                    print(f"Failed to fetch {result['link']}: Status code {response.status_code}")

        print(f"Successfully downloaded and saved {len(saved_files)} pages as HTML to '{self.save_directory}'/")
        return saved_files

    def load_saved_html(self):
        html_files = glob.glob(os.path.join(self.save_directory, "*.html"))
        loaded_html_strings = []

        for file_path in html_files:
            with open(file_path, 'r', encoding='utf-8') as file:
                loaded_html_strings.append(file.read())

        print(f"Successfully loaded {len(loaded_html_strings)} HTML pages into strings")
        return loaded_html_strings

    # def get_nav_links(self, html_content):
    #     soup = BeautifulSoup(html_content, "html.parser")
    #     nav_links = []
    #     for a in soup.find_all('a'):
    #         text = a.get_text(strip=True)
    #         href = a.get('href')
    #         if text and href:
    #             # Check if this link is one of the informative sections (About, Services, Team, etc.)
    #             text_lower = text.lower()
    #             if any(keyword in text_lower for keyword in ["about", "service", "team"]):
    #                 nav_links.append((text, href))

    #     return nav_links


    # ──────────────────────────────────────────────────────────────────────────────
    #  1.  Build a dictionary of semantic categories → list[regex pattern]
    # ──────────────────────────────────────────────────────────────────────────────

    def normalise_href(self, base_url: str, raw_href: str) -> str:
        """Return an absolute URL if possible, else the raw href."""
        if not raw_href:
            return ""
        if raw_href.startswith(("http://", "https://")):
            return raw_href
        if raw_href.startswith("//"):
            # protocol-relative → inherit https by default
            return f"https:{raw_href}"
        # relative path → join with base host
        if base_url:
            base = urlparse(base_url)
            # ensure no trailing slash duplications
            root = f"{base.scheme}://{base.netloc}"
            return root + (raw_href if raw_href.startswith("/") else f"/{raw_href}")
        return raw_href


    def match_category(self, text_or_path: str) -> str | None:
        """Return the first matching category or None."""
        for category, patterns in self.KEYWORD_PATTERNS.items():
            if any(p.search(text_or_path) for p in patterns):
                return category
        return None


    def get_nav_links(self, html_content: str, page_url: str = "") -> list[tuple[str, str, str]]:
        """
        Extract navigation links of interest.

        Parameters
        ----------
        html_content : str
            The full HTML string.
        page_url : str, optional
            Absolute URL of the page (used to turn relative hrefs into absolute).

        Returns
        -------
        list[tuple[text, href, category]]
            Ordered list with duplicates removed:
            e.g. ('Contact Us', 'https://example.com/contact', 'contact')
        """
        soup = BeautifulSoup(html_content, "html.parser")

        seen: set[str] = set()
        nav_links: list[tuple[str, str, str]] = []

        # Traverse all <a> elements; consider restricting to <nav>, header, etc. for speed
        for a in soup.find_all("a"):
            href_raw: str | None = a.get("href")
            if not href_raw or self.JUNK_HREF.match(href_raw):
                continue  # skip empty or junk links

            href = self.normalise_href(page_url, href_raw)

            # Use both visible text and pathname (for icon-only links)
            text = a.get_text(strip=True) or ""
            basis_strings = [text.lower(), urlparse(href).path.lower()]

            # Find first matching category
            category: str | None = next(
                (cat for s in basis_strings for cat in [self.match_category(s)] if cat), None
            )
            if category and href not in seen:
                nav_links.append((text or category.title(), href, category))
                seen.add(href)

        return nav_links


    def clean_html_content(self, html_content: str,
                        language: str = "English",
                        drop_inline_styles: bool = False):
        """
        Return (clean_text, clean_html) where:
        * clean_html is the original page minus junk tags / comments / ads
        * clean_text is boilerplate-free plain text (just-ext) for NLP
        """

        STRIP_TAGS = {
            # executable / dynamic
            "script", 
            "noscript", 
            # "template",
            # presentation
            "style", 
            # "link",          # link[rel=stylesheet] handled below
            # navigation & widgets
            # "header", "nav", "footer", "aside",
            # media wrappers
            "video", "audio", 
            # "iframe", "canvas", "svg",
            # forms / ads
            # "form", "input", "select", "button", "textarea", "ins",
        }

        AD_PATTERNS = ("ad-", "-ad", "advert", "promo", "cookie") #, "banner"
        soup = BeautifulSoup(html_content, "lxml")

        # ------------------------------------------------------------------
        # 1) Remove unwanted *elements* outright
        # ------------------------------------------------------------------
        for tag in soup.find_all(list(STRIP_TAGS)):
            tag.decompose()

        # Strip only those <link> tags that are CSS files
        for link in soup.find_all("link", rel=lambda v: v and "stylesheet" in v):
            link.decompose()

        # ------------------------------------------------------------------
        # 2) Remove comment nodes
        # ------------------------------------------------------------------
        # for c in soup.find_all(string=lambda t: isinstance(t, Comment)):
        #     c.extract()

        # ------------------------------------------------------------------
        # 3) Remove obvious ad / cookie containers by class or id patterns
        # ------------------------------------------------------------------
        def looks_like_ad(attrs):
            if not attrs:
                return False
            haystack = " ".join(
                attrs.get("class", []) + [attrs.get("id", "")]
            ).lower()
            return any(p in haystack for p in AD_PATTERNS)

        for elt in soup.find_all(looks_like_ad):
            elt.decompose()

        # ------------------------------------------------------------------
        # 4) (Optional) strip *inline* style attributes
        # ------------------------------------------------------------------
        # if drop_inline_styles:
        #     for elt in soup.find_all(True, style=True):
        #         del elt["style"]

        # ------------------------------------------------------------------
        # 5) Produce outputs
        # ------------------------------------------------------------------
        clean_html = str(soup)

        # If you don’t need boilerplate removal, comment this block out
        paragraphs = justext.justext(clean_html, justext.get_stoplist(language))
        # clean_text = "\n\n".join(p.text for p in paragraphs
        #                         if not p.is_boilerplate and p.text.strip())
        clean_text = "\n\n".join(p.text for p in paragraphs if p.text.strip())

        return clean_text, clean_html


    def save_html(self, html_content, link: str):
        def slugify(url: str) -> str:
            p = urlparse(url)
            # combine host + path, unquote (%20 → space) then replace non-word chars
            raw = (p.netloc + p.path).rstrip("/").lower()
            raw = unquote(raw)
            return re.sub(r"[^\w\-]+", "_", raw).strip("_") or "index"

        os.makedirs(self.save_directory, exist_ok=True)
        file_path = Path(self.save_directory) / f"{slugify(link)}.html"
        file_path.write_text(html_content, encoding="utf-8")

    # def save_logo(self, logo_url: str, download_dir="../growbal_django/media/logos"):
    #     os.makedirs(download_dir, exist_ok=True)
    #     is_logo = True
    #     if not logo_url:
    #         print("No logo found")
    #         is_logo = False
    #     else:
    #         try:
    #             resp = requests.get(logo_url, stream=True, timeout=10)
    #             resp.raise_for_status()
    #         except requests.RequestException as e:
    #             print(f"Failed to download logo: {e}")
    #             is_logo = False

    #         if is_logo and resp.status_code != 200:
    #             print(f"Failed to download logo: {resp.status_code}")
    #             is_logo = False

    #     if not is_logo:
    #         filename = "logo-placeholder.png"
    #         filepath = os.path.join(download_dir, filename)
    #     else:
    #         filename = os.path.basename(urlparse(logo_url).path) or urlparse(logo_url).netloc
    #         i = 0
    #         while f"{filename}_{i}.svg" in os.listdir(download_dir):
    #             i += 1
    #         filename = f"{filename}_{i}.svg"
    #         filepath = os.path.join(download_dir, filename)

    #         with open(filepath, "wb") as f:
    #             for chunk in resp.iter_content(8192):
    #                 f.write(chunk)

    #     print(f"Logo saved to {filepath}")
    #     return filepath


    def save_logo(
        self,
        logo_url: str,
        download_dir="../growbal_django/media/logos",
    ):
        os.makedirs(download_dir, exist_ok=True)

        if not logo_url:
            print("No logo found")
            filename = "logo-placeholder.png"
            filepath = os.path.join(download_dir, filename)
            return filepath

        try:
            resp = requests.get(logo_url, stream=True, timeout=10)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"Failed to download logo: {e}")
            filename = "logo-placeholder.png"
            filepath = os.path.join(download_dir, filename)
            return filepath

        content_type = resp.headers.get("Content-Type", "").lower()
        extension = ""

        if "image/svg+xml" in content_type:
            extension = "svg"
        elif "image/png" in content_type:
            extension = "png"
        elif "image/jpeg" in content_type or "image/jpg" in content_type:
            extension = "jpg"
        elif "image/gif" in content_type:
            extension = "gif"
        elif "image/webp" in content_type:
            extension = "webp"
        elif "image/bmp" in content_type:
            extension = "bmp"
        elif "image/tiff" in content_type:
            extension = "tiff"
        elif "image/x-icon" in content_type:
            extension = "ico"
        elif "image/avif" in content_type:
            extension = "avif"
        else:
            extension = "img"  # default extension for unknown types

        filename_base = os.path.basename(urlparse(logo_url).path).split(".")[0] or urlparse(
            logo_url
        ).netloc

        i = 0
        filename = f"{filename_base}_{i}.{extension}"
        while filename in os.listdir(download_dir):
            i += 1
            filename = f"{filename_base}_{i}.{extension}"

        filepath = os.path.join(download_dir, filename)

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

        print(f"Logo saved to {filepath}")
        return filepath