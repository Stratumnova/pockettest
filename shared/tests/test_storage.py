import os
from pathlib import Path

import pytest

from storage import prepare_data_root, resolve_data_root


def mode(path):
    return path.stat().st_mode & 0o777


def test_default_path(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    assert resolve_data_root(None, repo) == (
        Path.home() / "a25-data" / "shared-space"
    ).resolve()


def test_reject_repo_and_child(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for value in (repo, repo / "data"):
        with pytest.raises(ValueError):
            resolve_data_root(str(value), repo)


def test_reject_repo_parent(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError):
        resolve_data_root(str(tmp_path), repo)


def test_reject_symlink_into_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    link = tmp_path / "link"
    link.symlink_to(repo, target_is_directory=True)
    with pytest.raises(ValueError):
        resolve_data_root(str(link), repo)


@pytest.mark.parametrize("value", ["", "data", "./data"])
def test_reject_invalid_value(tmp_path, value):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError):
        resolve_data_root(value, repo)


def test_private_new_directories(tmp_path):
    root = tmp_path / "first" / "second"
    prepare_data_root(root)
    assert mode(root) == 0o700
    assert mode(root.parent) == 0o700


def test_existing_root_rechmod(tmp_path):
    root = tmp_path / "data"
    root.mkdir(mode=0o755)
    os.chmod(root, 0o755)
    prepare_data_root(root)
    assert mode(root) == 0o700


def test_existing_parent_unchanged(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    os.chmod(parent, 0o755)
    prepare_data_root(parent / "data")
    assert mode(parent) == 0o755
    assert mode(parent / "data") == 0o700


def test_regular_file_rejected_unchanged(tmp_path):
    root = tmp_path / "data"
    root.write_text("keep")
    os.chmod(root, 0o644)
    with pytest.raises(ValueError):
        prepare_data_root(root)
    assert mode(root) == 0o644
    assert root.read_text() == "keep"


def test_broken_symlink_rejected(tmp_path):
    root = tmp_path / "broken"
    root.symlink_to(tmp_path / "missing")
    with pytest.raises(ValueError):
        prepare_data_root(root)
    assert root.is_symlink()
