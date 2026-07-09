"""Unit tests for :mod:`src.templates.flex.style` (T4.13).

Cover the shared design helpers and the category-colour token so the
card-in-card structure stays consistent across builders. Style follows
``tests/test_activity_carousel.py``: no pytest dependency.
"""

from src.templates.flex import style


class TestCategoryColor:
    def test_known_type_returns_mapped_color(self) -> None:
        assert style.get_category_color("event") == style.CATEGORY_COLORS["event"]

    def test_unknown_type_falls_back_to_navy(self) -> None:
        assert style.get_category_color("does-not-exist") == style.NAVY

    def test_sponsored_keeps_gold(self) -> None:
        # FR-S9: the PR slot must stay visually distinct.
        assert style.CATEGORY_COLORS["sponsored"] == "#C9A227"

    def test_generated_is_navy(self) -> None:
        assert style.CATEGORY_COLORS["generated"] == style.NAVY


class TestAccentBar:
    def test_is_a_thin_rounded_box(self) -> None:
        bar = style.accent_bar("#123456")
        assert bar["type"] == "box"
        assert bar["width"] == "5px"
        assert bar["backgroundColor"] == "#123456"
        assert bar["cornerRadius"] == style.RADIUS_BAR
        assert bar["contents"] == []


class TestCard:
    def test_wraps_contents_in_rounded_tone_box(self) -> None:
        child = {"type": "text", "text": "hello"}
        card = style.card([child])
        assert card["type"] == "box"
        assert card["backgroundColor"] == style.CARD_BG
        assert card["cornerRadius"] == style.RADIUS_CARD
        assert card["paddingAll"] == style.PAD_CARD
        assert card["contents"] == [child]

    def test_custom_background_is_respected(self) -> None:
        card = style.card([], bg=style.TONE_BG)
        assert card["backgroundColor"] == style.TONE_BG


class TestHeaderBox:
    def test_keeps_background_color_at_top_level(self) -> None:
        header = style.header_box("#00579C", [{"type": "text", "text": "t"}])
        assert header["type"] == "box"
        assert header["backgroundColor"] == "#00579C"
        assert header["paddingAll"] == style.PAD_HEADER


class TestSectionHeading:
    def test_has_leading_accent_bar_and_bold_text(self) -> None:
        heading = style.section_heading("見出し", bar_color="#abcdef")
        assert heading["layout"] == "horizontal"
        bar, text = heading["contents"]
        assert bar["backgroundColor"] == "#abcdef"
        assert text["type"] == "text"
        assert text["text"] == "見出し"
        assert text["weight"] == "bold"


class TestBubble:
    def test_skeleton_has_mega_size_and_white_body(self) -> None:
        header = style.header_box(style.NAVY, [])
        bubble = style.bubble(header=header, body=[{"type": "text", "text": "x"}])
        assert bubble["type"] == "bubble"
        assert bubble["size"] == "mega"
        assert bubble["body"]["backgroundColor"] == style.WHITE
        assert "footer" not in bubble

    def test_footer_included_when_provided(self) -> None:
        header = style.header_box(style.NAVY, [])
        button = {"type": "button", "action": {"type": "postback", "data": "x"}}
        bubble = style.bubble(header=header, body=[], footer=[button])
        assert bubble["footer"]["contents"] == [button]
