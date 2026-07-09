"""Unit tests for :mod:`src.templates.flex.style` (T4.13).

Cover the shared white/airy design helpers and the category-colour token so
the accent-bar structure stays consistent across builders. Style follows
``tests/test_activity_carousel.py``: no pytest dependency.
"""

from src.templates.flex import style


def _walk(node: object) -> list[dict]:
    """Yield every dict node in a Flex tree (depth-first)."""
    found: list[dict] = []
    if isinstance(node, dict):
        found.append(node)
        for value in node.values():
            found.extend(_walk(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_walk(item))
    return found


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
        assert bar["width"] == style.ACCENT_WIDTH
        assert bar["backgroundColor"] == "#123456"
        assert bar["cornerRadius"] == style.RADIUS_BAR
        assert bar["contents"] == []

    def test_custom_width_is_respected(self) -> None:
        assert style.accent_bar("#000000", width="8px")["width"] == "8px"


class TestHairline:
    def test_is_a_grey_separator(self) -> None:
        line = style.hairline()
        assert line == {"type": "separator", "color": style.SEPARATOR}


class TestHeadingRow:
    def test_has_leading_accent_bar_and_navy_title(self) -> None:
        row = style.heading_row("見出し", accent="#abcdef")
        assert row["layout"] == "horizontal"
        bar, text = row["contents"]
        assert bar["backgroundColor"] == "#abcdef"
        assert text["type"] == "text"
        assert text["text"] == "見出し"
        assert text["weight"] == "bold"
        assert text["color"] == style.NAVY


class TestWhiteHeader:
    def test_white_background_with_accent_bar_and_navy_rule(self) -> None:
        header = style.white_header("タイトル", subtitle="小見出し", accent="#C9A227")
        assert header["type"] == "box"
        assert header["backgroundColor"] == style.WHITE
        # subtitle line is present
        texts = [n["text"] for n in _walk(header) if n.get("type") == "text"]
        assert "小見出し" in texts and "タイトル" in texts
        # the accent bar carries the (gold) accent colour
        bars = [n for n in _walk(header) if n.get("width") == style.ACCENT_WIDTH]
        assert bars and bars[0]["backgroundColor"] == "#C9A227"
        # a navy hairline separates header from body
        seps = [n for n in _walk(header) if n.get("type") == "separator"]
        assert any(s.get("color") == style.NAVY for s in seps)

    def test_accepts_multiple_subtitle_lines(self) -> None:
        header = style.white_header("T", subtitle=["A", "B"])
        texts = [n["text"] for n in _walk(header) if n.get("type") == "text"]
        assert "A" in texts and "B" in texts and "T" in texts


class TestLabelValue:
    def test_stacks_weak_label_over_bold_value(self) -> None:
        box = style.label_value("大学", "同志社大学")
        label, value = box["contents"]
        assert label["text"] == "大学" and label["color"] == style.TEXT_WEAK
        assert value["text"] == "同志社大学" and value["weight"] == "bold"


class TestBubble:
    def test_skeleton_has_mega_size_and_white_body(self) -> None:
        header = style.white_header("x")
        bubble = style.bubble(header=header, body=[{"type": "text", "text": "y"}])
        assert bubble["type"] == "bubble"
        assert bubble["size"] == "mega"
        assert bubble["body"]["backgroundColor"] == style.WHITE
        assert "footer" not in bubble

    def test_footer_included_when_provided(self) -> None:
        header = style.white_header("x")
        button = {"type": "button", "action": {"type": "postback", "data": "x"}}
        bubble = style.bubble(header=header, body=[], footer=[button])
        assert bubble["footer"]["contents"] == [button]
