# AI-Powered Website Link Analysis API

A FastAPI application that analyzes a public website URL and returns structured
business, competitor, SEO, search-query, service, and target-audience insights.

The application extracts website content with HTTPX and BeautifulSoup, analyzes
it using a configurable LLM provider (OpenAI, Anthropic, Gemini, or a built-in
mock for demonstration), and returns all findings as validated JSON.

**Endpoint:** `POST http://localhost:4000/link-analysis`  
**Interactive docs:** `http://localhost:4000/docs`  
**Health check:** `http://localhost:4000/health`

---

## What it does

**Input:** A public website URL (e.g., `https://example.com`).

**Process:**
1. Validates the URL and blocks private/loopback addresses (SSRF protection).
2. Fetches the homepage and up to three relevant same-domain pages.
3. Extracts title, meta tags, Open Graph data, headings, JSON-LD, text, and links.
4. Runs a deterministic SEO audit (title length, H1 count, image alt ratio,
   canonical, viewport, internal links).
5. Sends cleaned content to an LLM provider for analysis.
6. Validates the LLM response against Pydantic schemas, with one repair retry.
7. Returns structured JSON across five sections.

**Output:** Five analysis sections:

1. **Competitor vs Your Brand** — brand overview, identified competitors,
   strengths, weaknesses/opportunities, and a comparison table.
2. **Top 5 Target Search Queries** — platform-aware queries for Google,
   Facebook, Instagram, LinkedIn, and X with intent and audience.
3. **SEO Improvements** — primary/secondary/long-tail keywords, recommended
   title, meta description, and supporting content ideas.
4. **Top 5 Services** — service name, description, target industry/customer,
   and main benefit (with `inferred` flags for AI-suggested items).
5. **Target Audience** — primary/secondary audiences, industries, business
   types, customer profiles, needs, challenges, and interests.

---

## Project structure

```
ai-powered-link-analyzer/
├── app/
│   ├── main.py                # FastAPI app, /health, POST /link-analysis
│   ├── config.py              # Pydantic-settings config (.env)
│   ├── errors.py              # Custom exceptions + HTTP status mapping
│   ├── schemas.py             # Request/response Pydantic models
│   ├── services/
│   │   ├── website_extractor.py   # HTTPX fetch + BeautifulSoup extraction
│   │   ├── website_audit.py       # Deterministic SEO audit
│   │   ├── llm_service.py         # OpenAI / Anthropic / Gemini / Mock
│   │   ├── analysis_service.py    # Pipeline orchestration
│   │   └── competitor_service.py  # Competitor dedup / self-rejection
│   │   └── scoring.py             # Opportunity scoring
│   └── utils/
│       └── validators.py          # URL validation + SSRF protection
├── frontend/
│   ├── index.html               # Frontend UI (served at /)
│   ├── styles.css               # Vanilla CSS
│   └── app.js                   # Vanilla JavaScript (fetch API)
├── examples/
│   └── sample-response.json     # Example API response
├── scripts/
│   └── benchmark_llms.py        # LLM provider benchmark script
├── tests/
│   └── test_link_analysis.py    # 36 tests (mocked, no network/keys)
├── docs/
│   ├── benchmarks/              # Benchmark results
│   ├── sample_responses/        # Example responses
│   └── screenshots/             # UI verification notes
├── .env.example                 # Environment variable template
├── .gitignore
├── Dockerfile                   # Container build
├── pytest.ini                   # Pytest configuration
├── requirements.txt             # Pinned dependencies
└── README.md
```

---

## Setup

### Prerequisites
Python 3.10+, `pip`, `venv`.

### Install

```bash
git clone https://github.com/Saralfury/ai-powered-link-analyzer.git
cd ai-powered-link-analyzer

python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your LLM API key if you want live provider mode.
Leave `USE_MOCK_LLM=true` to run in deterministic demonstration mode without any
API key.

### Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Visit `http://localhost:4000/` for the frontend UI or
`http://localhost:4000/docs` for the Swagger API documentation.

### Docker

