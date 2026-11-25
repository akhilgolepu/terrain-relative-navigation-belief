#!/usr/bin/env python3
"""Week 7: the filter assumes the wrong drift (0.5x or 2x the true RMS drift); recorded fixes, offline.

"0.5x / 2x the true drift" is taken as the RMS drift LEVEL: the filter's random-walk coefficient is
b_filter = factor^2 x b_true (drift grows as sqrt(b)), i.e. 0.25x and 4x b. The odometry itself is
generated with b_true (same seeds as the open-loop runs, 20 seeds), the fixes are the recorded
accept-all candidates, the fusion design is frozen (fusion_frozen.json). Reports ATE RMSE, NEES and
95 % coverage per flight, drift level and factor (1.0 = matched, for reference).
Venv (GTSAM). Never flight 11.

Usage: env -u PYTHONPATH ~/venvs/trn/bin/python eval/drift_mismatch.py [--workers 2]
"""
from __future__ import annotations

import argparse
import csv
import multiprocessing
import sys
from pathlib import Path

import numpy as np

import envcheck
import eval_fusion as ef
from trn_fusion.core import load_config
from trn_fusion.fix_factor import FixModel
from trn_fusion.odometry_sim import drift_b, simulate

OUT = Path(__file__).parent / "results/week7"
FACTORS = [0.5, 1.0, 2.0]
_W: dict = {}


def _run(task):
    flight, level, factor, seed = task
    if flight not in _W:
        _W[flight] = ef.load_inputs(flight)
        _W["fm"] = FixModel()
    inp = _W[flight]
    cfg = load_config()
    so = cfg["synthetic_odometry"]
    b = drift_b(level, so["reference_distance_m"])
    odo = simulate(inp["labels"], b, so["floor_a_m"], seed=1000 * so["drift_levels_pct"].index(level) + seed)
    mean, cov, _, _, _ = ef.run_fused(inp, odo, factor ** 2 * b, cfg, _W["fm"])
    e = mean - inp["labels"]
    d2 = ef.nees(e, cov)
    return {"flight": flight, "drift_pct": level, "factor": factor, "seed": seed,
            "rmse": float(np.sqrt(np.mean(np.sum(e ** 2, axis=1)))), "nees": float(d2.mean()),
            "cov95": float(np.mean(d2 <= ef.CHI2_95))}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    envcheck.require_reference_env(envcheck.FUSION)
    so = load_config()["synthetic_odometry"]
    tasks = [(f, lv, fa, s) for f in ("10", "05") for lv in so["drift_levels_pct"] for fa in FACTORS
             for s in range(so["seeds"])]
    with multiprocessing.get_context("fork").Pool(args.workers) as pool:
        rows = pool.map(_run, tasks, chunksize=8)
    with (OUT / "drift_mismatch.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    lines = ["## Filter drift model mismatched: assumes 0.5x / 1x / 2x the true RMS drift (b x 0.25 / 1 / 4)", "",
             "Recorded fixes, SYNTHETIC odometry (20 seeds), frozen design. Errors are against dataset labels and "
             "include label registration error.", "",
             "| Flight | True drift | RMSE [m] 0.5x / 1x / 2x | NEES 0.5x / 1x / 2x | cov 95 % 0.5x / 1x / 2x |",
             "|---|---|---|---|---|"]
    for f in ("10", "05"):
        for lv in so["drift_levels_pct"]:
            cells = []
            for key, fmt in (("rmse", "{:.1f}"), ("nees", "{:.2f}"), ("cov95", "{:.2f}")):
                cells.append(" / ".join(fmt.format(np.mean([r[key] for r in rows if r["flight"] == f and
                                                            r["drift_pct"] == lv and r["factor"] == fa]))
                                        for fa in FACTORS))
            lines.append(f"| {f} | {lv} % | " + " | ".join(cells) + " |")
    lines.append("")
    (OUT / "drift_mismatch.md").write_text("\n".join(lines))
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
