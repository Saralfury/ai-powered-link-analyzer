"""Competitor identification helpers.

Provides registrable-domain comparison, self-domain rejection, and
deduplication so the submitted site is never listed as its own competitor
and AI-suggested competitors are clearly labelled.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

FALLBACK_COMPETITORS: List[Dict[str, Any]] = [
    {
        "name": "Competitor A",
        "overview": "Established player in the same category.",
        "strengths": ["Brand recognition", "Wide service range"],
        "weaknesses_or_gaps": ["Higher pricing", "Slower support"],
        "ai_suggested": True,
        "source": "llm",
    },
    {
        "name": "Competitor B",
        "overview": "Growing challenger focused on digital solutions.",
        "strengths": ["Modern tech stack", "Agile delivery"],
        "weaknesses_or_gaps": ["Smaller team", "Limited case studies"],
        "ai_suggested": True,
        "source": "llm",
    },
    {
        "name": "Competitor C",
        "overview": "Local/regional service provider.",
        "strengths": ["Local presence", "Personalized service"],
        "weaknesses_or_gaps": ["Limited scale", "Basic online presence"],
        "ai_suggested": True,
        "source": "llm",
    },
]


def registrable_domain(host: str) -> str:
    """Return the registrable domain (last two host labels).

    Example: "www.example.com" -> "example.com"; "sub.co.uk" -> "sub.co.uk".
    Known limitation: multi-part TLDs like co.uk are treated as a single label.
    """
    host = host.lower().strip().rstrip(".")
    # Strip port if present.
    host = host.split(":")[0]
    parts = host.split(".")
    # Drop empty parts from e.g. trailing dot.
    parts = [p for p in parts if p]
    if len(parts) <= 2:
        return host
    return ".".join(parts[-2:])


def _same_registrable_domain(a: str, b: str) -> bool:
    return registrable_domain(a) == registrable_domain(b) and registrable_domain(a) != ""


def reject_self_domain_competitors(
    competitors: List[Dict[str, Any]], submitted_domain: str
) -> List[Dict[str, Any]]:
    """Remove any competitor whose registrable domain matches the submitted site."""
    submitted_rd = registrable_domain(submitted_domain)
    result: List[Dict[str, Any]] = []
    for comp in competitors:
        comp_domain = comp.get("domain") or comp.get("name") or ""
        if _same_registrable_domain(comp_domain, submitted_domain):
            continue  # reject self as competitor
        result.append(comp)
    return result


def deduplicate_competitors(competitors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate competitors by registrable domain (first occurrence wins)."""
    seen: set = set()
    result: List[Dict[str, Any]] = []
    for comp in competitors:
        domain = comp.get("domain") or comp.get("name") or ""
        rd = registrable_domain(domain)
        if rd in seen:
            continue
        seen.add(rd)
        result.append(comp)
    return result


def ensure_minimum_competitors(
    competitors: List[Dict[str, Any]], minimum: int = 3
) -> List[Dict[str, Any]]:
    """Pad the competitor list with clearly-labelled fallback entries."""
    result = list(competitors)
    index = 1
    while len(result) < minimum:
        fallback = dict(
            FALLBACK_COMPETITORS[(len(result) - len(competitors)) % len(FALLBACK_COMPETITORS)]
        )
        fallback["name"] = f"Competitor {index}"
        fallback["ai_suggested"] = True
        fallback["source"] = "llm"
        fallback.setdefault("overview", "AI-generated suggestion — verify independently.")
        result.append(fallback)
        index += 1
    return result


def extract_competitor_hints_from_links(links: List[str], current_domain: str) -> List[str]:
    """Very light hint extraction from outbound links (not a source of truth)."""
    hints: List[str] = []
    for link in links:
        if current_domain and current_domain in link:
            continue
        hints.append(link)
    return hints[:10]
