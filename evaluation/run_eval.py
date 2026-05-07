"""Single-command CLI to run the DeltaTerms evaluation suite.

Usage examples (from the repo root):

    # Full nightly run, all datasets:
    python -m evaluation.run_eval all

    # Just the QA dataset and the adversarial suite:
    python -m evaluation.run_eval run --datasets c,adversarial

    # Build the summary + regression report against a baseline:
    python -m evaluation.run_eval report --run-dir evaluation/results/run_X \
        --baseline evaluation/results/run_Y

    # Thirty independent full suites, pause 15s between (HF), then aggregate stats:
    EVAL_PAUSE_BETWEEN_RUNS_S=15 python -m evaluation.run_eval all --repeat 30
"""

from __future__ import annotations

import argparse
import os
import sys
import time
import uuid
from datetime import datetime

from .calibration import write_calibration_report
from .reporting import write_summary_report
from .runner import EvaluationRunner
from .stats_aggregate import aggregate_repeated_runs, write_aggregate_report


def _default_pause_between_runs() -> float:
    try:
        return float(os.environ.get("EVAL_PAUSE_BETWEEN_RUNS_S", "10"))
    except ValueError:
        return 10.0


def _pause_between_runs(seconds: float) -> None:
    if seconds > 0:
        print(f"[runner] pausing {seconds:.1f}s between suite runs (HF rate limiting)")
        time.sleep(seconds)


def _run(args) -> None:
    selected = {s.strip().lower() for s in (args.datasets or "a,b,c,adversarial").split(",")}
    runner = EvaluationRunner(
        random_sample_rate=args.sample_rate,
        random_seed=args.seed,
    )
    repeat = max(1, int(args.repeat))
    pause_s = args.pause_between_runs
    if pause_s is None:
        pause_s = _default_pause_between_runs()

    group_ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
    group_uuid = uuid.uuid4().hex[:6]
    run_dirs: list[str] = []

    for rep in range(repeat):
        if repeat > 1:
            run_id = f"{group_ts}-rep{rep + 1:02d}of{repeat:02d}-{group_uuid}"
        else:
            run_id = None
        run_dir = runner.run_full_suite(
            include_a="a" in selected,
            include_b="b" in selected,
            include_c="c" in selected,
            include_adversarial="adversarial" in selected or "adv" in selected,
            run_id=run_id,
        )
        run_dirs.append(run_dir)
        if repeat == 1:
            print(f"OK: results in {run_dir}")
        else:
            print(f"OK: suite run {rep + 1}/{repeat} → {run_dir}")
        if rep < repeat - 1:
            _pause_between_runs(pause_s)

    last_dir = run_dirs[-1]
    if args.report:
        path = write_summary_report(last_dir, baseline_dir=args.baseline)
        if repeat == 1:
            print(f"Summary report: {path}")
        else:
            print(f"Summary report (last suite run): {path}")

    if repeat > 1:
        agg_dir = os.path.join(
            os.path.dirname(last_dir),
            f"multi_{group_ts}-{group_uuid}",
        )
        payload = aggregate_repeated_runs(run_dirs, null_mean=float(args.null_mean))
        agg_path = write_aggregate_report(payload, agg_dir)
        print(f"Aggregate report ({repeat} runs): {agg_path}")


def _all(args) -> None:
    args.datasets = "a,b,c,adversarial"
    args.report = True
    _run(args)


def _report(args) -> None:
    path = write_summary_report(args.run_dir, baseline_dir=args.baseline)
    print(f"Summary report: {path}")


def _calibrate(args) -> None:
    path = write_calibration_report(args.run_dir)
    print(f"Calibration report: {path}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="evaluation.run_eval")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="Run a subset of datasets")
    p_run.add_argument(
        "--datasets",
        default="a,b,c,adversarial",
        help="Comma list from {a,b,c,adversarial}",
    )
    p_run.add_argument("--sample-rate", type=float, default=0.10)
    p_run.add_argument("--seed", type=int, default=None)
    p_run.add_argument("--report", action="store_true")
    p_run.add_argument("--repeat", type=int, default=1, help="Run the full suite this many times (default 1)")
    p_run.add_argument(
        "--pause-between-runs",
        type=float,
        default=None,
        help="Seconds to sleep between suite runs when --repeat>1 (default: env EVAL_PAUSE_BETWEEN_RUNS_S or 10)",
    )
    p_run.add_argument(
        "--null-mean",
        type=float,
        default=0.5,
        help="Null hypothesis mean for normalized scores in aggregate t-test (default 0.5)",
    )
    p_run.add_argument(
        "--baseline",
        default=None,
        help="Optional baseline run directory for regression comparison in summary_report.json",
    )
    p_run.set_defaults(func=_run)

    p_all = sub.add_parser("all", help="Run all datasets and emit a report")
    p_all.add_argument("--sample-rate", type=float, default=0.10)
    p_all.add_argument("--seed", type=int, default=None)
    p_all.add_argument("--repeat", type=int, default=1)
    p_all.add_argument("--pause-between-runs", type=float, default=None)
    p_all.add_argument("--null-mean", type=float, default=0.5)
    p_all.add_argument(
        "--baseline",
        default=None,
        help="Optional baseline run directory for regression comparison in summary_report.json",
    )
    p_all.set_defaults(func=_all)

    p_rep = sub.add_parser("report", help="Build summary + regression report")
    p_rep.add_argument("--run-dir", required=True)
    p_rep.add_argument("--baseline", default=None)
    p_rep.set_defaults(func=_report)

    p_cal = sub.add_parser("calibrate", help="Build calibration + kappa report")
    p_cal.add_argument("--run-dir", required=True)
    p_cal.set_defaults(func=_calibrate)

    args = parser.parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())