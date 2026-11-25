#!/usr/bin/env python3
"""How often is a correct position among the matcher's top-k distinct candidates? (diagnostic)

For each frame of frames_<method>.csv with diag['topk'] (coarse candidates, best first, > 20 m
apart), finds the first candidate within --near-m of the label. Reports, per flight and for
accepted / rejected / wrong (accepted, error > --near-m) frames, the share whose label is near
candidate 1, near candidate 2 or 3 only, or near none; plus the z gap between candidates 1 and 2
for each group. Refuses the test split.

Usage: python3 eval/topk_check.py RUN/frames_ncc.csv [...] [--near-m 50]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np


def first_near(row: dict, top: list[dict], near_m: float) -> int:
    t = np.array([float(row["true_e"]), float(row["true_n"])])
    for k, c in enumerate(top):
        if np.hypot(c["east"] - t[0], c["north"] - t[1]) <= near_m:
            return k + 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frames", type=Path, nargs="+")
    ap.add_argument("--near-m", type=float, default=50.0)
    args = ap.parse_args()
    for path in args.frames:
        rows = list(csv.DictReader(path.open()))
        if any(r["split"] == "test" for r in rows):
            print(f"refusing {path}: test split")
            return 2
        groups: dict[str, list[tuple[int, float]]] = {"accepted": [], "rejected": [], "wrong (accepted)": []}
        for r in rows:
            d = json.loads(r["diag"]) if r["diag"] else {}
            top = d.get("topk")
            if not top:
                continue
            k = first_near(r, top, args.near_m)
            gap = top[0]["z"] - top[1]["z"] if len(top) > 1 else float("nan")
            if r["status"] == "fix":
                groups["accepted"].append((k, gap))
                if float(r["err_m"]) > args.near_m:
                    groups["wrong (accepted)"].append((k, gap))
            else:
                groups["rejected"].append((k, gap))
        print(f"== {path.parent.name} ({rows[0]['split']}, flight {rows[0]['flight']}): label within "
              f"{args.near_m:g} m of candidate ...")
        for g, v in groups.items():
            if not v:
                print(f"  {g:17s} n=0")
                continue
            c = Counter(k for k, _ in v)
            n = len(v)
            print(f"  {g:17s} n={n:3d}: #1 {c[1] / n:.2f}, #2 {c[2] / n:.2f}, #3 {c[3] / n:.2f}, none {c[0] / n:.2f};"
                  f" median z gap #1-#2 {np.nanmedian([x for _, x in v]):.1f}")
    print("diagnostic only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
