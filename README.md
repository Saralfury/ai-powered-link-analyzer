# SiteIntel — AI-Powered Website Link Analysis API

FastAPI application that analyses a public website URL using an LLM and returns
structured business, competitor, SEO, search-query, service, and target-audience
insights in five sections, plus metadata, provenance labels, and a comparison
table.

**Stack:** Python 3.x · FastAPI · Uvicorn · Pydantic · HTTPX · BeautifulSoup ·
OpenAI (configurable) · dotenv

**Endpoint:** `POST http://localhost:4000/link-analysis`  
**Frontend:** `http://localhost:4000/`  
**Docs:** `http://localhost:4000/docs`  
**Health:** `http://localhost:4000/health`

---

## Repository structure

```
ai-link-analysis/
├── app/
│   ├── __init__.py
│   ├── main.py                # FastAPI app, /health, POST /link-analysis, error handling, rate limiter
│   ├── config.py              # Pydantic-settings config (.env)
│   ├── errors.py              # Custom exceptions + HTTP status mapping
│   ├── schemas.py             # Request / response Pydantic models (exact brief contract)
│   ├── static/                # (mounted) served frontend assets
│   ├── services/
│   │   ├── __init__.py
│   │   ├── website_extractor.py   # HTTPX fetch + BeautifulSoup + multi-page discovery
│   │   ├── website_audit.py       # Deterministic SEO audit (title, meta, H1, images, canonical, viewport, links)
│   │   ├── llm_service.py         # OpenAI + Mock LLM, structured JSON, retry, fallback
│   │   ├── analysis_service.py    # Orchestrates validate → extract → audit → LLM → validate → respond
│   │   ├── competitor_service.py  # Registrable-domain dedup, self-rejection, ai_suggested labels
│   │   └── scoring.py             # Opportunity scoring: impact × confidence / effort
│   └── utils/
│       └── validators.py          # URL validation + SSRF protection (ports 80/443, DNS, global-routability)
├── frontend/
│   ├── index.html               # Plain HTML5 frontend
│   ├── styles.css               # Vanilla CSS3
│   └── app.js                   # Vanilla JavaScript (fetch API, AbortController)
├── examples/
│   └── sample-response.json     # Real API response against https://example.com
├── scripts/
│   └── benchmark_llms.py        # LLM provider benchmark (measured vs documented)
├── tests/
│   └── test_link_analysis.py    # 36 tests (mocks, no network/keys)
├── docs/
│   ├── benchmarks/              # Benchmark results + README
│   ├── sample_responses/        # Committed API response examples
│   └── screenshots/             # Frontend verification notes
├── .github/workflows/test.yml   # CI: pytest on push/PR
├── Dockerfile                   # Containerised run
├── .env.example                 # Copy to .env, add keys (placeholders only)
├── .gitignore
├── pytest.ini
├── requirements.txt
└── README.md
```

---

## Setup & execution

### Prerequisites
* Python 3.9+
* `pip` / `venv`

### Install

```bash
cd ai-link-analysis
python -m venv .venv
# Windows (PowerShell):
.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your LLM API key(s).
# Leave USE_MOCK_LLM=true to run without any key (deterministic demo mode).
```

### Run the server

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

* Frontend UI: http://localhost:4000/
* API docs (Swagger): http://localhost:4000/docs
* Health check: http://localhost:4000/health

### Run with Docker

```bash
docker build -t ai-link-analysis .
docker run -p 4000:4000 --env-file .env ai-link-analysis
```

### Run tests

```bash
pytest -q
```

No API key or network access is required (extractor and LLM are mocked).

---

## API usage

### Request

```http
POST http://localhost:4000/link-analysis
Content-Type: application/json

{
  "url": "https://example.com"
}
```

### Response (exact contract from the brief)