```bash
docker build -t ai-link-analysis .
docker run -p 4000:4000 --env-file .env ai-link-analysis
```

### Tests

```bash
pytest -q
```

All tests use mocks and require no network access or LLM API keys.

---

## API

### POST /link-analysis

```http
POST http://localhost:4000/link-analysis
Content-Type: application/json

{
  "url": "https://example.com"
}
```

### Example response

```json
{
  "success": true,
  "website": "https://example.com/",
  "brand": {
    "name": "Example Domain",
    "category": "Technology Services",
    "summary": "This domain is for use in documentation examples."
  },
  "analysis": {
    "competitor_analysis": {
      "brand_overview": "…",
      "competitors": [
        {
          "name": "Competitor A",
          "overview": "Established player in the same category.",
          "strengths": ["Brand recognition", "Wide service range"],
          "weaknesses_or_gaps": ["Higher pricing", "Slower support"],
          "ai_suggested": true,
          "source": "llm"
        }
      ],
      "comparison_table": [
        {"field": "Brand Name", "your_brand": "Example Domain", "competitor": "Competitor A"}
      ],
      "strengths": ["Focused service offering"],
      "opportunities": ["Improve online visibility through SEO"]
    },
    "target_search_queries": [
      {
        "query": "Best Technology Services company",
        "platforms": ["Google", "LinkedIn"],
        "intent": "Service Discovery",
        "business_relevance": "…",
        "target_audience": "…",
        "search_volume": null
      }
    ],
    "seo_improvements": {
      "primary_keyword": "Technology Services",
      "secondary_keywords": ["Technology Services company"],
      "long_tail_keywords": ["affordable Technology Services for small business"],
      "relevant_business_keywords": ["Technology Services"],
      "recommended_title": "Example Domain | Professional Technology Services",
      "meta_description": "…",
      "supporting_content": ["Service landing pages", "FAQ", "Blog topics"]
    },
    "top_services": [
      {
        "service_name": "Web Development",
        "description": "Professional web development tailored to client needs.",
        "target_industry": "General business",
        "target_customer": "Small and medium businesses",
        "main_benefit": "Improves online presence and operational efficiency.",
        "inferred": false,
        "source": "website"
      }
    ],
    "target_audience": {
      "primary_audience": ["Small businesses", "Startups"],
      "secondary_audience": ["Enterprise companies"],
      "industry_segments": ["Technology", "Professional services"],
      "business_types": ["SMB", "Startup"],
      "customer_profiles": ["Business owner", "Marketing manager"],
      "location_focus": "",
      "customer_needs": ["Website development", "Digital presence"],
      "customer_challenges": ["Low online visibility"],
      "customer_interests": ["Growth", "Lead generation"],
      "recommended_segments": ["Small businesses needing a website"]
    }
  },
  "meta": {
    "model": "mock-llm",
    "provider": "mock",
    "pages_analyzed": 1,
    "input_tokens": 111,
    "output_tokens": 1378,
    "estimated_cost_usd": null,
    "latency_ms": 0.2,
    "cached": false,
    "notes": []
  },
  "data_sources": ["website", "llm"],
  "disclaimer": "Competitor and audience insights marked as inferred or ai_suggested are AI-generated suggestions. Search query volumes are not reported."
}
```

A complete committed example is available in `examples/sample-response.json`.

### Error handling

| Condition | HTTP status | Error code |
|-----------|-------------|------------|
| Malformed URL / unsupported scheme | 422 | `INVALID_URL` |
| Private / loopback / blocked destination | 400 | `BLOCKED_DESTINATION` |
| Website unreachable / non-HTML / fetch failure | 502 | `EXTRACTION_FAILED` |
| LLM failure after retry/fallback | 502 | `LLM_FAILED` |
| Request validation failure | 422 | `VALIDATION_ERROR` |
| Unexpected internal failure | 500 | `INTERNAL_ERROR` |

---

## Architecture

