"""Unit tests for :func:`src.handlers.parent._normalize_code` (FR-P2).

The parent-facing invitation code redemption must accept fullwidth
digits/letters typed via iOS/Android IMEs, as well as incidental spaces
and hyphens, before format validation runs. See ``docs/04 §4.6``.

Style follows ``tests/test_posts.py``: no pytest fixtures, class-based.
"""

from __future__ import annotations

from src.handlers.parent import _is_valid_format, _normalize_code


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
