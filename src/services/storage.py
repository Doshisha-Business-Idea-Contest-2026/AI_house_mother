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
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# repo_root / data
DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def ensure_data_dir() -> None:
    """Create ``data/`` and ``data/seed/`` if they do not exist."""
    (DATA_DIR / "seed").mkdir(parents=True, exist_ok=True)


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
