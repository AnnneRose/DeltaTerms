"""Phase 3 human-review web app.

A lightweight Flask app that lets generalist or domain-expert reviewers score
cases the triage layer routed for review. The app shows the user input, the
bot's response, the source ToS, and the scoring form, and crucially keeps the
LLM judge's score hidden until after the reviewer submits — preventing
anchoring.

Run from the repo root:

    python -m evaluation.human_review.server --run-dir evaluation/results/run_<id>

Reviews are appended to ``human_reviews.jsonl`` inside the same run directory.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template, request


app = Flask(__name__)
app.config["RUN_DIR"] = None


# ---------------------------------------------------------------------------
# Storage helpers


def _load_review_queue(run_dir: str) -> List[dict]:
    path = os.path.join(run_dir, "review_queue.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_existing_reviews(run_dir: str) -> Dict[str, dict]:
    path = os.path.join(run_dir, "human_reviews.jsonl")
    if not os.path.exists(path):
        return {}
    out: Dict[str, dict] = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                review = json.loads(line)
            except json.JSONDecodeError:
                continue
            out.setdefault(review["test_id"], []).append(review)
    return out


def _append_review(run_dir: str, review: dict) -> None:
    path = os.path.join(run_dir, "human_reviews.jsonl")
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(review) + "\n")


# ---------------------------------------------------------------------------
# Routes


@app.route("/")
def index():
    run_dir = app.config["RUN_DIR"]
    queue = _load_review_queue(run_dir)
    reviews = _load_existing_reviews(run_dir)
    summary = []
    for case in queue:
        summary.append({
            "test_id": case["test_id"],
            "mode": case["mode"],
            "sector": case.get("sector") or "",
            "is_adversarial": case.get("is_adversarial", False),
            "reasons": case.get("triage", {}).get("reasons", []),
            "review_count": len(reviews.get(case["test_id"], [])),
        })
    return render_template("review.html", queue=summary, mode="index")


@app.route("/case/<test_id>")
def case_view(test_id: str):
    run_dir = app.config["RUN_DIR"]
    queue = _load_review_queue(run_dir)
    case = next((c for c in queue if c["test_id"] == test_id), None)
    if not case:
        return "Case not found", 404

    # Per the plan: hide the LLM evaluator scores until after review submit.
    metric_names = sorted(case.get("metrics", {}).keys())
    return render_template(
        "review.html",