"""Frozen fusion configuration; no gtsam needed, so the replay node runs under system Python."""
from __future__ import annotations

import json
from pathlib import Path

FROZEN = Path(__file__).with_name('fusion_frozen.json')


def load_config(path: Path = FROZEN) -> dict:
    """Return the frozen fusion configuration."""
    return json.loads(Path(path).read_text())
