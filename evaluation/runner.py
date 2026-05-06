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
            "triage": self.triage,
            "timestamp": self.timestamp,
        }


# ---------------------------------------------------------------------------
# Helpers for assembling ground-truth context for each metric


def _format_annotations(item: dict) -> str:
    ann = item.get("annotations", {})
    parts = []
    for label in ("harmful", "neutral", "user_favorable"):
        entries = ann.get(label, [])
        if not entries:
            continue
        parts.append(f"[{label.upper()}]")
        for e in entries:
            clause = e.get("clause", "")
            rationale = e.get("rationale", "")
            line = f"- {clause}"
            if rationale:
                line += f" ({rationale})"
            parts.append(line)
    expected = item.get("expected_summary_points") or []
    if expected:
        parts.append("[EXPECTED SUMMARY POINTS]")
        for p in expected:
            parts.append(f"- {p}")
    return "\n".join(parts)


def _format_pair_ground_truth(pair: dict) -> str:
    gt = pair.get("ground_truth_changes") or []
    non = pair.get("non_changes_to_ignore") or []
    parts = ["[MATERIAL CHANGES]"]
    parts += [f"- {c}" for c in gt] or ["- (none)"]
    parts.append("[CHANGES TO IGNORE]")
    parts += [f"- {c}" for c in non] or ["- (none)"]
    parts.append(f"[CASE TYPE]\n{pair.get('case_type', '')}")
    return "\n".join(parts)


def _format_qa_ground_truth(qa_item: dict) -> str:
    parts = [f"[REFERENCE ANSWER]\n{qa_item.get('reference_answer', '')}"]
    must = qa_item.get("must_mention") or []
    must_not = qa_item.get("must_not_mention") or []
    if must:
        parts.append("[MUST MENTION]\n" + "\n".join(f"- {m}" for m in must))
    if must_not:
        parts.append("[MUST NOT MENTION]\n" + "\n".join(f"- {m}" for m in must_not))
    if qa_item.get("should_decline_legal_advice"):
        parts.append("[CONSTRAINT] Bot must decline to give legal advice.")
    if qa_item.get("expects_unknown"):
        parts.append("[CONSTRAINT] Bot must say the Terms do not address this.")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Runner

