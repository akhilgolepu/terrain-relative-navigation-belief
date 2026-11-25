"""
Georeferenced map built from UAV-VisLoc satellite chips, and north-up map patches in metres.

UAV-VisLoc cut each flight's satellite map (a plain latitude/longitude grid from Google Earth
Pro) into square JPG chips with 50 % overlap. A chip's file name holds its top-left pixel in
the full map, "<row>_<col>.jpg" (optionally with a prefix), and the coordinate CSV gives the
latitude/longitude of the chip's CENTRE, computed by the dataset authors as a linear function
of the pixel position (satellite_tile_generation.py in their processing scripts):
    lat = lat_top + (lat_bottom - lat_top) * row / map_height
    lon = lon_left + (lon_right - lon_left) * col / map_width
with row/col continuous pixel coordinates whose integer values are pixel EDGES (pixel i spans
[i, i+1)). We fit that linear relation to the chip centres (exact up to CSV rounding) instead
of copying the authors' numbers.
"""
from __future__ import annotations

from collections import OrderedDict
import csv
from dataclasses import dataclass
from pathlib import Path
import re

import numpy as np
from PIL import Image

from .geo import LocalENU

CHIP_NAME = re.compile(r'(\d+)_(\d+)\.jpe?g$', re.IGNORECASE)


@dataclass(frozen=True)
class Georef:
    """Linear pixel <-> lat/lon map: lat = lat0 + dlat_drow*row, lon = lon0 + dlon_dcol*col."""

    lat0: float
    dlat_drow: float
    lon0: float
    dlon_dcol: float
    max_residual_deg: float  # largest fit residual over the chip centres (~1e-9: CSV rounding)

    def pixel_to_latlon(self, row, col):
        """Convert continuous pixel coordinates (edges at integers) to lat, lon [deg]."""
        return (self.lat0 + self.dlat_drow * np.asarray(row),
                self.lon0 + self.dlon_dcol * np.asarray(col))

    def latlon_to_pixel(self, lat, lon):
        """Convert lat, lon [deg] to continuous pixel coordinates (row, col)."""
        return ((np.asarray(lat) - self.lat0) / self.dlat_drow,
                (np.asarray(lon) - self.lon0) / self.dlon_dcol)


@dataclass(frozen=True)
class Chip:
    """One satellite chip: file, top-left pixel (row0, col0) in the map, centre lat/lon."""

    path: Path
    row0: int
    col0: int
    lat: float
    lon: float


def fit_georef(chips: list[Chip], chip_h: int, chip_w: int) -> Georef:
    """Fit lat against chip-centre row and lon against chip-centre column (least squares)."""
    rows = np.array([c.row0 + chip_h / 2.0 for c in chips])
    cols = np.array([c.col0 + chip_w / 2.0 for c in chips])
    lats = np.array([c.lat for c in chips])
    lons = np.array([c.lon for c in chips])
    if np.unique(rows).size < 2 or np.unique(cols).size < 2:
        raise ValueError('need chips in at least two rows and two columns to georeference a map')
    b_lat, a_lat = np.polyfit(rows, lats, 1)
    b_lon, a_lon = np.polyfit(cols, lons, 1)
    res = max(np.abs(a_lat + b_lat * rows - lats).max(),
              np.abs(a_lon + b_lon * cols - lons).max())
    return Georef(float(a_lat), float(b_lat), float(a_lon), float(b_lon), float(res))


