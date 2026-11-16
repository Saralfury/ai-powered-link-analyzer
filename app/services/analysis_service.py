"""Analysis service: orchestrates validate -> extract -> audit -> LLM -> validate -> respond.

Wraps the whole pipeline in a 90 s asyncio.wait_for budget (502 UPSTREAM_TIMEOUT on breach),
enforces evidence verification for observed claims, and uses a FIFO-capped in-memory cache
that replays recorded meta (tokens/cost/latency) with meta.cached=true on a hit.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import re
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.errors import ExtractionError, LLMError
from app.schemas import (
    Analysis,
    AnalysisMeta,
    Brand,
    Competitor,
    CompetitorAnalysis,
    LinkAnalysisResponse,
    SEOImprovements,
    Service,
    TargetAudience,
    TargetSearchQuery,
)
from app.services.competitor_service import (
    deduplicate_competitors,
    reject_self_domain_competitors,
)
from app.services.llm_service import BaseLLMService, get_llm_service
from app.services.website_extractor import fetch_website
from app.utils.validators import InvalidURLError, SSRFError, validate_url

logger = logging.getLogger("link-analysis.analysis")

# Overall pipeline budget: fetch + extract + LLM + validation must complete within 90 s.
PIPELINE_BUDGET_SECONDS = 90.0
# In-memory cache cap (FIFO eviction).
CACHE_MAX_ENTRIES = 100


def _normalize_text(text: str) -> str:
    """Lowercase and collapse whitespace for snippet comparison."""
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _snippet_in_page(snippet: str, page_text: str) -> bool:
    """Return True if the normalized snippet appears in the normalized page text."""
    return _normalize_text(snippet) in _normalize_text(page_text)


class AnalysisService:
    def __init__(self, llm_service: BaseLLMService | None = None) -> None:
        self.llm: BaseLLMService = llm_service or get_llm_service()
        # FIFO-capped cache: key -> response dict. Evicts oldest when full.
        self._cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._cache_enabled = settings.CACHE_ENABLED

    async def analyze(self, url: str) -> LinkAnalysisResponse:
        """Run the full pipeline inside a single asyncio.wait_for budget."""
        try:
            return await asyncio.wait_for(
                self._analyze_unbounded(url), timeout=PIPELINE_BUDGET_SECONDS
            )
        except Exception as exc:  # noqa: BLE001
            if isinstance(exc, asyncio.TimeoutError):
                logger.exception("Pipeline budget breached for %s", url)
                raise LLMError(
                    "Pipeline timeout: analysis did not complete within the budget.",
                    error_code="UPSTREAM_TIMEOUT",
                    status_code=502,
                    details={"budget_seconds": PIPELINE_BUDGET_SECONDS},
                ) from None
            raise

    async def _analyze_unbounded(self, url: str) -> LinkAnalysisResponse:
        start_total = time.perf_counter()

        # 1. Validate URL + SSRF protection.
        try:
            clean_url = validate_url(url)
        except (InvalidURLError, SSRFError):
            raise

        # 2. Extract content.
        logger.info("Extracting content from %s", clean_url)
        try:
            page = await fetch_website(clean_url)
        except ExtractionError:
            raise

        # 3. Cache lookup (key = normalised URL + content hash).
        content_hash = str(hash(page.get("text", "")))
        cache_key = f"{clean_url}:{content_hash}"
        if self._cache_enabled and cache_key in self._cache:
            logger.info("Cache hit for %s", clean_url)
            cached = self._cache[cache_key]
            # Replay recorded meta; mark as cache hit; do not re-measure.
            cached_meta = dict(cached["meta"])
            cached_meta["cached"] = True
            return LinkAnalysisResponse(**{**cached, "meta": cached_meta})

        # 4. LLM analysis with one repair retry.
        logger.info("Sending content to LLM (%s)", type(self.llm).__name__)
        raw, meta = await self._llm_analyze(page)

        # 5. Evidence verification: downgrade unverified "observed" claims to "inferred".
        page_text_by_url = self._build_page_text_lookup(page)
        raw = self._verify_observed_claims(raw, page_text_by_url)

        # 6. Build and validate response sections.
        brand = self._build_brand(raw.get("brand", {}), page)
        competitor_analysis = self._build_competitor_analysis(
            raw.get("competitor_analysis", {}), submitted_domain=clean_url
        )
        search_queries = self._build_search_queries(
            raw.get("target_search_queries", [])
        )
        seo = self._build_seo(raw.get("seo_improvements", {}), page)
        services = self._build_services(raw.get("top_services", []))
        audience = self._build_audience(raw.get("target_audience", {}))

        analysis = Analysis(
            competitor_analysis=competitor_analysis,
            target_search_queries=search_queries,
            seo_improvements=seo,
            top_services=services,
            target_audience=audience,
        )

        notes: List[str] = []
        if page.get("is_thin"):
            notes.append("Page content is thin; results may be less specific.")

        response_meta = AnalysisMeta(
            model=meta.get("model", settings.LLM_MODEL),
            provider=meta.get("provider", settings.LLM_PROVIDER),
            pages_analyzed=page.get("pages_analyzed", 1),
            input_tokens=meta.get("input_tokens"),
            output_tokens=meta.get("output_tokens"),
            estimated_cost_usd=None,
            latency_ms=meta.get("latency_ms"),
            cached=False,
            notes=notes,
        )

        response = LinkAnalysisResponse(
            success=True,
            website=clean_url,
            brand=brand,
            analysis=analysis,
            meta=response_meta,
            data_sources=["website", "llm"],
        )

        # 7. Cache the result (FIFO-capped).
        if self._cache_enabled:
            self._store_in_cache(cache_key, response.model_dump())

        total_latency = time.perf_counter() - start_total
        logger.info(
            "Analysis complete for %s in %.2fs (LLM %.2fs)",
            clean_url, total_latency, meta.get("latency_seconds", 0),
        )
        return response

    # ------------------------------------------------------------------
    # Cache helpers (FIFO-capped)
    # ------------------------------------------------------------------
    def _store_in_cache(self, key: str, value: Dict[str, Any]) -> None:
        """Insert into cache, evicting oldest entry when over cap."""
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        while len(self._cache) > CACHE_MAX_ENTRIES:
            self._cache.popitem(last=False)

    # ------------------------------------------------------------------
    # Evidence verification
    # ------------------------------------------------------------------
    def _build_page_text_lookup(self, page: Dict[str, Any]) -> Dict[str, str]:
        """Map each fetched page URL to its cleaned text."""
        lookup: Dict[str, str] = {}
        for p in page.get("pages", []):
            lookup[p.get("url", "")] = p.get("text", "")
        # Always include the homepage URL itself.
        if page.get("url"):
            lookup.setdefault(page["url"], page.get("text", ""))
        return lookup

    def _verify_observed_claims(
        self, raw: Dict[str, Any], page_text_by_url: Dict[str, str]
    ) -> Dict[str, Any]:
        """Downgrade any 'observed' claim whose snippet is not in the referenced page text.

        Claims that fail verification are marked inferred with a note; never silently kept
        as observed. Returns a (possibly modified) copy of raw.
        """
        raw = copy.deepcopy(raw)

        def check_item(item: Dict[str, Any], kind: str) -> None:
            if not isinstance(item, dict):
                return
            evidence = item.get("evidence") or {}
            source = item.get("source") or item.get("ai_suggested")
            # Only enforced for observed claims.
            if evidence and (item.get("source") == "observed" or not item.get("ai_suggested")):
                page_url = evidence.get("page", "")
                snippet = evidence.get("snippet", "")
                page_text = page_text_by_url.get(page_url, "")
                if page_url and snippet and not _snippet_in_page(snippet, page_text):
                    item["source"] = "inferred"
                    item.setdefault(
                        "notes",
                        f"Snippet not found on referenced page; downgraded from observed to inferred.",
                    )
                    raw.setdefault("_evidence_downgrades", []).append(
                        {"kind": kind, "name": item.get("name") or item.get("service_name"), "page": page_url}
                    )

        # Verify services.
        for svc in raw.get("top_services", []):
            check_item(svc, "service")
        # Verify competitors.
        for comp in raw.get("competitor_analysis", {}).get("competitors", []) if isinstance(raw.get("competitor_analysis"), dict) else []:
            check_item(comp, "competitor")

        return raw

    # ------------------------------------------------------------------
    # LLM with repair retry
    # ------------------------------------------------------------------
    async def _llm_analyze(
        self, page: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Call LLM with at most one repair retry."""
        last_error: Optional[Exception] = None
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                return await self.llm.analyze(page)
            except Exception as exc:
                last_error = exc
                logger.warning("LLM attempt %d failed: %s", attempt + 1, exc)
        raise LLMError(
            f"LLM analysis failed after {settings.LLM_MAX_RETRIES + 1} attempt(s)",
            details={"last_error": str(last_error)},
        )

    # --- section builders ---
    def _build_brand(self, raw: Dict[str, Any], page: Dict[str, Any]) -> Brand:
        return Brand(
            name=str(raw.get("name") or page.get("title") or "Unknown Brand"),
            category=str(raw.get("category") or "Technology Services"),
            summary=str(raw.get("summary") or ""),
        )

    def _build_competitor_analysis(
        self, raw: Dict[str, Any], submitted_domain: str = ""
    ) -> CompetitorAnalysis:
        competitors = []
        for item in raw.get("competitors", [])[:8]:
            competitors.append(
                {
                    "name": str(item.get("name") or "Unnamed Competitor"),
                    "overview": str(item.get("overview") or ""),
                    "domain": str(item.get("domain") or item.get("name") or ""),
                    "strengths": [str(s) for s in item.get("strengths", [])][:5],
                    "weaknesses_or_gaps": [str(w) for w in item.get("weaknesses_or_gaps", [])][:5],
                    "ai_suggested": bool(item.get("ai_suggested", True)),
                    "source": str(item.get("source", "llm")),
                    "source_urls": item.get("source_urls"),
                }
            )
        # Reject the submitted site as its own competitor.
        competitors = reject_self_domain_competitors(competitors, submitted_domain)
        # Deduplicate by registrable domain.
        competitors = deduplicate_competitors(competitors)
        # Guarantee at least 3 where possible.
        if len(competitors) < 3:
            competitors = ensure_minimum_competitors(competitors, minimum=3)

        comp_models = [
            Competitor(
                name=c["name"],
                overview=c["overview"],
                strengths=c["strengths"],
                weaknesses_or_gaps=c["weaknesses_or_gaps"],
                ai_suggested=c["ai_suggested"],
                source=c["source"],
                source_urls=c["source_urls"],
            )
            for c in competitors
        ]
        return CompetitorAnalysis(
            brand_overview=str(raw.get("brand_overview") or ""),
            competitors=comp_models,
            comparison_table=[
                {
                    "field": str(r.get("field", "")),
                    "your_brand": str(r.get("your_brand", "")),
                    "competitor": str(r.get("competitor", "")),
                }
                for r in raw.get("comparison_table", [])[:20]
            ],
            strengths=[str(s) for s in raw.get("strengths", [])][:5],
            opportunities=[str(o) for o in raw.get("opportunities", [])][:5],
        )

    def _build_search_queries(self, raw: list) -> list:
        queries = []
        seen = set()
        for item in raw:
            query = str(item.get("query") or "").strip()
            if not query or query.lower() in seen:
                continue
            seen.add(query.lower())
            queries.append(
                TargetSearchQuery(
                    query=query,
                    platforms=[str(p) for p in item.get("platforms", [])[:5]],
                    intent=str(item.get("intent") or "Service Discovery"),
                    business_relevance=str(item.get("business_relevance") or ""),
                    target_audience=str(item.get("target_audience") or ""),
                    search_volume=None,
                )
            )
        while len(queries) < 5:
            queries.append(
                TargetSearchQuery(
                    query="Professional services company",
                    platforms=["Google"],
                    intent="Service Discovery",
                    business_relevance="Fallback query.",
                    target_audience="Business buyers",
                    search_volume=None,
                )
            )
        return queries[:5]

    def _build_seo(self, raw: Dict[str, Any], page: Dict[str, Any]) -> SEOImprovements:
        return SEOImprovements(
            primary_keyword=str(raw.get("primary_keyword") or "Services"),
            secondary_keywords=[str(k) for k in raw.get("secondary_keywords", [])][:8],
            long_tail_keywords=[str(k) for k in raw.get("long_tail_keywords", [])][:8],
            relevant_business_keywords=[str(k) for k in raw.get("relevant_business_keywords", [])][:8],
            recommended_title=str(raw.get("recommended_title") or page.get("title") or "Home"),
            primary_keyword_in_title=str(raw.get("primary_keyword_in_title") or ""),
            improved_title_structure=str(raw.get("improved_title_structure") or ""),
            meta_description=str(raw.get("meta_description") or ""),
            supporting_content=[str(c) for c in raw.get("supporting_content", [])][:8],
        )

    def _build_services(self, raw: list) -> list:
        services = []
        for item in raw[:5]:
            services.append(
                Service(
                    service_name=str(item.get("service_name") or "Unnamed Service"),
                    description=str(item.get("description") or ""),
                    target_industry=str(item.get("target_industry") or "General"),
                    target_customer=str(item.get("target_customer") or "Businesses"),
                    main_benefit=str(item.get("main_benefit") or ""),
                    inferred=bool(item.get("inferred", False)),
                    source=str(item.get("source", "llm")),
                    evidence=item.get("evidence"),
                )
            )
        return services

    def _build_audience(self, raw: Dict[str, Any]) -> TargetAudience:
        return TargetAudience(
            primary_audience=[str(a) for a in raw.get("primary_audience", [])],
            secondary_audience=[str(a) for a in raw.get("secondary_audience", [])],
            industry_segments=[str(i) for i in raw.get("industry_segments", [])],
            business_types=[str(b) for b in raw.get("business_types", [])],
            customer_profiles=[str(p) for p in raw.get("customer_profiles", [])],
            location_focus=str(raw.get("location_focus") or ""),
            customer_needs=[str(n) for n in raw.get("customer_needs", [])],
            customer_challenges=[str(c) for c in raw.get("customer_challenges", [])],
            customer_interests=[str(i) for i in raw.get("customer_interests", [])],
            recommended_segments=[str(s) for s in raw.get("recommended_segments", [])],
        )
