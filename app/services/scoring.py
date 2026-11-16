"""Opportunity scoring.

LLM classifies impact, confidence and effort on documented 1-5 scales.
Python computes: priority_score = impact × confidence / effort.

All scales start at 1 (effort >= 1) so division by zero is impossible by
construction. LLM-supplied values are clamped to documented ranges before
computation. The LLM must not invent the final calculated score.
"""

from __future__ import annotations

from typing import Any, Dict

MIN_SCALE = 1
MAX_SCALE = 5


def clamp(value: Any, lo: int = MIN_SCALE, hi: int = MAX_SCALE) -> int:
    """Clamp a numeric value to [lo, hi]."""
    try:
        v = int(value)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, v))


def compute_priority_score(impact: int, confidence: int, effort: int) -> Dict[str, Any]:
    """Compute priority_score = impact × confidence / effort.

    All inputs are clamped to [1, 5] before computation.
    """
    impact_c = clamp(impact)
    confidence_c = clamp(confidence)
    effort_c = clamp(effort)

    score = (impact_c * confidence_c) / effort_c

    return {
        "impact": impact_c,
        "confidence": confidence_c,
        "effort": effort_c,
        "priority_score": round(score, 2),
        "scale": {"min": MIN_SCALE, "max": MAX_SCALE},
        "formula": "impact × confidence / effort",
    }


def score_opportunities(opportunities: list) -> list:
    """Score a list of opportunities, each with impact/confidence/effort."""
    scored = []
    for opp in opportunities:
        result = compute_priority_score(
            opp.get("impact", 3),
            opp.get("confidence", 3),
            opp.get("effort", 3),
        )
        result["opportunity"] = str(opp.get("description", opp.get("text", "")))
        scored.append(result)
    # Sort by priority_score descending.
    scored.sort(key=lambda x: x["priority_score"], reverse=True)
    return scored
