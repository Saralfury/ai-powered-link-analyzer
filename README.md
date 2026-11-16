# SiteIntel
### AI-Powered Website Intelligence & Analysis Platform

SiteIntel is an AI-powered website analysis platform that transforms publicly accessible website content into structured business intelligence.

Built with **Python, FastAPI, HTTPX, BeautifulSoup, and configurable Large Language Model (LLM) integrations**, SiteIntel combines deterministic website auditing with AI-assisted analysis to identify business positioning, potential competitors, SEO opportunities, services, search queries, and target audiences.

Rather than relying entirely on AI-generated observations, the application separates deterministic checks from model-generated insights and uses structured validation to maintain consistent API responses.

---

## Application Preview

The following screenshots show the actual application interface and its analysis workflow.

<table>
  <tr>
    <td width="50%">
      <img src="./Screenshot%202026-11-16%20210527.png" alt="SiteIntel interface" width="100%">
      <p align="center"><strong>Website Analysis Interface</strong></p>
    </td>
    <td width="50%">
      <img src="./Screenshot%202026-11-16%20210546.png" alt="SiteIntel analysis" width="100%">
      <p align="center"><strong>Analysis Workflow</strong></p>
    </td>
  </tr>
  <tr>
    <td width="50%">
      <img src="./Screenshot%202026-11-16%20210552.png" alt="SiteIntel analysis results" width="100%">
      <p align="center"><strong>Analysis Results</strong></p>
    </td>
    <td width="50%">
      <img src="./Screenshot%202026-11-16%20210611.png" alt="SiteIntel detailed insights" width="100%">
      <p align="center"><strong>Detailed Business Insights</strong></p>
    </td>
  </tr>
</table>

---

## Core Capabilities

| Capability | Description |
|---|---|
| Website Extraction | Fetches and processes publicly accessible website content |
| Business Intelligence | Generates structured brand and business insights |
| Competitor Analysis | Identifies potential competitors and compares business positioning |
| SEO Analysis | Performs deterministic SEO checks and generates optimization suggestions |
| Search Query Generation | Suggests platform-aware target search queries |
| Service Identification | Extracts or infers business services |
| Audience Analysis | Identifies potential customer segments and audience characteristics |
| LLM Integration | Supports configurable AI providers and a deterministic mock provider |
| API Validation | Uses Pydantic schemas to validate structured responses |
| Security | Includes URL validation and SSRF mitigation measures |

---

## How It Works

SiteIntel processes a submitted website through a structured analysis pipeline.

```text
             Website URL
                  |
                  v
          URL Validation
          + SSRF Checks
                  |
                  v
          Website Extraction
          HTTPX + BeautifulSoup
                  |
                  v
          Content Processing
                  |
                  v
          Deterministic SEO Audit
                  |
                  v
          LLM-Based Analysis
       OpenAI / Anthropic / Gemini
                  |
                  v
          Pydantic Validation
             + Repair Retry
                  |
                  v
          Evidence Verification
                  |
                  v
          Structured JSON Output
```

### Processing stages

**1. URL Validation**

Validates submitted URLs, restricts accepted schemes and ports, and checks resolved network addresses to reduce exposure to SSRF attacks.

**2. Website Extraction**

Fetches the homepage and discovers up to three relevant internal pages on the same domain.

**3. Content Extraction**

Uses HTTPX and BeautifulSoup to extract:

- Page titles and meta descriptions.
- Open Graph metadata.
- Headings and page text.
- JSON-LD structured data.
- Internal and external links.
- Image information and alternative text.

**4. Deterministic SEO Audit**

Performs programmatic checks on:

- Title length.
- Meta descriptions.
- H1 heading count.
- Image alt-text coverage.
- Canonical URLs.
- Viewport configuration.
- Internal linking.

**5. AI-Powered Analysis**

Sends cleaned website content to the configured LLM provider to generate business and market-oriented insights.

**6. Structured Response Validation**

Validates generated output against Pydantic schemas and attempts one repair when the generated structure is invalid.

**7. Evidence Verification**

Checks whether claims marked as directly observed are supported by extracted website content.

---

## Analysis Modules

SiteIntel produces five structured analysis categories.

### 1. Competitor and Brand Analysis

Evaluates the submitted business and identifies potential competitors.

Includes:
- Brand overview and positioning.
- Potential competitor identification.
- Competitor strengths and weaknesses.
- Brand strengths.
- Business opportunities.
- Comparative analysis table.

AI-suggested competitors are explicitly distinguished from independently observed website information.

### 2. Target Search Queries

Generates five suggested search queries based on the website's business context.

Supported platform recommendations include:

- Google
- Facebook
- Instagram
- LinkedIn
- X

Each query includes search intent, business relevance, and intended audience.

Search-volume data is intentionally returned as `null` because no external keyword-volume provider is integrated.

### 3. SEO Recommendations

Generates actionable SEO recommendations, including:

- Primary keywords.
- Secondary keywords.
- Long-tail keywords.
- Relevant business keywords.
- Recommended page title.
- Meta description.
- Supporting content ideas.

