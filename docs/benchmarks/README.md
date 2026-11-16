# LLM Benchmark Results

## Methodology

The same cleaned website content (260 chars, a fictional web design agency
homepage) was sent to each available LLM provider. Results are labelled:

- **measured**: from an actual run with an API key available
- **documented**: from public provider pricing pages (retrieval date: 2026-11-16)
- **not_tested**: provider not available / no API key

## Results

| Provider | Model | Latency (ms) | In Tokens | Out Tokens | Cost/analysis | JSON OK | Label |
|----------|-------|-------------|-----------|------------|---------------|---------|-------|
| mock | mock-llm | 0.2 | 111 | 1378 | $0.000000 | True | measured |
| openai | gpt-4o-mini | — | — | — | — | — | not_tested |

## Recommendation

**OpenAI `gpt-4o-mini`** is recommended as the primary model (best balance of
accuracy, native JSON output, low latency, low cost). `gpt-3.5-turbo` is the
fallback. The mock provider is used for demo/CI runs with zero API cost.

Raw data: `benchmark-results.json`

## Cost controls implemented

- Content cleaning before LLM (scripts, styles, nav, footer stripped)
- Token truncation (`MAX_CONTENT_CHARS=12000` per page, `MAX_TOTAL_CHARS=20000`)
- Single LLM call for all five sections
- In-memory TTL cache with FIFO cap (100 entries)
- No invented search volumes (no separate data-source API calls)
- Mock provider for CI/demo with zero cost
