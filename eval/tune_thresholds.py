#!/usr/bin/env python3
"""Choose the matcher's accept thresholds (peak_min, ratio_min) on the TUNE split, by a fixed rule.

Input: frames_ncc.csv from an accept-all run (peak_min = ratio_min = 0), which holds every
frame's peak and ratio in its diag column, and its error against the label.
Rule (fixed before looking at the results, 2026-11-19):
  - grid: peak_min in PEAKS, ratio_min in RATIOS (coarse, to limit overfitting 144 frames);
  - a fix is wrong if its error against the label exceeds --wrong-m (default 50 m: beyond the
    10-40 m label registration error, and well beyond a correct NCC peak);
  - keep pairs whose accepted set has >= --min-accepted frames and a wrong rate <= --max-wrong;
  - among those, take the largest acceptance; ties -> higher within-15 m rate -> larger
    thresholds (more conservative).
The label offset is never used: thresholds are chosen on raw errors against the labels.
Writes RESULTS/threshold_grid.csv and prints the chosen pair.

Usage: python3 eval/tune_thresholds.py eval/results/week4/tune_variants/<run>/frames_ncc.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

PEAKS = [0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.5]
RATIOS = [1.0, 1.05, 1.1, 1.15, 1.2, 1.3, 1.4, 1.5, 1.75, 2.0]


def frame_table(rows: list[dict]) -> list[dict]:
    """Return per frame: peak, ratio (None if the matcher had no candidate) and error."""
    out = []
    for r in rows:
        d = json.loads(r["diag"]) if r["diag"] else {}
        out.append({"peak": d.get("peak"), "ratio": d.get("ratio"),
                    "err": float(r["err_m"]) if r["status"] == "fix" else None})
    return out


def evaluate(frames: list[dict], peak_min: float, ratio_min: float, wrong_m: float) -> dict:
    n = len(frames)
    acc = [f for f in frames if f["err"] is not None and f["peak"] is not None
           and f["peak"] >= peak_min and f["ratio"] >= ratio_min]
    wrong = sum(f["err"] > wrong_m for f in acc)
    near = sum(f["err"] <= 15.0 for f in acc)
    return {"peak_min": peak_min, "ratio_min": ratio_min, "n_frames": n, "n_accepted": len(acc),
            "acceptance": round(len(acc) / n, 3) if n else 0.0,
            "wrong_rate_accepted": round(wrong / len(acc), 3) if acc else None,
            "within_15m_rate_accepted": round(near / len(acc), 3) if acc else None}


def choose(grid: list[dict], max_wrong: float, min_accepted: int) -> dict | None:
    ok = [g for g in grid if g["n_accepted"] >= min_accepted and g["wrong_rate_accepted"] is not None
          and g["wrong_rate_accepted"] <= max_wrong]
    if not ok:
        return None
    return max(ok, key=lambda g: (g["n_accepted"], g["within_15m_rate_accepted"], g["peak_min"], g["ratio_min"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frames", type=Path)
    ap.add_argument("--wrong-m", type=float, default=50.0)
    ap.add_argument("--max-wrong", type=float, default=0.05)
    ap.add_argument("--min-accepted", type=int, default=20)
    args = ap.parse_args()
    rows = list(csv.DictReader(args.frames.open()))
    if {r["split"] for r in rows} != {"tune"}:
        print("refusing: thresholds are chosen on the tune split only")
        return 2
    frames = frame_table(rows)
    grid = [evaluate(frames, p, r, args.wrong_m) for p in PEAKS for r in RATIOS]
    path = args.frames.parent / "threshold_grid.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(grid[0]))
        w.writeheader()
        w.writerows(grid)
    best = choose(grid, args.max_wrong, args.min_accepted)
    print(f"accept-all: {evaluate(frames, 0.0, 0.0, args.wrong_m)}")
    print(f"chosen (wrong <= {args.max_wrong:.0%} of accepted, >= {args.min_accepted} accepted, wrong = "
          f"> {args.wrong_m:g} m): {best}")
    print(f"wrote {path}")
    return 0 if best else 1


if __name__ == "__main__":
    sys.exit(main())
