"""Website content extraction.

Fetches the homepage and up to three relevant same-domain pages, extracts
useful information (metadata, headings, JSON-LD, text, links), and cleans
it for LLM consumption.
"""

from __future__ import annotations

import html
import json
import logging
import re
from typing import Any, Dict, List, Set
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Comment

from app.config import settings

logger = logging.getLogger("link-analysis.extractor")

# Elements to remove before extracting text.
REMOVE_TAGS = {
    "script",
    "style",
    "noscript",
    "svg",
    "iframe",
    "form",
    "button",
    "input",
    "select",
    "textarea",
    "meta",
    "link",
}

# Keywords that signal a page is worth fetching.
PAGE_DISCOVERY_KEYWORDS = (
    "about", "service", "solution", "product", "pricing", "feature",
    "industry", "contact", "company", "team", "case-study", "portfolio",
)

MAX_HTML_BYTES = 2_000_000  # ~2 MB response size cap


def _clean_text(text: str) -> str:
    """Collapse whitespace and normalise extracted text."""
    lines = [line.strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    # Deduplicate consecutive repeated lines.
    deduped: List[str] = []
    prev = None
    for line in lines:
        if line != prev:
            deduped.append(line)
            prev = line
    return "\n".join(deduped)


def _is_internal(href: str, base_domain: str) -> bool:
    """Return True if href points to the same domain as base_domain."""
    try:
        parsed = urlparse(href)
    except Exception:
        return False
    if not parsed.netloc:
        return True  # relative link -> internal
    return parsed.netloc.lower() == base_domain.lower()


def _score_link(href: str) -> int:
    """Score an internal link by relevance to business content."""
    href_lower = href.lower()
    score = 0
    for kw in PAGE_DISCOVERY_KEYWORDS:
        if kw in href_lower:
            score += 3
    if len(href) < 60:
        score += 1
    return score


def extract_page(html_content: str, url: str) -> Dict[str, Any]:
    """Parse a single HTML page and return structured data."""
    soup = BeautifulSoup(html_content, "lxml")

    # Title.
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    # Meta tags.
    meta_description = ""
    meta_keywords = ""
    og_title = ""
    og_description = ""
    html_lang = ""

    for meta in soup.find_all("meta"):
        name = (meta.get("name") or "").lower()
        prop = (meta.get("property") or "").lower()
        content = meta.get("content") or ""
        if name == "description" or prop == "og:description":
            if not meta_description:
                meta_description = html.unescape(content.strip())
        if name == "keywords":
            meta_keywords = html.unescape(content.strip())
        if prop == "og:title":
            og_title = html.unescape(content.strip())
        if prop == "og:description" and not meta_description:
            meta_description = html.unescape(content.strip())

    html_tag = soup.find("html")
    if html_tag and html_tag.get("lang"):
        html_lang = html_tag["lang"].strip()

    # Canonical URL.
    canonical = ""
    canon_tag = soup.find("link", attrs={"rel": "canonical"})
    if canon_tag and canon_tag.get("href"):
        canonical = canon_tag["href"].strip()

    # JSON-LD.
    json_ld: List[Any] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or "{}")
            if isinstance(data, list):
                json_ld.extend(data)
            else:
                json_ld.append(data)
        except (json.JSONDecodeError, TypeError):
            continue

    # Headings.
    headings: List[str] = []
    for level in ("h1", "h2", "h3"):
        for tag in soup.find_all(level):
            text = tag.get_text(" ", strip=True)
            if text and len(text) < 200:
                headings.append(text)

    # Images and alt attributes.
    images: List[Dict[str, str]] = []
    for img in soup.find_all("img"):
        images.append({
            "src": img.get("src", ""),
            "alt": img.get("alt", "") or "",
        })

    # Address, phone, email hints.
    text_raw = soup.get_text(" ", strip=True)
    email_pattern = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    phone_pattern = re.compile(r"\+?\d[\d\s\-\(\)]{7,}\d")
    emails = email_pattern.findall(text_raw)
    phones = phone_pattern.findall(text_raw)

    # Links.
    base_domain = urlparse(url).netloc.lower()
    links: List[str] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
            links.append(href)

    internal_links: List[str] = []
    for href in links:
        if _is_internal(href, base_domain):
            abs_url = urljoin(url, href)
            if abs_url != url and abs_url not in internal_links:
                internal_links.append(abs_url)

    # Remove noise for text extraction.
    for tag in soup(REMOVE_TAGS):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    body = soup.find("body") or soup
    text = _clean_text(body.get_text(" ", strip=True))

    return {
        "url": url,
        "title": title,
        "meta_description": meta_description,
        "meta_keywords": meta_keywords,
        "og_title": og_title,
        "og_description": og_description,
        "html_lang": html_lang,
        "canonical": canonical,
        "json_ld": json_ld,
        "headings": headings[:50],
        "images": images,
        "emails": list(dict.fromkeys(emails))[:10],
        "phones": list(dict.fromkeys(phones))[:10],
        "links": links[:100],
        "internal_links": internal_links,
        "text": text,
        "text_length": len(text),
        "is_thin": len(text) < 300,
    }