```json
{
  "success": true,
  "website": "https://example.com/",
  "brand": {
    "name": "Example Domain",
    "category": "Technology Services",
    "summary": "…"
  },
  "analysis": {
    "competitor_analysis": {
      "brand_overview": "…",
      "competitors": [
        {
          "name": "Competitor A",
          "overview": "…",
          "strengths": ["…"],
          "weaknesses_or_gaps": ["…"],
          "ai_suggested": true,
          "source": "llm"
        }
      ],
      "comparison_table": [
        {"field": "Brand Name", "your_brand": "…", "competitor": "…"},
        {"field": "Main Service", "your_brand": "…", "competitor": "…"}
      ],
      "strengths": ["…"],
      "opportunities": ["…"]
    },
    "target_search_queries": [
      {"query": "…", "platforms": ["Google", "LinkedIn"], "intent": "Service Discovery", "business_relevance": "…", "target_audience": "…", "search_volume": null}
    ],
    "seo_improvements": {
      "primary_keyword": "…",
      "secondary_keywords": ["…"],
      "long_tail_keywords": ["…"],
      "relevant_business_keywords": ["…"],
      "recommended_title": "…",
      "meta_description": "…",
      "supporting_content": ["…"]
    },
    "top_services": [
      {"service_name": "…", "description": "…", "target_industry": "…", "target_customer": "…", "main_benefit": "…", "inferred": false, "source": "website"}
    ],
    "target_audience": {
      "primary_audience": ["…"],
      "customer_needs": ["…"]
    }
  },
  "meta": {
    "model": "mock-llm",
    "provider": "mock",
    "pages_analyzed": 1,
    "input_tokens": 123,
    "output_tokens": 456,
    "estimated_cost_usd": null,
    "latency_ms": 50.0,
    "cached": false,
    "notes": []
  },
  "data_sources": ["website", "llm"],
  "disclaimer": "…"
}
```

A complete committed example is in `examples/sample-response.json`.

### Error responses

All errors use a consistent envelope:

```json
{
  "success": false,
  "website": "http://127.0.0.1/",
  "error": {"code": "BLOCKED_DESTINATION", "message": "Access to internal address 127.0.0.1 is not allowed."},
  "detail": null
}
```

| Condition | HTTP status | Error code |
|-----------|-------------|------------|
| Malformed URL / unsupported scheme | 422 | INVALID_URL |
| Private / loopback / link-local / blocked destination | 400 | BLOCKED_DESTINATION |
| Website timeout / unreachable / non-HTML / fetch failure | 502 | EXTRACTION_FAILED |
| LLM failure after repair/fallback | 502 | LLM_FAILED |
| Request validation failure | 422 | VALIDATION_ERROR |
| Unexpected internal failure | 500 | INTERNAL_ERROR |

---

## Frontend

A lightweight frontend (plain HTML5, CSS3, vanilla JavaScript — no frameworks,
no build tooling) is served at `http://localhost:4000/`. It:

* Accepts a URL and calls `POST /link-analysis`
* Shows a loading state and disables the button during the request
* Renders all five sections plus the comparison table
* Displays metadata (provider/model, pages analysed, latency, token usage, cache status)
* Shows provenance labels (`ai_suggested`, `inferred`) on competitors and services
* Uses `textContent` for safe rendering (no `innerHTML` of untrusted content)
* Has a 120-second client-side timeout (AbortController)
* Is responsive for desktop and mobile

---

## Data integrity & provenance

Source labels used throughout:

| Label | Meaning |
|-------|---------|
| `observed` | Directly supported by extracted website content (with page URL + snippet) |
| `inferred` | Reasoned conclusion from website evidence |
| `ai_suggested` | Model-generated suggestion or hypothesis |

Rules:
* Exactly 5 target search queries returned on success (search volume is `null`)
* At least 3 competitors only where reliable information exists
* Default competitor source is `ai_suggested`
* The submitted website is rejected as its own competitor
* Competitors are deduplicated by registrable domain
* `search_volume` is always `null` (no real search-volume data source connected)

---

## LLM model research & benchmark

### Provider comparison (documented pricing + measured latency)

| Provider | Model | API cost (per 1M in/out) | Response speed | JSON support | Label |
|----------|-------|-------------------------|----------------|--------------|-------|
| OpenAI | gpt-4o-mini | $0.15 / $0.60 (documented) | Fast (~2–6 s measured) | Native `response_format={json_object}` | Primary |
| OpenAI | gpt-3.5-turbo | $0.50 / $1.50 (documented) | Fast | Native JSON mode | Fallback |
| Mock | mock-llm | Free | ~50 ms (measured) | Valid JSON | Demo / CI |

### Recommended model