```text
URL input
    │
    ▼
URL validation + SSRF protection
    │
    ▼
Website extraction (homepage + up to 3 internal pages)
    │
    ▼
Deterministic SEO audit
    │
    ▼
LLM analysis (provider-agnostic, structured JSON)
    │
    ▼
Pydantic schema validation + evidence verification
    │
    ▼
Structured JSON response
```

### Key design decisions
* **Single LLM call:** All five sections are generated in one structured JSON
  response to minimize latency and API cost.
* **Provider-agnostic LLM:** The same pipeline works with OpenAI, Anthropic,
  Gemini, or a deterministic mock for testing/demonstration.
* **Provenance labels:** Every competitor and service carries `ai_suggested`
  or `inferred` flags so reviewers can distinguish extracted data from
  AI-generated suggestions.
* **No invented data:** Search query volumes are always `null`; competitors
  are clearly labeled as AI-suggested unless found on the website.

---

## Security

* **SSRF protection:** Only `http://` and `https://` on ports 80 and 443 are
  accepted. Private, loopback, link-local, multicast, reserved, and
  unspecified addresses are rejected via `ipaddress` checks and DNS
  resolution.
* **Redirect safety:** Automatic redirect following is disabled; up to five
  manual hops are each re-validated.
* **Credential management:** API keys are loaded from environment variables
  via `pydantic-settings`. `.env` is gitignored; `.env.example` contains
  placeholders only.
* **Prompt-injection defence:** Website content is delimited and treated as
  untrusted data; the system prompt instructs the model to ignore embedded
  instructions.

---

## LLM model research

Benchmark results are recorded in `docs/benchmarks/benchmark-results.json`.

**Measured results (mock provider, deterministic demo mode):**

| Provider | Model | Latency | Input tokens | Output tokens | JSON valid | Label |
|----------|-------|---------|--------------|---------------|------------|-------|
| Mock | mock-llm | 0.2 ms | 111 | 1,378 | Yes | measured |

OpenAI, Anthropic, and Gemini providers are implemented but were not tested
with live API keys during this submission; their results are labeled
`not_tested` and documented pricing is used for cost estimates only.

**Recommended model:** OpenAI `gpt-4o-mini`, based on its native JSON mode,
low latency, and competitive per-token pricing. Fallback: `gpt-3.5-turbo`.
Estimated cost per analysis is under $0.01 in most cases (documented pricing,
not measured).

---

## Cost optimization

* HTML is cleaned (scripts, styles, nav, footer removed) before being sent to
  the LLM.
* Page text is truncated to stay within token and cost budgets.
* A single LLM call generates all five sections, avoiding repeated API calls.
* Results are cached in memory (100-entry FIFO cap) keyed by normalized URL
  plus content hash; cache hits replay recorded metadata without re-billing.
* No search-volume or ranking data sources are called, eliminating extra API
  costs.

---

## Testing

36 tests cover URL validation, SSRF protection, extraction, SEO audit,
scoring, competitor deduplication, self-rejection, evidence verification,
pipeline budget enforcement, cache key behavior, endpoint contract, and
end-to-end pipeline behavior with the mock LLM. No live LLM or network calls
are required.

```bash
pytest -q
```

Continuous integration runs on every push/pull request via GitHub Actions.

---

## Limitations

* JavaScript-rendered (SPA) sites may yield thin content; a warning is added
  to `meta.notes`. Browser automation (e.g., Playwright) is future work.
* Competitor information is AI-generated unless it appears verbatim on the
  submitted site; every competitor carries `ai_suggested` / `source` labels.
* Search-query volumes are intentionally not reported.
* Benchmark results are based on limited runs; accuracy ratings are
  qualitative estimates, not formal benchmark scores.
* Residual DNS-rebinding risk remains with the fallback redirect-validation
  approach and is documented rather than claimed as eliminated.

---

## Repository verification

* Public repository: `https://github.com/Saralfury/ai-powered-link-analyzer`
* Required run command: `uvicorn app.main:app --host 0.0.0.0 --port 4000`
* Swagger UI: `http://localhost:4000/docs`
* Health endpoint: `http://localhost:4000/health`
* No API keys or secrets are committed.
* Dependencies are pinned in `requirements.txt`.