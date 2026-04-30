"""Phase 6 — reporting and regression gating.

Builds aggregate per-metric statistics from a single run, compares against a
baseline run, and reports any regressions. The plan specifies that
regressions of more than 0.05 on any normalized metric block deployment
until investigated.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple


REGRESSION_THRESHOLD = 0.05


@dataclass
class MetricSummary:
    metric: str
    n: int
    mean_normalized: float
    min_normalized: float
    max_normalized: float
    pct_above_0_8: float

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class RegressionFinding:
    metric: str
    baseline: float
    candidate: float
    delta: float
    is_regression: bool

    def as_dict(self) -> dict:
        return asdict(self)


def _load_jsonl(path: str) -> List[dict]:
    out: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def summarize(run_dir: str) -> Dict[str, MetricSummary]:
    cases = _load_jsonl(os.path.join(run_dir, "results.jsonl"))
    by_metric: Dict[str, List[float]] = defaultdict(list)
    for case in cases:
        for metric_name, result in case.get("metrics", {}).items():
            by_metric[metric_name].append(float(result.get("normalized", 0.0)))

    out: Dict[str, MetricSummary] = {}
    for metric, scores in by_metric.items():
        if not scores:
            continue
        out[metric] = MetricSummary(
            metric=metric,
            n=len(scores),
            mean_normalized=round(sum(scores) / len(scores), 4),
            min_normalized=round(min(scores), 4),
            max_normalized=round(max(scores), 4),
            pct_above_0_8=round(sum(1 for s in scores if s >= 0.8) / len(scores), 4),
        )
    return out


def worst_cases(run_dir: str, metric: str, k: int = 10) -> List[dict]:
    """Top-k worst-performing cases for a given metric."""
    cases = _load_jsonl(os.path.join(run_dir, "results.jsonl"))
    rows: List[Tuple[float, dict]] = []
    for case in cases:
        m = case.get("metrics", {}).get(metric)
        if not m:
            continue
        rows.append((float(m.get("normalized", 0.0)), case))
    rows.sort(key=lambda row: row[0])
    return [
        {
            "test_id": case["test_id"],
            "mode": case["mode"],
            "normalized": score,
            "review_required": case.get("triage", {}).get("review_required", False),
            "user_input": case["user_input"][:200],
        }
        for score, case in rows[:k]
    ]

