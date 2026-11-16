"""Pydantic request/response schemas for the link-analysis API.

Preserves the exact response contract from the practical-test brief:
- success, website, brand
- analysis.competitor_analysis
- analysis.target_search_queries
- analysis.seo_improvements
- analysis.top_services
- analysis.target_audience
- meta.model, meta.provider, meta.pages_analyzed
- meta.input_tokens, meta.output_tokens, meta.estimated_cost_usd
- meta.latency_ms, meta.cached, meta.notes
"""

from __future__ import annotations

from typing import Any, List, Optional

from pydantic import BaseModel, HttpUrl, Field, field_validator


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
class LinkAnalysisRequest(BaseModel):
    url: HttpUrl = Field(..., description="Public website URL to analyse.")


# ---------------------------------------------------------------------------
# Brand
# ---------------------------------------------------------------------------
class Brand(BaseModel):
    name: str = Field(..., description="Detected brand / company name.")
    category: str = Field(..., description="Main business category.")
    summary: str = Field(..., description="Short description of the business.")


# ---------------------------------------------------------------------------
# Competitor analysis (Section 1)
# ---------------------------------------------------------------------------
class Competitor(BaseModel):
    name: str = Field(..., description="Competitor brand name.")
    overview: str = Field(default="", description="Brief overview.")
    strengths: List[str] = Field(default_factory=list)
    weaknesses_or_gaps: List[str] = Field(default_factory=list)
    ai_suggested: bool = Field(default=True, description="AI-generated suggestion.")
    source: str = Field(default="llm", description="Data source: 'llm' or 'researched'.")
    source_urls: Optional[List[str]] = Field(
        default=None, description="Required if source is 'researched'."
    )

    @field_validator("source_urls")
    @classmethod
    def _require_source_urls_for_researched(cls, v, info):
        if info.data and info.data.get("source") == "researched" and not v:
            raise ValueError("researched competitors must include source_urls")
        return v


class BrandComparisonRow(BaseModel):
    field: str
    your_brand: str
    competitor: str


class CompetitorAnalysis(BaseModel):
    brand_overview: str
    competitors: List[Competitor] = Field(default_factory=list)
    comparison_table: List[BrandComparisonRow] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    opportunities: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Target search queries (Section 2)
# ---------------------------------------------------------------------------
class TargetSearchQuery(BaseModel):
    query: str
    platforms: List[str]
    intent: str
    business_relevance: str = ""
    target_audience: str = ""
    search_volume: Optional[Any] = Field(
        default=None, description="Null unless a real data source is connected."
    )


# ---------------------------------------------------------------------------
# SEO improvements (Section 3)
# ---------------------------------------------------------------------------
class SEOImprovements(BaseModel):
    primary_keyword: str
    secondary_keywords: List[str] = Field(default_factory=list)
    long_tail_keywords: List[str] = Field(default_factory=list)
    relevant_business_keywords: List[str] = Field(default_factory=list)
    recommended_title: str
    primary_keyword_in_title: str = ""
    improved_title_structure: str = ""
    meta_description: str
    supporting_content: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Top services (Section 4)
# ---------------------------------------------------------------------------
class Service(BaseModel):
    service_name: str
    description: str
    target_industry: str
    target_customer: str
    main_benefit: str
    inferred: bool = False
    source: str = "llm"
    evidence: Optional[Dict[str, Any]] = None


# ---------------------------------------------------------------------------
# Target audience (Section 5)
# ---------------------------------------------------------------------------
class TargetAudience(BaseModel):
    primary_audience: List[str] = Field(default_factory=list)
    secondary_audience: List[str] = Field(default_factory=list)
    industry_segments: List[str] = Field(default_factory=list)
    business_types: List[str] = Field(default_factory=list)
    customer_profiles: List[str] = Field(default_factory=list)
    location_focus: str = ""
    customer_needs: List[str] = Field(default_factory=list)
    customer_challenges: List[str] = Field(default_factory=list)
    customer_interests: List[str] = Field(default_factory=list)
    recommended_segments: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Meta block
# ---------------------------------------------------------------------------
class AnalysisMeta(BaseModel):
    model: str = Field(default="", description="LLM model used.")
    provider: str = Field(default="", description="LLM provider name.")
    pages_analyzed: int = Field(default=1)
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    latency_ms: Optional[float] = None
    cached: bool = Field(default=False)
    notes: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------
class Analysis(BaseModel):
    competitor_analysis: CompetitorAnalysis
    target_search_queries: List[TargetSearchQuery]
    seo_improvements: SEOImprovements
    top_services: List[Service]
    target_audience: TargetAudience


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class LinkAnalysisResponse(BaseModel):
    success: bool = True
    website: str
    brand: Brand
    analysis: Analysis
    meta: AnalysisMeta = Field(default_factory=AnalysisMeta)
    data_sources: List[str] = Field(default_factory=list)
    disclaimer: str = Field(
        default=(
            "Competitor and audience insights marked as inferred or ai_suggested "
            "are AI-generated suggestions. Search query volumes are not reported."
        )
    )


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------
class ErrorResponse(BaseModel):
    success: bool = False
    website: Optional[str] = None
    error: dict
    detail: Optional[Any] = None
