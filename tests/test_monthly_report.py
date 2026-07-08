"""Unit tests for :mod:`src.services.monthly_report` and the enriched
Flex bubble in :mod:`src.templates.flex.monthly_report` (FR-P3 extension).

Covers the report dict assembly (prev-month count, lifetime total, usage
counters, AI summary fallback) and the Flex renderer's low-consultation
fallback / usage section rules. See ``docs/04_functional_spec.md`` §5.3.

Style follows ``tests/test_sponsored.py``: pytest-independent assert
classes. Each service-level test uses a temp DATA_DIR and monkeypatches
:func:`gemini.summarize_month` so the tests never hit the network.
"""

from __future__ import annotations

import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.services import gemini, monthly_report, posts, storage, usage_stats
from src.templates.flex import monthly_report as flex_monthly

_JST = ZoneInfo("Asia/Tokyo")


class _TempDataDirMixin:
    def setup_method(self) -> None:
        self._orig_data_dir = storage.DATA_DIR
        self._orig_summarize = gemini.summarize_month
        self._tmp = Path(tempfile.mkdtemp(prefix="ai_house_mother_test_"))
        storage.DATA_DIR = self._tmp
        # Seed posts.json so posts._load() doesn't die on a missing key.
        (self._tmp / "posts.json").write_text('{"posts": []}', encoding="utf-8")

        def _fake_summary(
            profile: dict[str, Any] | None,
            year_month: str,
            posts_month: list[dict[str, Any]],
            usage: dict[str, int],
        ) -> str:
            return f"[stub] {year_month} posts={len(posts_month)}"

        gemini.summarize_month = _fake_summary  # type: ignore[assignment]

    def teardown_method(self) -> None:
        storage.DATA_DIR = self._orig_data_dir
        gemini.summarize_month = self._orig_summarize  # type: ignore[assignment]
        shutil.rmtree(self._tmp, ignore_errors=True)


def _add_shared_post(
    user_id: str, when: datetime, title: str = "title", category: str = "study"
) -> None:
    posts.add_post(
        line_user_id=user_id,
        category=category,
        title=title,
        body="body",
        area=None,
        share_with_parent=True,
    )
    # posts.add_post uses datetime.now(JST) for created_at, which fails
    # the per-month filter in tests that need explicit timestamps. Patch
    # the created_at field in-place.
    data = posts._load()
    data["posts"][-1]["created_at"] = when.isoformat()
    from src.services.storage import save_json

    save_json("posts.json", data)


class TestReportAssembly(_TempDataDirMixin):
    def test_current_month_report_carries_prev_total_and_usage(self) -> None:
        now = datetime(2026, 7, 15, 12, 0, tzinfo=_JST)
        _add_shared_post("U-abc", datetime(2026, 7, 1, 9, 0, tzinfo=_JST))
        _add_shared_post("U-abc", datetime(2026, 7, 10, 9, 0, tzinfo=_JST))
        _add_shared_post("U-abc", datetime(2026, 6, 20, 9, 0, tzinfo=_JST))
        _add_shared_post("U-abc", datetime(2026, 5, 20, 9, 0, tzinfo=_JST))
        usage_stats.record("U-abc", "life", now_jst=now)
        usage_stats.record("U-abc", "activity", now_jst=now)
        usage_stats.record("U-abc", "activity", now_jst=now)

        report = monthly_report.build_current_month_report("U-abc", now_jst=now)

        assert report["year_month"] == "2026-07"
        assert report["current_count"] == 2
        assert report["prev_count"] == 1
        assert report["total_count"] == 4
        assert report["usage"] == {"life": 1, "activity": 2, "post": 0, "profile": 0}
        assert report["ai_summary"].startswith("[stub]")

    def test_previous_month_report_uses_prior_month(self) -> None:
        now = datetime(2026, 7, 15, 12, 0, tzinfo=_JST)
        _add_shared_post("U-abc", datetime(2026, 6, 5, 9, 0, tzinfo=_JST))
        _add_shared_post("U-abc", datetime(2026, 5, 3, 9, 0, tzinfo=_JST))

        report = monthly_report.build_previous_month_report("U-abc", now_jst=now)

        assert report["year_month"] == "2026-06"
        assert report["current_count"] == 1
        assert report["prev_count"] == 1  # May had 1 post
        assert report["total_count"] == 2

    def test_previous_month_january_crosses_year(self) -> None:
        now = datetime(2026, 1, 15, 12, 0, tzinfo=_JST)
        _add_shared_post("U-abc", datetime(2025, 12, 10, 9, 0, tzinfo=_JST))
        _add_shared_post("U-abc", datetime(2025, 11, 10, 9, 0, tzinfo=_JST))

        report = monthly_report.build_previous_month_report("U-abc", now_jst=now)

        assert report["year_month"] == "2025-12"
        assert report["current_count"] == 1
        assert report["prev_count"] == 1