### 4. Service Identification

Identifies up to five relevant business services.

Each service includes:

- Service name.
- Description.
- Target industry.
- Target customer.
- Main customer benefit.
- Inference and source indicators.

### 5. Target Audience Identification

Generates structured audience insights, including:

- Primary and secondary audiences.
- Industry segments.
- Business types.
- Customer profiles.
- Customer needs.
- Customer challenges.
- Customer interests.
- Recommended audience segments.

---

## Technology Stack

| Component | Technology | Purpose |
|---|---|---|
| Backend | Python | Application logic |
| API Framework | FastAPI | REST API implementation |
| ASGI Server | Uvicorn | Application serving |
| HTTP Client | HTTPX | Asynchronous website fetching |
| HTML Parsing | BeautifulSoup | Website content extraction |
| Data Validation | Pydantic | Request and response schemas |
| Configuration | Pydantic Settings | Environment-based configuration |
| AI Integration | OpenAI / Anthropic / Gemini | LLM-powered analysis |
| Frontend | HTML5, CSS3, JavaScript | User interface |
| Testing | Pytest | Automated testing |
| Containerization | Docker | Container-based deployment |

---

## Project Structure

```text
ai-link-analysis/
│
├── app/
│   ├── main.py
│   ├── config.py
│   ├── errors.py
│   ├── schemas.py
│   │
│   ├── services/
│   │   ├── website_extractor.py
│   │   ├── website_audit.py
│   │   ├── llm_service.py
│   │   ├── analysis_service.py
│   │   ├── competitor_service.py
│   │   └── scoring.py
│   │
│   └── utils/
│       └── validators.py
│
├── frontend/
│   ├── index.html
│   ├── styles.css
│   └── app.js
│
├── scripts/
│   └── benchmark_llms.py
│
├── tests/
│   └── test_link_analysis.py
│
├── logs/
│
├── Screenshot 2026-11-16 210527.png
├── Screenshot 2026-11-16 210546.png
├── Screenshot 2026-11-16 210552.png
├── Screenshot 2026-11-16 210611.png
│
├── .env
├── .env.example
├── .gitignore
├── Dockerfile
├── pytest.ini
├── requirements.txt
└── README.md
```

*The tree highlights the documented application components. Optional example and benchmark-result files can be added to this structure when present in the repository.*

---

## Installation and Setup

### Prerequisites

- Python 3.10+
- pip
- venv
- Docker (optional)

### 1. Clone the repository

```bash
git clone https://github.com/Saralfury/ai-powered-link-analyzer.git

cd ai-powered-link-analyzer
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate the environment.

**Windows PowerShell**

```powershell
.venv\Scripts\Activate.ps1
```

**Linux / macOS**

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a local environment file using the supplied template.

**Windows PowerShell**

```powershell
Copy-Item .env.example .env
```

**Linux / macOS**

```bash
cp .env.example .env
```

For demonstration without external API credentials, configure:

```env
USE_MOCK_LLM=true
```

For live provider mode, configure the appropriate API credentials in `.env` according to the available configuration options.

Never commit actual API keys or credentials.

### 5. Start the application

```bash
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Access the application:

| Resource | Address |
|---|---|
| Frontend | http://localhost:4000/ |
| Swagger UI | http://localhost:4000/docs |
| Health Check | http://localhost:4000/health |

---

## Docker

Build the application image:

```bash
docker build -t siteintel .
```

Run the container:

```bash
docker run -p 4000:4000 --env-file .env siteintel
```

The container exposes the application on port `4000`.

---

## API Documentation

### POST `/link-analysis`

Accepts a website URL and returns structured analysis.

**Request**

```http
POST /link-analysis
Content-Type: application/json
```

**Request Body**

```json
{
  "url": "https://example.com"
}
```

### Response Structure

A successful response contains:

```json
{
  "success": true,
  "website": "https://example.com/",
  "brand": {
    "name": "Example Domain",
    "category": "Technology Services",
    "summary": "Illustrative brand summary."
  },
  "analysis": {
    "competitor_analysis": {},
    "target_search_queries": [],
    "seo_improvements": {},
    "top_services": [],
    "target_audience": {}
  },
  "meta": {
    "model": "mock-llm",
    "provider": "mock",
    "pages_analyzed": 1,
    "estimated_cost_usd": null,
    "latency_ms": 0.2,
    "cached": false,
    "notes": []
  },
  "data_sources": [
    "website",
    "llm"
  ],
  "disclaimer": "AI-generated suggestions should be treated as recommendations rather than independently verified facts."
}
```

The example above illustrates the response structure. Actual values and optional fields depend on the configured provider and the website being analyzed.

A complete response example can be maintained in `examples/sample-response.json` if that file is included in the repository.

### Error Handling

The API uses structured error responses.