async def fetch_single_page(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    """Fetch one URL and return its extracted content."""
    headers = {
        "User-Agent": settings.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    try:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"Server returned {exc.response.status_code} for {url}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(f"Could not fetch {url}: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if "text/html" not in content_type.lower():
        raise RuntimeError(
            f"URL did not return HTML (content-type: {content_type}). "
            "Only HTML websites are supported."
        )

    if len(response.content) > MAX_HTML_BYTES:
        raise RuntimeError(
            f"Response too large ({len(response.content)} bytes)."
        )

    return extract_page(response.text, url)


async def fetch_website(url: str) -> Dict[str, Any]:
    """Fetch homepage and up to MAX_PAGES_PER_SITE relevant internal pages."""
    timeout = httpx.Timeout(settings.REQUEST_TIMEOUT)
    limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)

    async with httpx.AsyncClient(
        timeout=timeout, limits=limits, follow_redirects=False
    ) as client:
        # Homepage.
        try:
            homepage = await fetch_single_page(client, url)
        except RuntimeError as exc:
            raise RuntimeError(str(exc)) from exc

        # Discover secondary pages.
        candidates = homepage.get("internal_links", [])
        scored = sorted(candidates, key=_score_link, reverse=True)
        secondary_urls = scored[: settings.MAX_PAGES_PER_SITE - 1]

        secondary: List[Dict[str, Any]] = []
        if secondary_urls:
            tasks = [fetch_single_page(client, u) for u in secondary_urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, RuntimeError):
                    logger.warning("Secondary page failed: %s", result)
                    continue
                if isinstance(result, Exception):
                    logger.warning("Secondary page error: %s", result)
                    continue
                secondary.append(result)

    # Merge text from all pages.
    all_text_parts = [homepage["text"]]
    for page in secondary:
        all_text_parts.append(f"\n--- Page: {page['url']} ---\n{page['text']}")
    merged_text = "\n".join(all_text_parts)[: settings.MAX_TOTAL_CHARS]

    return {
        "url": url,
        "title": homepage["title"],
        "meta_description": homepage["meta_description"],
        "meta_keywords": homepage["meta_keywords"],
        "og_title": homepage.get("og_title", ""),
        "og_description": homepage.get("og_description", ""),
        "html_lang": homepage.get("html_lang", ""),
        "canonical": homepage.get("canonical", ""),
        "headings": homepage["headings"],
        "json_ld": homepage.get("json_ld", []),
        "text": merged_text,
        "text_length": len(merged_text),
        "full_text_length": homepage["text_length"]
        + sum(p["text_length"] for p in secondary),
        "links": homepage.get("links", []),
        "internal_links": homepage.get("internal_links", []),
        "pages": [homepage] + secondary,
        "pages_analyzed": len(secondary) + 1,
        "is_thin": homepage["is_thin"] and not secondary,
    }


import asyncio  # noqa: E402
