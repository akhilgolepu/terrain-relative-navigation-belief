"""Test the metre conversion in overlay_offsets.py compute on a hand-made landmark file."""
import csv

import pytest

import overlay_offsets


def test_offsets_from_landmarks(tmp_path):
    (tmp_path / "overlay_index.csv").write_text("file,flight,footprint_m\noverlays/a.png,10,200\n")
    with (tmp_path / "overlay_landmarks.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["overlay", "landmark", "uav_x", "uav_y", "map_x", "map_y"])
        w.writerow(["a.png", "junction", 200, 200, 180, 220])   # map 20 px left, 20 px down
        w.writerow(["a.png", "hut", 100, 100, 80, 120])
    assert overlay_offsets.compute(tmp_path) == 0
    rows = list(csv.DictReader((tmp_path / "overlay_offsets.csv").open()))
    ov = next(r for r in rows if r["level"] == "overlay")
    # 200 m / 400 px = 0.5 m/px: 20 px left = 10 m west, 20 px down = 10 m south
    assert float(ov["east_m"]) == pytest.approx(-10.0) and float(ov["north_m"]) == pytest.approx(-10.0)
    assert float(ov["offset_m"]) == pytest.approx(14.1, abs=0.05)
    fl = next(r for r in rows if r["level"] == "flight")
    assert fl["flight"] == "10" and fl["n"] == "1"


def test_overlay_without_landmark_is_listed_not_averaged(tmp_path):
    (tmp_path / "overlay_index.csv").write_text(
        "file,flight,footprint_m\noverlays/a.png,10,200\noverlays/b.png,10,200\n")
    with (tmp_path / "overlay_landmarks.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["overlay", "landmark", "uav_x", "uav_y", "map_x", "map_y", "quality", "note"])
        w.writerow(["a.png", "junction", 200, 200, 180, 220, "good", ""])
        w.writerow(["b.png", "", "", "", "", "", "", "map from another season"])
    assert overlay_offsets.compute(tmp_path) == 0
    rows = list(csv.DictReader((tmp_path / "overlay_offsets.csv").open()))
    b = next(r for r in rows if r["overlay"] == "b.png")
    assert b["landmark"] == "none found" and b["n"] == "0" and b["note"] == "map from another season"
    fl = next(r for r in rows if r["level"] == "flight")
    assert fl["n"] == "1" and float(fl["east_m"]) == pytest.approx(-10.0)
