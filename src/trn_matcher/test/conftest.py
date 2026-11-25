"""Synthetic UAV-VisLoc-style flight folders for the tile store and loader tests (no data)."""
import csv

import numpy as np
from PIL import Image
import pytest

MAP_H, MAP_W = 600, 800          # full map, pixels
CHIP, STEP = 200, 100            # chip size and stride (50 % overlap, as in UAV-VisLoc)
LAT_TOP, LAT_BOTTOM = 30.010, 30.000
LON_LEFT, LON_RIGHT = 120.000, 120.012


def map_rgb(rows, cols):
    """Colour of the synthetic map at continuous pixel positions: R grows east, G grows south."""
    r = 40.0 + 180.0 * np.asarray(cols) / MAP_W
    g = 40.0 + 180.0 * np.asarray(rows) / MAP_H
    return r, g


def make_flight(root, name, lat_top=LAT_TOP, lon_left=LON_LEFT, uav_rows=None,
                heading_cols=('Phi2',), chip_prefix=''):
    """Write <root>/<name>/ with satellite chips, both CSVs and small UAV images."""
    d = root / name
    (d / 'satellite-tile').mkdir(parents=True)
    (d / 'UAV-image').mkdir()
    rr, cc = np.mgrid[0:MAP_H, 0:MAP_W] + 0.5
    r, g = map_rgb(rr, cc)
    full = np.stack([r, g, np.full_like(r, 128.0)], -1).round().astype(np.uint8)
    dlat = (LAT_BOTTOM - LAT_TOP) / MAP_H
    dlon = (LON_RIGHT - LON_LEFT) / MAP_W
    with (d / f'{name}-satellite-tile-coordinates.csv').open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['patchname', 'latitude', 'longitude'])
        for row0 in range(0, MAP_H - CHIP + 1, STEP):
            for col0 in range(0, MAP_W - CHIP + 1, STEP):
                chip_name = f'{row0}_{col0}.jpg'
                Image.fromarray(full[row0:row0 + CHIP, col0:col0 + CHIP]).save(
                    d / 'satellite-tile' / (chip_prefix + chip_name), quality=98)
                w.writerow([chip_name, lat_top + dlat * (row0 + CHIP / 2),
                            lon_left + dlon * (col0 + CHIP / 2)])
    rows = uav_rows or [(lat_top - 0.005, lon_left + 0.006, 30.0),
                        (lat_top - 0.003, lon_left + 0.004, 120.0)]
    cols = ['filename', 'num', 'date', 'lat', 'lon', 'height', 'Omega', 'Kappa', 'Phi1', 'Phi2']
    with (d / f'{name}-UAV-coordinates.csv').open('w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for k, (lat, lon, heading) in enumerate(rows):
            fn = f'{name}_{k + 1:04d}.JPG'
            Image.fromarray(np.full((300, 400, 3), 90, np.uint8)).save(d / 'UAV-image' / fn)
            phi1 = heading if 'Phi1' in heading_cols else '-'
            phi2 = heading if 'Phi2' in heading_cols else '-'
            w.writerow([fn, k + 1, '-', lat, lon, 500.0, 1.0, 2.0, phi1, phi2])
    return d


@pytest.fixture
def flight_dir(tmp_path):
    """One synthetic flight '91' covering 30.000-30.010 N, 120.000-120.012 E."""
    return make_flight(tmp_path, '91')


@pytest.fixture
def splits_two_regions(tmp_path):
    """Two synthetic regions far apart, one flight each, and a splits dict using them."""
    make_flight(tmp_path, '91')
    make_flight(tmp_path, '92', lat_top=40.010, lon_left=100.000,
                uav_rows=[(40.005, 100.006, 0.0)])
    splits = {
        'regions': {
            'a': {'flights': ['91'], 'enu_origin': {'lat': 30.005, 'lon': 120.006}},
            'b': {'flights': ['92'], 'enu_origin': {'lat': 40.005, 'lon': 100.006}},
        },
        'splits': {'tune': ['a'], 'test': ['b']},
    }
    return tmp_path, splits
