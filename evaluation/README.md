# DeltaTerms Evaluation Framework

Implements the evaluation plan for the DeltaTerms chatbot: a G-Eval style
automated LLM judge backed by structured human-in-the-loop review,
calibration, and reporting.

## Layout

```
evaluation/
├── metrics.py            # Six metric rubrics (rel., task, protocol, faith., harm, delta)
├── evaluator.py          # G-Eval judge — CoT, 3x averaging at temp 0.2, 0..5 → 0..1
├── chatbot_wrapper.py    # Drives chat.Chatbot + delta.DeltaGenerator for evaluation
├── runner.py             # Phases 1+2 orchestrator: generate, judge, triage, persist
├── triage.py             # Phase 2 routing: disagreement / low-score / high-stakes / 10% sample
├── calibration.py        # Phase 4: human↔judge agreement + Cohen's kappa
├── reporting.py          # Phase 6: aggregate, worst-cases, regression gating (Δ > 0.05)
├── run_eval.py           # Single-command CLI
├── datasets/
│   ├── dataset_a_single.json   # Single-version ToS, annotated harmful/neutral/favorable
│   ├── dataset_b_pairs.json    # (old, new) pairs with ground-truth material changes
│   ├── dataset_c_qa.json       # ToS + question + reference answer
│   └── adversarial.json        # Prompt injection, long input, non-English, contradictions, legal advice
├── human_review/
│   ├── server.py               # Flask app for reviewers
│   └── templates/review.html   # Reviewers see input/response/source ToS; judge scores hidden until submit
└── results/                    # Run outputs go here
```

## Running

From the repository root:

```bash
# Full nightly suite + summary report
python -m evaluation.run_eval all

# Subset
python -m evaluation.run_eval run --datasets c,adversarial

# Build a summary + regression report comparing to a baseline run
python -m evaluation.run_eval report \
    --run-dir evaluation/results/run_<id> \
    --baseline evaluation/results/run_<baseline_id>

# Open the human-review web UI on the queued cases
python -m evaluation.human_review.server --run-dir evaluation/results/run_<id>

# After reviews are submitted, build the calibration + Cohen's kappa report
python -m evaluation.run_eval calibrate --run-dir evaluation/results/run_<id>
```

## Phase mapping

| Plan phase                         | Module / artifact                                       |
| ---------------------------------- | ------------------------------------------------------- |
| 1. Automated LLM evaluation        | `evaluator.py`, `runner.py`, `results.csv`, `results.jsonl` |
| 2. Triage and sampling             | `triage.py`, `review_queue.json`                        |
| 3. Human-in-the-loop review        | `human_review/server.py`, `human_reviews.jsonl`         |
| 4. Calibration                     | `calibration.py`, `calibration_report.json`             |
| 5. Adversarial / safety            | `datasets/adversarial.json` (mandatory human review)    |
| 6. Reporting and iteration         | `reporting.py`, `summary_report.json`                   |

## Outputs per run

Inside `evaluation/results/run_<id>/`:

* `results.csv`        — flat per-(case, metric) rows for dashboards.
* `results.jsonl`      — full per-case payload incl. CoT traces and source ToS.
* `review_queue.json`  — cases the triage layer routed for human review.
* `human_reviews.jsonl`— appended by the review web app.
* `calibration_report.json` — judge↔human deltas + Cohen's kappa per pair.
* `summary_report.json`     — aggregate stats, worst cases, regression findings.

## Triage rules (implemented)

* **Disagreement**: any metric whose three judge runs span > 1 point.
* **Low score**: `faithfulness` or `harm_flagging_accuracy` normalized < 0.6.
* **High stakes**: research consent / medical / financial sectors, or any item
  whose dataset entry sets `"high_stakes": true`.
* **Adversarial**: every adversarial case (mandatory human review).
* **Random sample**: 10% of all cases (default; tunable via `--sample-rate`).

## Regression gating

`reporting.compare_runs` flags any metric where the candidate run's mean
normalized score drops by more than 0.05 vs. the baseline. Deployment is
blocked on these until investigated.

## Calibration target

A per-metric target of "human and judge within 1 point on the 0..5 scale on
≥ 80% of cases" must be met before the automated score is trusted in
production monitoring (see `calibration.calibrate`). Inter-rater Cohen's
kappa < 0.6 between any reviewer pair flags the rubric for sharpening.

## Sequencing note

Per the plan, the first iteration should focus on **Datasets A and C** with
metrics 1–4 (relevancy, task completion, protocol adherence, faithfulness).