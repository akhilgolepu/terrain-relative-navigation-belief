#!/usr/bin/env python3
"""Scan a directory tree for anything that must not be published; exit 1 on any finding.

Fails on:
  - CSV files whose header has a position column (latitude/longitude or ENU east/north positions:
    lat, lon, latitude, longitude, east, north, true_e, true_n, prior_e, prior_n, fix_e, fix_n, est_e,
    est_n, cand_east, cand_north, cx, cy);
  - JSON files with coordinate keys (lat, lon, latitude, longitude, enu_origin, chip_centre_bbox, or any
    of the position columns above);
  - any prose or code file (not CSV/JSON, whose numbers are checked through their columns and keys)
    containing a decimal-degree coordinate in the dataset's ranges (latitude 20-49 or longitude 100-129
    with at least four decimals; a degrees value of that shape anywhere in the text counts);
  - imagery, recordings and caches: .jpg .jpeg .tif .tiff .mcap .db3 .bag .zip, *.cache.jsonl;
  - binary documents the scan cannot read (.docx .pdf .odt .xlsx .pptx).
PNG figures are allowed (plots, no imagery: the dataset's images are JPG and were never plotted
into docs/figures or result plots except git-ignored overlays, which are not copied).
Usage: python3 eval/scan_public.py ROOT
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

POS_COLS = {"lat", "lon", "latitude", "longitude", "east", "north", "true_e", "true_n", "prior_e", "prior_n", "fix_e",
            "fix_n", "est_e", "est_n", "cand_east", "cand_north", "cx", "cy"}
JSON_KEYS = POS_COLS | {"enu_origin", "chip_centre_bbox", "lat_min", "lat_max", "lon_min", "lon_max"}
COORD = re.compile(r"(?<![\w.])(?:[2-4]\d\.\d{4,}|1[0-2]\d\.\d{4,})(?![\d])")
# allowed coordinate values, each with its reason (none is from the datasets)
ALLOWED = {"47.3979706": "PX4 SITL built-in default home (Zurich), week 1 smoke test",
           "47.397971": "PX4 SITL built-in default home (Zurich), week 1 smoke test"}
BANNED_SUFFIX = {".jpg", ".jpeg", ".tif", ".tiff", ".mcap", ".db3", ".bag", ".zip",
                 ".docx", ".pdf", ".odt", ".xlsx", ".pptx"}
TEXT_SUFFIX = {".py", ".md", ".txt", ".csv", ".json", ".yaml", ".yml", ".xml", ".cfg", ".sh", ".log", ".msg", ""}


def json_keys(obj) -> set:
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.add(k)
            out |= json_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            out |= json_keys(v)
    return out


def scan(root: Path) -> list[str]:
    bad = []
    for p in sorted(root.rglob("*")):
        if ".git" in p.parts or not p.is_file():
            continue
        rel = p.relative_to(root)
        if p.suffix.lower() in BANNED_SUFFIX or p.name.endswith(".cache.jsonl"):
            bad.append(f"{rel}: banned file type")
            continue
        if p.suffix.lower() not in TEXT_SUFFIX:
            continue
        text = p.read_text(errors="ignore")
        if p.suffix == ".csv":
            header = {c.strip() for c in text.splitlines()[0].split(",")} if text else set()
            if header & POS_COLS:
                bad.append(f"{rel}: CSV position columns {sorted(header & POS_COLS)}")
        if p.suffix == ".json":
            try:
                keys = json_keys(json.loads(text))
            except json.JSONDecodeError:
                keys = set()
            if keys & JSON_KEYS:
                bad.append(f"{rel}: JSON coordinate keys {sorted(keys & JSON_KEYS)}")
        if p.suffix in (".csv", ".json"):
            continue   # data files: checked by header/keys above (metre values often have many decimals)
        for n, line in enumerate(text.splitlines(), 1):
            for m in COORD.finditer(line):
                if m.group(0) not in ALLOWED:
                    bad.append(f"{rel}:{n}: coordinate-like number {m.group(0)}")
    return bad


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    bad = scan(root)
    n = sum(1 for p in root.rglob("*") if p.is_file() and ".git" not in p.parts)
    for b in bad:
        print("FOUND", b)
    print(f"scanned {n} files under {root}: {'FAIL, ' + str(len(bad)) + ' findings' if bad else 'clean'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
