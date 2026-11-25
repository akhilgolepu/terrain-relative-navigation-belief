#!/usr/bin/env python3
"""Compare VIO scores with and without the start-up skip.

RESULTS/vio_scores.csv must already be scored with the default --skip-start-s (eval/score_week2_vio.sh does this).
This script rescores the same runs (inputs from RESULTS/vio_scores_settings.json, so only runs that passed the
validity checks) with --skip-start-s 0, the earlier behaviour, into RESULTS/skip_start_0/, then writes
RESULTS/skip_start_comparison.csv: per run, RPE RMSE and median at 1, 10 and 50 m and the start-aligned final
horizontal error, for both settings. No OpenVINS run; scoring only.

Usage (in ~/venvs/trn): python eval/compare_skip_start.py eval/results/vio
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
METRICS = ["rpe_trans_rmse_1m", "rpe_trans_median_1m", "rpe_trans_rmse_10m", "rpe_trans_median_10m",
           "rpe_trans_rmse_50m", "rpe_trans_median_50m", "final_horiz_err_start_aligned_m"]


def read_scores(path: Path) -> dict[str, dict[str, str]]:
    return {r["sequence"]: r for r in csv.DictReader(path.open())}


def compare(new: dict[str, dict[str, str]], old: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    rows = []
    for run in sorted(new):
        for m in METRICS:
            a, b = float(new[run][m]), float(old[run][m])
            rows.append({"sequence": run.rsplit("_run", 1)[0], "run": run, "metric": m,
                         f"skip_{new[run]['skip_start_s']}s": f"{a:.4f}", f"skip_{old[run]['skip_start_s']}s": f"{b:.4f}",
                         "difference": f"{a - b:+.4f}"})
    return rows


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    results = Path(sys.argv[1])
    settings = json.loads((results / "vio_scores_settings.json").read_text())
    if float(settings["rpe_skip_start_s"]) == 0:
        print("RESULTS/vio_scores.csv is already scored with --skip-start-s 0; rescore with the default first")
        return 1
    out0 = results / "skip_start_0"
    seq_args = [a for n, i in sorted(settings["inputs"].items()) for a in ("--seq", n, i["estimate"], i["ground_truth"])]
    subprocess.run([sys.executable, str(HERE / "score_vio.py"), "--out", str(out0), "--skip-start-s", "0"] + seq_args,
                   check=True, stdout=subprocess.DEVNULL)
    rows = compare(read_scores(results / "vio_scores.csv"), read_scores(out0 / "vio_scores.csv"))
    out = results / "skip_start_comparison.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} ({len(rows)} rows); skip 0 scores in {out0}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
