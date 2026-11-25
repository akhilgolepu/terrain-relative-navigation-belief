#!/usr/bin/env python3
"""Look at the drift data before fitting: RPE RMSE vs segment length on log-log axes, one line per distinct run.

A straight line on these axes means a power law e = c * delta^p; a line that steepens with delta means a second
term is needed. Also writes the local log-log slope between neighbouring segment lengths per run.
Uses the RPE files in RESULTS as they are (currently scored with --skip-start-s 2.0; the value is in the title).

Writes RESULTS/rpe_vs_delta_loglog.png and RESULTS/rpe_vs_delta_local_slopes.csv.
Usage (in ~/venvs/trn): python eval/plot_rpe_vs_delta.py eval/results/vio
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

from drift_data import distinct_runs, load_rpe_points, local_loglog_slopes, plot_rpe_vs_delta, scoring_settings


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    results = Path(sys.argv[1])
    skip = scoring_settings(results)["rpe_skip_start_s"]
    points = [load_rpe_points(results, run) for run in distinct_runs(results)]
    plot_rpe_vs_delta(results / "rpe_vs_delta_loglog.png", points,
                      f"Translation RPE vs segment length, distinct runs, skip_start_s = {skip:g} s\n"
                      "(point labels: number of segments; dotted: reference slopes, not fits)")
    rows = []
    for p in points:
        for (d0, d1), s in zip(zip(p.delta_m[:-1], p.delta_m[1:]), local_loglog_slopes(p.delta_m, p.rmse_m)):
            rows.append({"run": p.run, "from_delta_m": f"{d0:g}", "to_delta_m": f"{d1:g}", "local_slope_rmse": f"{s:.3f}"})
    with (results / "rpe_vs_delta_local_slopes.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    for p in points:
        slopes = local_loglog_slopes(p.delta_m, p.rmse_m)
        print(f"{p.run}: local slopes " + "  ".join(f"{a:g}-{b:g} m: {s:.2f}"
                                                    for a, b, s in zip(p.delta_m[:-1], p.delta_m[1:], slopes)))
    print(f"wrote {results / 'rpe_vs_delta_loglog.png'} and {results / 'rpe_vs_delta_local_slopes.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
