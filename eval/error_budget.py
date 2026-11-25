#!/usr/bin/env python3
"""Error budget of accepted fixes: systematic label offset vs scatter (diagnostic, nothing applied).

For the frozen matcher's ACCEPTED fixes with |e| <= 50 m (e = fix - label; wrong fixes are left
out as outliers) of each flight, grouped by flight direction (dataset heading Phi2, 90-degree bins):
  total     mean |e|^2
  between   sum_g n_g |mean_g|^2 / N   systematic offset per direction (label registration: lag or
                                       tilt along track plus a fixed map shift); not matcher noise
  within    mean |e - mean_g|^2        scatter around the direction means: matcher error plus random
                                       label noise, so an UPPER bound on the matcher's own error
total = between + within. Reports RMS values (sqrt), shares, and medians. Refuses the test split.

Usage: /usr/bin/python3 eval/error_budget.py eval/results/week5/features_10.csv eval/results/week5/features_05.csv
"""
from __future__ import annotations

import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

import envcheck


def budget(rows: list[dict], root: Path) -> dict:
    flight = rows[0]["flight"]
    with (root / flight / f"{flight}-UAV-coordinates.csv").open(encoding="utf-8-sig") as fh:
        head = {r["filename"]: float(r["Phi2"]) % 360 for r in csv.DictReader(fh)}
    groups = defaultdict(list)
    for r in rows:
        if int(r["accepted"]) and not int(r["wrong"]):
            groups[int(head[r["image"]] // 90)].append([float(r["e_e"]), float(r["e_n"])])
    allv = np.vstack([np.array(v) for v in groups.values()])
    n = len(allv)
    between = sum(len(v) * float(np.sum(np.mean(v, axis=0) ** 2)) for v in groups.values()) / n
    within = sum(float(np.sum((np.array(v) - np.mean(v, axis=0)) ** 2)) for v in groups.values()) / n
    resid = np.vstack([np.array(v) - np.mean(v, axis=0) for v in groups.values()])
    return {"flight": flight, "n": n, "directions": {f"{90 * k}-{90 * k + 90}": len(v) for k, v in groups.items()},
            "rms_total_m": float(np.sqrt(np.mean(np.sum(allv ** 2, axis=1)))),
            "rms_between_m": float(np.sqrt(between)), "rms_within_m": float(np.sqrt(within)),
            "share_between": between / (between + within), "share_within": within / (between + within),
            "median_err_m": float(np.median(np.hypot(*allv.T))),
            "median_within_resid_m": float(np.median(np.hypot(*resid.T))),
            "within_rms_per_axis_m": float(np.sqrt(within / 2))}


def main() -> int:
    envcheck.require_reference_env()
    root = Path.home() / "data/visloc/flights"
    out = []
    for p in sys.argv[1:]:
        rows = list(csv.DictReader(open(p)))
        if any(r["split"] == "test" for r in rows):
            print("refusing the test split")
            return 2
        b = budget(rows, root)
        out.append(b)
        print(f"flight {b['flight']} ({rows[0]['split']}): {b['n']} accepted fixes with |e| <= 50 m, directions "
              f"{b['directions']}\n  RMS error {b['rms_total_m']:.1f} m = systematic per-direction offset "
              f"{b['rms_between_m']:.1f} m ({b['share_between']:.0%} of mean square) + within-direction scatter "
              f"{b['rms_within_m']:.1f} m ({b['share_within']:.0%}); scatter per axis {b['within_rms_per_axis_m']:.1f} m"
              f"\n  median |e| {b['median_err_m']:.1f} m; median |e - direction mean| {b['median_within_resid_m']:.1f} m"
              " (matcher error + random label noise: an upper bound on the matcher's own error)")
    path = Path(__file__).parent / "results/week5/error_budget.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[k for k in out[0] if k != "directions"] + ["directions"])
        w.writeheader()
        w.writerows(out)
    print("diagnostic only; errors are against dataset labels\nwrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