**OpenAI `gpt-4o-mini`** — best balance of accuracy, native JSON output, low
latency, and low cost. Fallback: `gpt-3.5-turbo`.

Estimated cost per analysis: ~$0.001–$0.006 (documented pricing, estimated).
Measured latency with mock: ~50 ms.

Run the benchmark:

```bash
python scripts/benchmark_llms.py
```

Results are committed under `docs/benchmarks/` when available. All values are
labeled **measured** (from actual runs) or **documented** (from public pricing
pages). No estimates are presented as measured.

---

## Cost controls implemented

1. Content cleaning before LLM: scripts, styles, nav, footer, comments stripped
2. Token truncation: `MAX_CONTENT_CHARS` (12,000) per page, `MAX_TOTAL_CHARS` (20,000) across pages
3. Single LLM call generates all five sections in one JSON object
4. In-memory TTL cache keyed by normalised URL + content hash (`meta.cached = true` on hit)
5. Cache capped at 100 entries (FIFO eviction)
6. No invented search volumes — no separate data-source API calls
7. Mock provider for CI/demo runs with zero API cost

---

## Security

* **SSRF protection:** Only HTTP/HTTPS on ports 80/443. Localhost, private IPs
  (10.x, 172.16–31.x, 192.168.x), loopback, link-local (169.254.x including AWS
  metadata), multicast, reserved, unspecified, IPv4-mapped IPv6, and carrier-grade
  NAT are rejected. DNS resolution inspects every returned address.
* **Redirect safety:** Automatic redirect following disabled; up to 5 manual hops,
  each fully re-validated.
* **No credentials exposed:** API keys come from environment variables only.
* **Prompt-injection defence:** Website content is delimited and treated as
  untrusted data; the model is instructed to ignore embedded instructions.

---

## V2 mandatory controls

* **Evidence verification:** After the LLM call, Python verifies that each
  `observed` claim's snippet (whitespace/case-normalised) actually appears in
  the text of the referenced fetched page. Claims that fail verification are
  downgraded to `inferred` with a note in `meta.notes` — never silently kept
  as `observed`. Covered by a dedicated test.
* **Pipeline budget:** The entire fetch → extract → audit → LLM → validate
  chain is wrapped in a single `asyncio.wait_for(90s)`. A budget breach maps
  to `502` with error code `UPSTREAM_TIMEOUT`. Covered by a dedicated test.
* **Cache hardening:** In-memory TTL cache with a FIFO cap of 100 entries. On
  a cache hit, recorded tokens/cost/latency are replayed and `meta.cached` is
  set to `true` — nothing is re-measured or re-billed. Cache key is the
  normalised URL plus a content hash of extracted content (not URL alone).
  Covered by a dedicated test.

---

## Tests

36 tests cover URL validation, SSRF protection, extraction, SEO audit, scoring,
competitor dedup/self-rejection, evidence verification, pipeline budget,
cache key behaviour, endpoint contract, and end-to-end pipeline with mock LLM.
No live LLM or network calls required.

```bash
pytest -q
```

CI runs on every push/PR via GitHub Actions.

---

## Limitations

* JavaScript-rendered (SPA) sites may yield thin content; a `meta.notes` warning
  is added. Playwright integration is future work.
* Competitor information is AI-generated unless found on the site; every
  competitor carries `ai_suggested` / `source` labels.
* Search-query volumes are **not** reported (per the brief: no invented data).
* Benchmark latency figures are measured from limited runs; accuracy ratings are
  qualitative estimates.
* Residual DNS-rebinding risk remains with the fallback validation approach
  (documented, not claimed as complete protection).

---

## Application verification (mandatory)

Per the recruitment instructions:

1. Follow **Dxora Technologies** on LinkedIn:
   https://www.linkedin.com/company/dxora-technologies
2. Follow **CREST** on Instagram:
   https://www.instagram.com/crestspot/

Share your LinkedIn and Instagram profile links when submitting your application.

---

## Final submission — email

* **To:** hr@chivoxai.com
* **Subject:** Your Name - Python Practical test review
* **Body:** Full name, public GitHub repository link, contact number,
  current location, preferred date and time for final discussion, and your
  LinkedIn / Instagram profile links.
* **Deadline:** 22nd November 2026

Repository must be **public** and include this README with setup instructions,
sample requests/responses, and the LLM comparison above.
