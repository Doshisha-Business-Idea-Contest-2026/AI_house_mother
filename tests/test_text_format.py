"""Unit tests for :mod:`src.utils.text_format`.

These cover the life-consultation reply formatting (Issue #13):
Markdown residue removal, blank-line normalisation, and block joining.
The module depends only on ``re`` so the tests run without the LINE /
Gemini stack (and without ``fcntl``, which is unavailable on Windows).
"""
from src.utils import text_format


class TestNormalizeMarkdown:
    def test_unwraps_bold_asterisks(self) -> None:
        assert text_format.normalize_markdown("これは**強調**です") == "これは強調です"

    def test_unwraps_bold_underscores(self) -> None:
        assert text_format.normalize_markdown("__重要__な点") == "重要な点"

    def test_unwraps_inline_code(self) -> None:
        assert text_format.normalize_markdown("`code` を実行") == "code を実行"

    def test_converts_dash_bullet_to_fullwidth(self) -> None:
        assert text_format.normalize_markdown("- 項目A") == "・項目A"

    def test_converts_asterisk_bullet_to_fullwidth(self) -> None:
        assert text_format.normalize_markdown("* 項目B") == "・項目B"

    def test_drops_heading_marker(self) -> None:
        assert text_format.normalize_markdown("# 見出し") == "見出し"

    def test_removes_stray_markers(self) -> None:
        assert text_format.normalize_markdown("未閉じ**の強調") == "未閉じの強調"

    def test_empty_string(self) -> None:
        assert text_format.normalize_markdown("") == ""

    def test_plain_text_unchanged(self) -> None:
        assert text_format.normalize_markdown("普通の文章です。") == "普通の文章です。"


class TestCollapseBlankLines:
    def test_collapses_three_or_more_newlines(self) -> None:
        assert text_format.collapse_blank_lines("A\n\n\n\nB") == "A\n\nB"

    def test_keeps_single_blank_line(self) -> None:
        assert text_format.collapse_blank_lines("A\n\nB") == "A\n\nB"

    def test_strips_trailing_spaces_and_edges(self) -> None:
        # Trailing spaces are removed per line and outer whitespace stripped;
        # interior leading indentation is intentionally preserved (rstrip).
        assert text_format.collapse_blank_lines("\nA  \n\n\nB  \n") == "A\n\nB"


class TestJoinBlocks:
    def test_joins_three_blocks_with_single_blank_line(self) -> None:
        result = text_format.join_blocks(["導入部です。", "本文です。", "締めです。"])
        assert result == "導入部です。\n\n本文です。\n\n締めです。"

    def test_body_only(self) -> None:
        assert text_format.join_blocks(["本文だけ"]) == "本文だけ"

    def test_drops_empty_blocks(self) -> None:
        assert text_format.join_blocks(["", "本文", "   "]) == "本文"

    def test_normalises_block_internal_newlines(self) -> None:
        # Disclaimer constant ends with "\n\n"; followup starts with "\n\n".
        # After strip + join they must collapse to a single blank line.
        result = text_format.join_blocks(["注意書き\n\n", "本文", "\n\n補足"])
        assert result == "注意書き\n\n本文\n\n補足"
