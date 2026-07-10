"""Unit tests for :func:`src.handlers.parent._normalize_code` (FR-P2).

The parent-facing invitation code redemption must accept fullwidth
digits/letters typed via iOS/Android IMEs, as well as incidental spaces
and hyphens, before format validation runs. See ``docs/04 §4.6``.

Style follows ``tests/test_posts.py``: no pytest fixtures, class-based.
"""

from __future__ import annotations

import json
import tempfile
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from src.handlers.parent import _is_valid_format, _normalize_code
from src.services import invitations, storage


class TestNormalizeCode:
    def test_ascii_uppercase_passes_through(self) -> None:
        assert _normalize_code("A3F7K9") == "A3F7K9"

    def test_ascii_lowercase_is_uppercased(self) -> None:
        assert _normalize_code("a3f7k9") == "A3F7K9"

    def test_fullwidth_digits_and_letters_are_collapsed(self) -> None:
        assert _normalize_code("Ａ３Ｆ７Ｋ９") == "A3F7K9"

    def test_fullwidth_lowercase_letters_are_normalized(self) -> None:
        assert _normalize_code("ａ３ｆ７ｋ９") == "A3F7K9"

    def test_hyphen_grouping_is_stripped(self) -> None:
        assert _normalize_code("A3F-7K9") == "A3F7K9"

    def test_fullwidth_hyphen_grouping_is_stripped(self) -> None:
        # U+FF0D FULLWIDTH HYPHEN-MINUS collapses to ASCII '-' under
        # NFKC and is then removed by the ASCII hyphen strip, so the
        # code lands in canonical form.
        assert _normalize_code("Ａ３Ｆ－７Ｋ９") == "A3F7K9"

    def test_em_dash_grouping_is_not_stripped(self) -> None:
        # U+2014 EM DASH does not decompose under NFKC. That is a
        # deliberate line in the sand: only visually plausible
        # ASCII-hyphen inputs are absorbed, other dashes fall through
        # to the format check so the parent sees "invalid_format".
        assert _normalize_code("A3F—7K9") == "A3F—7K9"

    def test_ascii_spaces_between_chars_are_stripped(self) -> None:
        assert _normalize_code("A 3 F 7 K 9") == "A3F7K9"

    def test_fullwidth_space_between_chars_is_stripped(self) -> None:
        assert _normalize_code("Ａ　３　Ｆ　７　Ｋ　９") == "A3F7K9"

    def test_surrounding_whitespace_is_stripped(self) -> None:
        assert _normalize_code("   A3F7K9   ") == "A3F7K9"

    def test_short_input_stays_short(self) -> None:
        # Length is not enforced here; _is_valid_format owns that.
        assert _normalize_code("A3F") == "A3F"


class TestNormalizedCodeIsAcceptedByValidator:
    """The whole point: normalized inputs must pass :func:`_is_valid_format`."""

    def test_fullwidth_input_becomes_valid(self) -> None:
        assert _is_valid_format(_normalize_code("Ａ３Ｆ７Ｋ９")) is True

    def test_hyphenated_input_becomes_valid(self) -> None:
        assert _is_valid_format(_normalize_code("A3F-7K9")) is True

    def test_fullwidth_hyphenated_input_becomes_valid(self) -> None:
        assert _is_valid_format(_normalize_code("Ａ３Ｆ－７Ｋ９")) is True

    def test_em_dash_input_stays_invalid(self) -> None:
        # em-dash is not decomposed by NFKC, so the string keeps 7
        # characters and the format check rejects it. The parent gets
        # the usual invalid_format response and a chance to retry.
        assert _is_valid_format(_normalize_code("A3F—7K9")) is False

    def test_spaced_input_becomes_valid(self) -> None:
        assert _is_valid_format(_normalize_code("A 3 F 7 K 9")) is True

    def test_short_input_stays_invalid(self) -> None:
        assert _is_valid_format(_normalize_code("A3F")) is False

    def test_too_long_input_stays_invalid(self) -> None:
        assert _is_valid_format(_normalize_code("A3F7K9X")) is False

    def test_confusable_letters_stay_rejected(self) -> None:
        # CODE_ALPHABET excludes I/O/0/1 to avoid misreads. After NFKC
        # they still fail validation.
        assert _is_valid_format(_normalize_code("A3F7K0")) is False
        assert _is_valid_format(_normalize_code("A3F7K1")) is False
        assert _is_valid_format(_normalize_code("A3F7KO")) is False
        assert _is_valid_format(_normalize_code("A3F7KI")) is False


class TestInvitationConsume:
    def test_consume_uses_active_record_when_same_code_has_used_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            now = invitations._now_jst()
            (data_dir / "invitations.json").write_text(
                json.dumps(
                    {
                        "invitations": [
                            {
                                "code": "A3F7K9",
                                "student_user_id": "old-student",
                                "created_at": (now - timedelta(hours=2)).isoformat(),
                                "expires_at": (now + timedelta(hours=22)).isoformat(),
                                "used_at": (now - timedelta(hours=1)).isoformat(),
                                "used_by_parent_id": "old-parent",
                            },
                            {
                                "code": "A3F7K9",
                                "student_user_id": "active-student",
                                "created_at": now.isoformat(),
                                "expires_at": (now + timedelta(hours=24)).isoformat(),
                                "used_at": None,
                                "used_by_parent_id": None,
                            },
                        ]
                    },
                    indent=4,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(storage, "DATA_DIR", data_dir):
                student_id, err = invitations.consume("A3F7K9", "new-parent")

            assert err == "ok"
            assert student_id == "active-student"
            rows = json.loads(
                (data_dir / "invitations.json").read_text(encoding="utf-8")
            )["invitations"]
            assert rows[0]["used_by_parent_id"] == "old-parent"
            assert rows[1]["used_by_parent_id"] == "new-parent"

    def test_consume_uses_active_record_when_same_code_has_expired_history(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            now = invitations._now_jst()
            (data_dir / "invitations.json").write_text(
                json.dumps(
                    {
                        "invitations": [
                            {
                                "code": "A3F7K9",
                                "student_user_id": "expired-student",
                                "created_at": (now - timedelta(hours=30)).isoformat(),
                                "expires_at": (now - timedelta(hours=6)).isoformat(),
                                "used_at": None,
                                "used_by_parent_id": None,
                            },
                            {
                                "code": "A3F7K9",
                                "student_user_id": "active-student",
                                "created_at": now.isoformat(),
                                "expires_at": (now + timedelta(hours=24)).isoformat(),
                                "used_at": None,
                                "used_by_parent_id": None,
                            },
                        ]
                    },
                    indent=4,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(storage, "DATA_DIR", data_dir):
                student_id, err = invitations.consume("A3F7K9", "new-parent")

            assert err == "ok"
            assert student_id == "active-student"

    def test_generate_unique_code_rejects_any_existing_code(self) -> None:
        existing = [
            {
                "code": "A3F7K9",
                "used_at": "2026-07-01T00:00:00+09:00",
                "expires_at": "2026-07-02T00:00:00+09:00",
            },
            {
                "code": "B4G8LA",
                "used_at": None,
                "expires_at": "2026-07-02T00:00:00+09:00",
            },
        ]

        with patch.object(
            invitations,
            "generate_code",
            side_effect=["A3F7K9", "C5H9MB"],
        ):
            assert invitations._generate_unique_code(existing) == "C5H9MB"
