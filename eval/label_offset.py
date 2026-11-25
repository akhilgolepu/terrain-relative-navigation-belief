#!/usr/bin/env python3
"""Label-offset diagnostic: the median east/north offset of a matcher's fixes from the labels, per flight.

DIAGNOSTIC ONLY. The offsets are never applied to scores, labels or matcher output; correcting
labels with them would tune on the evaluation data (and on the test split, on the test labels).

For each flight, over the frames where the matcher returned a fix: median of err_e and err_n
(err = estimate - label, metres, region ENU frame), their spread (p10-p90 range and the median
absolute deviation from the median), and the median total error as scored. If the matcher is right,
err is the true ground position minus the label, which has the same sign as week 3's overlay
offsets (eval/results/week3/overlay_offsets.csv), so the two can be compared.
Wrong fixes pull the spread up but barely move the medians; --max-err-m drops fixes with a larger
total error (default: keep all) and the number used is reported.

Usage: python3 eval/label_offset.py eval/results/week4/tune/frames_<method>.csv [--max-err-m 100]
  Writes label_offset_<method>.csv next to the input.
"""
from __future__ import annotations

import argparse
import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

NOTE = "diagnostic only: never applied to scores, labels or matcher output"


def offsets(rows: list[dict], max_err_m: float = math.inf) -> list[dict]:
    """Return one summary row per (split, flight) for the fixes in rows."""
    groups: dict[tuple[str, str, str], list[tuple[float, float]]] = defaultdict(list)
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for r in rows:
        key = (r["split"], r["flight"], r["method"])
        counts[key] += 1
        if r["status"] == "fix" and float(r["err_m"]) <= max_err_m:
            groups[key].append((float(r["err_e"]), float(r["err_n"])))
    out = []
    for key in sorted(counts):
        e = np.array([v[0] for v in groups.get(key, [])])
        n = np.array([v[1] for v in groups.get(key, [])])
        row = {"split": key[0], "flight": key[1], "method": key[2], "n_frames": counts[key], "n_used": e.size,
               "max_err_m": max_err_m if math.isfinite(max_err_m) else ""}
        if e.size:
            me, mn = float(np.median(e)), float(np.median(n))
            row.update(median_e_m=round(me, 2), median_n_m=round(mn, 2),
                       median_offset_m=round(math.hypot(me, mn), 2),
                       p10_e_m=round(float(np.percentile(e, 10)), 2), p90_e_m=round(float(np.percentile(e, 90)), 2),
                       p10_n_m=round(float(np.percentile(n, 10)), 2), p90_n_m=round(float(np.percentile(n, 90)), 2),
                       mad_e_m=round(float(np.median(np.abs(e - me))), 2),
                       mad_n_m=round(float(np.median(np.abs(n - mn))), 2),
                       median_err_m=round(float(np.median(np.hypot(e, n))), 2))
        row["note"] = NOTE
        out.append(row)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frames", type=Path, help="frames_<method>.csv from eval_matcher.py")
    ap.add_argument("--max-err-m", type=float, default=math.inf, help="ignore fixes with a larger total error")
    args = ap.parse_args()
    rows = list(csv.DictReader(args.frames.open()))
    res = offsets(rows, args.max_err_m)
    method = args.frames.stem.removeprefix("frames_")
    path = args.frames.parent / f"label_offset_{method}.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in res for k in r)))
        w.writeheader()
        w.writerows(res)
    for r in res:
        if r["n_used"]:
            print(f"{r['split']} flight {r['flight']} {r['method']}: median offset east {r['median_e_m']:+.1f} m, "
                  f"north {r['median_n_m']:+.1f} m (|{r['median_offset_m']:.1f}| m); p10-p90 east "
                  f"{r['p10_e_m']:+.1f}..{r['p90_e_m']:+.1f}, north {r['p10_n_m']:+.1f}..{r['p90_n_m']:+.1f} m; "
                  f"MAD {r['mad_e_m']:.1f}/{r['mad_n_m']:.1f} m; median error {r['median_err_m']:.1f} m; fixes used "
                  f"{r['n_used']}/{r['n_frames']}")
        else:
            print(f"{r['split']} flight {r['flight']} {r['method']}: no fixes")
    print(f"{NOTE}\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
