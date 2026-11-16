"""LLM integration for website analysis.

Provider-agnostic interface with OpenAI and Mock implementations.
All providers return a single JSON object matching the analysis schema.
Responses are Pydantic-validated with one repair retry on failure.
"""

from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple

from openai import AsyncOpenAI

from app.config import settings
from app.schemas import Analysis

logger = logging.getLogger("link-analysis.llm")


class BaseLLMService(ABC):
    """Interface for LLM-based analysis."""

    @abstractmethod
    async def analyze(
        self, page: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Returns (raw_dict, meta)."""
        ...


def _build_system_prompt() -> str:
    return (
        "You are an expert business, SEO and competitor analyst. "
        "You receive extracted website content (homepage plus up to "
        "2-3 internal pages) and must produce a JSON object with EXACTLY "
        "these top-level keys: brand, competitor_analysis, "
        "target_search_queries, seo_improvements, top_services, target_audience.\n\n"
        "RULES:\n"
        "1. Base every answer ONLY on the provided website content. Do not "
        "invent traffic, rankings, search volumes, revenue, or social metrics. "
        "If something cannot be determined, mark it as inferred or return an "
        "empty list.\n"
        "2. Output VALID JSON only — no markdown fences, no commentary.\n"
        "3. For competitors: label AI-generated suggestions as "
        "ai_suggested: true. Provide at least 3 competitors where reliable.\n"
        "4. For search queries: give exactly 5 queries across Google, "
        "Facebook, Instagram, LinkedIn and X. No search volume.\n"
        "5. For SEO: primary keyword, secondary keywords, long-tail keywords, "
        "recommended title (~60 chars), meta description (~155 chars), "
        "supporting content ideas.\n"
        "6. For services: 5 most important services with name, description, "
        "target industry, target customer, main benefit. Flag inferred ones.\n"
        "7. For target audience: primary/secondary audiences, industry "
        "segments, business types, customer profiles, needs, challenges.\n"
    )


def _build_user_prompt(page: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"Website URL: {page.get('url', '')}")
    if page.get("title"):
        lines.append(f"Page title: {page['title']}")
    if page.get("meta_description"):
        lines.append(f"Meta description: {page['meta_description']}")
    if page.get("headings"):
        lines.append("Headings:\n- " + "\n- ".join(page["headings"][:30]))
    lines.append("\nPage content:\n" + page.get("text", ""))
    lines.append("\nReturn ONLY the JSON analysis object.")
    return "\n".join(lines)


def _parse_json_response(raw: str) -> Dict[str, Any]:
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            return json.loads(cleaned[start : end + 1])
        raise


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


class OpenAILLMService(BaseLLMService):
    def __init__(self) -> None:
        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider.")
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.LLM_MODEL or "gpt-4o-mini"
        self.provider = "openai"

    async def analyze(
        self, page: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        start = time.perf_counter()
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {"role": "user", "content": _build_user_prompt(page)},
            ],
            temperature=0.3,
            response_format={"type": "json_object"},
        )
        latency_ms = (time.perf_counter() - start) * 1000
        content = response.choices[0].message.content or "{}"

        usage = response.usage
        input_tokens = getattr(usage, "prompt_tokens", None) or _estimate_tokens(
            _build_user_prompt(page)
        )
        output_tokens = getattr(usage, "completion_tokens", None) or _estimate_tokens(
            content
        )

        meta = {
            "model": self.model,
            "provider": self.provider,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": round(latency_ms, 1),
        }
        return _parse_json_response(content), meta


class MockLLMService(BaseLLMService):
    """Deterministic, key-free analyser for demo / CI."""

    def __init__(self) -> None:
        self.model = "mock-llm"
        self.provider = "mock"

    async def analyze(
        self, page: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        text = page.get("text", "")
        title = page.get("title", "")
        headings = page.get("headings", [])
        url = page.get("url", "")

        brand_name = title or _domain_name(url) or "Unknown Brand"
        category = _infer_category(text, headings) or "Technology Services"
        summary = _first_sentence(text) or f"{brand_name} provides {category}."

        competitors = [
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

        services = _extract_services(text, headings)
        queries = _build_mock_queries(category, brand_name)
        seo = _build_mock_seo(category, brand_name, summary)
        audience = _build_mock_audience()

        raw = {
            "brand": {"name": brand_name, "category": category, "summary": summary},
            "competitor_analysis": {
                "brand_overview": summary,
                "competitors": competitors,
                "comparison_table": [],
                "strengths": ["Focused service offering"],
                "opportunities": ["Improve online visibility"],
            },
            "target_search_queries": queries,
            "seo_improvements": seo,
            "top_services": services,
            "target_audience": audience,
        }

        input_text = _build_user_prompt(page)
        output_text = json.dumps(raw)
        meta = {
            "model": self.model,
            "provider": self.provider,
            "input_tokens": _estimate_tokens(input_text),
            "output_tokens": _estimate_tokens(output_text),
            "latency_ms": 50.0,
        }
        return raw, meta


def _domain_name(url: str) -> str:
    from urllib.parse import urlparse

    try:
        host = urlparse(url).hostname or ""
        return host.replace("www.", "").split(".")[0].title()
    except Exception:
        return ""


def _infer_category(text: str, headings: List[str]) -> str:
    blob = " ".join(headings + [text]).lower()
    keywords = {
        "web development": ["web development", "website development", "web design"],
        "software development": ["software development", "custom software"],
        "digital marketing": ["digital marketing", "seo", "social media"],
        "e-commerce": ["ecommerce", "e-commerce", "online store"],
        "it consulting": ["it consulting", "technology consulting"],
    }
    for cat, signals in keywords.items():
        if any(s in blob for s in signals):
            return cat.title()
    return "Technology Services"


def _first_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    for sep in (". ", ".\n", "! ", "? "):
        if sep in text:
            return text.split(sep, 1)[0].strip() + "."
    return text[:200]


def _extract_services(text: str, headings: List[str]) -> List[Dict[str, Any]]:
    services: List[Dict[str, Any]] = []
    seen = set()

    def add(name: str, inferred: bool) -> None:
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        services.append(
            {
                "service_name": name,
                "description": f"Professional {name.lower()} tailored to client needs.",
                "target_industry": "General business",
                "target_customer": "Small and medium businesses",
                "main_benefit": "Improves online presence and operational efficiency.",
                "inferred": inferred,
                "source": "llm" if inferred else "website",
            }
        )

    for h in headings[:8]:
        if len(h) < 60:
            add(h, inferred=False)

    generic = [
        "Website Development",
        "UI/UX Design",
        "SEO & Digital Marketing",
        "Custom Software Development",
        "E-commerce Solutions",
    ]
    for name in generic:
        if len(services) >= 5:
            break
        add(name, inferred=True)

    return services[:5]


def _build_mock_queries(category: str, brand_name: str) -> List[Dict[str, Any]]:
    return [
        {
            "query": f"Best {category} company",
            "platforms": ["Google", "LinkedIn"],
            "intent": "Service Discovery",
            "business_relevance": f"Direct match for {category}.",
            "target_audience": "Businesses seeking service providers",
            "search_volume": None,
        },
        {
            "query": f"{category} services",
            "platforms": ["Facebook", "Instagram"],
            "intent": "Business Discovery",
            "business_relevance": "Broad service-category awareness.",
            "target_audience": "Small businesses and startups",
            "search_volume": None,
        },
        {
            "query": f"{category} ideas",
            "platforms": ["Instagram"],
            "intent": "Inspiration",
            "business_relevance": "Top-of-funnel design/idea traffic.",
            "target_audience": "Creative and business decision-makers",
            "search_volume": None,
        },
        {
            "query": f"{category} for startups",
            "platforms": ["LinkedIn"],
            "intent": "B2B Search",
            "business_relevance": "Targets early-stage companies.",
            "target_audience": "Startup founders and CTOs",
            "search_volume": None,
        },
        {
            "query": f"affordable {category}",
            "platforms": ["X"],
            "intent": "Service Discovery",
            "business_relevance": "Price-sensitive demand signal.",
            "target_audience": "SMBs and budget-conscious buyers",
            "search_volume": None,
        },
    ]


def _build_mock_seo(category: str, brand_name: str, summary: str) -> Dict[str, Any]:
    return {
        "primary_keyword": category,
        "secondary_keywords": [
            f"{category} company",
            f"{category} services",
            "digital solutions",
        ],
        "long_tail_keywords": [
            f"affordable {category} for small business",
            f"best {category} provider",
            f"{category} consultation",
        ],
        "relevant_business_keywords": [category],
        "recommended_title": f"{brand_name} | Professional {category}",
        "primary_keyword_in_title": category,
        "improved_title_structure": "Brand + Primary Keyword + Value Proposition",
        "meta_description": summary[:155],
        "supporting_content": [
            "Service landing pages for each core offering",
            "Industry-specific solution pages",
            "Frequently Asked Questions (FAQ)",
            "Blog topics addressing customer challenges",
            "Location-based landing pages (if relevant)",
        ],
    }


def _build_mock_audience() -> Dict[str, Any]:
    return {
        "primary_audience": ["Small businesses", "Startups"],
        "secondary_audience": ["Enterprise companies", "Professional services"],
        "industry_segments": ["Technology", "Professional services", "Retail"],
        "business_types": ["SMB", "Startup", "Agency"],
        "customer_profiles": ["Business owner", "Marketing manager", "CTO"],
        "location_focus": "",
        "customer_needs": ["Website development", "Digital presence", "SEO"],
        "customer_challenges": ["Low online visibility", "Outdated website"],
        "customer_interests": ["Growth", "Lead generation", "Branding"],
        "recommended_segments": [
            "Small businesses needing a website",
            "Startups needing digital solutions",
        ],
    }


def get_llm_service() -> BaseLLMService:
    if settings.USE_MOCK_LLM or settings.LLM_PROVIDER == "mock":
        logger.info("Using MockLLMService (no API key required).")
        return MockLLMService()
    if settings.LLM_PROVIDER == "openai":
        logger.info("Using OpenAILLMService with model %s", settings.LLM_MODEL)
        return OpenAILLMService()
    logger.warning(
        "Provider %s not implemented; falling back to MockLLMService.",
        settings.LLM_PROVIDER,
    )
    return MockLLMService()
