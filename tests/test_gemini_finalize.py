"""Unit tests for :func:`src.services.gemini.finalize_post` (FR-S6 / T4.15).

Cover the fallback path (used on ``GEMINI_MOCK_MODE`` / API failure /
malformed JSON) and the defensive JSON parser, without hitting the real
Gemini API. See ``docs/06_ai_spec.md`` §4.5.

Style follows ``tests/test_activity_carousel.py``: no pytest fixtures;
each test toggles the module-level ``gemini.GEMINI_MOCK_MODE`` flag in
``setup_method`` and restores it in ``teardown_method``.
"""

from __future__ import annotations

from src.services import gemini, posts


class _MockModeMixin:
    def setup_method(self) -> None:
        self._orig_mock = gemini.GEMINI_MOCK_MODE
        gemini.GEMINI_MOCK_MODE = True

    def teardown_method(self) -> None:
        gemini.GEMINI_MOCK_MODE = self._orig_mock


class TestFinalizePostFallback(_MockModeMixin):
    def _call(self, **overrides: object) -> dict[str, str]:
        kwargs: dict = {
            "category": "volunteer",
            "summary": "下鴨神社の清掃に参加した",
            "learned": "地域の人と話せた",
            "regret": None,
            "advice": None,
            "area": "下鴨神社",
            "period_raw": "去年の10月",
            "today": "2026-07-09",
        }
        kwargs.update(overrides)
        return gemini.finalize_post(**kwargs)  # type: ignore[arg-type]

    def test_mock_mode_uses_summary_and_raw_period(self) -> None:
        result = self._call()
        assert result["title"] == "下鴨神社の清掃に参加した"
        assert result["period"] == "去年の10月"

    def test_title_is_truncated_to_max_len(self) -> None:
        result = self._call(summary="あ" * (posts.MAX_TITLE_LEN + 20))
        assert len(result["title"]) == posts.MAX_TITLE_LEN

    def test_missing_period_raw_yields_empty_period(self) -> None:
        result = self._call(period_raw=None)
        assert result["period"] == ""

    def test_return_keys_are_exactly_title_and_period(self) -> None:
        assert set(self._call().keys()) == {"title", "period"}


class TestParseFinalizeJson:
    def test_valid_object_is_returned(self) -> None:
        parsed = gemini._parse_finalize_json('{"title": "T", "period": "2025年10月"}')
        assert parsed == {"title": "T", "period": "2025年10月"}

    def test_empty_string_returns_empty_dict(self) -> None:
        assert gemini._parse_finalize_json("") == {}

    def test_malformed_json_returns_empty_dict(self) -> None:
        assert gemini._parse_finalize_json("{not json") == {}

    def test_non_object_top_level_returns_empty_dict(self) -> None:
        assert gemini._parse_finalize_json('["a", "b"]') == {}
