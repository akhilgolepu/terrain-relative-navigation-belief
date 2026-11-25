"""
SYNTHETIC odometry: label-path increments plus sampled drift. Not a measured sensor.

The drift is the week 2 floor + random-walk form, e(delta)^2 = a^2 + b * delta: a white "floor"
on every position and a random walk whose variance grows with distance travelled. The level
sweep scales b so that the RMS horizontal drift after D_ref metres is X % of D_ref
(b = (X/100)^2 * D_ref); drift then grows as the square root of distance.
"""
from __future__ import annotations

import numpy as np


def drift_b(level_pct: float, d_ref_m: float) -> float:
    """Return the random-walk coefficient b [m] for a drift level given in % of D_ref."""
    return (level_pct / 100.0) ** 2 * d_ref_m


def simulate(labels: np.ndarray, b: float, a: float, seed: int) -> np.ndarray:
    """
    Return SYNTHETIC odometry positions (N, 2): labels + random-walk drift + white floor.

    The random walk starts at 0 at the first frame; per step of length d along the label path
    it adds N(0, b d / 2) per axis. The floor adds N(0, a^2 / 2) per axis to every position.
    """
    labels = np.asarray(labels, float)
    rng = np.random.default_rng(seed)
    d = np.r_[0.0, np.hypot(*np.diff(labels, axis=0).T)]
    rw = np.cumsum(rng.normal(0.0, 1.0, (len(labels), 2)) * np.sqrt(b * d / 2.0)[:, None], axis=0)
    floor = rng.normal(0.0, a / np.sqrt(2.0), (len(labels), 2))
    return labels + rw + floor


def step_sigma(increment: np.ndarray, b: float, a: float) -> float:
    """Return the per-axis standard deviation of one odometry increment (matched filter model)."""
    d = float(np.hypot(*np.asarray(increment, float)))
    return float(np.sqrt(b * d / 2.0 + a ** 2))
