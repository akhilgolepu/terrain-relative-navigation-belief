"""
Matcher interface: what a terrain matcher receives and returns.

A matcher is any object with

    match(image, map_patch, prior, search=DEFAULT_SEARCH) -> MatchResult | tuple | None

  image      (H, W, 3) uint8 RGB aerial image, stored north-up (to within a few degrees).
  map_patch  tile_store.MapPatch: north-up RGB patch, row 0 = north, column 0 = west, with
             center_en (E, N [m]) and m_per_px, so pixels convert to the region's ENU frame
             (see patch_px_to_en / en_to_patch_px below).
  prior      Prior: prior position (E, N [m]), its sigma, and the nominal footprint of the
             image (ground side length [m] at scale 1).
  search     SearchSpace: where the answer may lie. A matcher must not return a pose outside
             it; the harness counts such answers as no fix.

Return None for "no fix" (weak evidence), else (x, y, scale, rot_deg, score):
  x, y       east, north [m] of the image centre's ground position, region ENU frame.
  scale      estimated image ground size / prior.footprint_m (1.0 = nominal footprint).
  rot_deg    direction the image's up axis points, degrees clockwise from north
             (0 = image is exactly north-up).
  score      matcher confidence, larger = better; any scale, used for ranking in week 5.
A MatchResult may also carry a diag dict (inlier count, inlier ratio, residual, ...); the
harness writes it to the per-frame CSV. For a rejected frame (None) the harness writes the
matcher's last_diag attribute, if it has one.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple, Protocol

import numpy as np

from .tile_store import MapPatch


@dataclass(frozen=True)
class SearchSpace:
    """Allowed answers. window_m is the half side of a square around the prior position."""

    window_m: float = 150.0                         # 3 x the loader's default 50 m prior sigma
    scale_range: tuple[float, float] = (0.8, 1.3)   # image ground size / nominal footprint
    # widened from +-5 to +-20 deg on 2026-11-19: on tune, 63 % of fixes needed |rot| > 5 deg
    # (residual ~+-7 deg flipping sign with flight direction); none reached +-20 (docs/log.md)
    rot_range_deg: tuple[float, float] = (-20.0, 20.0)

    def contains(self, prior: 'Prior', x: float, y: float, scale: float, rot_deg: float) -> bool:
        """Return True if the pose lies inside the window, scale range and rotation range."""
        return (abs(x - prior.east) <= self.window_m and abs(y - prior.north) <= self.window_m
                and self.scale_range[0] <= scale <= self.scale_range[1]
                and self.rot_range_deg[0] <= rot_deg <= self.rot_range_deg[1])

    def patch_size_m(self, footprint_m: float) -> float:
        """Return the map patch side that holds the image anywhere in the search space."""
        a = np.radians(max(abs(r) for r in self.rot_range_deg))
        image_extent = footprint_m * self.scale_range[1] * (abs(np.cos(a)) + abs(np.sin(a)))
        return float(2 * self.window_m + image_extent)


DEFAULT_SEARCH = SearchSpace()


@dataclass(frozen=True)
class Prior:
    """Prior knowledge given to the matcher. Positions in metres, region ENU frame."""

    east: float
    north: float
    sigma_m: float          # standard deviation of the prior error, per axis
    footprint_m: float      # nominal ground side length of the image (chip ground size)
    # optional rotation prior (off by default): expected rot_deg and its standard deviation;
    # the matcher then searches rotation only within rot_deg +- ROT_PRIOR_NSIGMA x sigma
    rot_deg: float | None = None
    rot_sigma_deg: float | None = None

    @property
    def position(self) -> np.ndarray:
        """Return (east, north) as an array."""
        return np.array([self.east, self.north])


class MatchResult(NamedTuple):
    """A fix: (x, y, scale, rot_deg, score) plus optional diagnostics."""

    x: float
    y: float
    scale: float
    rot_deg: float
    score: float
    diag: dict | None = None    # optional diagnostics (inlier count, residual, ...)

    def astuple(self) -> tuple[float, float, float, float, float]:
        """Return (x, y, scale, rot_deg, score)."""
        return self.x, self.y, self.scale, self.rot_deg, self.score


class Matcher(Protocol):
    """Anything with this match() method can be evaluated by eval/eval_matcher.py."""

    def match(self, image: np.ndarray, map_patch: MapPatch, prior: Prior,
              search: SearchSpace = DEFAULT_SEARCH) -> MatchResult | tuple | None:
        """Return a fix (x, y, scale, rot_deg, score) or None."""


def as_result(out) -> MatchResult | None:
    """Normalise a matcher's return value (None, 5-tuple or MatchResult) to a MatchResult."""
    if out is None:
        return None
    if isinstance(out, MatchResult):
        return out
    x, y, scale, rot, score = (float(v) for v in out)
    return MatchResult(x, y, scale, rot, score, None)


def patch_px_to_en(patch: MapPatch, u, v) -> tuple[np.ndarray, np.ndarray]:
    """
    Convert patch pixel coordinates to east, north [m].

    u is the column and v the row, continuous, with pixel edges at integers (the centre of
    pixel (row 0, col 0) is u = v = 0.5).
    """
    half = patch.image.shape[1] / 2.0, patch.image.shape[0] / 2.0
    east = patch.center_en[0] + (np.asarray(u, float) - half[0]) * patch.m_per_px
    north = patch.center_en[1] - (np.asarray(v, float) - half[1]) * patch.m_per_px
    return east, north


def en_to_patch_px(patch: MapPatch, east, north) -> tuple[np.ndarray, np.ndarray]:
    """Convert east, north [m] to patch pixel coordinates (u = column, v = row)."""
    half = patch.image.shape[1] / 2.0, patch.image.shape[0] / 2.0
    u = (np.asarray(east, float) - patch.center_en[0]) / patch.m_per_px + half[0]
    v = half[1] - (np.asarray(north, float) - patch.center_en[1]) / patch.m_per_px
    return u, v
