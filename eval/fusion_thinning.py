#!/usr/bin/env python3
"""Week 6: fix-thinning interval from the autocorrelation of fix errors on flight 05 (CALIBRATE).

Rule (fixed before running): fix errors e = fix - label of candidates with |e| <= 50 m (right
fixes; wrong ones are outliers, handled by the mixture). Autocorrelation of e_east and e_north at
frame lag k, over pairs where both frames are right fixes (masked ACF, centred on the mean).
Interval k* = first lag where BOTH autocorrelations fall below 1/e; interval in seconds = k* x the
median frame step. Fixes are then fused at most once per interval. Flight 05 only.

Usage: python3 eval/fusion_thinning.py  -> prints and writes eval/results/week6/thinning_05.json
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent


def masked_acf(x: np.ndarray, valid: np.ndarray, max_lag: int) -> list[float]:
    m = x[valid].mean()
    xc = np.where(valid, x - m, 0.0)
    var = float(np.mean(xc[valid] ** 2))
    out = []
    for k in range(1, max_lag + 1):
        both = valid[:-k] & valid[k:]
        out.append(float(np.mean(xc[:-k][both] * xc[k:][both]) / var) if both.sum() > 10 else float("nan"))
    return out


def main() -> int:
    rows = list(csv.DictReader((HERE / "results/week6/inputs_05.csv").open()))
    has = np.array([int(r["has_fix"]) for r in rows], bool)
    e = np.array([[float(r["fix_e"]) - float(r["true_e"]), float(r["fix_n"]) - float(r["true_n"])] if h else [0, 0]
                  for r, h in zip(rows, has)])
    valid = has & (np.hypot(e[:, 0], e[:, 1]) <= 50.0)
    t = np.array([float(r["t_s"]) for r in rows])
    step = float(np.median(np.diff(t)))
    acf_e, acf_n = masked_acf(e[:, 0], valid, 40), masked_acf(e[:, 1], valid, 40)
    thr = 1 / math.e
    k_star = next((k + 1 for k in range(40) if acf_e[k] < thr and acf_n[k] < thr), None)
    res = {"flight": "05", "n_right_fixes": int(valid.sum()), "median_step_s": step, "threshold": thr,
           "acf_east": [round(a, 3) for a in acf_e], "acf_north": [round(a, 3) for a in acf_n],
           "k_star_frames": k_star, "interval_s": k_star * step if k_star else None}
    (HERE / "results/week6/thinning_05.json").write_text(json.dumps(res, indent=1) + "\n")
    print(f"ACF east  lags 1..10: {res['acf_east'][:10]}\nACF north lags 1..10: {res['acf_north'][:10]}\n"
          f"first lag with both < 1/e: {k_star} frames x {step:.0f} s = {res['interval_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
