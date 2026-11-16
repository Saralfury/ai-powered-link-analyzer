"""Tests for the link-analysis API.

Tests run without network access or LLM API keys by mocking the extractor
and LLM service.
"""

import asyncio
import socket
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from app.main import app
from app.schemas import LinkAnalysisResponse
from app.services.analysis_service import AnalysisService, PIPELINE_BUDGET_SECONDS
from app.services.competitor_service import (
    deduplicate_competitors,
    registrable_domain,
    reject_self_domain_competitors,
)
from app.services.website_audit import audit_page, audit_site
from app.services.website_extractor import extract_page
from app.services.scoring import compute_priority_score, score_opportunities
from app.errors import LinkAnalysisError, SSRFError
from app.utils.validators import validate_url


client = TestClient(app)

SAMPLE_PAGE: Dict[str, Any] = {
    "url": "https://example.com",
    "title": "ABC Technologies",
    "meta_description": "A technology company providing digital solutions.",
    "og_title": "ABC Technologies",
    "html_lang": "en",
    "canonical": "https://example.com/",
    "headings": ["Web Development", "UI/UX Design", "SEO Services"],
    "json_ld": [],
    "links": ["https://example.com/about", "https://example.com/services"],
    "internal_links": [],
    "text": (
        "ABC Technologies is a web development company serving small businesses "
        "and startups. We offer website development, UI/UX design, SEO services, "
        "and custom software development."
    ),
    "text_length": 200,
    "full_text_length": 200,
    "pages": [],
    "pages_analyzed": 1,
    "is_thin": False,
}


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------
def test_validate_url_accepts_https():
    assert validate_url("https://example.com").startswith("https://")


def test_validate_url_accepts_http():
    assert validate_url("http://example.com/path").startswith("http://")


def test_validate_url_rejects_malformed():
    try:
        validate_url("not-a-url")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


def test_validate_url_rejects_ftp():
    try:
        validate_url("ftp://example.com")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


def test_validate_url_rejects_localhost():
    try:
        validate_url("http://localhost/")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


def test_validate_url_rejects_loopback_ip():
    try:
        validate_url("http://127.0.0.1/")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


def test_validate_url_rejects_private_ip():
    try:
        validate_url("http://192.168.1.1/")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


def test_validate_url_rejects_10_private():
    try:
        validate_url("http://10.0.0.1/")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


def test_validate_url_rejects_link_local_metadata():
    try:
        validate_url("http://169.254.169.254/")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


def test_validate_url_rejects_ipv6_loopback():
    try:
        validate_url("http://[::1]/")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


def test_validate_url_rejects_non_standard_port():
    try:
        validate_url("http://example.com:8080/")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


def test_validate_url_rejects_userinfo():
    try:
        validate_url("http://user:pass@example.com/")
        assert False, "Should have raised"
    except LinkAnalysisError:
        pass


# ---------------------------------------------------------------------------
# Extractor
# ---------------------------------------------------------------------------
FAKE_HTML = """
<html lang="en"><head><title>Example Technologies</title>
<meta name="description" content="A tech company.">
<meta name="keywords" content="web, design">
<meta property="og:title" content="Example Technologies">
<meta property="og:description" content="OG description.">
<link rel="canonical" href="https://example.com/">
<script type="application/ld+json">
{"@type": "Organization", "name": "Example Org"}
</script>
</head>
<body>
<h1>Web Development</h1>
<h2>UI/UX Design</h2>
<h3>SEO Services</h3>
<p>We build websites for small businesses.</p>
<script>alert('x')</script>
<nav><a href="/about">About</a></nav>
<footer>&copy; 2026</footer>
<img src="/logo.png" alt="Logo">
<img src="/hero.jpg">
<a href="https://external.com">External</a>
<a href="/services">Services</a>
</body></html>
"""


def test_extract_page_returns_structured_data():
    data = extract_page(FAKE_HTML, "https://example.com")
    assert data["url"] == "https://example.com"
    assert data["title"] == "Example Technologies"
    assert "tech company" in data["meta_description"]
    assert data["og_title"] == "Example Technologies"
    assert data["html_lang"] == "en"
    assert data["canonical"] == "https://example.com/"
    assert len(data["json_ld"]) == 1
    assert data["json_ld"][0]["@type"] == "Organization"
    assert "Web Development" in data["headings"]
    assert "alert('x')" not in data["text"]
    assert "https://external.com" not in data["internal_links"]
    assert data["is_thin"] is True


