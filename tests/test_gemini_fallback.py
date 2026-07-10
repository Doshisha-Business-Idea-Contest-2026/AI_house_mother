"""Regression insurance for the Gemini timeout / retry policy (PR #83).

Audit finding B-1 (originally High, filed as Low #98) called out that the
retry-removal + 4-tier timeout rewrite has no test coverage for the
failure paths: a well-meaning contributor could re-introduce a retry
loop or bump ``DEFAULT_TIMEOUT_S`` back past the LINE Webhook 30 s
ceiling and nothing would go red.

These tests pin down, for each webhook-serving entry point:

- The exact ``request_options["timeout"]`` value (so a constant bump is
  caught).
- ``generate_content.call_count == 1`` (so a re-added retry loop is
  caught).
- Graceful fallback on ``ResourceExhausted`` / ``DeadlineExceeded`` /
  bare ``Exception`` (so a re-ordered ``except`` chain is caught).

We drive the code through the real (non-mock) branches by forcing
``GEMINI_MOCK_MODE = False`` and stubbing :func:`gemini._build_client`
with a MagicMock whose ``generate_content`` raises the target
exception.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import MagicMock, patch

from google.api_core import exceptions as gexc

from src.services import gemini


class _RealPathMixin:
    """Force the real (non-mock) code path for each test."""

    def setup_method(self) -> None:
        self._orig_mock = gemini.GEMINI_MOCK_MODE
        gemini.GEMINI_MOCK_MODE = False

    def teardown_method(self) -> None:
        gemini.GEMINI_MOCK_MODE = self._orig_mock


def _client_that_raises(exc: BaseException) -> MagicMock:
    """Return a stand-in for ``genai.GenerativeModel`` whose
    ``generate_content`` raises ``exc`` on every call."""
    cl = MagicMock()
    cl.generate_content.side_effect = exc
    return cl


_TEXT_EXCEPTIONS: list[BaseException] = [
    gexc.ResourceExhausted("rate limit"),
    gexc.DeadlineExceeded("timeout"),
    RuntimeError("unexpected"),
]


class _RecordingHandler(logging.Handler):
    """Capture log records without relying on pytest fixtures."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class TestCallGeminiFallback(_RealPathMixin):
    """``call_gemini`` is the text-mode hub: text answers, activity detail,
    the month summary. Its failure path must return an empty string,
    never retry, and always request the caller-supplied timeout."""

    def test_each_exception_yields_empty_string_with_single_call(self) -> None:
        for exc in _TEXT_EXCEPTIONS:
            cl = _client_that_raises(exc)
            with patch.object(gemini, "_build_client", return_value=cl):
                result = gemini.call_gemini("prompt")

            assert result == ""
            assert cl.generate_content.call_count == 1, (
                f"call_gemini retried on {type(exc).__name__} — retry loop "
                "must stay removed (docs/06 §6.3)."
            )

    def test_default_timeout_is_the_shared_default(self) -> None:
        cl = _client_that_raises(gexc.DeadlineExceeded("t"))
        with patch.object(gemini, "_build_client", return_value=cl):
            gemini.call_gemini("prompt")

        _, kwargs = cl.generate_content.call_args
        assert kwargs["request_options"]["timeout"] == gemini.DEFAULT_TIMEOUT_S

    def test_caller_supplied_timeout_is_honoured(self) -> None:
        cl = _client_that_raises(gexc.DeadlineExceeded("t"))
        with patch.object(gemini, "_build_client", return_value=cl):
            gemini.call_gemini("prompt", timeout=42)

        _, kwargs = cl.generate_content.call_args
        assert kwargs["request_options"]["timeout"] == 42


class TestProposeActivitiesFallback(_RealPathMixin):
    """``propose_activities`` runs on the longer JSON budget and falls
    back to seed picks on every exception. It must not retry."""

    def _profile(self) -> dict[str, Any]:
        return {"interests": ["volunteer"], "want_to_do": "help locally"}

    def test_each_exception_falls_back_to_seed_with_single_call(self) -> None:
        for exc in _TEXT_EXCEPTIONS:
            cl = _client_that_raises(exc)
            with (
                patch.object(gemini, "_build_client", return_value=cl),
                patch.object(
                    gemini.seed,
                    "pick_static_fallback_activities",
                    return_value=[{"title": "seed pick"}],
                ) as fallback_mock,
            ):
                result = gemini.propose_activities(self._profile())

            assert (
                cl.generate_content.call_count == 1
            ), f"propose_activities retried on {type(exc).__name__}"
            assert isinstance(result, list) and len(result) >= 1
            # A fallback was consulted, meaning the exception did not
            # crash and did not return the (empty) parsed JSON.
            assert fallback_mock.called

    def test_propose_uses_propose_timeout_constant(self) -> None:
        cl = _client_that_raises(gexc.DeadlineExceeded("t"))
        with (
            patch.object(gemini, "_build_client", return_value=cl),
            patch.object(
                gemini.seed,
                "pick_static_fallback_activities",
                return_value=[{"title": "seed"}],
            ),
        ):
            gemini.propose_activities(self._profile())

        _, kwargs = cl.generate_content.call_args
        assert kwargs["request_options"]["timeout"] == gemini._PROPOSE_TIMEOUT_S


