#!/usr/bin/env python3
"""Week 6: per-frame fusion inputs from the frozen matcher runs (accept-all candidates).

For every frame of a flight: time (s, from the dataset 'date' column, 1 s resolution), label
(true_e/n, region ENU), the loader's seeded prior (prior_e/n), and, if the frozen matcher found a
candidate, fix_e/n = label + e (from eval/results/week5/features_<flight>.csv: the accepted fix
or the best rejected candidate, i.e. what FeatureMatcher(accept_all=True) returns; frames whose
refined answer fell outside the search space have no candidate, as in accept-all mode), log_ratio
and gate_pass (old peak/ratio gate). Refuses flight 11.

Usage: python3 eval/fusion_inputs.py 10 05   -> eval/results/week6/inputs_<flight>.csv
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime
from pathlib import Path

RUNS = {"10": "tune_regression", "05": "calibrate"}
HERE = Path(__file__).parent


def main() -> int:
    for flight in sys.argv[1:]:
        if flight not in RUNS:
            print(f"refusing flight {flight}: only {sorted(RUNS)} (never 11)")
            return 2
        frames = sorted(csv.DictReader((HERE / f"results/week4/{RUNS[flight]}/frames_ncc.csv").open()),
                        key=lambda r: r["image"])
        feats = {r["image"]: r for r in csv.DictReader((HERE / f"results/week5/features_{flight}.csv").open())}
        with (Path.home() / f"data/visloc/flights/{flight}/{flight}-UAV-coordinates.csv").open(encoding="utf-8-sig") as fh:
            date = {r["filename"]: datetime.fromisoformat(r["date"]).timestamp() for r in csv.DictReader(fh)}
        t0 = date[frames[0]["image"]]
        out = []
        for r in frames:
            f = feats.get(r["image"])
            if f is not None and r["diag"] and "outside the search space" in r["diag"]:
                f = None   # FeatureMatcher(accept_all=True) returns no candidate for these either
            te, tn = float(r["true_e"]), float(r["true_n"])
            out.append({"flight": flight, "split": r["split"], "region": r["region"], "image": r["image"],
                        "t_s": date[r["image"]] - t0, "true_e": te, "true_n": tn,
                        "prior_e": r["prior_e"], "prior_n": r["prior_n"], "has_fix": int(f is not None),
                        "fix_e": round(te + float(f["e_e"]), 3) if f else "",
                        "fix_n": round(tn + float(f["e_n"]), 3) if f else "",
                        "log_ratio": f["log_ratio"] if f else "", "gate_pass": f["accepted"] if f else ""})
        path = HERE / f"results/week6/inputs_{flight}.csv"
        with path.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(out[0]))
            w.writeheader()
            w.writerows(out)
        print(f"flight {flight}: {len(out)} frames, {sum(o['has_fix'] for o in out)} with a candidate -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