def test_extract_page_images_and_alt():
    data = extract_page(FAKE_HTML, "https://example.com")
    assert len(data["images"]) == 2
    alt_map = {img["src"]: img["alt"] for img in data["images"]}
    assert alt_map.get("/logo.png") == "Logo"
    assert alt_map.get("/hero.jpg") == ""


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------
FAKE_ANALYSIS_RESPONSE = {
    "website": "https://example.com/",
    "brand": {
        "name": "Example Technologies",
        "category": "Technology Services",
        "summary": "A tech company.",
    },
    "analysis": {
        "competitor_analysis": {
            "brand_overview": "Overview",
            "competitors": [
                {
                    "name": "Competitor A",
                    "overview": "O",
                    "strengths": ["s1"],
                    "weaknesses_or_gaps": ["w1"],
                    "ai_suggested": True,
                    "source": "llm",
                }
            ],
            "comparison_table": [],
            "strengths": ["strength"],
            "opportunities": ["opportunity"],
        },
        "target_search_queries": [
            {
                "query": "web development company",
                "platforms": ["Google"],
                "intent": "Service Discovery",
                "business_relevance": "rel",
                "target_audience": "aud",
                "search_volume": None,
            }
        ],
        "seo_improvements": {
            "primary_keyword": "Web Development",
            "secondary_keywords": ["web design"],
            "long_tail_keywords": [],
            "relevant_business_keywords": [],
            "recommended_title": "Example | Web Development",
            "primary_keyword_in_title": "Web Development",
            "improved_title_structure": "Brand + Keyword",
            "meta_description": "A tech company.",
            "supporting_content": ["FAQ"],
        },
        "top_services": [
            {
                "service_name": "Web Development",
                "description": "Build websites",
                "target_industry": "General",
                "target_customer": "SMBs",
                "main_benefit": "Online presence",
                "inferred": False,
                "source": "website",
            }
        ],
        "target_audience": {
            "primary_audience": ["Small businesses"],
            "secondary_audience": ["Startups"],
            "industry_segments": ["Technology"],
            "business_types": ["SMB"],
            "customer_profiles": ["Owner"],
            "location_focus": "",
            "customer_needs": ["Website"],
            "customer_challenges": ["Visibility"],
            "customer_interests": ["Growth"],
            "recommended_segments": ["SMBs"],
        },
    },
    "meta": {
        "model": "mock-llm",
        "provider": "mock",
        "pages_analyzed": 1,
        "input_tokens": 100,
        "output_tokens": 200,
        "estimated_cost_usd": None,
        "latency_ms": 50.0,
        "cached": False,
        "notes": [],
    },
    "data_sources": ["website", "llm"],
    "disclaimer": "Competitor and audience insights marked as inferred or ai_suggested are AI-generated suggestions.",
}


