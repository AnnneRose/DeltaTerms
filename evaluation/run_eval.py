"""Single-command CLI to run the DeltaTerms evaluation suite.

Usage examples (from the repo root):

    # Full nightly run, all datasets:
    python -m evaluation.run_eval all

    # Just the QA dataset and the adversarial suite:
    python -m evaluation.run_eval run --datasets c,adversarial

    # Build the summary + regression report against a baseline:
    python -m evaluation.run_eval report --run-dir evaluation/results/run_X \
        --baseline evaluation/results/run_Y

    # Build the calibration + inter-rater report after human reviews land:
    python -m evaluation.run_eval calibrate --run-dir evaluation/results/run_X
"""

from __future__ import annotations

import argparse
import sys

from .calibration import write_calibration_report
from .reporting import write_summary_report
from .runner import EvaluationRunner


def _run(args) -> None:
    selected = {s.strip().lower() for s in (args.datasets or "a,b,c,adversarial").split(",")}
    runner = EvaluationRunner(
        random_sample_rate=args.sample_rate,
        random_seed=args.seed,
    )
    run_dir = runner.run_full_suite(
        include_a="a" in selected,
        include_b="b" in selected,
        include_c="c" in selected,
        include_adversarial="adversarial" in selected or "adv" in selected,
    )
    print(f"OK: results in {run_dir}")
    if args.report:
        path = write_summary_report(run_dir, baseline_dir=args.baseline)
        print(f"Summary report: {path}")


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
    p_run.add_argument("--baseline", default=None)
    p_run.set_defaults(func=_run)

    p_all = sub.add_parser("all", help="Run all datasets and emit a report")
    p_all.add_argument("--sample-rate", type=float, default=0.10)
    p_all.add_argument("--seed", type=int, default=None)
    p_all.add_argument("--baseline", default=None)
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