"""Generic JSON storage with fcntl locking and atomic writes.

All persisted data lives under the repository-level ``data/`` directory.
Reads take a shared lock; writes take an exclusive lock and use a
temporary file + :func:`os.replace` for atomicity so partial writes
never leave a JSON file in a broken state.
"""

import fcntl
import json
import logging
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

logger = logging.getLogger(__name__)

# repo_root / data
DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Sidecar lock directory (see docs/05 §3.1). Kept relative to DATA_DIR so
# tests that monkeypatch DATA_DIR at module scope automatically follow.
_LOCK_SUBDIR = ".locks"


def ensure_data_dir() -> None:
    """Create ``data/`` and ``data/seed/`` if they do not exist."""
    (DATA_DIR / "seed").mkdir(parents=True, exist_ok=True)


def _lock_path_for(relative_path: str) -> Path:
    """Return the sidecar lock path for ``relative_path``.

    Kept as a function (not a module constant) so ``DATA_DIR``
    monkeypatching in tests takes effect on every call.
    """
    name = Path(relative_path).name
    return DATA_DIR / _LOCK_SUBDIR / f"{name}.lock"


def load_json(relative_path: str, default: Any = None) -> Any:
    """Load a JSON file with a shared fcntl lock.

    Args:
        relative_path: Path under ``data/`` (for example ``"users.json"``).
        default: Value returned when the file is missing or unreadable.
            When ``None`` an empty ``dict`` is returned.

    Returns:
        The parsed JSON value, or ``default``.
    """
    path = DATA_DIR / relative_path
    if not path.exists():
        return default if default is not None else {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    except json.JSONDecodeError:
        logger.error("Failed to decode %s", path)
        return default if default is not None else {}
    except OSError:
        logger.exception("Failed to read %s", path)
        return default if default is not None else {}


def save_json(relative_path: str, data: Any) -> None:
    """Atomically write a JSON file with an exclusive fcntl lock.

    Writes ``data`` to a temporary file in the same directory as the
    destination, then uses :func:`os.replace` to swap it in atomically.
    On failure the temp file is unlinked.

    Args:
        relative_path: Path under ``data/`` (for example ``"users.json"``).
        data: JSON-serialisable value.
    """
    path = DATA_DIR / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def locked_edit(relative_path: str, default: Any = None) -> Iterator[Any]:
    """Atomically read → modify → write ``data/<relative_path>``.

    Load the JSON, yield it to the caller for mutation, and on clean
    exit persist it back with :func:`save_json`. An exception inside the
    ``with`` body skips the save so the on-disk state stays consistent.

    Concurrency is provided by a sidecar lock file
    (``data/.locks/<name>.lock``): its fd holds an exclusive
    ``fcntl.flock`` for the whole read → modify → write cycle. The
    sidecar approach survives the ``os.replace`` swap that :func:`save_json`
    performs on the destination inode, and it works cross-process — the
    two race patterns that broke plain ``load_json`` + ``save_json``
    (see Issue #45).

    Args:
        relative_path: Path under ``data/`` (for example
            ``"posts.json"``).
        default: Value handed to :func:`load_json` when the file is
            missing.

    Yields:
        The parsed JSON value. Mutate it in-place; anything you assign
        to the yielded object is persisted on normal exit.
    """
    lock_path = _lock_path_for(relative_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # ``a+`` is the safest mode for a lock sidecar: it creates the file
    # if missing, does not truncate, and never fails on concurrent
    # openers.
    with open(lock_path, "a+") as lock_fp:
        fcntl.flock(lock_fp.fileno(), fcntl.LOCK_EX)
        try:
            data = load_json(relative_path, default=default)
            yield data
            save_json(relative_path, data)
        finally:
            # LOCK_UN is redundant against the "with open" closing the
            # fd, but explicit unlock keeps the intent obvious and is
            # cheap.
            fcntl.flock(lock_fp.fileno(), fcntl.LOCK_UN)
