"""Private storage path and permission helpers for A25 Shared Space."""
import os
from pathlib import Path

DEFAULT_DATA_ROOT = "~/a25-data/shared-space"

def resolve_data_root(env_value=None, repo_root=None):
    repo = Path(
        repo_root if repo_root is not None
        else Path(__file__).resolve().parents[1]
    ).expanduser().resolve()

    value = DEFAULT_DATA_ROOT if env_value is None else env_value

    if not str(value).strip():
        raise ValueError("A25_SHARED_DATA cannot be empty")

    candidate = Path(value).expanduser()

    if not candidate.is_absolute():
        raise ValueError("A25_SHARED_DATA must be an absolute path")

    root = candidate.resolve()

    if root == repo or root.is_relative_to(repo):
        raise ValueError("Shared data cannot live inside the repository")

    if repo.is_relative_to(root):
        raise ValueError("Shared data cannot contain the repository")

    return root

def prepare_data_root(root):
    root = Path(root)

    if not root.is_absolute():
        raise ValueError("Data root must be absolute")

    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Data root must be a real directory")

    missing = []
    current = root

    while not current.exists():
        missing.append(current)
        current = current.parent

    for directory in reversed(missing):
        directory.mkdir(mode=0o700)
        os.chmod(directory, 0o700)

    os.chmod(root, 0o700)
    return root
