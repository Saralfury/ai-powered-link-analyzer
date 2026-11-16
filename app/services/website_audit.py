"""Deterministic SEO audit calculated directly from extracted HTML.

Python detects the facts; the LLM interprets them and proposes improvements.
"""

from __future__ import annotations

from typing import Any, Dict, List
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Comment


def audit_page(html: str, url: str) -> Dict[str, Any]:
    """Run deterministic SEO checks on a single page's HTML."""
    soup = BeautifulSoup(html, "lxml")

    # Remove noise for text-based checks.
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()
    for comment in soup.find_all(string=lambda t: isinstance(t, Comment)):
        comment.extract()

    # Title.
    title_tag = soup.find("title")
    title_text = title_tag.get_text(strip=True) if title_tag else ""
    title_present = bool(title_text)
    title_length = len(title_text)

    # Meta description.
    meta_desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find(
        "meta", attrs={"property": "og:description"}
    )
    meta_desc = meta_desc_tag.get("content", "").strip() if meta_desc_tag else ""
    meta_desc_present = bool(meta_desc)
    meta_desc_length = len(meta_desc)

    # H1 count.
    h1_elements = soup.find_all("h1")
    h1_count = len(h1_elements)

    # Headings counts.
    heading_counts = {}
    for level in ("h1", "h2", "h3", "h4", "h5", "h6"):
        heading_counts[level] = len(soup.find_all(level))

    # Images and alt text.
    images = soup.find_all("img")
    total_images = len(images)
    missing_alt = sum(1 for img in images if not img.get("alt", "").strip())
    missing_alt_ratio = (missing_alt / total_images) if total_images > 0 else 0.0

    # Canonical.
    canon_tag = soup.find("link", attrs={"rel": "canonical"})
    canonical_present = bool(canon_tag and canon_tag.get("href"))
    canonical_value = canon_tag.get("href", "").strip() if canon_tag else ""

    # Viewport.
    viewport_tag = soup.find("meta", attrs={"name": "viewport"})
    viewport_present = bool(viewport_tag)

    # Internal links count.
    base_domain = urlparse(url).netloc.lower()
    internal_links = 0
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
            try:
                parsed = urlparse(href)
            except Exception:
                continue
            if not parsed.netloc or parsed.netloc.lower() == base_domain:
                internal_links += 1

    # Heading hierarchy issues (h2 before h1, etc.)
    hierarchy_issues = []
    first_h1_index = None
    for i, tag in enumerate(soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6"])):
        if tag.name == "h1" and first_h1_index is None:
            first_h1_index = i
        if first_h1_index is not None and i < first_h1_index and tag.name != "h1":
            hierarchy_issues.append(f"{tag.name} before first h1")

    visible_text = soup.get_text(" ", strip=True)
    text_length = len(visible_text)

    return {
        "url": url,
        "title": {
            "present": title_present,
            "character_count": title_length,
        },
        "meta_description": {
            "present": meta_desc_present,
            "character_count": meta_desc_length,
        },
        "h1": {
            "count": h1_count,
        },
        "headings": heading_counts,
        "images": {
            "total": total_images,
            "missing_alt": missing_alt,
            "missing_alt_ratio": round(missing_alt_ratio, 2),
        },
        "canonical": {
            "present": canonical_present,
            "value": canonical_value,
        },
        "viewport": {
            "present": viewport_present,
        },
        "internal_links": {
            "count": internal_links,
        },
        "hierarchy_issues": hierarchy_issues,
        "text_length": text_length,
    }


def audit_site(pages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Aggregate audit results across all fetched pages."""
    if not pages:
        return {"pages": [], "summary": {}}

    page_audits = []
    for page in pages:
        html = page.get("_raw_html", "")
        url = page.get("url", "")
        if html:
            page_audits.append(audit_page(html, url))

    summary = {
        "total_pages": len(page_audits),
        "total_images": sum(p["images"]["total"] for p in page_audits),
        "total_missing_alt": sum(p["images"]["missing_alt"] for p in page_audits),
        "total_internal_links": sum(p["internal_links"]["count"] for p in page_audits),
        "pages_without_title": sum(1 for p in page_audits if not p["title"]["present"]),
        "pages_without_meta_desc": sum(
            1 for p in page_audits if not p["meta_description"]["present"]
        ),
        "pages_without_canonical": sum(1 for p in page_audits if not p["canonical"]["present"]),
        "pages_without_viewport": sum(1 for p in page_audits if not p["viewport"]["present"]),
    }

    return {
        "pages": page_audits,
        "summary": summary,
    }
