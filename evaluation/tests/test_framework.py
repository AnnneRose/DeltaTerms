"""Smoke tests for the evaluation framework.

Avoids hitting the real Hugging Face inference endpoint by injecting fake
``Chatbot`` / ``DeltaGenerator`` / ``Evaluator`` doubles. Run from the repo
root with::

    python -m evaluation.tests.test_framework
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile

# Allow `python -m evaluation.tests.test_framework` from repo root.
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from evaluation.calibration import calibrate, inter_rater_reliability  # noqa: E402
from evaluation.chatbot_wrapper import ChatbotUnderTest  # noqa: E402
from evaluation.evaluator import JudgeRun, MetricResult  # noqa: E402
from evaluation.metrics import Metric  # noqa: E402
from evaluation.reporting import summarize, compare_runs  # noqa: E402
from evaluation.runner import EvaluationRunner  # noqa: E402
from evaluation.triage import triage_case  # noqa: E402


# ---------------------------------------------------------------------------
# Fakes


class FakeChatbot:
    """Returns a deterministic response that references ToS content."""

    def get_response(self, user_input, history, service_name, current_tos,
                     previous_tos, delta):
        return (
            f"Summary for {service_name}: arbitration, data sharing, "
            f"termination clauses are present. Question was: {user_input}"
        )


class FakeDeltaGenerator:
    def get_delta(self, old_tos, new_tos):
        return "- something changed"


class FakeJudgeEvaluator:
    """Returns a fixed score per metric, with controllable spread."""

    def __init__(self, scores=None, spread=0):
        self.scores = scores or {}
        self.spread = spread

    def score_metric(self, metric, mode, user_input, response,
                     source_tos="", previous_tos="", ground_truth=""):
        base = self.scores.get(metric.name, 4)
        runs = []
        for i in range(3):
            offset = self.spread if i == 0 else (-self.spread if i == 2 else 0)
            s = max(0, min(5, base + offset))
            runs.append(JudgeRun(metric=metric.name, score=s, normalized=s / 5))
        scores = [r.score for r in runs]
        mean = sum(scores) / len(scores)
        return MetricResult(
            metric=metric.name,
            runs=runs,
            mean_score=mean,
            normalized=round(mean / 5.0, 4),
            score_spread=max(scores) - min(scores),
        )


# ---------------------------------------------------------------------------
# Tests


def test_triage_rules():
    # Low faithfulness should trigger review.
    decision = triage_case(
        metric_results={
            "faithfulness": {"normalized": 0.4, "score_spread": 0},
            "answer_relevancy": {"normalized": 0.9, "score_spread": 0},
        },
        random_sample_rate=0.0,
    )
    assert decision.review_required
    assert any("low_score:faithfulness" in r for r in decision.reasons)

    # Wide spread triggers review.
    decision = triage_case(
        metric_results={"faithfulness": {"normalized": 0.9, "score_spread": 2}},
        random_sample_rate=0.0,
    )
    assert decision.review_required
    assert any("judge_disagreement" in r for r in decision.reasons)