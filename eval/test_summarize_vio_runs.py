"""Tests for summarize_vio_runs.py helpers (system Python: needs only PyYAML)."""
import pytest

from summarize_vio_runs import distinct_rows, identity_groups, sequence_of, spread, summarise_scores


def test_sequence_of_strips_run_suffix():
    assert sequence_of("room1_run3") == "room1"
    assert sequence_of("room1") == "room1"


def test_spread_uses_sample_std():
    s = spread([1.0, 2.0, 3.0])
    assert s["mean"] == pytest.approx(2.0)
    assert s["std"] == pytest.approx(1.0)
    assert (s["min"], s["max"]) == (1.0, 3.0)
    assert spread([5.0])["std"] == 0.0


def test_summarise_groups_runs_by_sequence():
    base = {m: "0" for m in ["rpe_trans_rmse_1m", "rpe_trans_median_1m", "rpe_trans_rmse_10m", "rpe_trans_median_10m",
                             "se3_align_roll_deg", "se3_align_pitch_deg",
                             "se3_align_tilt_deg", "final_horiz_err_start_aligned_m",
                             "final_vert_err_start_aligned_m", "horiz_rmse_start_aligned_m",
                             "vert_rmse_start_aligned_m"]}
    rows = [{"sequence": "a_run1", "ate_rmse_m": "0.1", **base}, {"sequence": "a_run2", "ate_rmse_m": "0.3", **base},
            {"sequence": "b_run1", "ate_rmse_m": "1.0", **base}]
    out = {(r["sequence"], r["metric"]): r for r in summarise_scores(rows)}
    assert out[("a", "ate_rmse_m")]["n_runs"] == 2
    assert out[("a", "ate_rmse_m")]["mean"] == "0.2000"
    assert out[("b", "ate_rmse_m")]["n_runs"] == 1


def test_identity_groups_and_distinct_rows():
    hashes = {"a_run1": "h1", "a_run2": "h2", "a_run3": "h2", "b_run1": "h9", "b_run2": "h9"}
    ident = {i["run"]: i for i in identity_groups(hashes)}
    assert ident["a_run1"]["outcome"] == "a_A" and ident["a_run1"]["identical_to"] == ""
    assert ident["a_run2"]["outcome"] == ident["a_run3"]["outcome"] == "a_B"
    assert ident["a_run3"]["identical_to"] == "a_run2"
    assert ident["a_run1"]["n_distinct_in_sequence"] == 2 and ident["b_run1"]["n_distinct_in_sequence"] == 1
    rows = [{"sequence": r} for r in hashes]
    kept = [r["sequence"] for r in distinct_rows(rows, list(ident.values()))]
    assert kept == ["a_run1", "a_run2", "b_run1"]
