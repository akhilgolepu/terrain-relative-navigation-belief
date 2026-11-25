"""
Prepare one dataset frame for a matcher, identically for the eval harness and the ROS node.

For frame i: the aerial image, its label (true position), the loader's seeded noisy prior,
the nominal footprint (chip ground size of the frame's flight) and a north-up map patch
centred on the prior, just large enough to hold the image anywhere in the search space.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .interface import Prior, SearchSpace
from .loader import VisLocDataset
from .tile_store import MapPatch


@dataclass
class Frame:
    """Everything a matcher call needs, plus the label for scoring."""

    region: str
    flight: str
    filename: str
    image: np.ndarray
    patch: MapPatch
    prior: Prior
    true_en: np.ndarray


def footprints(ds: VisLocDataset) -> dict[tuple[str, str], float]:
    """Return the nominal footprint [m] per (region, flight)."""
    return {(reg, st.name): st.chip_ground_size_m()
            for reg, rm in ds.regions.items() for st in rm.stores}


def prepare_frame(ds: VisLocDataset, i: int, search: SearchSpace, prior_sigma_m: float,
                  map_m_per_px: float, foot: dict[tuple[str, str], float]) -> Frame:
    """Return frame i ready for match(image, patch, prior, search)."""
    region, rec = ds.records[i]
    true, prior_en = ds.true_position(i), ds.prior_position(i)
    f = foot[(region, rec.flight)]
    prior = Prior(float(prior_en[0]), float(prior_en[1]), prior_sigma_m, f)
    size = search.patch_size_m(f)
    px = int(math.ceil(size / map_m_per_px))
    patch = ds.regions[region].map_patch(prior_en, size, px)
    return Frame(region, rec.flight, rec.filename, ds.load_image(i), patch, prior, true)
