"""
Trivial matchers that set the error floor; any real matcher must beat them.

PriorMatcher   returns the prior position (no matching). Its error against the dataset label
               is the prior noise; against the true ground position it is prior noise plus
               the label registration offset.
RandomMatcher  returns a uniformly random pose inside the search space (window around the
               prior, scale and rotation ranges). Reproducible: the generator is seeded from
               (seed, prior position), and the prior is itself seeded per frame by the loader.
"""
from __future__ import annotations

import zlib

import numpy as np

from .interface import DEFAULT_SEARCH, MatchResult, Prior, SearchSpace


class PriorMatcher:
    """Answer = prior position, nominal scale, no rotation, score 0."""

    name = 'prior'

    def match(self, image, map_patch, prior: Prior, search: SearchSpace = DEFAULT_SEARCH):
        """Return the prior as the fix."""
        return MatchResult(prior.east, prior.north, 1.0, 0.0, 0.0, None)


class RandomMatcher:
    """Answer = uniform random pose in the search space, score 0."""

    name = 'random'

    def __init__(self, seed: int = 0):
        """Set the seed mixed into every frame's generator."""
        self.seed = seed

    def match(self, image, map_patch, prior: Prior, search: SearchSpace = DEFAULT_SEARCH):
        """Return a random pose inside the search space."""
        key = zlib.crc32(f'{prior.east:.3f},{prior.north:.3f}'.encode())
        rng = np.random.default_rng([self.seed, key])
        dx, dy = rng.uniform(-search.window_m, search.window_m, 2)
        scale = rng.uniform(*search.scale_range)
        rot = rng.uniform(*search.rot_range_deg)
        return MatchResult(prior.east + dx, prior.north + dy, scale, rot, 0.0, None)
