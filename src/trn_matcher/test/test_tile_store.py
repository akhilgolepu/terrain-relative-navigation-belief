"""Tests for tile_store.py on a synthetic map cut into overlapping chips (see conftest.py)."""
from conftest import CHIP, LAT_BOTTOM, LAT_TOP, LON_LEFT, LON_RIGHT, make_flight
from conftest import MAP_H, map_rgb, MAP_W
import numpy as np
import pytest
from trn_matcher.geo import LocalENU
from trn_matcher.tile_store import RegionMap, TileStore

JPEG_TOL = 6  # colour tolerance for JPEG compression


def test_georef_fit_recovers_map_corners(flight_dir):
    s = TileStore.from_flight_dir(flight_dir)
    g = s.georef
    assert g.lat0 == pytest.approx(LAT_TOP, abs=1e-12)
    assert g.dlat_drow * MAP_H == pytest.approx(LAT_BOTTOM - LAT_TOP, rel=1e-9)
    assert g.lon0 == pytest.approx(LON_LEFT, abs=1e-12)
    assert g.dlon_dcol * MAP_W == pytest.approx(LON_RIGHT - LON_LEFT, rel=1e-9)
    assert g.max_residual_deg < 1e-9
    assert (s.chip_h, s.chip_w, s.height_px, s.width_px) == (CHIP, CHIP, MAP_H, MAP_W)


def test_pixel_latlon_round_trip(flight_dir):
    g = TileStore.from_flight_dir(flight_dir).georef
    rows, cols = g.latlon_to_pixel(*g.pixel_to_latlon(123.4, 567.8))
    assert (float(rows), float(cols)) == pytest.approx((123.4, 567.8))


def test_read_window_matches_map_and_marks_uncovered(flight_dir):
    s = TileStore.from_flight_dir(flight_dir)
    win, ok = s.read_window(250, 350, 100, 120)
    rr, cc = np.mgrid[250:350, 350:470] + 0.5
    r, g = map_rgb(rr, cc)
    assert ok.all()
    assert np.abs(win[..., 0].astype(float) - r).max() <= JPEG_TOL
    assert np.abs(win[..., 1].astype(float) - g).max() <= JPEG_TOL
    win, ok = s.read_window(-10, MAP_W - 5, 20, 20)  # partly outside the map
    assert ok[10:, :5].all() and not ok[:10].any() and not ok[:, 5:].any()
    assert (win[~ok] == 0).all()


def region(flight_dir):
    s = TileStore.from_flight_dir(flight_dir)
    return RegionMap([s], LocalENU(30.005, 120.006)), s


def test_map_patch_is_north_up_and_georeferenced(flight_dir):
    reg, s = region(flight_dir)
    lat, lon = 30.004, 120.007
    e, n, _ = reg.frame.to_enu(lat, lon)
    p = reg.map_patch((float(e), float(n)), size_m=200.0, px=100)
    assert p.image.shape == (100, 100, 3) and p.valid.all() and p.m_per_px == pytest.approx(2.0)
    row, col = s.georef.latlon_to_pixel(lat, lon)
    r_exp, g_exp = map_rgb(row, col)
    centre = p.image[49:51, 49:51].astype(float).mean(axis=(0, 1))  # 4 pixels around centre
    assert centre[0] == pytest.approx(r_exp, abs=JPEG_TOL)
    assert centre[1] == pytest.approx(g_exp, abs=JPEG_TOL)
    # north-up: green (grows southward) increases down the rows, red (grows east) along columns
    assert p.image[-1, 50, 1] > p.image[0, 50, 1] and p.image[50, -1, 0] > p.image[50, 0, 0]
    # 200 m north-south span: green change over the patch equals the map's change over 200 m
    m_per_row = abs(s.georef.dlat_drow) * 111_000
    assert float(p.image[95, 50, 1]) - float(p.image[5, 50, 1]) == pytest.approx(
        180.0 / MAP_H * 180.0 / m_per_row, rel=0.1)


def test_map_patch_outside_map_is_invalid(flight_dir):
    reg, _ = region(flight_dir)
    p = reg.map_patch((5000.0, 5000.0), size_m=100.0, px=20)
    assert not p.valid.any()


def test_region_picks_map_that_covers_the_patch(tmp_path):
    a = TileStore.from_flight_dir(make_flight(tmp_path, '91'))
    b = TileStore.from_flight_dir(make_flight(tmp_path, '92', lat_top=30.020))  # 0.01 deg north
    reg = RegionMap([a, b], LocalENU(30.01, 120.006))
    e, n, _ = reg.frame.to_enu(30.016, 120.006)
    assert reg.map_patch((float(e), float(n)), 100.0, 20).source_map == '92'
    e, n, _ = reg.frame.to_enu(30.004, 120.006)
    assert reg.map_patch((float(e), float(n)), 100.0, 20).source_map == '91'


def test_chip_files_with_prefix_are_matched_by_row_col(tmp_path):
    # real UAV-VisLoc: CSV says '0_620.jpg', the file is 'satellite05_0_620.jpg'
    s = TileStore.from_flight_dir(make_flight(tmp_path, '91', chip_prefix='satellite91_'))
    assert s.chips[(100, 200)].path.name == 'satellite91_100_200.jpg'
    win, ok = s.read_window(0, 0, 10, 10)
    assert ok.all()


def test_missing_chip_file_is_reported(tmp_path):
    d = make_flight(tmp_path, '91')
    (d / 'satellite-tile' / '0_0.jpg').unlink()
    with pytest.raises(FileNotFoundError):
        TileStore.from_flight_dir(d)


def test_chip_ground_size_matches_georef(flight_dir):
    store = TileStore.from_flight_dir(flight_dir)
    g = store.georef
    lat_mid = g.lat0 + g.dlat_drow * store.height_px / 2
    ns = abs(g.dlat_drow) * 111_320.0 * store.chip_h
    ew = abs(g.dlon_dcol) * 111_320.0 * np.cos(np.radians(lat_mid)) * store.chip_h
    assert store.chip_ground_size_m() == pytest.approx((ns + ew) / 2)
    assert ns > 0 and ew > 0
