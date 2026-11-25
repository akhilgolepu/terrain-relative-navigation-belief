#!/usr/bin/env python3
"""EXPLORATORY, AFTER THE TEST RUN, NOT PRE-REGISTERED: label-offset diagnostic on flight 11.

Builds a frames CSV in label_offset.py's format from the test run's cached matcher pass
(eval/results/test_flight11/private/matcher_pass.cache.jsonl) and the labels: status 'fix' for
candidates accepted by the frozen gate (as in the week 4/5 diagnostics), err = fix - label.
Writes it to the git-ignored private/ folder, then runs eval/label_offset.py on it. Changes no
test result. Venv (the test run's environment).
Usage: env -u PYTHONPATH ~/venvs/trn/bin/python eval/posthoc_test_offset.py
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src/trn_matcher"))
from trn_matcher.loader import LoaderConfig, VisLocDataset  # noqa: E402

PRIV = ROOT / "eval/results/test_flight11/private"


def main() -> int:
    splits = json.loads((ROOT / "eval/splits.json").read_text())
    ds = VisLocDataset(Path.home() / "data/visloc/flights", splits, "test", LoaderConfig())
    idx = {r.filename: i for i, (_, r) in enumerate(ds.records)}
    rows = []
    for line in (PRIV / "matcher_pass.cache.jsonl").read_text().splitlines():
        c = json.loads(line)
        true = ds.true_position(idx[c["key"]])
        row = {"split": "test", "flight": "11", "method": "ncc_posthoc", "image": c["key"],
               "status": "fix" if (c["res"] is not None and c["gate_pass"]) else "no_fix",
               "err_e": "", "err_n": "", "err_m": ""}
        if c["res"] is not None:
            ee, en = c["res"][0] - true[0], c["res"][1] - true[1]
            row.update(err_e=round(ee, 3), err_n=round(en, 3), err_m=round((ee ** 2 + en ** 2) ** 0.5, 3))
        rows.append(row)
    path = PRIV / "frames_ncc_posthoc.csv"
    with path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("EXPLORATORY, after the test run, not pre-registered")
    for extra in ([], ["--max-err-m", "50"]):
        subprocess.run([sys.executable, str(ROOT / "eval/label_offset.py"), str(path), *extra], check=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
