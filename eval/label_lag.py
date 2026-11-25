#!/usr/bin/env python3
"""Label-lag check: is the along-track label offset explained by a time lag (offset = speed x lag)?

DIAGNOSTIC ONLY. Never applied to scores; corrected errors are printed only as a second, clearly
labelled column. Refuses the test split: nothing is fitted on flight 11.

For each ACCEPTED fix of each flight (frames_<method>.csv from eval_matcher.py):
  velocity v = (label[i+1] - label[i-1]) / (t[i+1] - t[i-1]) from the neighbouring frames' labels
  (ENU east/north from the CSV) and times ('date' column, 1 s resolution; --time attr3 uses the
  undocumented attr_3 column as milliseconds instead, for sensitivity); skipped if a neighbour is
  missing or the time step is outside 0.5..10 s per frame;
  along = (label - fix) . v/|v|   (negative = the label lies behind the fix along the flight)
  cross = (label - fix) . right-of-track unit vector
Fits per flight:
  lag model      along = speed x lag             (least squares through the origin; lag in s)
  constant model along = c                        (a fixed along-track offset, e.g. camera tilt)
  both           along = c + speed x lag          (only meaningful if speed varies)
  2-D model      (label - fix) = shift + speed x lag x track_unit, with shift a constant east/north
                 vector (map registration offset, same for both flight directions) and lag the
                 timing term; three unknowns, fitted on both coordinates together.
with residual RMS and MAD, the standard error of lag, the speed spread, and the cross-track mean.
If speed hardly varies, the lag and constant models cannot be told apart; the script says so.
Corrected error (DIAGNOSTIC column): distance from the fix to the label shifted by speed x lag along
the track, with each flight's own lag (in-sample) and with the other flight's lag (cross-check).

Usage: python3 eval/label_lag.py RUN/frames_ncc.csv [RUN2/frames_ncc.csv ...] [--time date|attr3]
  Writes eval/results/week4/label_lag[_attr3].csv.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import math
import sys
from pathlib import Path

import numpy as np

NOTE = "diagnostic only: never applied to scores"


def times(root: Path, flight: str, mode: str) -> dict[str, float]:
    with (root / flight / f"{flight}-UAV-coordinates.csv").open(encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    if mode == "attr3":
        return {r["filename"]: float(r["attr_3"]) / 1000.0 for r in rows}
    return {r["filename"]: datetime.fromisoformat(r["date"]).timestamp() for r in rows}


def samples(rows: list[dict], t: dict[str, float]) -> list[dict]:
    """Return per accepted fix: speed, unit track vector, along and cross offsets."""
    order = sorted(rows, key=lambda r: r["image"])
    pos = {r["image"]: np.array([float(r["true_e"]), float(r["true_n"])]) for r in order}
    names = [r["image"] for r in order]
    out = []
    for k, r in enumerate(order):
        if r["status"] != "fix" or k == 0 or k == len(order) - 1:
            continue
        a, b = names[k - 1], names[k + 1]
        dt = t[b] - t[a]
        if not 1.0 <= dt <= 20.0:      # 0.5..10 s per frame step
            continue
        v = (pos[b] - pos[a]) / dt
        speed = float(np.linalg.norm(v))
        if speed < 1.0:
            continue
        u = v / speed
        right = np.array([u[1], -u[0]])
        d = -np.array([float(r["err_e"]), float(r["err_n"])])   # label - fix
        out.append({"image": r["image"], "speed": speed, "u": u, "along": float(d @ u),
                    "cross": float(d @ right), "d": d})
    return out


def fit(s: list[dict]) -> dict:
    sp = np.array([x["speed"] for x in s])
    al = np.array([x["along"] for x in s])
    n = len(s)
    lag = float((sp @ al) / (sp @ sp))
    r_lag = al - sp * lag
    se_lag = math.sqrt(float(r_lag @ r_lag) / max(n - 1, 1) / float(sp @ sp))
    c = float(al.mean())
    r_c = al - c
    a_mat = np.c_[np.ones(n), sp]
    (c2, lag2), *_ = np.linalg.lstsq(a_mat, al, rcond=None)
    r_both = al - a_mat @ [c2, lag2]
    rows2 = []
    rhs = []
    for x in s:
        rows2 += [[1.0, 0.0, x["speed"] * x["u"][0]], [0.0, 1.0, x["speed"] * x["u"][1]]]
        rhs += [x["d"][0], x["d"][1]]
    m2, r2 = np.array(rows2), np.array(rhs)
    sol2, *_ = np.linalg.lstsq(m2, r2, rcond=None)
    res2 = (r2 - m2 @ sol2).reshape(-1, 2)
    cov2 = np.linalg.inv(m2.T @ m2) * float((res2 ** 2).sum()) / max(2 * n - 3, 1)
    rms = lambda r: float(np.sqrt(np.mean(r ** 2)))  # noqa: E731
    mad = lambda r: float(np.median(np.abs(r - np.median(r))))  # noqa: E731
    return {"n": n, "speed_mean": float(sp.mean()), "speed_cv": float(sp.std() / sp.mean()),
            "lag_s": lag, "lag_se_s": se_lag, "lag_rms_m": rms(r_lag), "lag_mad_m": mad(r_lag),
            "const_m": c, "const_rms_m": rms(r_c), "both_c_m": float(c2), "both_lag_s": float(lag2),
            "both_rms_m": rms(r_both), "along_median_m": float(np.median(al)),
            "cross_mean_m": float(np.mean([x["cross"] for x in s])),
            "cross_mad_m": mad(np.array([x["cross"] for x in s])),
            "m2_shift_e_m": float(sol2[0]), "m2_shift_n_m": float(sol2[1]), "m2_lag_s": float(sol2[2]),
            "m2_lag_se_s": float(math.sqrt(cov2[2, 2])),
            "m2_resid_rms_m": float(np.sqrt(np.mean((res2 ** 2).sum(axis=1)))),
            "m2_resid_median_m": float(np.median(np.hypot(res2[:, 0], res2[:, 1])))}


def corrected_errors(s: list[dict], lag: float) -> np.ndarray:
    """|fix - (label - u speed lag)| for each sample (DIAGNOSTIC)."""
    return np.array([np.linalg.norm(x["d"] - x["u"] * x["speed"] * lag) for x in s])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("frames", type=Path, nargs="+")
    ap.add_argument("--time", choices=["date", "attr3"], default="date")
    ap.add_argument("--root", type=Path, default=Path.home() / "data/visloc/flights")
    ap.add_argument("--out", type=Path, default=Path(__file__).parent / "results/week4")
    args = ap.parse_args()
    per = {}
    for path in args.frames:
        rows = list(csv.DictReader(path.open()))
        if any(r["split"] == "test" for r in rows):
            print(f"refusing {path}: no fitting on the test split")
            return 2
        for flight in sorted({r["flight"] for r in rows}):
            fr = [r for r in rows if r["flight"] == flight]
            s = samples(fr, times(args.root, flight, args.time))
            if len(s) < 5:
                print(f"flight {flight}: only {len(s)} usable fixes, skipped")
                continue
            per[(fr[0]["split"], flight)] = (s, fit(s))
    table = []
    for (split, flight), (s, f) in per.items():
        raw = np.array([np.linalg.norm(x["d"]) for x in s])
        own = corrected_errors(s, f["lag_s"])
        row = {"split": split, "flight": flight, "time_source": args.time, **{k: round(v, 3) if isinstance(v, float)
                                                                              else v for k, v in f.items()},
               "err_raw_median_m": round(float(np.median(raw)), 1), "err_raw_p95_m": round(float(np.percentile(raw, 95)), 1),
               "DIAG_err_lag_corrected_own_median_m": round(float(np.median(own)), 1),
               "DIAG_err_lag_corrected_own_p95_m": round(float(np.percentile(own, 95)), 1)}
        for (s2, fl2), (_, f2) in per.items():
            if fl2 != flight:
                cross = corrected_errors(s, f2["lag_s"])
                row[f"DIAG_err_corrected_with_lag_of_{fl2}_median_m"] = round(float(np.median(cross)), 1)
        row["note"] = NOTE
        table.append(row)
        print(f"{split} flight {flight} ({args.time} times): n={f['n']} accepted fixes, speed {f['speed_mean']:.1f} m/s "
              f"(CV {f['speed_cv']:.2f})\n"
              f"  lag model   along = speed x lag: lag {f['lag_s']:+.2f} +- {f['lag_se_s']:.2f} s, residual RMS "
              f"{f['lag_rms_m']:.1f} m, MAD {f['lag_mad_m']:.1f} m\n"
              f"  const model along = c: c {f['const_m']:+.1f} m, residual RMS {f['const_rms_m']:.1f} m\n"
              f"  both        c {f['both_c_m']:+.1f} m + speed x {f['both_lag_s']:+.2f} s, RMS {f['both_rms_m']:.1f} m\n"
              f"  cross-track mean {f['cross_mean_m']:+.1f} m (MAD {f['cross_mad_m']:.1f})\n"
              f"  2-D model  shift east {f['m2_shift_e_m']:+.1f} north {f['m2_shift_n_m']:+.1f} m + speed x lag "
              f"{f['m2_lag_s']:+.2f} +- {f['m2_lag_se_s']:.2f} s along track; residual |r| RMS "
              f"{f['m2_resid_rms_m']:.1f} m, median {f['m2_resid_median_m']:.1f} m\n"
              f"  error vs label: raw median {row['err_raw_median_m']} m, p95 {row['err_raw_p95_m']} m | "
              f"DIAGNOSTIC lag-corrected (own lag, in-sample): median "
              f"{row['DIAG_err_lag_corrected_own_median_m']} m, p95 {row['DIAG_err_lag_corrected_own_p95_m']} m"
              + "".join(f" | DIAGNOSTIC with lag of {k.split('_of_')[1].split('_')[0]}: median {v} m"
                        for k, v in row.items() if k.startswith("DIAG_err_corrected_with")))
    if len(per) == 2:
        (_, a), (_, b) = list(per.values())
        diff = a["lag_s"] - b["lag_s"]
        se = math.hypot(a["lag_se_s"], b["lag_se_s"])
        print(f"lag difference {diff:+.2f} s, combined SE {se:.2f} s -> {abs(diff) / se:.1f} SE apart "
              f"({'consistent' if abs(diff) <= 2 * se else 'NOT consistent'} at 2 SE)")
        dc = a["const_m"] - b["const_m"]
        print(f"constant along-track offsets: {a['const_m']:+.1f} m vs {b['const_m']:+.1f} m (difference {dc:+.1f} m)")
        d2 = a["m2_lag_s"] - b["m2_lag_s"]
        se2 = math.hypot(a["m2_lag_se_s"], b["m2_lag_se_s"])
        print(f"2-D model lags: {a['m2_lag_s']:+.2f} vs {b['m2_lag_s']:+.2f} s, difference {d2:+.2f} s = "
              f"{abs(d2) / se2:.1f} combined SE ({'consistent' if abs(d2) <= 2 * se2 else 'NOT consistent'} at 2 SE)")
    path = args.out / f"label_lag{'_attr3' if args.time == 'attr3' else ''}.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(dict.fromkeys(k for r in table for k in r)))
        w.writeheader()
        w.writerows(table)
    print(f"{NOTE}\nwrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
