"""LLM provider benchmark.

Runs the same cleaned website content through available LLM providers and
records latency, token usage, estimated cost, and JSON validity.

Values are labeled MEASURED (from actual runs) or DOCUMENTED (from public
pricing pages). Never present estimates as measured.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List

from app.config import settings
from app.services.llm_service import MockLLMService, OpenAILLMService, get_llm_service


SAMPLE_CONTENT: Dict[str, Any] = {
    "url": "https://example.com",
    "title": "Acme Web Design",
    "meta_description": "Professional web design and SEO services for small businesses.",
    "og_title": "Acme Web Design",
    "headings": ["Web Design", "SEO Services", "About Us"],
    "json_ld": [],
    "text": (
        "Acme Web Design is a web design and SEO agency serving small businesses "
        "and startups in the tri-state area. We offer custom website design, "
        "search engine optimisation, and ongoing website maintenance."
    ),
    "text_length": 260,
    "pages": [],
    "pages_analyzed": 1,
    "is_thin": False,
}

# DOCUMENTED pricing per 1M tokens (retrieval date: 2026-11-16).
# Source: official provider pricing pages. Update before production use.
DOCUMENTED_PRICING: Dict[str, Dict[str, float]] = {
    "openai:gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "openai:gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
}


def _cost_usd(model_key: str, input_tokens: int, output_tokens: int) -> float:
    pricing = DOCUMENTED_PRICING.get(model_key, {"input": 0.0, "output": 0.0})
    return (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]


async def _run_provider(name: str, factory) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "provider": name,
        "status": "skipped",
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "estimated_cost_usd": None,
        "json_valid": None,
        "error": None,
        "label": "not_tested",
    }

    try:
        svc = factory()
        start = time.perf_counter()
        raw, meta = await svc.analyze(SAMPLE_CONTENT)
        latency_ms = (time.perf_counter() - start) * 1000

        json_valid = True
        try:
            json.dumps(raw)
        except (TypeError, ValueError):
            json_valid = False

        input_tokens = meta.get("input_tokens") or 0
        output_tokens = meta.get("output_tokens") or 0
        model_key = f"{name}:{meta.get('model', 'unknown')}"

        result.update(
            status="ok",
            latency_ms=round(latency_ms, 1),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_usd=round(_cost_usd(model_key, input_tokens, output_tokens), 6),
            json_valid=json_valid,
            label="measured",
        )
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        result["label"] = "not_tested"

    return result


async def main() -> None:
    providers: List[tuple] = [("mock", MockLLMService)]
    if settings.OPENAI_API_KEY:
        providers.append(("openai", OpenAILLMService))

    print("LLM Benchmark — Website Link Analysis")
    print("=" * 50)
    print(f"Sample content: {SAMPLE_CONTENT['text_length']} chars\n")

    results: List[Dict[str, Any]] = []
    for name, factory in providers:
        res = await _run_provider(name, factory)
        results.append(res)
        print(f"\nProvider: {name}")
        print(f"  Status: {res['status']}  Label: {res['label']}")
        if res["status"] == "ok":
            print(f"  Latency: {res['latency_ms']} ms (measured)")
            print(f"  Input tokens: {res['input_tokens']} (measured)")
            print(f"  Output tokens: {res['output_tokens']} (measured)")
            print(f"  Est. cost per analysis: ${res['estimated_cost_usd']:.6f} (documented pricing)")
            print(f"  JSON valid: {res['json_valid']}")
        else:
            print(f"  Error: {res['error']}")

    print("\n\nSummary (Measured vs Documented)")
    print("=" * 75)
    print(f"{'Provider':<15} {'Model':<15} {'Latency(ms)':<14} {'In Tokens':<12} {'Out Tokens':<12} {'Cost/analysis':<16} {'JSON OK':<8} {'Label'}")
    print("-" * 75)
    for r in results:
        if r["status"] == "ok":
            model = r.get("model_used", "mock-llm")
            print(
                f"{r['provider']:<15} {model:<15} "
                f"{str(r['latency_ms']):<14} {str(r['input_tokens']):<12} "
                f"{str(r['output_tokens']):<12} ${r['estimated_cost_usd']:<15.6f} "
                f"{str(r['json_valid']):<8} {r['label']}"
            )
        else:
            print(f"{r['provider']:<15} {'—':<15} {'skipped':<14} {'—':<12} {'—':<12} {'—':<16} {'—':<8} not_tested")

    print(
        "\nNotes: Cost uses DOCUMENTED provider pricing (estimated). "
        "Latency and token counts are MEASURED from actual runs where API keys "
        "are available. Mock results are deterministic and not representative "
        "of production latency."
    )


async def main_with_results() -> list:
    providers: List[tuple] = [("mock", MockLLMService)]
    if settings.OPENAI_API_KEY:
        providers.append(("openai", OpenAILLMService))

    print("LLM Benchmark — Website Link Analysis")
    print("=" * 50)
    print(f"Sample content: {SAMPLE_CONTENT['text_length']} chars\n")

    results: List[Dict[str, Any]] = []
    for name, factory in providers:
        res = await _run_provider(name, factory)
        results.append(res)
        print(f"\nProvider: {name}")
        print(f"  Status: {res['status']}  Label: {res['label']}")
        if res["status"] == "ok":
            print(f"  Latency: {res['latency_ms']} ms (measured)")
            print(f"  Input tokens: {res['input_tokens']} (measured)")
            print(f"  Output tokens: {res['output_tokens']} (measured)")
            print(f"  Est. cost per analysis: ${res['estimated_cost_usd']:.6f} (documented pricing)")
            print(f"  JSON valid: {res['json_valid']}")
        else:
            print(f"  Error: {res['error']}")

    print("\n\nSummary (Measured vs Documented)")
    print("=" * 75)
    print(f"{'Provider':<15} {'Model':<15} {'Latency(ms)':<14} {'In Tokens':<12} {'Out Tokens':<12} {'Cost/analysis':<16} {'JSON OK':<8} {'Label'}")
    print("-" * 75)
    for r in results:
        if r["status"] == "ok":
            model = r.get("model_used", "mock-llm")
            print(
                f"{r['provider']:<15} {model:<15} "
                f"{str(r['latency_ms']):<14} {str(r['input_tokens']):<12} "
                f"{str(r['output_tokens']):<12} ${r['estimated_cost_usd']:<15.6f} "
                f"{str(r['json_valid']):<8} {r['label']}"
            )
        else:
            print(f"{r['provider']:<15} {'—':<15} {'skipped':<14} {'—':<12} {'—':<12} {'—':<16} {'—':<8} not_tested")

    print(
        "\nNotes: Cost uses DOCUMENTED provider pricing (estimated). "
        "Latency and token counts are MEASURED from actual runs where API keys "
        "are available. Mock results are deterministic and not representative "
        "of production latency."
    )

    # Write results to docs/benchmarks/
    import os, json
    bench_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "benchmarks")
    os.makedirs(bench_dir, exist_ok=True)
    with open(os.path.join(bench_dir, "benchmark-results.json"), "w", encoding="utf-8") as f:
        json.dump({
            "retrieval_date": "2026-11-16",
            "sample_content_chars": SAMPLE_CONTENT["text_length"],
            "results": results,
            "notes": "Cost uses DOCUMENTED provider pricing (estimated). Latency and token counts are MEASURED from actual runs where API keys are available. Mock results are deterministic and not representative of production latency.",
        }, f, indent=2)
    print(f"\nResults written to {bench_dir}/benchmark-results.json")
    return results


if __name__ == "__main__":
    asyncio.run(main_with_results())
