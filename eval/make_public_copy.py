#!/usr/bin/env python3
"""Build the public copy ~/trn-belief-public: a NEW git repository (fresh history, no remote, never pushed).

Copies, from the committed tree of this repository (git ls-files, clean tree required):
  code, tests, launch files, tools, docs, README, data/README.md, and from eval/results only the
  aggregated tables and plots (.md, .png, .txt, and .csv/.json that are not per-frame or per-pose).
Excludes everything in docs/private_files.md and more: per-frame and per-pose result files (frames_,
features_, inputs_, oof_, closed-loop runs, test closed_loop/, belief/consumer logs, failure indexes,
overlay indexes and landmarks, image-pair tables, TUM VI .tum trajectories and error-vs-distance series),
logs, lock and PID files, binary documents the scan cannot read (.docx/.pdf: the project plan);
eval/splits.json is copied WITHOUT its coordinates (region origins, map bounding boxes; regenerate the full
file with eval/make_splits.py after download), and never any imagery, chips, rosbags or caches (those were never tracked).
Markdown files: every coordinate-like number (see eval/scan_public.py) is replaced by
"[coordinate removed]". Then eval/scan_public.py runs on the copy; the copy is committed only if it
passes. Refuses to touch an existing target folder.

Usage: python3 eval/make_public_copy.py [--target ~/trn-belief-public]
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "eval"))
import scan_public  # noqa: E402

INCLUDE_TOP = ("src/", "launch/", "tools/", "docs/", "eval/")
INCLUDE_FILES = {"README.md", "CLAUDE.md", ".gitignore", "data/README.md"}
EXCLUDE = re.compile(r"(frames_|features_|inputs_|oof_|/runs/|test_flight11/closed_loop/|/belief_|/consumer_|node_|"
                     r"failures/|overlay_index|overlay_landmarks|uav_scale_pairs|\.log$|RUN\.lock|\.pid$|\.tum$|"
                     r"_error_vs_distance\.csv$|/private/|\.(docx|pdf|odt|xlsx|pptx)$)")
RESULT_SUFFIX = {".md", ".png", ".txt", ".csv", ".json"}


def wanted(rel: str) -> bool:
    if rel in INCLUDE_FILES:
        return True
    if not rel.startswith(INCLUDE_TOP) or EXCLUDE.search(rel):
        return False
    if rel.startswith("eval/results/"):
        return Path(rel).suffix in RESULT_SUFFIX
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=Path, default=Path.home() / "trn-belief-public")
    args = ap.parse_args()
    if subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=ROOT, capture_output=True,
                      text=True).stdout.strip():
        print("refusing: commit your changes first (the copy is made from committed files)")
        return 2
    if args.target.exists():
        print(f"refusing: {args.target} exists; not overwriting")
        return 2
    files = [f for f in subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True,
                                       text=True).stdout.split("\0") if f]
    keep = [f for f in files if wanted(f)]
    redacted = {}
    for rel in keep:
        dst = args.target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if rel == "eval/splits.json":   # keep structure, drop coordinates (region origins, map bounding boxes)
            sp = json.loads((ROOT / rel).read_text())
            for info in sp["regions"].values():
                info.pop("enu_origin", None)
                info.pop("chip_centre_bbox", None)
            sp["note"] = ("public copy: coordinates removed (enu_origin, chip_centre_bbox). Regenerate the full file "
                          "with `python3 eval/make_splits.py` after downloading UAV-VisLoc; the loader needs enu_origin.")
            dst.write_text(json.dumps(sp, indent=2) + "\n")
            continue
        if rel.endswith(".md"):
            text = (ROOT / rel).read_text()
            new, n = scan_public.COORD.subn(
                lambda m: m.group(0) if m.group(0) in scan_public.ALLOWED else "[coordinate removed]", text)
            if n and new != text:
                redacted[rel] = sum(1 for m in scan_public.COORD.finditer(text) if m.group(0) not in scan_public.ALLOWED)
            dst.write_text(new)
        else:
            shutil.copy2(ROOT / rel, dst)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    note = ["# About this public copy", "",
            f"Made by `eval/make_public_copy.py` from the private working repository at commit `{head}`, as a NEW git "
            "repository with fresh history. It has never been pushed anywhere.", "",
            "Left out on purpose (see `docs/private_files.md` and the builder's docstring): every file with "
            "label-derived positions (UAV-VisLoc forbids redistribution), per-frame and per-pose result files, logs, "
            "the coordinates in `eval/splits.json` (it keeps regions, flights and splits; regenerate the full file with "
            "`python3 eval/make_splits.py` after downloading the data), and of course all imagery, map chips, overlays, rosbags and caches (never tracked).", "",
            f"Coordinates removed from Markdown text: {sum(redacted.values())} numbers in "
            f"{', '.join(f'`{k}`' for k in sorted(redacted)) or 'no files'}.", "",
            "Scripts that read per-frame results (for example `eval/matcher_report.py`, `eval/calib_eval.py`) need "
            "those files, so they only run after the data is downloaded and the pipeline re-run.", ""]
    (args.target / "PUBLIC_COPY.md").write_text("\n".join(note))
    bad = scan_public.scan(args.target)
    for b in bad:
        print("FOUND", b)
    if bad:
        print(f"scan FAILED ({len(bad)} findings): no git repository created; fix and rebuild")
        return 1
    subprocess.run(["git", "init", "-q"], cwd=args.target, check=True)
    subprocess.run(["git", "add", "."], cwd=args.target, check=True)
    subprocess.run(["git", "commit", "-q", "-m",
                    f"Public copy of trn-belief (fresh history, from private commit {head})\n\n"
                    "Code, tests, launch files, docs and aggregated results only; no dataset files, no label-derived "
                    "positions, no imagery. Scanned with eval/scan_public.py."], cwd=args.target, check=True)
    n = len(keep) + 1
    print(f"public copy: {n} files in {args.target}; scan clean; fresh git repository committed (no remote)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