class TestIsReportEmpty(_TempDataDirMixin):
    def _base_report(self) -> dict[str, Any]:
        return {
            "posts": [],
            "current_count": 0,
            "prev_count": 0,
            "total_count": 0,
            "usage": {"life": 0, "activity": 0, "post": 0, "profile": 0},
            "ai_summary": "",
        }

    def test_zero_posts_and_zero_usage_is_empty(self) -> None:
        assert monthly_report.is_report_empty(self._base_report())

    def test_zero_posts_but_usage_present_is_not_empty(self) -> None:
        report = self._base_report()
        report["usage"]["life"] = 1
        assert not monthly_report.is_report_empty(report)

    def test_posts_present_is_not_empty(self) -> None:
        report = self._base_report()
        report["posts"] = [{"title": "x", "body": "y", "category": "study"}]
        assert not monthly_report.is_report_empty(report)


def _texts(bubble: dict[str, Any]) -> list[str]:
    body = bubble["body"]
    return [c["text"] for c in body["contents"] if c.get("type") == "text"]


class TestFlexRendering:
    def _report(
        self,
        *,
        posts_list: list[dict[str, Any]] | None = None,
        prev: int = 0,
        total: int = 0,
        usage: dict[str, int] | None = None,
        ai_summary: str = "",
    ) -> dict[str, Any]:
        posts_list = posts_list or []
        return {
            "student_user_id": "U-abc",
            "student_display": "あなたのお子さん",
            "year_month": "2026-07",
            "posts": posts_list,
            "current_count": len(posts_list),
            "prev_count": prev,
            "total_count": total,
            "usage": usage or {"life": 0, "activity": 0, "post": 0, "profile": 0},
            "ai_summary": ai_summary,
        }

    def test_header_and_posts_section_show_prev_and_total(self) -> None:
        report = self._report(
            posts_list=[
                {"title": "レポート提出", "body": "書いた", "category": "study"}
            ],
            prev=0,
            total=5,
        )
        bubble = flex_monthly.build_monthly_report_bubble(report)
        texts = _texts(bubble)
        assert "🌸 頑張ったこと 1 件" in texts
        assert "（先月 0 / 通算 5）" in texts

    def test_consult_at_threshold_shows_numeric_line(self) -> None:
        report = self._report(usage={"life": 2, "activity": 1, "post": 0, "profile": 0})
        bubble = flex_monthly.build_monthly_report_bubble(report)
        texts = _texts(bubble)
        assert "相談 3回（生活 2 / 活動 1）" in texts

    def test_consult_below_threshold_falls_back_to_qualitative(self) -> None:
        report = self._report(usage={"life": 1, "activity": 1, "post": 0, "profile": 0})
        bubble = flex_monthly.build_monthly_report_bubble(report)
        texts = _texts(bubble)
        assert flex_monthly._LOW_CONSULT_TEXT in texts
        assert not any(t.startswith("相談 ") for t in texts)

    def test_no_records_line_when_record_total_zero(self) -> None:
        report = self._report(usage={"life": 5, "activity": 0, "post": 0, "profile": 0})
        bubble = flex_monthly.build_monthly_report_bubble(report)
        texts = _texts(bubble)
        assert not any(t.startswith("記録・更新 ") for t in texts)

    def test_zero_everything_shows_no_activity_line(self) -> None:
        report = self._report()
        bubble = flex_monthly.build_monthly_report_bubble(report)
        texts = _texts(bubble)
        assert flex_monthly._NO_ACTIVITY_TEXT in texts

    def test_ai_summary_section_only_when_summary_present(self) -> None:
        with_summary = flex_monthly.build_monthly_report_bubble(
            self._report(ai_summary="今月も前向きに過ごされているようです。")
        )
        assert "💬 AI寮母より" in _texts(with_summary)

        without = flex_monthly.build_monthly_report_bubble(self._report())
        assert "💬 AI寮母より" not in _texts(without)


class TestGeminiFallback:
    """``summarize_month`` short-circuits without any I/O for empty months."""

    def test_empty_month_returns_fallback_without_api_call(self) -> None:
        # No posts, 0 consultations → the guard fires before Gemini is
        # touched, so this works even when GEMINI_MOCK_MODE is off and
        # no credentials are available in the test environment.
        result = gemini.summarize_month(
            profile=None,
            year_month="2026-07",
            posts_month=[],
            usage={"life": 0, "activity": 0, "post": 0, "profile": 0},
        )
        assert result == gemini._MONTH_SUMMARY_FALLBACK
