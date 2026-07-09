"""Coupon distribution on experience-post milestones (FR-S10).

Every time a student's total experience-post count reaches a new multiple
of :data:`COUPONS_PER_BATCH` (3, 6, 9, ...), a batch of three coupons is
awarded and pushed as a Flex carousel. Selection is deterministic and
rotates through the active coupon seed so consecutive milestones hand out
different coupons; when the seed is exhausted it wraps back to the start.

This is a **demo-only** feature: there is no redemption, no consumption,
and no point ledger (``docs/02_mvp_scope.md §4.1``). The store data is
fictional (``data/seed/coupons.json``). See ``docs/04_functional_spec.md
§4.8`` and ``docs/05_data_model.md §4.15/§4.16``.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from src.services import posts, seed
from src.services.storage import load_json, save_json

logger = logging.getLogger(__name__)

_FILE = "coupon_distributions.json"
JST = ZoneInfo("Asia/Tokyo")

#: Number of posts between coupon batches, and coupons handed out per batch.
COUPONS_PER_BATCH = 3


def _active_coupons() -> list[dict[str, Any]]:
    """Return the ``active`` coupon entries in seed order (FR-S10)."""
    return [c for c in seed.get_coupons() if c.get("active")]


def select_coupons_for_milestone(milestone: int) -> list[dict[str, Any]]:
    """Return the three coupons to award at ``milestone``.

    The batch index is ``(milestone // COUPONS_PER_BATCH) - 1`` (0-based:
    milestone 3 → batch 0, 6 → batch 1, ...). Coupons are taken from the
    active seed by circular slicing, so the seed count need not be a
    multiple of three and rotation wraps back to the start once exhausted
    (docs/05 §4.15).

    Args:
        milestone: The post-count milestone (a positive multiple of
            :data:`COUPONS_PER_BATCH`).

    Returns:
        Up to :data:`COUPONS_PER_BATCH` coupon dicts. Empty when no active
        coupons exist in the seed.
    """
    active = _active_coupons()
    if not active:
        return []
    batch = (milestone // COUPONS_PER_BATCH) - 1
    start = batch * COUPONS_PER_BATCH
    return [active[(start + i) % len(active)] for i in range(COUPONS_PER_BATCH)]


def award_if_due(
    user_id: str, now_jst: datetime | None = None
) -> list[dict[str, Any]] | None:
    """Award a coupon batch when the student hits a new post milestone.

    Computes ``milestone = (count_all // COUPONS_PER_BATCH) * COUPONS_PER_BATCH``
    from the student's total experience-post count. When ``milestone`` is at
    least :data:`COUPONS_PER_BATCH` and greater than the last awarded
    milestone, three coupons are selected, the milestone and batch are
    recorded to ``coupon_distributions.json``, and the coupons are returned
    for the caller to push. The monotonically increasing
    ``last_awarded_milestone`` prevents double-awarding the same milestone
    (docs/04 §4.8, docs/05 §4.16).

    Args:
        user_id: The student's LINE user id.
        now_jst: Optional reference time (JST) for the ``awarded_at``
            stamp. Defaults to :func:`datetime.now`.

    Returns:
        The awarded coupon dicts, or ``None`` when no batch is due (below
        the first milestone, already awarded, or no active coupons).
    """
    total = posts.count_all(user_id)
    milestone = (total // COUPONS_PER_BATCH) * COUPONS_PER_BATCH
    if milestone < COUPONS_PER_BATCH:
        return None

    data = load_json(_FILE, default={})
    if not isinstance(data, dict):
        data = {}
    user_bucket = data.get(user_id, {})
    last_awarded = int(user_bucket.get("last_awarded_milestone", 0))
    if milestone <= last_awarded:
        return None

    coupons = select_coupons_for_milestone(milestone)
    if not coupons:
        logger.warning("Coupon milestone %d reached but seed is empty", milestone)
        return None

    awarded_at = (now_jst or datetime.now(JST)).astimezone(JST).isoformat()
    distributions = user_bucket.get("distributions", [])
    distributions.append(
        {
            "milestone": milestone,
            "coupon_ids": [c.get("coupon_id") for c in coupons],
            "awarded_at": awarded_at,
        }
    )
    user_bucket["last_awarded_milestone"] = milestone
    user_bucket["distributions"] = distributions
    data[user_id] = user_bucket
    save_json(_FILE, data)
    logger.info(
        "Coupons awarded: user=%s milestone=%d coupons=%s",
        user_id[:8],
        milestone,
        [c.get("coupon_id") for c in coupons],
    )
    return coupons
