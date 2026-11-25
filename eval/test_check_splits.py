"""Leakage assertion for the splits: the committed splits.json must pass, and the checker must catch leaks."""
import copy
import json
from pathlib import Path

import pytest

from check_splits import geographic_problems, structural_problems

SPLITS = json.loads((Path(__file__).parent / "splits.json").read_text())
DATA = Path.home() / "data/visloc/index"


def test_committed_splits_have_no_leakage():
    assert structural_problems(SPLITS) == []


def test_every_flight_in_exactly_one_split():
    seen = {}
    for split, regions in SPLITS["splits"].items():
        for r in regions:
            for f in SPLITS["regions"][r]["flights"]:
                assert f not in seen, f"flight {f} in {seen.get(f)} and {split}"
                seen[f] = split
    assert set(seen) == {f for info in SPLITS["regions"].values() for f in info["flights"]}


def test_flight_in_two_regions_is_caught():
    bad = copy.deepcopy(SPLITS)
    bad["regions"]["gansu"]["flights"].append("10")  # 10 is the tune region's flight
    problems = structural_problems(bad)
    assert any("flight 10 is in regions" in p for p in problems)
    assert any("appear in both" in p for p in problems)


def test_excluded_flight_in_a_split_is_caught():
    assert SPLITS["excluded_regions"]["jiangsu_wuxi"]["flights"] == ["18", "19", "20"]
    bad = copy.deepcopy(SPLITS)
    bad["regions"]["gansu"]["flights"].append("19")  # thermal flight sneaking into test
    assert any("excluded flights ['19'] appear in split test" in p for p in structural_problems(bad))


def test_region_in_two_splits_is_caught():
    bad = copy.deepcopy(SPLITS)
    bad["splits"]["test"].append("yunnan")
    assert any("region yunnan is in more than one split" in p for p in structural_problems(bad))


def test_unknown_and_unused_regions_are_caught():
    bad = copy.deepcopy(SPLITS)
    bad["splits"]["test"] = ["atlantis"]
    problems = structural_problems(bad)
    assert any("unknown region atlantis" in p for p in problems)
    assert any("region gansu is in no split" in p for p in problems)


@pytest.mark.skipif(not DATA.exists(), reason="UAV-VisLoc index not downloaded")
def test_regions_of_different_splits_are_far_apart():
    assert geographic_problems(SPLITS, DATA, min_gap_km=10.0) == []