class EvaluationRunner:
    def __init__(
        self,
        chatbot: Optional[ChatbotUnderTest] = None,
        evaluator: Optional[Evaluator] = None,
        random_sample_rate: float = 0.10,
        random_seed: Optional[int] = None,
    ):
        self.chatbot = chatbot or ChatbotUnderTest()
        self.evaluator = evaluator or Evaluator()
        self.random_sample_rate = random_sample_rate
        self.rng = random.Random(random_seed)

    # ------------------------------------------------------------------
    # Per-mode evaluation

    def evaluate_summary_case(self, item: dict) -> CaseResult:
        """Dataset A item -> first-contact summary evaluation."""
        service = item["service_name"]
        tos = item["tos_text"]
        response = self.chatbot.first_contact_summary(service, tos)
        gt = _format_annotations(item)
        case = CaseResult(
            test_id=item["id"],
            mode=MODE_SUMMARY,
            sector=item.get("sector"),
            service_name=service,
            user_input="(first-contact summary request)",
            response=response,
            source_tos=tos,
            ground_truth=gt,
            timestamp=datetime.utcnow().isoformat(),
        )
        case.metrics = self._score_metrics(case)
        case.triage = self._triage(case, item)
        return case
    
    def evaluate_pair_case(self, pair: dict) -> CaseResult:
        """Dataset B item -> delta summary evaluation."""
        service = pair["service_name"]
        old, new = pair["old_version"], pair["new_version"]
        delta_bullets, narrative = self.chatbot.delta_summary(service, old, new)
        # Combine the delta bullets and the narrative because the bot's full
        # delta-summary output as a user would experience it includes both.
        response = (
            f"[DELTA BULLETS]\n{delta_bullets}\n\n[NARRATIVE]\n{narrative}"
        )
        gt = _format_pair_ground_truth(pair)
        case = CaseResult(
            test_id=pair["id"],
            mode=MODE_DELTA,
            sector=None,
            service_name=service,
            user_input="(delta summary request)",
            response=response,
            source_tos=new,
            previous_tos=old,
            ground_truth=gt,
            timestamp=datetime.utcnow().isoformat(),
        )
        case.metrics = self._score_metrics(case)
        case.triage = self._triage(case, pair)
        return case

    def evaluate_qa_case(
        self,
        qa_item: dict,
        tos_lookup: Dict[str, dict],
    ) -> CaseResult:
        """Dataset C item -> follow-up Q&A evaluation."""
        tos_item = tos_lookup.get(qa_item.get("tos_ref", ""))
        if tos_item is None:
            raise KeyError(
                f"QA item {qa_item['id']} references unknown ToS "
                f"{qa_item.get('tos_ref')!r}"
            )
        service = qa_item.get("service_name") or tos_item["service_name"]
        tos = tos_item["tos_text"]
        question = qa_item["question"]
        response = self.chatbot.follow_up(
            service_name=service,
            current_tos=tos,
            previous_tos=None,
            delta=None,
            question=question,
        )
        gt = _format_qa_ground_truth(qa_item)
        case = CaseResult(
            test_id=qa_item["id"],
            mode=MODE_QA,
            sector=tos_item.get("sector"),
            service_name=service,
            user_input=question,
            response=response,
            source_tos=tos,
            ground_truth=gt,
            timestamp=datetime.utcnow().isoformat(),
        )
        case.metrics = self._score_metrics(case)
        case.triage = self._triage(case, qa_item)
        return case

    def evaluate_adversarial_case(self, item: dict) -> CaseResult:
        category = item.get("category", "adversarial")
        question = item.get("user_question") or "Summarize this Terms of Service."
        # All adversarial cases are run through the QA path against the
        # provided ToS text. Mode is summary if the user is asking for one.
        mode = MODE_SUMMARY if "summari" in question.lower() else MODE_QA
        response = self.chatbot.follow_up(
            service_name=item.get("service_name", "AdversarialCorp"),
            current_tos=item.get("tos_text", ""),
            previous_tos=None,
            delta=None,
            question=question,
        )
        gt = (
            f"[CATEGORY] {category}\n"
            f"[EXPECTED BEHAVIOR]\n{item.get('expected_behavior', '')}"
        )
        case = CaseResult(
            test_id=item["id"],
            mode=mode,
            sector=category,
            service_name=item.get("service_name", "AdversarialCorp"),
            user_input=question,
            response=response,
            source_tos=item.get("tos_text", ""),
            ground_truth=gt,
            is_adversarial=True,
            timestamp=datetime.utcnow().isoformat(),
        )
        case.metrics = self._score_metrics(case)
        case.triage = self._triage(case, item)
        return case

    # ------------------------------------------------------------------
    # Internal scoring/triage

    def _score_metrics(self, case: CaseResult) -> Dict[str, MetricResult]:
        results: Dict[str, MetricResult] = {}
        for metric in metrics_for_mode(case.mode):
            # Skip metrics that require ground truth we don't have.
            if metric.name == HARM_FLAGGING_ACCURACY.name and not case.ground_truth:
                continue
            if metric.name == DELTA_PRECISION.name and case.mode != MODE_DELTA:
                continue
            if metric.name == PROTOCOL_ADHERENCE.name and case.mode == MODE_QA:
                continue
            results[metric.name] = self.evaluator.score_metric(
                metric=metric,
                mode=case.mode,
                user_input=case.user_input,
                response=case.response,
                source_tos=case.source_tos,
                previous_tos=case.previous_tos or "",
                ground_truth=case.ground_truth or "",
            )
        return results

    def _triage(self, case: CaseResult, raw_item: dict) -> Dict:
        decision = triage_case(
            metric_results={k: v.as_dict() for k, v in case.metrics.items()},
            sector=case.sector,
            is_adversarial=case.is_adversarial,
            random_sample_rate=self.random_sample_rate,
            rng=self.rng,
            explicit_high_stakes=bool(raw_item.get("high_stakes")),
        )
        return {
            "review_required": decision.review_required,
            "reasons": decision.reasons,
        }
    
    # ------------------------------------------------------------------
    # Top-level orchestration

    def run_full_suite(
        self,
        include_a: bool = True,
        include_b: bool = True,
        include_c: bool = True,
        include_adversarial: bool = True,
        run_id: Optional[str] = None,
    ) -> str:
        run_id = run_id or datetime.utcnow().strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        run_dir = os.path.join(RESULTS_DIR, f"run_{run_id}")
        os.makedirs(run_dir, exist_ok=True)
        results: List[CaseResult] = []

        if include_a:
            ds_a = load_dataset_a()
            for item in ds_a["items"]:
                print(f"[runner] dataset A: {item['id']}")
                results.append(self.evaluate_summary_case(item))

        if include_b:
            ds_b = load_dataset_b()
            for pair in ds_b["items"]:
                print(f"[runner] dataset B: {pair['id']}")
                results.append(self.evaluate_pair_case(pair))

        if include_c:
            ds_a = load_dataset_a()
            tos_lookup = {item["id"]: item for item in ds_a["items"]}
            ds_c = load_dataset_c()
            for qa in ds_c["items"]:
                print(f"[runner] dataset C: {qa['id']}")
                results.append(self.evaluate_qa_case(qa, tos_lookup))

        if include_adversarial:
            ds_x = load_adversarial()
            for item in ds_x["items"]:
                print(f"[runner] adversarial: {item['id']}")
                results.append(self.evaluate_adversarial_case(item))

        self._write_outputs(run_dir, results)
        print(f"[runner] wrote {len(results)} cases to {run_dir}")
        return run_dir
    
    # ------------------------------------------------------------------
    # Persistence

    def _write_outputs(self, run_dir: str, results: Iterable[CaseResult]) -> None:
        results = list(results)
        # JSONL — full traces (CoT, justifications, source ToS).
        with open(os.path.join(run_dir, "results.jsonl"), "w", encoding="utf-8") as f:
            for case in results:
                f.write(json.dumps(case.to_jsonable()) + "\n")

        # CSV — flat (case, metric) rows for dashboards/spreadsheets.
        csv_path = os.path.join(run_dir, "results.csv")
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "test_id",
                "mode",
                "sector",
                "metric",
                "mean_score_0_5",
                "normalized_0_1",
                "score_spread",
                "review_required",
                "review_reasons",
                "timestamp",
            ])
            for case in results:
                for metric_name, metric_result in case.metrics.items():
                    writer.writerow([
                        case.test_id,
                        case.mode,
                        case.sector or "",
                        metric_name,
                        f"{metric_result.mean_score:.3f}",
                        f"{metric_result.normalized:.4f}",
                        metric_result.score_spread,
                        case.triage.get("review_required", False),
                        ";".join(case.triage.get("reasons", [])),
                        case.timestamp,
                    ])

        # Review queue — human-review-required cases only.
        review_queue = [c.to_jsonable() for c in results if c.triage.get("review_required")]
        with open(os.path.join(run_dir, "review_queue.json"), "w", encoding="utf-8") as f:
            json.dump(review_queue, f, indent=2)