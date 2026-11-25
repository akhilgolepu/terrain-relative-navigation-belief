"""
Coordinate frames: WGS84 geodetic (lat, lon, h) and a local East-North-Up (ENU) frame in metres.

Geodetic input is WGS84 (degrees, metres above the ellipsoid). Each region gets its own local
ENU frame: a plane tangent to the WGS84 ellipsoid at a fixed origin, x = east, y = north,
z = up, in metres. Conversions go through Earth-centred Earth-fixed (ECEF) coordinates and are
exact (no flat-Earth approximation).
"""
from __future__ import annotations

import numpy as np

WGS84_A = 6378137.0                    # semi-major axis [m]
WGS84_F = 1.0 / 298.257223563          # flattening
WGS84_E2 = WGS84_F * (2.0 - WGS84_F)   # first eccentricity squared


def geodetic_to_ecef(lat_deg, lon_deg, h_m=0.0):
    """Convert WGS84 lat/lon [deg] and height [m] to ECEF x, y, z [m] (scalars or arrays)."""
    lat, lon = np.radians(lat_deg), np.radians(lon_deg)
    n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * np.sin(lat) ** 2)
    x = (n + h_m) * np.cos(lat) * np.cos(lon)
    y = (n + h_m) * np.cos(lat) * np.sin(lon)
    z = (n * (1.0 - WGS84_E2) + h_m) * np.sin(lat)
    return x, y, z


def ecef_to_geodetic(x, y, z):
    """Convert ECEF x, y, z [m] to WGS84 lat/lon [deg] and height [m] (fixed-point iteration)."""
    x, y, z = np.asarray(x, float), np.asarray(y, float), np.asarray(z, float)
    lon = np.arctan2(y, x)
    p = np.hypot(x, y)
    lat = np.arctan2(z, p * (1.0 - WGS84_E2))
    for _ in range(5):  # converges to well below a millimetre for terrestrial heights
        n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * np.sin(lat) ** 2)
        h = p / np.cos(lat) - n
        lat = np.arctan2(z, p * (1.0 - WGS84_E2 * n / (n + h)))
    n = WGS84_A / np.sqrt(1.0 - WGS84_E2 * np.sin(lat) ** 2)
    h = p / np.cos(lat) - n
    return np.degrees(lat), np.degrees(lon), h


class LocalENU:
    """Local East-North-Up frame tangent to WGS84 at (origin_lat, origin_lon, origin_h)."""

    def __init__(self, origin_lat: float, origin_lon: float, origin_h: float = 0.0):
        """Fix the origin and the rotation from ECEF to ENU."""
        self.origin = (float(origin_lat), float(origin_lon), float(origin_h))
        self._o = np.array(geodetic_to_ecef(*self.origin))
        lat, lon = np.radians(origin_lat), np.radians(origin_lon)
        sl, cl, so, co = np.sin(lat), np.cos(lat), np.sin(lon), np.cos(lon)
        # rows: east, north, up unit vectors expressed in ECEF
        self._r = np.array([[-so, co, 0.0],
                            [-sl * co, -sl * so, cl],
                            [cl * co, cl * so, sl]])

    def to_enu(self, lat_deg, lon_deg, h_m=0.0):
        """Convert WGS84 lat/lon [deg], h [m] to east, north, up [m] in this frame."""
        x, y, z = geodetic_to_ecef(lat_deg, lon_deg, h_m)
        d = np.stack(np.broadcast_arrays(x, y, z), axis=-1) - self._o
        enu = d @ self._r.T
        return enu[..., 0], enu[..., 1], enu[..., 2]

    def to_geodetic(self, e_m, n_m, u_m=0.0):
        """Convert east, north, up [m] in this frame to WGS84 lat/lon [deg], h [m]."""
        enu = np.stack(np.broadcast_arrays(np.asarray(e_m, float), np.asarray(n_m, float),
                                           np.asarray(u_m, float)), axis=-1)
        xyz = enu @ self._r + self._o
        return ecef_to_geodetic(xyz[..., 0], xyz[..., 1], xyz[..., 2])