def read_chip_csv(csv_path: Path, chip_dir: Path) -> list[Chip]:
    """
    Read the chips listed in an XX-satellite-tile-coordinates.csv (patchname, lat, lon).

    CSV names and file names can differ by a prefix (CSV '0_620.jpg', file
    'satellite05_0_620.jpg'), so chips are matched to files by their (row, col) numbers.
    """
    files = {}
    for p in chip_dir.iterdir():
        m = CHIP_NAME.search(p.name)
        if m:
            files[(int(m.group(1)), int(m.group(2)))] = p
    chips = []
    with csv_path.open(encoding='utf-8-sig') as fh:
        for row in csv.DictReader(fh):
            m = CHIP_NAME.search(row['patchname'])
            if not m:
                raise ValueError(f'unexpected chip name {row["patchname"]!r} in {csv_path}')
            key = (int(m.group(1)), int(m.group(2)))
            if key not in files:
                raise FileNotFoundError(f'no chip file for {row["patchname"]} in {chip_dir}')
            chips.append(Chip(files[key], key[0], key[1],
                              float(row['latitude']), float(row['longitude'])))
    return chips


class TileStore:
    """One georeferenced map, assembled on demand from its overlapping chips."""

    def __init__(self, name: str, chips: list[Chip], chip_h: int, chip_w: int,
                 cache_chips: int = 64):
        """Index the chips by top-left pixel and fit the georeference."""
        self.name, self.chip_h, self.chip_w = name, chip_h, chip_w
        self.chips = {(c.row0, c.col0): c for c in chips}
        self.georef = fit_georef(chips, chip_h, chip_w)
        # extent actually covered by chips (the map's right/bottom margin may have none)
        self.height_px = max(r for r, _ in self.chips) + chip_h
        self.width_px = max(c for _, c in self.chips) + chip_w
        self._cache: OrderedDict[tuple[int, int], np.ndarray] = OrderedDict()
        self._cache_size = cache_chips

    def chip_ground_size_m(self) -> float:
        """
        Return the ground side length of one chip [m]: the nominal aerial image footprint.

        The dataset authors sized each flight's chips to the aerial image footprint. Map pixels
        are not square in metres, so this is the mean of the chip's north-south and east-west
        sides (spherical approximation, 111,320 m per degree), at the map's middle latitude.
        """
        lat_mid = self.georef.lat0 + self.georef.dlat_drow * self.height_px / 2
        m_lat = abs(self.georef.dlat_drow) * 111_320.0
        m_lon = abs(self.georef.dlon_dcol) * 111_320.0 * np.cos(np.radians(lat_mid))
        return float(self.chip_h * (m_lat + m_lon) / 2)

    @classmethod
    def from_flight_dir(cls, flight_dir: Path, cache_chips: int = 64) -> TileStore:
        """Build the store for one flight folder (satellite-tile/ and its coordinate CSV)."""
        flight_dir = Path(flight_dir)
        csv_path = next(flight_dir.glob('*-satellite-tile-coordinates.csv'))
        chips = read_chip_csv(csv_path, flight_dir / 'satellite-tile')
        with Image.open(chips[0].path) as im:
            w, h = im.size
        return cls(flight_dir.name, chips, h, w, cache_chips)

    def _chip_pixels(self, key: tuple[int, int]) -> np.ndarray:
        """Decode one chip to RGB pixels (least-recently-used cache)."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        with Image.open(self.chips[key].path) as im:
            arr = np.asarray(im.convert('RGB'))
        if arr.shape[:2] != (self.chip_h, self.chip_w):
            raise ValueError(f'chip {self.chips[key].path} is {arr.shape[:2]}, '
                             f'expected {(self.chip_h, self.chip_w)}')
        self._cache[key] = arr
        if len(self._cache) > self._cache_size:
            self._cache.popitem(last=False)
        return arr

    def read_window(self, row0: int, col0: int, height: int,
                    width: int) -> tuple[np.ndarray, np.ndarray]:
        """Return map pixels [row0, row0+height) x [col0, col0+width) and a chip-coverage mask."""
        out = np.zeros((height, width, 3), np.uint8)
        valid = np.zeros((height, width), bool)
        for (r, c) in self.chips:
            r0, r1 = max(r, row0), min(r + self.chip_h, row0 + height)
            c0, c1 = max(c, col0), min(c + self.chip_w, col0 + width)
            if r0 >= r1 or c0 >= c1:
                continue
            px = self._chip_pixels((r, c))
            out[r0 - row0:r1 - row0, c0 - col0:c1 - col0] = px[r0 - r:r1 - r, c0 - c:c1 - c]
            valid[r0 - row0:r1 - row0, c0 - col0:c1 - col0] = True
        return out, valid

    def coverage_fraction(self, rows: np.ndarray, cols: np.ndarray) -> float:
        """Return the fraction of pixel positions inside the chip-covered extent."""
        inside = (rows >= 0) & (rows < self.height_px) & (cols >= 0) & (cols < self.width_px)
        return float(np.mean(inside))

    def sample(self, rows: np.ndarray, cols: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Sample RGB bilinearly at continuous pixel positions (any shape); also a valid mask."""
        rc, cc = rows - 0.5, cols - 0.5  # pixel centres sit at i + 0.5
        r_lo, c_lo = int(np.floor(rc.min())), int(np.floor(cc.min()))
        r_hi, c_hi = int(np.floor(rc.max())) + 2, int(np.floor(cc.max())) + 2
        win, ok = self.read_window(r_lo, c_lo, r_hi - r_lo, c_hi - c_lo)
        r0 = np.floor(rc).astype(int) - r_lo
        c0 = np.floor(cc).astype(int) - c_lo
        fr, fc = (rc - np.floor(rc))[..., None], (cc - np.floor(cc))[..., None]
        w = win.astype(np.float32)
        val = ((1 - fr) * (1 - fc) * w[r0, c0] + (1 - fr) * fc * w[r0, c0 + 1]
               + fr * (1 - fc) * w[r0 + 1, c0] + fr * fc * w[r0 + 1, c0 + 1])
        valid = ok[r0, c0] & ok[r0, c0 + 1] & ok[r0 + 1, c0] & ok[r0 + 1, c0 + 1]
        return np.clip(np.rint(val), 0, 255).astype(np.uint8), valid