class TestFinalizePostFallback(_RealPathMixin):
    """``finalize_post`` is inline before the confirmation card and must
    never block the post flow — every exception yields a usable dict."""

    def _kwargs(self) -> dict[str, Any]:
        return dict(
            category="volunteer",
            summary="Ran a small event",
            learned="Prep matters",
            regret=None,
            advice=None,
            area=None,
            period_raw="yesterday",
            today="2026-07-10",
        )

    def test_each_exception_returns_fallback_dict_with_single_call(self) -> None:
        for exc in _TEXT_EXCEPTIONS:
            cl = _client_that_raises(exc)
            with patch.object(gemini, "_build_client", return_value=cl):
                result = gemini.finalize_post(**self._kwargs())

            assert (
                cl.generate_content.call_count == 1
            ), f"finalize_post retried on {type(exc).__name__}"
            # docs/04 §4.5: never block a legitimate post on outage.
            assert result["valid"] is True
            # Fallback title is derived from the summary (see docstring).
            assert result["title"].startswith("Ran a small event"[:1])
            assert result["period"] == "yesterday"

    def test_finalize_uses_finalize_timeout_constant(self) -> None:
        cl = _client_that_raises(gexc.DeadlineExceeded("t"))
        with patch.object(gemini, "_build_client", return_value=cl):
            gemini.finalize_post(**self._kwargs())

        _, kwargs = cl.generate_content.call_args
        assert kwargs["request_options"]["timeout"] == gemini._FINALIZE_TIMEOUT_S


class TestTimeoutConstantsRemainInsideWebhookBudget:
    """Even a caller who forgets ``interactive=True`` on the batch path
    must not accidentally blow the 30 s webhook ceiling on the paths
    that DO run inside a webhook."""

    def test_default_timeout_leaves_headroom_under_30s(self) -> None:
        assert gemini.DEFAULT_TIMEOUT_S <= 20, (
            "DEFAULT_TIMEOUT_S is used for interactive webhook calls; "
            "keep it well below the 30 s LINE ceiling."
        )

    def test_propose_timeout_leaves_headroom_under_30s(self) -> None:
        assert gemini._PROPOSE_TIMEOUT_S <= 25

    def test_finalize_timeout_is_snappy(self) -> None:
        # Runs before the confirmation card — must feel instant.
        assert gemini._FINALIZE_TIMEOUT_S <= 10


class TestParseActivityJson:
    def test_drops_items_missing_required_fields(self) -> None:
        handler = _RecordingHandler()
        logger = logging.getLogger(gemini.__name__)
        original_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)
        try:
            result = gemini._parse_activity_json(
                "["
                '{"title": "A", "summary": "S", "reference_type": "generated"},'
                '{"title": "B", "summary": "S", "why_recommend": "W", '
                '"reference_type": "generated"}'
                "]"
            )
        finally:
            logger.removeHandler(handler)
            logger.setLevel(original_level)

        assert [item["title"] for item in result] == ["B"]
        assert any("missing keys" in record.getMessage() for record in handler.records)

    def test_drops_items_with_invalid_reference_type(self) -> None:
        result = gemini._parse_activity_json(
            "["
            '{"title": "A", "summary": "S", "why_recommend": "W", '
            '"reference_type": "made_up"},'
            '{"title": "B", "summary": "S", "why_recommend": "W", '
            '"reference_type": "store"}'
            "]"
        )

        assert [item["reference_type"] for item in result] == ["store"]

    def test_optional_location_and_when_still_default_to_empty(self) -> None:
        result = gemini._parse_activity_json(
            "["
            '{"title": "A", "summary": "S", "why_recommend": "W", '
            '"reference_type": "generated"}'
            "]"
        )

        assert result == [
            {
                "title": "A",
                "summary": "S",
                "why_recommend": "W",
                "reference_type": "generated",
                "location": "",
                "when": "",
            }
        ]


class TestNormaliseInterests:
    def test_string_interest_stays_as_single_item(self) -> None:
        assert gemini._normalise_interests({"interests": "sports"}) == ["sports"]

    def test_list_keeps_only_string_items(self) -> None:
        assert gemini._normalise_interests({"interests": ["sports", 123, "music"]}) == [
            "sports",
            "music",
        ]

    def test_none_or_missing_interests_yields_empty_list(self) -> None:
        assert gemini._normalise_interests({"interests": None}) == []
        assert gemini._normalise_interests({}) == []
