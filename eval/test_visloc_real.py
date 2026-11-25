"""Checks of the loader on the downloaded UAV-VisLoc flights (skipped when the data is not present)."""
import json
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/trn_matcher"))
from trn_matcher.loader import LoaderConfig, VisLocDataset  # noqa: E402

ROOT = Path.home() / "data/visloc/flights"
SPLITS = json.loads((Path(__file__).parent / "splits.json").read_text())
NEEDED = [f for r in SPLITS["regions"].values() for f in r["flights"]]
HAS_COORDS = all("enu_origin" in r for r in SPLITS["regions"].values())   # public copy: stripped
pytestmark = pytest.mark.skipif(not HAS_COORDS or not all((ROOT / f).is_dir() for f in NEEDED),
                                reason="UAV-VisLoc flights not downloaded, or splits.json has no coordinates")


@pytest.fixture(scope="module", params=list(SPLITS["splits"]))
def dataset(request):
    return VisLocDataset(ROOT, SPLITS, request.param, LoaderConfig(patch_px=128, image_px=128))


def test_georeference_fits_chip_centres(dataset):
    for reg in dataset.regions.values():
        for store in reg.stores:
            assert store.georef.max_residual_deg < 1e-8, store.name


def test_every_uav_position_is_inside_its_region_map(dataset):
    outside = []
    for i, (region, rec) in enumerate(dataset.records):
        reg = dataset.regions[region]
        lat, lon = np.array([rec.lat]), np.array([rec.lon])
        if not any(s.coverage_fraction(*s.georef.latlon_to_pixel(lat, lon)) == 1.0 for s in reg.stores):
            outside.append(rec.filename)
    assert outside == [], f"{len(outside)} images outside the map, e.g. {outside[:3]}"


def test_one_sample_per_flight_loads(dataset):
    seen = set()
    for i, (_, rec) in enumerate(dataset.records):
        if rec.flight in seen:
            continue
        seen.add(rec.flight)
        image, true, patch, prior = dataset[i].as_tuple()
        assert image.ndim == 3 and max(image.shape[:2]) == 128
        assert patch.image.shape == (128, 128, 3)
        assert np.linalg.norm(prior - true) < 6 * dataset.config.prior_sigma_m
        assert np.abs(true).max() < 20_000  # within 20 km of the region's ENU origin
