"""Unit tests for :func:`src.services.gemini.finalize_post` (FR-S6 / T4.15).

Cover the fallback path (used on ``GEMINI_MOCK_MODE`` / API failure /
malformed JSON) and the defensive JSON parser, without hitting the real
Gemini API. See ``docs/06_ai_spec.md`` §4.5.

Style follows ``tests/test_activity_carousel.py``: no pytest fixtures;
each test toggles the module-level ``gemini.GEMINI_MOCK_MODE`` flag in
``setup_method`` and restores it in ``teardown_method``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from src.services import gemini, posts


class _MockModeMixin:
    def setup_method(self) -> None:
        self._orig_mock = gemini.GEMINI_MOCK_MODE
        gemini.GEMINI_MOCK_MODE = True

    def teardown_method(self) -> None:
        gemini.GEMINI_MOCK_MODE = self._orig_mock


class TestFinalizePostFallback(_MockModeMixin):
    def _call(self, **overrides: object) -> dict[str, object]:
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

    def test_return_keys_include_valid_and_reason(self) -> None:
        assert set(self._call().keys()) == {"title", "period", "valid", "reason"}

    def test_mock_mode_defaults_valid_true(self) -> None:
        # Fallback / mock must never reject a post (docs/04 §4.5).
        result = self._call()
        assert result["valid"] is True
        assert result["reason"] == ""


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


class TestFinalizePostRealPathFallback:
    def setup_method(self) -> None:
        self._orig_mock = gemini.GEMINI_MOCK_MODE
        gemini.GEMINI_MOCK_MODE = False

    def teardown_method(self) -> None:
        gemini.GEMINI_MOCK_MODE = self._orig_mock

    def _kwargs(self, **overrides: object) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
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
        return kwargs

    def _client_with_text(self, text: str) -> MagicMock:
        cl = MagicMock()
        response = MagicMock()
        response.text = text
        cl.generate_content.return_value = response
        return cl

    def test_api_exception_returns_fallback_dict(self) -> None:
        cl = MagicMock()
        cl.generate_content.side_effect = RuntimeError("api failed")

        with patch.object(gemini, "_build_client", return_value=cl):
            result = gemini.finalize_post(**self._kwargs())

        assert cl.generate_content.call_count == 1
        assert result == {
            "title": "下鴨神社の清掃に参加した",
            "period": "去年の10月",
            "valid": True,
            "reason": "",
        }

    def test_empty_model_period_falls_back_to_raw_period(self) -> None:
        cl = self._client_with_text(
            '{"title": "地域清掃への参加", "period": "", "valid": true, "reason": ""}'
        )

        with patch.object(gemini, "_build_client", return_value=cl):
            result = gemini.finalize_post(**self._kwargs())

        assert result["title"] == "地域清掃への参加"
        assert result["period"] == "去年の10月"
        assert result["valid"] is True

    def test_malformed_or_empty_json_returns_fallback_dict(self) -> None:
        for raw in ("", "{not json"):
            cl = self._client_with_text(raw)

            with patch.object(gemini, "_build_client", return_value=cl):
                result = gemini.finalize_post(**self._kwargs())

            assert cl.generate_content.call_count == 1
            assert result["title"] == "下鴨神社の清掃に参加した"
            assert result["period"] == "去年の10月"
            assert result["valid"] is True
            assert result["reason"] == ""
