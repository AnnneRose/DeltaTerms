"""Triage Phase 2 — decide which evaluation cases get human review.

Routing rules from the evaluation plan:

* Disagreement trigger: scores across the 3 judge runs diverge by >1 point.
* Low-score trigger: faithfulness or harm-flagging normalized < 0.6.
* Random sampling: 10% of cases regardless of score.
* High-stakes trigger: research consent forms or medical/financial ToS — and
  every adversarial test — go to mandatory human review.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable, List, Optional


HIGH_STAKES_SECTORS = frozenset(
    {"research_consent", "medical", "financial", "irb"}
)


@dataclass
class TriageDecision:
    review_required: bool
    reasons: List[str]


def triage_case(
    metric_results: dict,
    sector: Optional[str] = None,
    is_adversarial: bool = False,
    random_sample_rate: float = 0.10,
    rng: Optional[random.Random] = None,
    explicit_high_stakes: bool = False,
) -> TriageDecision:
    """Decide whether a case needs human review.

    ``metric_results`` is a mapping ``metric_name -> MetricResult-shaped dict``
    (with ``normalized`` and ``score_spread`` fields).
    """
    rng = rng or random
    reasons: List[str] = []

    if is_adversarial:
        reasons.append("adversarial_case_mandatory_review")

    if explicit_high_stakes or (sector and sector in HIGH_STAKES_SECTORS):
        reasons.append(f"high_stakes_sector:{sector or 'flagged'}")

    for metric_name, result in metric_results.items():
        spread = result.get("score_spread", 0)
        if spread > 1:
            reasons.append(f"judge_disagreement:{metric_name}(spread={spread})")

    for metric_name in ("faithfulness", "harm_flagging_accuracy"):
        result = metric_results.get(metric_name)
        if result and result.get("normalized", 1.0) < 0.6:
            reasons.append(
                f"low_score:{metric_name}={result['normalized']:.2f}"
            )

    if rng.random() < random_sample_rate:
        reasons.append("random_sample")

    return TriageDecision(review_required=bool(reasons), reasons=reasons)


def filter_for_review(
    rows: Iterable[dict],
) -> List[dict]:
    """Select rows whose triage decision is ``review_required``."""
    return [row for row in rows if row.get("triage", {}).get("review_required")]