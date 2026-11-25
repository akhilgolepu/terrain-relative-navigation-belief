"""
UAV-VisLoc loader: aerial image, true position, map patch and noisy prior for one split.

Frames and units: positions are (east, north) in metres in the region's local ENU frame (see
geo.LocalENU; origin from splits.json). Heading is degrees clockwise from north. Heights are
the dataset's `height` column in metres, as given (whether above sea level or above ground is
not documented; not used for positions).
The prior is the true position plus a 2-D Gaussian error (prior_sigma_m per axis), drawn from a
generator seeded by (seed, flight, file name), so the same image always gets the same prior for
a given seed. The map patch is centred on the PRIOR by default (what a matcher would see);
patch_center='true' is for overlays and debugging.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
import json
from pathlib import Path
import zlib

import numpy as np
from PIL import Image

from .geo import LocalENU
from .tile_store import MapPatch, RegionMap, TileStore

# heading = the first of these columns that is numeric in every row of a flight
HEADING_COLUMNS = ('Phi2', 'Phi1')


@dataclass(frozen=True)
class UavRecord:
    """One aerial image and its metadata row."""

    flight: str
    filename: str
    path: Path
    lat: float
    lon: float
    height_m: float
    heading_deg: float
    heading_source: str


def _num(value: str | None) -> float | None:
    """Parse a float, or return None for '-', '' or missing."""
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def read_uav_records(flight_dir: Path) -> list[UavRecord]:
    """
    Read XX-UAV-coordinates.csv: lat, lon, height and heading (see HEADING_COLUMNS).

    Image files are matched to CSV names ignoring case (CSV '18_0001.JPG', file '18_0001.jpg').
    """
    flight_dir = Path(flight_dir)
    image_dir = flight_dir / 'UAV-image'
    files = {p.name.lower(): p for p in image_dir.iterdir()} if image_dir.is_dir() else {}
    csv_path = next(flight_dir.glob('*-UAV-coordinates.csv'))
    with csv_path.open(encoding='utf-8-sig') as fh:
        rows = [{k.strip(): v for k, v in r.items() if k} for r in csv.DictReader(fh)]
    source = next((c for c in HEADING_COLUMNS
                   if rows and all(_num(r.get(c)) is not None for r in rows)), None)
    if source is None:
        cols = ', '.join(HEADING_COLUMNS)
        raise ValueError(f'no complete heading column ({cols}) in {csv_path}')
    missing = [r['filename'] for r in rows if r['filename'].lower() not in files]
    if missing:
        raise FileNotFoundError(f'{len(missing)} UAV images listed in {csv_path} not found in '
                                f'{image_dir}, e.g. {missing[0]}')
    return [UavRecord(flight_dir.name, r['filename'], files[r['filename'].lower()],
                      float(r['lat']), float(r['lon']), float(r['height']),
                      float(r[source]) % 360.0, source) for r in rows]


@dataclass
class LoaderConfig:
    """Loader settings. Distances in metres."""

    prior_sigma_m: float = 50.0     # standard deviation of the prior error, per axis (E, N)
    patch_size_m: float = 600.0     # map patch side length
    patch_px: int = 512             # map patch resolution
    image_px: int | None = 512      # resize the aerial image to this long side (None: keep)
    seed: int = 0
    patch_center: str = 'prior'     # 'prior' or 'true'


@dataclass
class Sample:
    """One loader item; as_tuple() gives (image, true_position, map_patch, prior_position)."""

    image: np.ndarray               # (H, W, 3) uint8 RGB aerial image
    true_position: np.ndarray       # (2,) east, north [m]
    map_patch: MapPatch
    prior_position: np.ndarray      # (2,) east, north [m]
    record: UavRecord
    region: str
    meta: dict = field(default_factory=dict)

    def as_tuple(self):
        """Return (image, true_position, map_patch, prior_position)."""
        return self.image, self.true_position, self.map_patch, self.prior_position


def load_splits(path: Path) -> dict:
    """Read splits.json (regions with flights and ENU origins; regions of each split)."""
    return json.loads(Path(path).read_text())


class VisLocDataset:
    """Samples of every flight in the regions of one split."""

    def __init__(self, root: Path, splits: dict, split: str, config: LoaderConfig | None = None):
        """Index the split's flights; root holds the extracted flight folders."""
        self.root, self.config = Path(root), config or LoaderConfig()
        if self.config.patch_center not in ('prior', 'true'):
            raise ValueError("patch_center must be 'prior' or 'true'")
        self.regions: dict[str, RegionMap] = {}
        self.records: list[tuple[str, UavRecord]] = []
        for region in splits['splits'][split]:
            info = splits['regions'][region]
            frame = LocalENU(info['enu_origin']['lat'], info['enu_origin']['lon'])
            stores = [TileStore.from_flight_dir(self.root / f) for f in info['flights']]
            self.regions[region] = RegionMap(stores, frame)
            for f in info['flights']:
                self.records += [(region, r) for r in read_uav_records(self.root / f)]

    def __len__(self) -> int:
        """Return the number of aerial images in the split."""
        return len(self.records)

    def true_position(self, i: int) -> np.ndarray:
        """Return east, north [m] of image i in its region's frame."""
        region, r = self.records[i]
        e, n, _ = self.regions[region].frame.to_enu(r.lat, r.lon)
        return np.array([float(e), float(n)])

    def prior_position(self, i: int) -> np.ndarray:
        """Return the true position plus a reproducible Gaussian error (prior_sigma_m per axis)."""
        _, r = self.records[i]
        key = zlib.crc32(f'{r.flight}/{r.filename}'.encode())
        rng = np.random.default_rng([self.config.seed, key])
        return self.true_position(i) + rng.normal(0.0, self.config.prior_sigma_m, 2)

    def load_image(self, i: int) -> np.ndarray:
        """Return aerial image i as RGB uint8, resized to image_px on its long side if set."""
        _, r = self.records[i]
        with Image.open(r.path) as im:
            im = im.convert('RGB')
            if self.config.image_px:
                s = self.config.image_px / max(im.size)
                size = (max(1, round(im.width * s)), max(1, round(im.height * s)))
                im = im.resize(size, Image.BILINEAR)
            return np.asarray(im)

    def __getitem__(self, i: int) -> Sample:
        """Return image i, its true position, the map patch (around the prior) and the prior."""
        region, r = self.records[i]
        true, prior = self.true_position(i), self.prior_position(i)
        center = prior if self.config.patch_center == 'prior' else true
        cfg = self.config
        patch = self.regions[region].map_patch(center, cfg.patch_size_m, cfg.patch_px)
        return Sample(self.load_image(i), true, patch, prior, r, region,
                      {'prior_error_m': float(np.linalg.norm(prior - true))})
