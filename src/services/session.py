"""In-memory conversation session management.

Sessions are stored in a module-level dict keyed by LINE ``user_id``.
Each session tracks a dotted ``state`` string (for example
``"profile.university"``), an arbitrary ``context`` dict, a JST
timestamp, and a failure counter. Sessions expire after
:data:`SESSION_TIMEOUT_MINUTES` minutes of inactivity.

The uvicorn service is launched with ``--workers 1`` so this in-memory
store is safe. Once the app scales beyond a single worker, this module
must be replaced with a shared store (Redis or similar).
"""
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo
import logging

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")

SESSION_TIMEOUT_MINUTES = 10
MAX_FAIL_COUNT = 5

# Session record shape:
# {
#     "state": "profile.university",
#     "context": {...},
#     "timestamp": datetime (JST),
#     "fail_count": int,
# }
_sessions: dict[str, dict[str, Any]] = {}


def set_state(line_user_id: str, state: str, **context: Any) -> None:
    """Create or replace the session for ``line_user_id``.

    ``context`` keyword arguments are stored on the session so that
    subsequent turns can retrieve them via :func:`get_state`.
    """
    _sessions[line_user_id] = {
        "state": state,
        "context": dict(context),
        "timestamp": datetime.now(JST),
        "fail_count": 0,
    }
    logger.info("session set_state %s -> %s", line_user_id[:8], state)


def get_state(line_user_id: str) -> dict[str, Any] | None:
    """Return the active session for ``line_user_id`` or ``None``.

    Sessions older than :data:`SESSION_TIMEOUT_MINUTES` minutes are
    silently discarded before returning.
    """
    session = _sessions.get(line_user_id)
    if session is None:
        return None

    elapsed = datetime.now(JST) - session["timestamp"]
    if elapsed > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        logger.info("session timeout %s", line_user_id[:8])
        clear_state(line_user_id)
        return None
    return session


def clear_state(line_user_id: str) -> None:
    """Drop the session for ``line_user_id`` if it exists."""
    if line_user_id in _sessions:
        logger.info("session clear %s", line_user_id[:8])
        del _sessions[line_user_id]


def touch(line_user_id: str) -> None:
    """Refresh the session timestamp so it does not expire mid-flow."""
    if line_user_id in _sessions:
        _sessions[line_user_id]["timestamp"] = datetime.now(JST)


def is_active(line_user_id: str) -> bool:
    """Return ``True`` when a non-expired session exists."""
    return get_state(line_user_id) is not None


def increment_fail(line_user_id: str) -> int:
    """Increment the failure counter and return the new value.

    Returns 0 when there is no active session.
    """
    session = _sessions.get(line_user_id)
    if session is None:
        return 0
    session["fail_count"] = session.get("fail_count", 0) + 1
    logger.info("session fail_count %s -> %d", line_user_id[:8], session["fail_count"])
    return session["fail_count"]
