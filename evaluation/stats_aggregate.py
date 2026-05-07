"""Aggregate statistics across multiple full evaluation runs.

Each run produces one ``mean_normalized`` per metric (suite-wide mean). Repeating
the suite ``N`` times yields ``N`` samples per metric for stability analysis."""

from __future__ import annotations

import json
import math
import os
import statistics
from datetime import datetime
from typing import List, Optional

from .reporting import summarize

# Two-sided 95% Student t critical values t_{df, 0.975}; linear interpolation between knots.
_T975_KNOTS: List[tuple[int, float]] = [
    (1, 12.706),
    (2, 4.303),
    (5, 2.571),
    (10, 2.228),
    (15, 2.131),
    (20, 2.086),
    (25, 2.060),
    (29, 2.045),
    (35, 2.030),
    (40, 2.021),
    (60, 2.000),
    (120, 1.980),
    (9999, 1.960),
]


def _t_critical_975(df: int) -> float:
    """Approximate two-sided 95% t multiplier for given degrees of freedom."""
    if df < 1:
        return 1.96
    if df >= _T975_KNOTS[-1][0]:
        return _T975_KNOTS[-1][1]
    lo_df, lo_t = _T975_KNOTS[0]
    for hi_df, hi_t in _T975_KNOTS[1:]:
        if df <= hi_df:
            if hi_df == lo_df:
                return hi_t
            w = (df - lo_df) / (hi_df - lo_df)
            return lo_t + w * (hi_t - lo_t)
        lo_df, lo_t = hi_df, hi_t
    return 1.96


def _two_sided_p_normal(t_like: float) -> float:
    """Two-sided p-value using standard normal (adequate for df >= ~25)."""
    try:
        from statistics import NormalDist

        z = abs(t_like)
        return 2.0 * (1.0 - NormalDist().cdf(z))
    except Exception:
        return float("nan")


def aggregate_repeated_runs(
    run_dirs: List[str],
    *,
    null_mean: float = 0.5,
) -> dict:
    """Build per-metric stats from suite-level means of each run.

    ``null_mean`` is the hypothesized population mean for the one-sample t-style
    comparison (default 0.5 = midpoint of normalized 0..1 scores).
    """
    summaries = [summarize(rd) for rd in run_dirs]
    all_metrics: set[str] = set()
    for s in summaries:
        all_metrics.update(s.keys())

    metrics_out: dict = {}
    for name in sorted(all_metrics):
        vals: List[float] = []
        for s in summaries:
            if name in s:
                vals.append(float(s[name].mean_normalized))
        n = len(vals)
        if n == 0:
            continue
        mu = statistics.mean(vals)
        sd = statistics.stdev(vals) if n > 1 else 0.0
        se = sd / math.sqrt(n) if n > 1 else 0.0
        df = n - 1
        tcrit = _t_critical_975(df) if df >= 1 else 1.96
        ci_low = mu - tcrit * se if n > 1 else mu
        ci_high = mu + tcrit * se if n > 1 else mu

        t_stat = (mu - null_mean) / se if se > 0 else float("nan")
        p_norm = _two_sided_p_normal(t_stat) if se > 0 and not math.isnan(t_stat) else float("nan")

        p_exact: Optional[float] = None
        try:
            from scipy.stats import ttest_1samp  # type: ignore

            if n >= 2:
                _, p_exact = ttest_1samp(vals, popmean=null_mean)
                p_exact = float(p_exact)
        except Exception:
            pass

        metrics_out[name] = {
            "n_runs": n,
            "mean_of_run_means": round(mu, 6),
            "std_across_runs": round(sd, 6),
            "stderr_of_mean": round(se, 6),
            "ci95_low": round(ci_low, 6),
            "ci95_high": round(ci_high, 6),
            "null_mean": null_mean,
            "t_statistic_vs_null": round(t_stat, 4) if not math.isnan(t_stat) else None,
            "p_value_two_sided_normal_approx": round(p_norm, 6)
            if not math.isnan(p_norm)
            else None,
            "p_value_two_sided_student_t_exact": round(p_exact, 6) if p_exact is not None else None,
            "per_run_mean_normalized": [round(v, 6) for v in vals],
        }

    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "n_suite_runs": len(run_dirs),
        "run_dirs": run_dirs,
        "null_hypothesis_mean_normalized": null_mean,
        "interpretation": (
            "mean_of_run_means is the average of each run's suite-wide mean for that metric. "
            "std_across_runs measures repeatability across suite invocations. "
            "t_statistic_vs_null tests whether the mean differs from null_mean (two-sided); "
            "p_value_two_sided_student_t_exact uses Student's t when scipy is installed, "
            "else use p_value_two_sided_normal_approx (fine for n_runs >= 30)."
        ),
        "metrics": metrics_out,
    }


def write_aggregate_report(payload: dict, out_dir: str) -> str:
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "aggregate_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")
    return path
