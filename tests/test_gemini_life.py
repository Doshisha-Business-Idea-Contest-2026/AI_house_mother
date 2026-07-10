"""Unit tests for :func:`src.services.gemini.answer_life_question` (FR-S5).

Cover the structured (empathy / answer / closing) return contract, the
mock-mode path, and the defensive JSON parser, without hitting the real
Gemini API. See ``docs/06_ai_spec.md`` §4.2 and ``docs/04`` §4.4.

Style follows ``tests/test_gemini_finalize.py``: no pytest fixtures; each
test toggles the module-level ``gemini.GEMINI_MOCK_MODE`` flag in
``setup_method`` and restores it in ``teardown_method``.
"""

from __future__ import annotations

from src.services import gemini


class _MockModeMixin:
    def setup_method(self) -> None:
        self._orig_mock = gemini.GEMINI_MOCK_MODE
        gemini.GEMINI_MOCK_MODE = True

    def teardown_method(self) -> None:
        gemini.GEMINI_MOCK_MODE = self._orig_mock


class TestAnswerLifeQuestionMock(_MockModeMixin):
    def _call(self) -> dict[str, str]:
        return gemini.answer_life_question(
            None,
            "熱っぽいんですけど、近くの病院はどこ？",
            {
                "stores": [],
                "areas": [],
                "senior_posts": [],
                "student_posts": [],
            },
            total_hits=0,
        )

    def test_returns_three_string_fields(self) -> None:
        result = self._call()
        assert set(result.keys()) == {"empathy", "answer", "closing"}
        assert all(isinstance(v, str) for v in result.values())

    def test_answer_is_non_empty(self) -> None:
        # The body bubble must always carry text so the reply is never blank.
        assert self._call()["answer"].strip() != ""


class TestParseLifeJson:
    def test_valid_object_is_returned(self) -> None:
        parsed = gemini._parse_life_json(
            '{"empathy": "つらいですね", "answer": "近くの内科へ", "closing": ""}'
        )
        assert parsed == {
            "empathy": "つらいですね",
            "answer": "近くの内科へ",
            "closing": "",
        }

    def test_empty_string_returns_empty_dict(self) -> None:
        assert gemini._parse_life_json("") == {}

    def test_malformed_json_returns_empty_dict(self) -> None:
        assert gemini._parse_life_json("{not json") == {}

    def test_non_object_top_level_returns_empty_dict(self) -> None:
        assert gemini._parse_life_json('["a", "b"]') == {}
