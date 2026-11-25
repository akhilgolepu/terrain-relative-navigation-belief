#!/usr/bin/env python3
"""Leakage check for splits.json: no flight may reach two splits.

Structural checks (no data needed): every region's flights are listed once; no flight belongs to two
regions; every region is in exactly one split; no split names an unknown region; no flight appears
in two splits; no flight listed under excluded_regions is used by a split. With --data (folder of extracted flights or of the remote index), also checks that
regions in different splits are geographically apart: their satellite maps do not overlap and the
closest UAV positions of two different splits are at least --min-gap-km apart.
Exit code 1 and one line per problem if anything leaks.

Usage: python3 eval/check_splits.py [eval/splits.json] [--data ~/data/visloc/index] [--min-gap-km 10]
"""
from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
from pathlib import Path


def structural_problems(splits: dict) -> list[str]:
    problems = []
    region_of: dict[str, str] = {}
    for region, info in splits["regions"].items():
        flights = info["flights"]
        if len(flights) != len(set(flights)):
            problems.append(f"region {region} lists a flight twice: {flights}")
        for f in flights:
            if f in region_of and region_of[f] != region:
                problems.append(f"flight {f} is in regions {region_of[f]} and {region}")
            region_of.setdefault(f, region)
    split_of_region: dict[str, list[str]] = {}
    for split, regions in splits["splits"].items():
        for r in regions:
            if r not in splits["regions"]:
                problems.append(f"split {split} names unknown region {r}")
            split_of_region.setdefault(r, []).append(split)
    for r, ss in split_of_region.items():
        if len(ss) > 1:
            problems.append(f"region {r} is in more than one split: {ss}")
    for r in splits["regions"]:
        if r not in split_of_region:
            problems.append(f"region {r} is in no split")
    flights_of_split = {s: {f for r in rs if r in splits["regions"] for f in splits["regions"][r]["flights"]}
                        for s, rs in splits["splits"].items()}
    excluded = {f for info in splits.get("excluded_regions", {}).values() for f in info["flights"]}
    for s, fs in flights_of_split.items():
        if fs & excluded:
            problems.append(f"excluded flights {sorted(fs & excluded)} appear in split {s}")
    for a, b in itertools.combinations(flights_of_split, 2):
        both = flights_of_split[a] & flights_of_split[b]
        if both:
            problems.append(f"flights {sorted(both)} appear in both {a} and {b}")
    return problems


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def geographic_problems(splits: dict, data: Path, min_gap_km: float) -> list[str]:
    problems = []
    boxes, points = {}, {}
    for split, regions in splits["splits"].items():
        lats, lons, pts = [], [], []
        for r in regions:
            for f in splits["regions"][r]["flights"]:
                chips = _rows(data / f / f"{f}-satellite-tile-coordinates.csv")
                lats += [float(c["latitude"]) for c in chips]
                lons += [float(c["longitude"]) for c in chips]
                pts += [(float(u["lat"]), float(u["lon"])) for u in _rows(data / f / f"{f}-UAV-coordinates.csv")]
        boxes[split] = (min(lats), max(lats), min(lons), max(lons))
        points[split] = pts
    for a, b in itertools.combinations(boxes, 2):
        la0, la1, lo0, lo1 = boxes[a]
        lb0, lb1, mb0, mb1 = boxes[b]
        if la0 <= lb1 and lb0 <= la1 and lo0 <= mb1 and mb0 <= lo1:
            problems.append(f"satellite maps of {a} and {b} overlap")
        # closest pair, on a thinned set (every 10th point) to stay fast; regions are far apart or not
        gap = min(_haversine_km(*p, *q) for p in points[a][::10] for q in points[b][::10])
        if gap < min_gap_km:
            problems.append(f"UAV positions of {a} and {b} come within {gap:.2f} km (< {min_gap_km} km)")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("splits", nargs="?", type=Path, default=Path(__file__).parent / "splits.json")
    ap.add_argument("--data", type=Path, help="flight folders with the coordinate CSVs")
    ap.add_argument("--min-gap-km", type=float, default=10.0)
    args = ap.parse_args()
    splits = json.loads(args.splits.read_text())
    problems = structural_problems(splits)
    if args.data and not problems:
        problems += geographic_problems(splits, args.data, args.min_gap_km)
    for p in problems:
        print(f"LEAK: {p}")
    if not problems:
        n = {s: sum(len(splits["regions"][r]["flights"]) for r in rs) for s, rs in splits["splits"].items()}
        print(f"no leakage: {n} flights per split" + (" (geographic check included)" if args.data else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
