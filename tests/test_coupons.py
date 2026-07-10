"""Unit tests for :mod:`src.services.coupons` selection behavior."""

from __future__ import annotations

from typing import Any

from src.services import coupons, seed


def _coupon(coupon_id: str, *, active: bool = True) -> dict[str, Any]:
    return {"coupon_id": coupon_id, "active": active}


class TestSelectCouponsForMilestone:
    def setup_method(self) -> None:
        self._orig_get_coupons = seed.get_coupons

    def teardown_method(self) -> None:
        seed.get_coupons = self._orig_get_coupons  # type: ignore[assignment]

    def _set_seed(self, entries: list[dict[str, Any]]) -> None:
        seed.get_coupons = lambda: entries  # type: ignore[assignment]

    def test_less_than_three_active_coupons_are_not_duplicated(self) -> None:
        self._set_seed([_coupon("C1"), _coupon("C2")])

        selected = coupons.select_coupons_for_milestone(3)

        assert [c["coupon_id"] for c in selected] == ["C1", "C2"]

    def test_rotation_keeps_unique_batch_when_only_two_active(self) -> None:
        self._set_seed([_coupon("C1"), _coupon("C2")])

        selected = coupons.select_coupons_for_milestone(6)

        assert [c["coupon_id"] for c in selected] == ["C2", "C1"]

    def test_inactive_coupons_do_not_count_toward_batch_size(self) -> None:
        self._set_seed([_coupon("C1"), _coupon("C2", active=False), _coupon("C3")])

        selected = coupons.select_coupons_for_milestone(3)

        assert [c["coupon_id"] for c in selected] == ["C1", "C3"]
