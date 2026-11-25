#!/usr/bin/env python3
"""Compare two per-frame CSVs from eval_matcher.py on the answer columns (exact string match).

Columns: status, est_e, est_n, scale, rot_deg, score, err_m, and every diag key present in the
reference (new diag keys are ignored). Prints the number of frames compared and any differences.
Exit 1 if anything differs.

Usage: python3 eval/compare_runs.py REFERENCE.csv NEW.csv
"""
from __future__ import annotations

import csv
import json
import sys

COLS = ("status", "est_e", "est_n", "scale", "rot_deg", "score", "err_m")


def main() -> int:
    ref = {r["image"]: r for r in csv.DictReader(open(sys.argv[1]))}
    new = {r["image"]: r for r in csv.DictReader(open(sys.argv[2]))}
    diffs = []
    if set(ref) != set(new):
        diffs.append(f"different frames: {len(ref)} vs {len(new)}")
    for img in sorted(set(ref) & set(new)):
        a, b = ref[img], new[img]
        diffs += [f"{img} {c}: {a[c]} -> {b[c]}" for c in COLS if a[c] != b[c]]
        da, db = (json.loads(x["diag"]) if x["diag"] else {} for x in (a, b))
        diffs += [f"{img} diag.{k}: {da[k]} -> {db.get(k)}" for k in da if da[k] != db.get(k)]
    print(f"compared {len(set(ref) & set(new))} frames; {len(diffs)} differences")
    for d in diffs[:20]:
        print("  " + d)
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
