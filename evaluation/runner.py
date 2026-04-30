"""Phase 1 + Phase 2 orchestrator: generate chatbot responses for every test
case, run the LLM judge, triage cases for human review, and persist results.

Results are written to two complementary stores:

* ``results/run_<id>/results.csv``  — flat per-(case, metric) rows.
* ``results/run_<id>/results.jsonl`` — one full JSON object per case, with the
  source ToS, response, judge runs (CoT included), and triage decision.
"""

from __future__ import annotations

import csv
import json
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from .chatbot_wrapper import ChatbotUnderTest
from .evaluator import Evaluator, MetricResult
from .metrics import (
    ALL_METRICS,
    DELTA_PRECISION,
    HARM_FLAGGING_ACCURACY,
    MODE_DELTA,
    MODE_QA,
    MODE_SUMMARY,
    PROTOCOL_ADHERENCE,
    metrics_for_mode,
)
from .triage import triage_case


HERE = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(HERE, "datasets")
RESULTS_DIR = os.path.join(HERE, "results")


# ---------------------------------------------------------------------------
# Dataset loaders


def _load_json(name: str) -> dict:
    with open(os.path.join(DATASETS_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def load_dataset_a() -> dict:
    return _load_json("dataset_a_single.json")


def load_dataset_b() -> dict:
    return _load_json("dataset_b_pairs.json")


def load_dataset_c() -> dict:
    return _load_json("dataset_c_qa.json")


def load_adversarial() -> dict:
    return _load_json("adversarial.json")


# ---------------------------------------------------------------------------
# Result containers


@dataclass
class CaseResult:
    test_id: str
    mode: str
    sector: Optional[str]
    service_name: str
    user_input: str
    response: str
    source_tos: str
    previous_tos: Optional[str] = None
    ground_truth: Optional[str] = None
    metrics: Dict[str, MetricResult] = field(default_factory=dict)
    triage: Dict = field(default_factory=dict)
    is_adversarial: bool = False
    timestamp: str = ""

    def to_jsonable(self) -> dict:
        return {
            "test_id": self.test_id,
            "mode": self.mode,
            "sector": self.sector,
            "service_name": self.service_name,
            "user_input": self.user_input,
            "response": self.response,
            "source_tos": self.source_tos,
            "previous_tos": self.previous_tos,
            "ground_truth": self.ground_truth,
            "is_adversarial": self.is_adversarial,
            "metrics": {k: v.as_dict() for k, v in self.metrics.items()},