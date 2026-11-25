"""Tests for geo.py: WGS84 <-> local ENU."""
import numpy as np
import pytest

from trn_matcher.geo import ecef_to_geodetic, geodetic_to_ecef, LocalENU, WGS84_A, WGS84_E2


def test_origin_is_zero():
    f = LocalENU(38.83, 101.05)
    e, n, u = f.to_enu(38.83, 101.05)
    assert (float(e), float(n), float(u)) == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)


def test_round_trip_below_a_millimetre():
    f = LocalENU(24.66, 102.35)
    lat = 24.66 + np.linspace(-0.05, 0.05, 11)
    lon = 102.35 + np.linspace(-0.05, 0.05, 11)
    e, n, u = f.to_enu(lat, lon, 2300.0)
    lat2, lon2, h2 = f.to_geodetic(e, n, u)
    assert np.abs(lat2 - lat).max() < 1e-9 and np.abs(lon2 - lon).max() < 1e-9
    assert np.abs(h2 - 2300.0).max() < 1e-3


def test_small_offsets_match_radii_of_curvature():
    lat0 = 30.0
    f = LocalENU(lat0, 120.0)
    s = np.sin(np.radians(lat0)) ** 2
    meridian = WGS84_A * (1 - WGS84_E2) / (1 - WGS84_E2 * s) ** 1.5   # metres per radian north
    prime = WGS84_A / np.sqrt(1 - WGS84_E2 * s)                       # m per rad east / cos(lat)
    e, n, _ = f.to_enu(lat0 + 1e-4, 120.0)
    assert float(n) == pytest.approx(meridian * np.radians(1e-4), rel=1e-6)
    assert abs(float(e)) < 1e-6
    e, n, _ = f.to_enu(lat0, 120.0 + 1e-4)
    assert float(e) == pytest.approx(prime * np.cos(np.radians(lat0)) * np.radians(1e-4), rel=1e-6)


def test_ecef_round_trip():
    x, y, z = geodetic_to_ecef(38.83, 101.05, 1500.0)
    lat, lon, h = ecef_to_geodetic(x, y, z)
    assert (float(lat), float(lon), float(h)) == pytest.approx((38.83, 101.05, 1500.0), abs=1e-6)
