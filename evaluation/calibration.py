"""Phase 4 — calibration loop.

Compares human review scores to the LLM judge's scores, per metric, and
reports the agreement rate. The plan requires per-metric agreement of 0.8
(within 1 point on the 0..5 scale, on at least 80% of cases) before automated
scores are trusted in production monitoring.

If the LLM judge systematically over- or under-scores a metric, the metric's
prompt should be revised and the suite re-run.

This module also computes Cohen's kappa across pairs of human reviewers when
multiple reviewers have scored the same case (used for inter-rater
reliability tracking).
"""

from __future__ import annotations

import json
import math
import os
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple


@dataclass
class CalibrationReport:
    metric: str
    n_compared: int
    within_one_rate: float  # fraction of cases where |human - judge| <= 1
    mean_judge_minus_human: float  # systematic bias (positive => judge over-scores)
    median_abs_diff: float
    passes_threshold: bool
    threshold: float = 0.8

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class KappaReport:
    pair: Tuple[str, str]
    metric: str
    n_compared: int
    cohens_kappa: float
    needs_rubric_review: bool  # kappa < 0.6

    def as_dict(self) -> dict:
        return {
            "pair": list(self.pair),
            "metric": self.metric,
            "n_compared": self.n_compared,
            "cohens_kappa": self.cohens_kappa,
            "needs_rubric_review": self.needs_rubric_review,
        }


# ---------------------------------------------------------------------------
# IO helpers


def _load_run(run_dir: str) -> Tuple[Dict[str, dict], List[dict]]:
    cases: Dict[str, dict] = {}
    with open(os.path.join(run_dir, "results.jsonl"), "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            cases[case["test_id"]] = case

    reviews: List[dict] = []
    review_path = os.path.join(run_dir, "human_reviews.jsonl")
    if os.path.exists(review_path):
        with open(review_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                reviews.append(json.loads(line))
    return cases, reviews


# ---------------------------------------------------------------------------
# Calibration math


def _median(values: List[float]) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2


def calibrate(
    run_dir: str,
    threshold: float = 0.8,
    threshold_window: int = 1,
) -> Dict[str, CalibrationReport]:
    """Per-metric agreement: |human_score - judge_mean_score| <= 1 (on 0..5)."""
    cases, reviews = _load_run(run_dir)

    # Aggregate human scores: for each (test_id, metric), use the mean across
    # reviewers (so multiple reviewers don't double-count).
    human_per_metric: Dict[str, Dict[str, List[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for review in reviews:
        tid = review["test_id"]
        for metric, score in (review.get("scores") or {}).items():
            human_per_metric[metric][tid].append(int(score))

    reports: Dict[str, CalibrationReport] = {}
    for metric, by_case in human_per_metric.items():
        diffs: List[float] = []
        signed_diffs: List[float] = []
        for tid, scores in by_case.items():
            if not scores:
                continue
            case = cases.get(tid)
            if not case:
                continue
            judge = case.get("metrics", {}).get(metric)
            if not judge:
                continue
            human_mean = sum(scores) / len(scores)
            judge_mean = float(judge.get("mean_score", 0.0))
            diff = judge_mean - human_mean
            diffs.append(abs(diff))
            signed_diffs.append(diff)

        n = len(diffs)
        if n == 0:
            continue
        within = sum(1 for d in diffs if d <= threshold_window) / n
        bias = sum(signed_diffs) / n
        median_abs = _median(diffs)
        reports[metric] = CalibrationReport(
            metric=metric,
            n_compared=n,
            within_one_rate=round(within, 4),
            mean_judge_minus_human=round(bias, 4),
            median_abs_diff=round(median_abs, 4),
            passes_threshold=within >= threshold,
            threshold=threshold,
        )
    return reports