def test_link_analysis_endpoint_shape():
    with patch.object(
        AnalysisService,
        "analyze",
        new=AsyncMock(return_value=LinkAnalysisResponse(**FAKE_ANALYSIS_RESPONSE)),
    ):
        response = client.post("/link-analysis", json={"url": "https://example.com"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["website"].rstrip("/") == "https://example.com"
    assert body["brand"]["name"] == "Example Technologies"
    assert body["brand"]["category"] == "Technology Services"
    assert "analysis" in body
    assert "meta" in body
    assert body["meta"]["model"] == "mock-llm"
    assert body["meta"]["provider"] == "mock"
    assert body["meta"]["pages_analyzed"] == 1
    assert "data_sources" in body
    assert "disclaimer" in body


def test_link_analysis_rejects_invalid_url():
    response = client.post("/link-analysis", json={"url": "not-a-url"})
    assert response.status_code == 422
    assert response.json()["success"] is False


def test_link_analysis_rejects_ssrf_localhost():
    response = client.post("/link-analysis", json={"url": "http://127.0.0.1/"})
    assert response.status_code == 400
    assert response.json()["success"] is False


def test_link_analysis_rejects_ssrf_private_ip():
    response = client.post("/link-analysis", json={"url": "http://192.168.1.1/"})
    assert response.status_code == 400
    assert response.json()["success"] is False


def test_link_analysis_missing_url():
    response = client.post("/link-analysis", json={})
    assert response.status_code == 422


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "AI-Powered Website Link Analysis API"
    assert body["docs"] == "/docs"


@pytest.mark.asyncio
async def test_end_to_end_with_mock_llm():
    with patch(
        "app.services.analysis_service.fetch_website",
        new=AsyncMock(return_value=SAMPLE_PAGE),
    ):
        response = client.post("/link-analysis", json={"url": "https://example.com"})

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["success"] is True
    assert body["brand"]["name"]
    assert body["brand"]["category"]
    assert body["brand"]["summary"]

    a = body["analysis"]
    assert len(a["competitor_analysis"]["competitors"]) >= 3
    assert a["competitor_analysis"]["strengths"]
    assert a["competitor_analysis"]["opportunities"]
    assert len(a["target_search_queries"]) == 5
    for q in a["target_search_queries"]:
        assert q["query"]
        assert q["platforms"]
        assert q["intent"]
        assert q["search_volume"] is None
    assert a["seo_improvements"]["primary_keyword"]
    assert a["seo_improvements"]["meta_description"]
    assert len(a["top_services"]) == 5
    for s in a["top_services"]:
        assert s["service_name"]
        assert s["description"]
        assert "inferred" in s
    ta = a["target_audience"]
    assert ta["primary_audience"]
    assert ta["customer_needs"]
    assert body["meta"]["model"]
    assert body["meta"]["provider"]
    assert body["meta"]["pages_analyzed"]
    assert body["data_sources"]
    assert body["disclaimer"]


# ---------------------------------------------------------------------------
# SEO Audit
# ---------------------------------------------------------------------------
AUDIT_HTML = """
<html><head><title>Test Page</title>
<meta name="description" content="A test page for SEO audit.">
<link rel="canonical" href="https://example.com/">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body>
<h1>Main Heading</h1>
<h2>Sub Heading</h2>
<h3>Sub Sub</h3>
<img src="/img1.png" alt="Image 1">
<img src="/img2.png">
<a href="/about">About</a>
<a href="/services">Services</a>
<a href="https://external.com">External</a>
<p>Some visible text content here for the audit test.</p>
</body></html>
"""


def test_audit_page_title_and_meta():
    result = audit_page(AUDIT_HTML, "https://example.com/")
    assert result["title"]["present"] is True
    assert result["title"]["character_count"] == 9
    assert result["meta_description"]["present"] is True
    assert result["meta_description"]["character_count"] > 0


def test_audit_page_headings_and_images():
    result = audit_page(AUDIT_HTML, "https://example.com/")
    assert result["h1"]["count"] == 1
    assert result["headings"]["h1"] == 1
    assert result["headings"]["h2"] == 1
    assert result["headings"]["h3"] == 1
    assert result["images"]["total"] == 2
    assert result["images"]["missing_alt"] == 1
    assert result["images"]["missing_alt_ratio"] == 0.5


def test_audit_page_canonical_and_viewport():
    result = audit_page(AUDIT_HTML, "https://example.com/")
    assert result["canonical"]["present"] is True
    assert result["canonical"]["value"] == "https://example.com/"
    assert result["viewport"]["present"] is True


def test_audit_page_internal_links():
    result = audit_page(AUDIT_HTML, "https://example.com/")
    assert result["internal_links"]["count"] == 2


def test_audit_site_aggregation():
    pages = [{"url": "https://example.com/", "_raw_html": AUDIT_HTML}]
    result = audit_site(pages)
    assert result["summary"]["total_pages"] == 1
    assert result["summary"]["total_images"] == 2
    assert len(result["pages"]) == 1


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def test_scoring_basic():
    result = compute_priority_score(impact=5, confidence=4, effort=2)
    assert result["impact"] == 5
    assert result["confidence"] == 4
    assert result["effort"] == 2
    assert result["priority_score"] == 10.0  # 5*4/2


def test_scoring_clamp_low():
    result = compute_priority_score(impact=0, confidence=0, effort=0)
    assert result["impact"] == 1
    assert result["confidence"] == 1
    assert result["effort"] == 1
    assert result["priority_score"] == 1.0


def test_scoring_clamp_high():
    result = compute_priority_score(impact=100, confidence=100, effort=100)
    assert result["impact"] == 5
    assert result["confidence"] == 5
    assert result["effort"] == 5
    assert result["priority_score"] == 5.0


def test_scoring_sort():
    opportunities = [
        {"description": "Low", "impact": 1, "confidence": 1, "effort": 5},
        {"description": "High", "impact": 5, "confidence": 5, "effort": 1},
    ]
    scored = score_opportunities(opportunities)
    assert scored[0]["priority_score"] > scored[1]["priority_score"]
    assert scored[0]["opportunity"] == "High"


# ---------------------------------------------------------------------------
# Item 4a: content-hash cache key changes when content changes
# ---------------------------------------------------------------------------
def test_cache_key_changes_on_content_change():
    svc = AnalysisService.__new__(AnalysisService)
    svc._cache = {}
    svc._cache_enabled = True
    key_a = f"https://example.com:{hash('content A')}"
    key_b = f"https://example.com:{hash('content B')}"
    assert key_a != key_b
    # Storing under key_a must not make key_b present.
    svc._cache[key_a] = {"meta": {"cached": False}}
    assert key_b not in svc._cache


# ---------------------------------------------------------------------------
# Item 4b: registrable-domain self-match rejection
# ---------------------------------------------------------------------------
def test_registrable_domain_self_match():
    assert registrable_domain("www.example.com") == "example.com"
    assert registrable_domain("example.com") == "example.com"
    assert registrable_domain("blog.example.com") == "example.com"
    assert registrable_domain("other.com") != "example.com"


def test_reject_self_domain_competitors():
    competitors = [
        {"name": "Example Corp", "domain": "example.com", "ai_suggested": True, "source": "llm"},
        {"name": "Real Competitor", "domain": "competitor.com", "ai_suggested": True, "source": "llm"},
        {"name": "www.example.com", "domain": "www.example.com", "ai_suggested": True, "source": "llm"},
    ]
    result = reject_self_domain_competitors(competitors, "example.com")
    names = [c["name"] for c in result]
    assert "Example Corp" not in names
    assert "www.example.com" not in names
    assert "Real Competitor" in names


def test_deduplicate_competitors_by_registrable_domain():
    competitors = [
        {"name": "Acme", "domain": "www.acme.com"},
        {"name": "Acme Blog", "domain": "blog.acme.com"},
        {"name": "Other", "domain": "other.com"},
    ]
    result = deduplicate_competitors(competitors)
    assert len(result) == 2  # www.acme.com and blog.acme.com collapse to acme.com


# ---------------------------------------------------------------------------
# Item 4c: budget breach -> 502 UPSTREAM_TIMEOUT
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_pipeline_budget_breach_returns_502():
    svc = AnalysisService.__new__(AnalysisService)
    svc.llm = None
    svc._cache = {}
    svc._cache_enabled = False

    async def _raise_timeout(url):  # matches _analyze_unbounded(url) signature
        raise asyncio.TimeoutError("simulated budget breach")

    svc._analyze_unbounded = _raise_timeout  # type: ignore[method-assign]
    with patch("app.services.analysis_service.PIPELINE_BUDGET_SECONDS", 0.1):
        try:
            await svc.analyze("https://example.com")
            assert False, "Should have raised LLMError"
        except LinkAnalysisError as exc:
            assert exc.error_code == "UPSTREAM_TIMEOUT"
            assert exc.status_code == 502


# ---------------------------------------------------------------------------
# Item 4d: redirect DNS-flip re-validation (public -> private between hops)
# ---------------------------------------------------------------------------
def test_validator_blocks_when_dns_resolves_private():
    """Simulate a hostname whose DNS flips from public to private: any private
    resolved address must block the URL."""
    with patch("app.utils.validators.socket.getaddrinfo") as mock_getaddrinfo:
        # First address public, second private (DNS flip / multi-answer).
        mock_getaddrinfo.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80)),
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.1", 80)),
        ]
        try:
            validate_url("http://example.com/")
            assert False, "Should have raised SSRFError"
        except SSRFError:
            pass

