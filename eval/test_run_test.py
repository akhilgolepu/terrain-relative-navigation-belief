"""Refusal tests for eval/run_test.py (no flight 11 data is touched)."""
import hashlib
import json
import subprocess

import pytest

import run_test as rt


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.invalid")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "a.txt").write_text("frozen\n")
    (tmp_path / "docs").mkdir()
    manifest = {"files": {"a.txt": hashlib.sha256(b"frozen\n").hexdigest()}}
    (tmp_path / "docs/frozen_manifest.json").write_text(json.dumps(manifest))
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    _git(tmp_path, "tag", "pre-test")
    return tmp_path


def test_clean_tree_passes_and_dirty_tree_is_refused(repo):
    rt.check_clean(repo)
    (repo / "a.txt").write_text("changed\n")
    with pytest.raises(rt.Refused, match="uncommitted"):
        rt.check_clean(repo)


def test_untracked_files_do_not_block(repo):
    (repo / "scratch.txt").write_text("x")
    rt.check_clean(repo)


def test_hash_mismatch_is_refused(repo):
    m = rt.manifest_from_tag(repo)
    rt.check_hashes(repo, m)
    (repo / "a.txt").write_text("changed\n")
    with pytest.raises(rt.Refused, match="changed since pre-test"):
        rt.check_hashes(repo, m)


def test_manifest_is_read_from_the_tag_not_the_working_tree(repo):
    (repo / "docs/frozen_manifest.json").write_text(json.dumps({"files": {}}))   # edited manifest
    assert "a.txt" in rt.manifest_from_tag(repo)["files"]


def test_missing_tag_is_refused(repo):
    _git(repo, "tag", "-d", "pre-test")
    with pytest.raises(rt.Refused, match="pre-test"):
        rt.check_tag_ancestor(repo)
    with pytest.raises(rt.Refused):
        rt.manifest_from_tag(repo)


def test_second_run_is_refused_and_complete_run_cannot_resume(tmp_path):
    out = tmp_path / "res"
    rt.acquire_lock(out, resume=False, info={"time": "t0"})
    with pytest.raises(rt.Refused, match="second run is refused"):
        rt.acquire_lock(out, resume=False, info={"time": "t1"})
    state = rt.acquire_lock(out, resume=True, info={"time": "t2"})     # crash recovery is allowed
    assert state["resumes"] == [{"time": "t2"}]
    rt.finish_lock(out)
    with pytest.raises(rt.Refused, match="complete"):
        rt.acquire_lock(out, resume=True, info={"time": "t3"})
    with pytest.raises(rt.Refused):
        rt.acquire_lock(out, resume=False, info={"time": "t4"})


def test_resume_without_a_started_run_is_refused(tmp_path):
    with pytest.raises(rt.Refused, match="no run was started"):
        rt.acquire_lock(tmp_path / "res", resume=True, info={})
