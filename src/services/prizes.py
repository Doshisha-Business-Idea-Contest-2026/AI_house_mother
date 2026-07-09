"""Prize lottery draw (FR-S11).

Students draw a lottery once per completed experience post (docs/04 §4.9).
The draw is ranked: 1st (theme-park ticket) / 2nd (free-item voucher) /
3rd (coupon) / miss, with higher ranks rarer. This is a **demo-only**
feature: prizes are fictional, nothing is shipped, and **no winner PII
(name / address / phone) is collected or stored** (docs/02 §4.1,
.codex/rules/project_rules.md). The random seed is recorded for a
reproducible, fair-looking audit trail with no PII.

See ``docs/04_functional_spec.md §4.9`` and ``docs/05_data_model.md
§4.17/§4.18``.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.services import seed
from src.services.storage import load_json, save_json

logger = logging.getLogger(__name__)

_FILE = "prize_draws.json"
JST = ZoneInfo("Asia/Tokyo")

#: Win probability per rank for the natural (non-forced) draw. The
#: remainder (1 - sum) is a miss. Higher ranks are rarer. Demo runs force
#: the rank, so these affect unforced draws only.
RANK_PROBABILITIES: dict[int, float] = {1: 0.01, 2: 0.30, 3: 0.50}

_SEED_MAX = 10_000_000


def _active_prizes() -> list[dict[str, Any]]:
    """Return the ``active`` prize entries (FR-S11)."""
    return [p for p in seed.get_prizes() if p.get("active")]


def _prize_by_rank(rank: int) -> dict[str, Any] | None:
    """Return the first active prize with ``rank``, or ``None``."""
    for prize in _active_prizes():
        if prize.get("rank") == rank:
            return prize
    return None


def _record_draw(
    user_id: str,
    rank: int | None,
    prize_id: str | None,
    result: str,
    seed_val: int,
    now_jst: datetime | None,
) -> None:
    """Append a draw result to ``prize_draws.json`` (no PII).

    Records only ``{rank, prize_id, result, seed, drawn_at}``. Winner
    name/address/phone must never be added here (docs/05 §4.18,
    .codex/rules/project_rules.md).
    """
    drawn_at = (now_jst or datetime.now(JST)).astimezone(JST).isoformat()
    data = load_json(_FILE, default={})
    if not isinstance(data, dict):
        data = {}
    user_bucket = data.get(user_id, {})
    draws = user_bucket.get("draws", [])
    draws.append(
        {
            "rank": rank,
            "prize_id": prize_id,
            "result": result,
            "seed": seed_val,
            "drawn_at": drawn_at,
        }
    )
    user_bucket["draws"] = draws
    data[user_id] = user_bucket
    save_json(_FILE, data)
    logger.info(
        "Prize draw: user=%s rank=%s prize=%s result=%s",
        user_id[:8],
        rank,
        prize_id,
        result,
    )


def draw(
    user_id: str,
    *,
    force_rank: int | None = None,
    now_jst: datetime | None = None,
) -> dict[str, Any] | None:
    """Run one ranked prize draw for ``user_id`` and record the result.

    A random seed decides the outcome. When ``force_rank`` is ``None`` the
    rank is drawn from :data:`RANK_PROBABILITIES` (remainder = miss); when
    it is ``1``/``2``/``3`` that rank is forced; when it is ``0`` a miss is
    forced. The seed and result are recorded to ``prize_draws.json`` with
    no PII (docs/04 §4.9, docs/05 §4.18).

    Args:
        user_id: The student's LINE user id.
        force_rank: ``1``/``2``/``3`` to force a rank, ``0`` to force a
            miss, ``None`` for a random outcome.
        now_jst: Optional reference time (JST) for the ``drawn_at`` stamp.

    Returns:
        A dict ``{"rank", "prize", "result", "seed"}`` where ``result`` is
        ``"win"`` (with a ``prize`` dict and int ``rank``) or ``"lose"``
        (``prize`` / ``rank`` are ``None``). ``None`` when the seed has no
        active prizes.
    """
    prizes = _active_prizes()
    if not prizes:
        logger.warning("Prize draw requested but seed has no active prizes")
        return None

    seed_val = random.randrange(_SEED_MAX)
    rng = random.Random(seed_val)

    won_rank: int | None
    if force_rank is None:
        roll = rng.random()
        cumulative = 0.0
        won_rank = None
        for rank in (1, 2, 3):
            cumulative += RANK_PROBABILITIES.get(rank, 0.0)
            if roll < cumulative:
                won_rank = rank
                break
    else:
        won_rank = force_rank if force_rank in (1, 2, 3) else None

    prize = _prize_by_rank(won_rank) if won_rank is not None else None
    if won_rank is not None and prize is None:
        # Requested rank has no active prize; treat as a miss.
        won_rank = None
    result = "win" if won_rank is not None else "lose"
    prize_id = prize.get("prize_id") if prize else None

    _record_draw(user_id, won_rank, prize_id, result, seed_val, now_jst)
    return {"rank": won_rank, "prize": prize, "result": result, "seed": seed_val}
