#!/usr/bin/env python3
"""Evaluate terrain matchers on one split: per-frame errors against the dataset labels.

For every frame of the split (or of --flights within it), the harness loads the aerial image,
the dataset label (true position) and the loader's seeded noisy prior. It cuts a north-up map
patch centred on the prior, just big enough to hold the image anywhere in the search space,
and calls each matcher:

    match(image, map_patch, prior, search) -> (x, y, scale, rot_deg, score) or None

(contract: src/trn_matcher/trn_matcher/interface.py). A pose outside the search space counts
as no fix ("outside_search"). The baselines "prior" and "random" (random pose in the search
space) always run as well: they are the floor every error table shows (matcher_report.py).

Output in --out (default eval/results/week4/<split>/):
  frames_<method>.csv   one row per frame: label, prior, fix, error east/north/total [m],
                        scale, rotation, score, time, matcher diagnostics (JSON)
  run_<method>.json     command, git commit, configuration, date
  summary.csv/.md, cdf_<flight>.png   per-flight tables and CDFs (matcher_report.py)

The test split (flight 11) is refused unless --allow-test is given; Akhil decides when.
Matchers: "prior", "random", or MODULE:ATTR (a class or factory called with no arguments, or
an object with .match), e.g. trn_matcher.matcher:FeatureMatcher.

Usage: python3 eval/eval_matcher.py [--split tune] [--matcher MODULE:ATTR ...] [--every 1]
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import datetime
import importlib
import json
import math
import multiprocessing
import subprocess
import sys
import time
import zlib
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/trn_matcher"))
from trn_matcher.baselines import PriorMatcher, RandomMatcher  # noqa: E402
from trn_matcher.frames import footprints, prepare_frame  # noqa: E402
from trn_matcher.interface import Prior, SearchSpace, as_result  # noqa: E402
from trn_matcher.loader import LoaderConfig, VisLocDataset  # noqa: E402

import envcheck  # noqa: E402
import matcher_report  # noqa: E402

FIELDS = ["split", "region", "flight", "image", "method", "status", "true_e", "true_n", "prior_e", "prior_n",
          "prior_err_m", "footprint_m", "patch_size_m", "patch_px", "map_valid_frac", "est_e", "est_n",
          "scale", "rot_deg", "score", "err_e", "err_n", "err_m", "time_ms", "diag"]


def load_matcher(spec: str, seed: int, kwargs: dict | None = None):
    if spec == "prior":
        return PriorMatcher()
    if spec == "random":
        return RandomMatcher(seed)
    module, _, attr = spec.partition(":")
    obj = getattr(importlib.import_module(module), attr)
    return obj if hasattr(obj, "match") and not isinstance(obj, type) else obj(**(kwargs or {}))


def matcher_name(spec: str, m) -> str:
    return getattr(m, "name", None) or spec.replace(":", "_").replace(".", "_")


def evaluate_frame(matcher, image, patch, prior: Prior, true_en, search: SearchSpace) -> dict:
    """Call the matcher once and score its answer against the label. Exceptions propagate."""
    t0 = time.perf_counter()
    res = as_result(matcher.match(image, patch, prior, search))
    ms = (time.perf_counter() - t0) * 1000
    out = {"time_ms": round(ms, 2), "est_e": "", "est_n": "", "scale": "", "rot_deg": "", "score": "",
           "err_e": "", "err_n": "", "err_m": "", "diag": ""}
    if res is None:  # a matcher may keep the diagnostics of a rejected frame in .last_diag
        last = getattr(matcher, "last_diag", None)
        return {**out, "status": "no_fix", "diag": json.dumps(last, default=float) if last else ""}
    out.update(est_e=round(res.x, 3), est_n=round(res.y, 3), scale=round(res.scale, 4),
               rot_deg=round(res.rot_deg, 3), score=res.score,
               diag=json.dumps(res.diag, default=float) if res.diag else "")
    if not all(math.isfinite(v) for v in res.astuple()):
        return {**out, "status": "invalid"}
    if not search.contains(prior, res.x, res.y, res.scale, res.rot_deg):
        return {**out, "status": "outside_search"}
    ee, en = res.x - true_en[0], res.y - true_en[1]
    return {**out, "status": "fix", "err_e": round(ee, 3), "err_n": round(en, 3), "err_m": round(math.hypot(ee, en), 3)}


_CTX: dict = {}


def _worker_init() -> None:
    cv2.setNumThreads(1)   # one thread per worker; the pool provides the parallelism


def rotation_priors(root: Path, flights: list[str]) -> dict[tuple[str, str], float]:
    """Return wrap(Phi1 - Phi2) [deg] per (flight, file name) from the UAV-coordinates CSVs."""
    out = {}
    for f in flights:
        with (root / f / f"{f}-UAV-coordinates.csv").open(encoding="utf-8-sig") as fh:
            for r in csv.DictReader(fh):
                out[(f, r["filename"])] = (float(r["Phi1"]) - float(r["Phi2"]) + 180.0) % 360.0 - 180.0
    return out


def run_frame(i: int) -> dict[str, dict]:
    """Prepare frame i and run every method on it; return {method: CSV row}."""
    c = _CTX
    args, search = c["args"], c["search"]
    fr = prepare_frame(c["ds"], i, search, args.prior_sigma, args.map_m_per_px, c["footprint"])
    image, patch, prior, true = fr.image, fr.patch, fr.prior, fr.true_en
    if c["rot_prior"] is not None:
        key = zlib.crc32(f"rot/{fr.flight}/{fr.filename}".encode())
        noise = float(np.random.default_rng([args.seed, key]).normal(0.0, args.rotation_prior_sigma))
        prior = dataclasses.replace(prior, rot_deg=c["rot_prior"][(fr.flight, fr.filename)] + noise,
                                    rot_sigma_deg=args.rotation_prior_sigma)
    base = {"split": args.split, "region": fr.region, "flight": fr.flight, "image": fr.filename,
            "true_e": round(float(true[0]), 3), "true_n": round(float(true[1]), 3),
            "prior_e": round(prior.east, 3), "prior_n": round(prior.north, 3),
            "prior_err_m": round(float(np.linalg.norm(prior.position - true)), 3),
            "footprint_m": round(prior.footprint_m, 2), "patch_size_m": round(patch.size_m, 2),
            "patch_px": patch.image.shape[0], "map_valid_frac": round(float(patch.valid.mean()), 4)}
    return {name: {**base, "method": name, **evaluate_frame(m, image, patch, prior, true, search)}
            for name, m in c["matchers"]}


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True,
                              cwd=Path(__file__).parent, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=Path.home() / "data/visloc/flights")
    ap.add_argument("--splits", type=Path, default=Path(__file__).parent / "splits.json")
    ap.add_argument("--split", default="tune", choices=["tune", "calibrate", "test"])
    ap.add_argument("--allow-test", action="store_true", help="required for --split test (Akhil's call)")
    ap.add_argument("--flights", nargs="*", help="only these flights of the split")
    ap.add_argument("--matcher", action="append", default=[], help="MODULE:ATTR; baselines always run too")
    ap.add_argument("--matcher-args", default="{}", help="JSON keyword arguments for the --matcher constructors")
    ap.add_argument("--rot-max-deg", type=float, default=20.0,
                    help="search rotation range +-this (default 20; widened from 5 after the tune sweep)")
    ap.add_argument("--scale-range", type=float, nargs=2, default=(0.8, 1.3))
    ap.add_argument("--every", type=int, default=1, help="use every k-th frame of each flight (development)")
    ap.add_argument("--seed", type=int, default=0, help="prior noise seed (loader) and random-baseline seed")
    ap.add_argument("--prior-sigma", type=float, default=50.0)
    ap.add_argument("--window-m", type=float, default=150.0, help="search window half side around the prior")
    ap.add_argument("--image-px", type=int, default=1024, help="aerial image long side after resizing")
    ap.add_argument("--map-m-per-px", type=float, default=0.5, help="map patch resolution")
    ap.add_argument("--rotation-prior", choices=["none", "phi1-phi2"], default="none",
                    help="VARIANT, off by default: give the matcher a rotation prior derived from the dataset's "
                         "angle columns, wrap(Phi1 - Phi2) + Gaussian noise (--rotation-prior-sigma)")
    ap.add_argument("--rotation-prior-sigma", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=1, help="parallel processes (results identical to 1)")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if args.split == "test" and not args.allow_test:
        print("refusing the test split: it stays untouched until Akhil says so (pass --allow-test then)")
        return 2
    envcheck.require_reference_env()

    search = SearchSpace(window_m=args.window_m, scale_range=tuple(args.scale_range),
                         rot_range_deg=(-args.rot_max_deg, args.rot_max_deg))
    splits = json.loads(args.splits.read_text())
    ds = VisLocDataset(args.root, splits, args.split,
                       LoaderConfig(prior_sigma_m=args.prior_sigma, image_px=args.image_px, seed=args.seed))
    specs = ["prior", "random"] + [m for m in args.matcher if m not in ("prior", "random")]
    kwargs = json.loads(args.matcher_args)
    matchers = [(matcher_name(s, m), m) for s in specs
                for m in [load_matcher(s, args.seed, kwargs if s not in ("prior", "random") else None)]]
    out = args.out or Path(__file__).parent / "results/week4" / args.split
    out.mkdir(parents=True, exist_ok=True)

    footprint = footprints(ds)
    by_flight: dict[str, list[int]] = {}
    for i, (_, rec) in enumerate(ds.records):
        if not args.flights or rec.flight in args.flights:
            by_flight.setdefault(rec.flight, []).append(i)
    frames = [i for f in sorted(by_flight) for i in by_flight[f][::args.every]]
    print(f"split {args.split}: {len(frames)} frames from flights {sorted(by_flight)}; "
          f"methods {[n for n, _ in matchers]}; search window +-{search.window_m:g} m, scale "
          f"{search.scale_range}, rotation {search.rot_range_deg} deg", flush=True)

    rot_prior = rotation_priors(args.root, sorted(by_flight)) if args.rotation_prior != "none" else None
    _CTX.update(ds=ds, search=search, args=args, footprint=footprint, matchers=matchers, rot_prior=rot_prior)
    files = {n: (out / f"frames_{n}.csv").open("w", newline="") for n, _ in matchers}
    writers = {n: csv.DictWriter(fh, fieldnames=FIELDS) for n, fh in files.items()}
    for w in writers.values():
        w.writeheader()
    pool = multiprocessing.get_context("fork").Pool(args.workers, initializer=_worker_init) \
        if args.workers > 1 else None
    try:
        results = pool.imap(run_frame, frames, chunksize=1) if pool else map(run_frame, frames)
        for k, rows in enumerate(results):
            for name, row in rows.items():
                writers[name].writerow(row)
            if (k + 1) % 25 == 0 or k + 1 == len(frames):
                print(f"  {k + 1}/{len(frames)} frames", flush=True)
    finally:
        if pool:
            pool.close()
            pool.join()
        for fh in files.values():
            fh.close()

    manifest = {"command": " ".join(sys.argv), "git_commit": git_commit(),
                "date": datetime.datetime.now().isoformat(timespec="seconds"), "split": args.split,
                "flights": sorted(by_flight), "n_frames": len(frames), "every": args.every, "seed": args.seed,
                "prior_sigma_m": args.prior_sigma, "image_px": args.image_px, "map_m_per_px": args.map_m_per_px,
                "search": {"window_m": search.window_m, "scale_range": search.scale_range,
                           "rot_range_deg": search.rot_range_deg},
                "labels": "dataset UAV-coordinates.csv positions; label registration error ~10-40 m (week 3)",
                "rotation_prior": (args.rotation_prior if args.rotation_prior == "none" else
                                   f"{args.rotation_prior} + N(0, {args.rotation_prior_sigma} deg), "
                                   f"matcher sigma {args.rotation_prior_sigma} deg (VARIANT)"),
                "workers": args.workers,
                "versions": {"python": sys.version.split()[0], "numpy": np.__version__,
                             "opencv": cv2.__version__, "scipy": __import__("scipy").__version__}}
    for name, m in matchers:
        settings = m.settings_dict() if hasattr(m, "settings_dict") else {}
        (out / f"run_{name}.json").write_text(json.dumps({**manifest, "method": name, "settings": settings},
                                                         indent=2) + "\n")
    matcher_report.write_report(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
