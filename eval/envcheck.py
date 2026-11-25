"""Fail loudly if the library versions differ from those of the reported runs.

The reference is eval/reference_env.json (taken from the run manifests). Matcher numbers change
slightly between OpenCV/numpy versions, so reported metrics are only reproducible in that
environment. Call require_reference_env() at the start of every eval script that reports metrics.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REFERENCE = Path(__file__).with_name("reference_env.json")
FUSION = Path(__file__).with_name("reference_env_fusion.json")   # week 6 fusion runs (venv with GTSAM)


def current_versions() -> dict[str, str]:
    import numpy
    import scipy
    out = {"python": sys.version.split()[0], "numpy": numpy.__version__, "scipy": scipy.__version__}
    try:
        import cv2
        out["opencv"] = cv2.__version__
    except ImportError:
        out["opencv"] = "missing"
    try:
        from importlib.metadata import version
        out["gtsam"] = version("gtsam")
    except Exception:  # noqa: BLE001
        out["gtsam"] = "missing"
    return out


def mismatches(reference: Path = REFERENCE) -> list[str]:
    ref = json.loads(reference.read_text())
    cur = current_versions()
    return [f"{k}: running {cur[k]}, reported runs used {ref[k]}" for k in ("python", "numpy", "opencv", "scipy",
                                                                            "gtsam") if k in ref and cur[k] != ref[k]]


def require_reference_env(reference: Path = REFERENCE) -> None:
    bad = mismatches(reference)
    if bad:
        sys.stderr.write("ENVIRONMENT MISMATCH - results would not be comparable with the reported runs:\n  "
                         + "\n  ".join(bad) + f"\n(reference: {reference}; use /usr/bin/python3)\n")
        raise SystemExit(3)