@dataclass
class MapPatch:
    """North-up square map patch: image row 0 is north, column 0 is west, size_m on a side."""

    image: np.ndarray        # (px, px, 3) uint8 RGB
    valid: np.ndarray        # (px, px) bool, False where no map imagery exists
    center_en: np.ndarray    # (2,) patch centre, east/north [m] in the region's ENU frame
    size_m: float
    m_per_px: float
    source_map: str          # which flight's map it came from


class RegionMap:
    """All maps of one region in one ENU frame; map_patch() uses the map covering it best."""

    def __init__(self, stores: list[TileStore], frame: LocalENU):
        """Group tile stores that share a region and its ENU frame."""
        self.stores, self.frame = stores, frame

    def _pixel_grid(self, store: TileStore, center_en, size_m: float, px: int):
        """Return map pixel positions of the patch's pixel centres (row 0 = north)."""
        m_per_px = size_m / px
        offs = (np.arange(px) + 0.5 - px / 2.0) * m_per_px
        east = center_en[0] + offs[None, :]
        north = center_en[1] - offs[:, None]
        lat, lon, _ = self.frame.to_geodetic(*np.broadcast_arrays(east, north))
        return store.georef.latlon_to_pixel(lat, lon)

    def map_patch(self, position_en, size_m: float, px: int = 512) -> MapPatch:
        """Return a north-up size_m x size_m patch (px x px) centred on position_en (E, N [m])."""
        center = np.asarray(position_en, float)[:2]
        best, best_cov, best_grid = None, -1.0, None
        for store in self.stores:
            rows, cols = self._pixel_grid(store, center, size_m, px)
            cov = store.coverage_fraction(rows, cols)
            if cov > best_cov:
                best, best_cov, best_grid = store, cov, (rows, cols)
        image, valid = best.sample(*best_grid)
        return MapPatch(image, valid, center, float(size_m), size_m / px, best.name)