| Condition | HTTP Status | Error Code |
|---|---:|---|
| Malformed URL or unsupported scheme | 422 | `INVALID_URL` |
| Private or blocked destination | 400 | `BLOCKED_DESTINATION` |
| Website extraction failure | 502 | `EXTRACTION_FAILED` |
| LLM failure after retry/fallback | 502 | `LLM_FAILED` |
| Request validation failure | 422 | `VALIDATION_ERROR` |
| Unexpected internal failure | 500 | `INTERNAL_ERROR` |

---

## Data Integrity and Provenance

AI-generated analysis can contain assumptions. SiteIntel distinguishes different levels of evidence.

| Label | Meaning |
|---|---|
| `observed` | Directly supported by extracted website content |
| `inferred` | Derived from available website evidence |
| `ai_suggested` | Generated as an AI recommendation or hypothesis |

### Data integrity measures

- Search-volume values are not fabricated.
- Competitor suggestions are labeled appropriately.
- The submitted website is rejected as its own competitor.
- Competitors are deduplicated by registrable domain.
- Claims marked as observed undergo snippet verification.
- Unverified claims can be downgraded to inferred information.

These measures improve transparency but do not guarantee the factual accuracy of every AI-generated recommendation.

---

## Security Considerations

SiteIntel includes several protections for processing user-submitted URLs and external website content.

### SSRF Mitigation

- Restricts URL schemes to HTTP and HTTPS.
- Restricts ports to 80 and 443.
- Checks DNS-resolved IP addresses.
- Rejects private, loopback, link-local, multicast, reserved, and unspecified addresses.
- Revalidates redirect destinations.

### Redirect Validation

Automatic redirect following is disabled. Redirects are handled manually, with destinations checked before subsequent requests.

### Credential Management

- Credentials are loaded through environment variables.
- Configuration uses `pydantic-settings`.
- `.env` is excluded through `.gitignore`.
- `.env.example` contains placeholders only.

### Prompt-Injection Mitigation

Extracted website content is treated as untrusted input. The LLM is instructed to analyze the content rather than follow instructions embedded within it.

**Security limitation:** URL and DNS validation reduce SSRF exposure but do not completely eliminate DNS rebinding or network-level attack risks. Production deployment requires additional network isolation and connection-level safeguards.

---

## LLM Integration and Benchmarking

SiteIntel supports a configurable LLM architecture.

| Provider | Integration |
|---|---|
| OpenAI | Supported |
| Anthropic | Supported |
| Google Gemini | Supported |
| Mock Provider | Supported |

### Benchmark Status

The built-in mock provider offers deterministic output for demonstration and automated testing.

An illustrative recorded mock result:

| Provider | Model | Latency | Input Tokens | Output Tokens | Valid JSON |
|---|---|---:|---:|---:|---|
| Mock | mock-llm | 0.2 ms | 111 | 1,378 | Yes |

**Benchmark clarification:** Mock-provider latency does not represent external LLM performance. Live provider latency, response quality, and cost must be measured separately using actual API requests.

Run the benchmark script:

```bash
python scripts/benchmark_llms.py
```

Provider pricing and model recommendations should be evaluated using current provider documentation.

---

## Performance and Cost Optimization

The application incorporates several measures to reduce unnecessary processing.

1. HTML cleaning before LLM requests.
2. Per-page and total-content limits.
3. A single structured analysis request for all five categories.
4. In-memory caching with a documented 100-entry FIFO capacity.
5. Normalized URL and content-hash-based cache keys.
6. Mock mode for testing without external API costs.
7. No unnecessary search-volume API requests.

Caching behavior depends on whether a valid cached analysis can be reused without making another provider request.

---

## Testing

The documented test suite covers:

- URL validation.
- SSRF protection.
- Website extraction.
- SEO auditing.
- Opportunity scoring.
- Competitor deduplication.
- Competitor self-rejection.
- Evidence verification.
- Pipeline timeout handling.
- Cache behavior.
- API contract validation.
- End-to-end analysis using the mock provider.

Run the test suite:

```bash
pytest -q
```

Tests use mocks to avoid requiring live LLM credentials or external network access.

The repository also includes GitHub Actions CI configuration for automated testing, where configured.

---

## Known Limitations

1. **JavaScript-rendered websites:** Client-side rendered websites may provide incomplete content during extraction.
2. **Competitor verification:** AI-generated competitor suggestions are not equivalent to independently verified market research.
3. **Search-volume data:** Actual search volume and ranking metrics require an external SEO data provider.
4. **LLM variability:** Generated insights depend on the selected provider, model, and available website content.
5. **Benchmark coverage:** Live provider performance and analytical accuracy require further evaluation.
6. **Network security:** DNS rebinding and network-level SSRF risks require additional deployment safeguards.

---

## Repository

**GitHub:**  
https://github.com/Saralfury/ai-powered-link-analyzer

**Primary API:** `POST /link-analysis`

**Interactive API Documentation:** `/docs`

**Health Endpoint:** `/health`

---

## License

Developed as part of a Python practical recruitment assessment.

---

**SiteIntel**  
*Turning website content into structured business intelligence.*

Built with Python, FastAPI, HTTPX, BeautifulSoup, Pydantic, and configurable LLM integrations.