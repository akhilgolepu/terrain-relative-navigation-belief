#!/usr/bin/env python3
"""Write docs/frozen_manifest.json: SHA-256 of every file the single test run may depend on.

The list follows docs/frozen_for_test.md (algorithms, frozen settings, environments, shared
evaluation helpers). eval/run_test.py refuses to run if any hash differs.
Usage: python3 eval/make_frozen_manifest.py
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "eval/splits.json",
    "src/trn_matcher/trn_matcher/geo.py", "src/trn_matcher/trn_matcher/tile_store.py",
    "src/trn_matcher/trn_matcher/loader.py", "src/trn_matcher/trn_matcher/frames.py",
    "src/trn_matcher/trn_matcher/interface.py", "src/trn_matcher/trn_matcher/features.py",
    "src/trn_matcher/trn_matcher/masked_ncc.py", "src/trn_matcher/trn_matcher/matcher.py",
    "src/trn_matcher/trn_matcher/matcher_frozen.json",
    "src/trn_calibration/trn_calibration/covariance.py",
    "src/trn_calibration/trn_calibration/calibration_frozen.json",
    "src/trn_calibration/trn_calibration/validity_cuts.json",
    "src/trn_fusion/trn_fusion/config.py", "src/trn_fusion/trn_fusion/core.py",
    "src/trn_fusion/trn_fusion/fix_factor.py", "src/trn_fusion/trn_fusion/odometry_sim.py",
    "src/trn_fusion/trn_fusion/validity.py", "src/trn_fusion/trn_fusion/fusion_frozen.json",
    "src/trn_consumer/trn_consumer/policy.py",
    "eval/reference_env.json", "eval/reference_env_fusion.json", "eval/envcheck.py",
    "eval/calib_metrics.py", "eval/eval_fusion.py",
    "docs/test_preregistration.md",
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    manifest = {"note": "SHA-256 of the frozen files for the single flight 11 test run; checked by eval/run_test.py",
                "files": {f: sha256(ROOT / f) for f in FILES}}
    (ROOT / "docs/frozen_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"wrote docs/frozen_manifest.json ({len(FILES)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
