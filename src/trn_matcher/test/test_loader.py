"""Tests for loader.py on synthetic flights (see conftest.py)."""
from conftest import make_flight
import numpy as np
import pytest
from trn_matcher.loader import LoaderConfig, read_uav_records, VisLocDataset


def test_heading_column_prefers_phi2_then_phi1(tmp_path):
    assert read_uav_records(make_flight(tmp_path, '91'))[0].heading_source == 'Phi2'
    recs = read_uav_records(make_flight(tmp_path, '92', heading_cols=('Phi1',)))
    assert recs[0].heading_source == 'Phi1' and recs[1].heading_deg == pytest.approx(120.0)
    with pytest.raises(ValueError):
        read_uav_records(make_flight(tmp_path, '93', heading_cols=()))


def test_sample_contents_and_frames(splits_two_regions):
    root, splits = splits_two_regions
    cfg = LoaderConfig(prior_sigma_m=20.0, patch_size_m=300.0, patch_px=64, image_px=100)
    ds = VisLocDataset(root, splits, 'tune', cfg)
    assert len(ds) == 2
    s = ds[0]
    image, true, patch, prior = s.as_tuple()
    assert image.shape == (75, 100, 3) and image.dtype == np.uint8  # 300x400 -> 100 long side
    e, n, _ = ds.regions['a'].frame.to_enu(30.005, 120.006)
    assert true == pytest.approx([float(e), float(n)], abs=1e-6)  # first image: at ENU origin
    assert patch.center_en == pytest.approx(prior)  # patch around the prior by default
    assert patch.image.shape == (64, 64, 3) and patch.valid.all()
    assert s.meta['prior_error_m'] == pytest.approx(float(np.linalg.norm(prior - true)))
    assert s.region == 'a' and s.record.flight == '91'


def test_patch_center_true_option(splits_two_regions):
    root, splits = splits_two_regions
    ds = VisLocDataset(root, splits, 'tune', LoaderConfig(patch_center='true', patch_px=16))
    s = ds[1]
    assert s.map_patch.center_en == pytest.approx(s.true_position)
    with pytest.raises(ValueError):
        VisLocDataset(root, splits, 'tune', LoaderConfig(patch_center='middle'))


def test_prior_is_reproducible_and_seeded(splits_two_regions):
    root, splits = splits_two_regions
    a = VisLocDataset(root, splits, 'tune', LoaderConfig(seed=1))
    b = VisLocDataset(root, splits, 'tune', LoaderConfig(seed=1))
    c = VisLocDataset(root, splits, 'tune', LoaderConfig(seed=2))
    assert a.prior_position(0) == pytest.approx(b.prior_position(0))
    assert not np.allclose(a.prior_position(0), c.prior_position(0))
    err0 = a.prior_position(0) - a.true_position(0)
    assert not np.allclose(err0, a.prior_position(1) - a.true_position(1))


def test_prior_error_has_configured_spread(tmp_path):
    rows = [(30.009 - 0.00002 * k, 120.001 + 0.00002 * k, 0.0) for k in range(400)]
    make_flight(tmp_path, '91', uav_rows=rows)
    splits = {'regions': {'a': {'flights': ['91'], 'enu_origin': {'lat': 30.005, 'lon': 120.006}}},
              'splits': {'tune': ['a']}}
    ds = VisLocDataset(tmp_path, splits, 'tune', LoaderConfig(prior_sigma_m=50.0))
    err = np.array([ds.prior_position(i) - ds.true_position(i) for i in range(len(ds))])
    assert err.mean(axis=0) == pytest.approx([0.0, 0.0], abs=8.0)  # 3 std errors of the mean
    assert err.std(axis=0) == pytest.approx([50.0, 50.0], rel=0.12)


def test_split_only_loads_its_regions(splits_two_regions):
    root, splits = splits_two_regions
    ds = VisLocDataset(root, splits, 'test')
    assert set(ds.regions) == {'b'} and {r.flight for _, r in ds.records} == {'92'}


def test_image_names_matched_ignoring_case_and_missing_reported(tmp_path):
    d = make_flight(tmp_path, '91')
    jpg = d / 'UAV-image' / '91_0001.JPG'
    jpg.rename(jpg.with_name('91_0001.jpg'))       # real data: CSV '.JPG', file '.jpg'
    assert read_uav_records(d)[0].path.name == '91_0001.jpg'
    (d / 'UAV-image' / '91_0002.JPG').unlink()
    with pytest.raises(FileNotFoundError):
        read_uav_records(d)
