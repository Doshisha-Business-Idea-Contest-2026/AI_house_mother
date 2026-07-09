"""Unit tests for :mod:`src.templates.flex.activity_carousel` (Phase 3).

These cover NFR-Truth-4 for the want-to-do consultation Flex carousel:
bubbles that represent a real-world seed record (``store`` / ``event`` /
``volunteer``) must render a generic freshness caveat at the body tail,
while purely AI-generated proposals must not. See
``docs/04_functional_spec.md §4.3`` and §4.4.

Style follows ``tests/test_text_format.py``: no pytest dependency.
"""

from src.templates.flex import activity_carousel


def _make_activity(reference_type: str) -> dict[str, object]:
    return {
        "title": "サンプル提案",
        "summary": "先輩の投稿からピックアップした活動です。",
        "location": "上京区",
        "when": "毎月第2土曜",
        "why_recommend": "プロフィールにマッチ。",
        "reference_type": reference_type,
    }


def _walk_texts(node: object) -> list[str]:
    """Recursively collect every ``text`` string under a Flex node.

    The card-in-card redesign (T4.13) nests body text inside rounded card
    boxes, so a flat scan of ``body.contents`` no longer sees it.
    """
    texts: list[str] = []
    if isinstance(node, dict):
        if node.get("type") == "text" and "text" in node:
            texts.append(node["text"])
        for value in node.values():
            texts.extend(_walk_texts(value))
    elif isinstance(node, list):
        for item in node:
            texts.extend(_walk_texts(item))
    return texts


def _collect_texts(bubble: dict[str, object]) -> list[str]:
    return _walk_texts(bubble["body"])  # type: ignore[index]


class TestFreshnessNote:
    def test_store_bubble_appends_freshness_note(self) -> None:
        bubble = activity_carousel._build_bubble(
            index=1, activity=_make_activity("store"), key="ABC"
        )
        texts = _collect_texts(bubble)
        assert activity_carousel._FRESHNESS_NOTE_TEXT in texts

    def test_event_bubble_appends_freshness_note(self) -> None:
        bubble = activity_carousel._build_bubble(
            index=1, activity=_make_activity("event"), key="ABC"
        )
        texts = _collect_texts(bubble)
        assert activity_carousel._FRESHNESS_NOTE_TEXT in texts

    def test_volunteer_bubble_appends_freshness_note(self) -> None:
        bubble = activity_carousel._build_bubble(
            index=1, activity=_make_activity("volunteer"), key="ABC"
        )
        texts = _collect_texts(bubble)
        assert activity_carousel._FRESHNESS_NOTE_TEXT in texts

    def test_generated_bubble_omits_freshness_note(self) -> None:
        bubble = activity_carousel._build_bubble(
            index=1, activity=_make_activity("generated"), key="ABC"
        )
        texts = _collect_texts(bubble)
        assert activity_carousel._FRESHNESS_NOTE_TEXT not in texts

    def test_senior_post_bubble_omits_freshness_note(self) -> None:
        # 先輩投稿由来は seed の実在情報ではないので、鮮度注記は付けない。
        bubble = activity_carousel._build_bubble(
            index=1, activity=_make_activity("senior_post"), key="ABC"
        )
        texts = _collect_texts(bubble)
        assert activity_carousel._FRESHNESS_NOTE_TEXT not in texts

    def test_static_fallback_bubble_omits_freshness_note(self) -> None:
        bubble = activity_carousel._build_bubble(
            index=1, activity=_make_activity("static_fallback"), key="ABC"
        )
        texts = _collect_texts(bubble)
        assert activity_carousel._FRESHNESS_NOTE_TEXT not in texts


def _make_sponsored() -> dict[str, object]:
    return {
        "sponsor_id": "SPN001",
        "company_name": "テスト社（架空）",
        "title": "選考直結ハッカソン",
        "summary": "2 日間のハッカソン。",
        "apply_url": "https://example.com/apply",
        "event_date": "2026-11-15",
        "deadline": "2026-10-31",
    }


def _header_texts(bubble: dict[str, object]) -> list[str]:
    # The white header nests the title inside a heading row, so scan
    # recursively (T4.13 white/airy redesign).
    return _walk_texts(bubble["header"])  # type: ignore[index]


def _header_accent_color(bubble: dict[str, object]) -> str | None:
    """Return the colour of the header's left accent bar, if any."""
    header = bubble["header"]  # type: ignore[index]

    def find(node: object) -> str | None:
        if isinstance(node, dict):
            if (
                node.get("type") == "box"
                and node.get("width")
                and node.get("contents") == []
            ):
                return node.get("backgroundColor")
            for value in node.values():
                got = find(value)
                if got is not None:
                    return got
        elif isinstance(node, list):
            for item in node:
                got = find(item)
                if got is not None:
                    return got
        return None

    return find(header)


def _footer_actions(bubble: dict[str, object]) -> list[dict[str, object]]:
    footer = bubble["footer"]  # type: ignore[index]
    return [c["action"] for c in footer["contents"] if c.get("type") == "button"]


class TestSponsoredBubble:
    def test_header_carries_pr_badge_and_company(self) -> None:
        bubble = activity_carousel._build_sponsored_bubble(_make_sponsored())
        texts = _header_texts(bubble)
        assert activity_carousel._SPONSORED_BADGE_TEXT in texts
        assert "テスト社（架空）" in texts

    def test_body_has_disclosure_and_freshness_note(self) -> None:
        bubble = activity_carousel._build_sponsored_bubble(_make_sponsored())
        texts = _collect_texts(bubble)
        assert activity_carousel._SPONSORED_DISCLOSURE_TEXT in texts
        assert activity_carousel._FRESHNESS_NOTE_TEXT in texts

    def test_footer_has_uri_and_interest_postback(self) -> None:
        bubble = activity_carousel._build_sponsored_bubble(_make_sponsored())
        actions = _footer_actions(bubble)
        uri_actions = [a for a in actions if a.get("type") == "uri"]
        postbacks = [a for a in actions if a.get("type") == "postback"]
        assert uri_actions and uri_actions[0]["uri"] == "https://example.com/apply"
        assert postbacks and postbacks[0]["data"] == "sponsored:interest:SPN001"

    def test_missing_apply_url_drops_uri_button(self) -> None:
        entry = _make_sponsored()
        entry["apply_url"] = ""
        bubble = activity_carousel._build_sponsored_bubble(entry)
        actions = _footer_actions(bubble)
        assert all(a.get("type") != "uri" for a in actions)

    def test_uses_gold_accent_bar(self) -> None:
        # White/airy redesign (T4.13): the gold PR distinction now lives in
        # the header accent bar rather than a filled header background.
        bubble = activity_carousel._build_sponsored_bubble(_make_sponsored())
        assert (
            _header_accent_color(bubble)
            == activity_carousel._CATEGORY_COLORS["sponsored"]
        )


class TestCarouselWithSponsored:
    def test_sponsored_is_prepended_as_first_bubble(self) -> None:
        activities = [_make_activity("generated"), _make_activity("event")]
        carousel = activity_carousel.build_activity_carousel(
            activities, ["K1", "K2"], sponsored=_make_sponsored()
        )
        bubbles = carousel["contents"]  # type: ignore[index]
        assert len(bubbles) == 3  # 1 sponsored + 2 organic
        first_texts = _header_texts(bubbles[0])
        assert activity_carousel._SPONSORED_BADGE_TEXT in first_texts

    def test_single_activity_plus_sponsored_is_carousel(self) -> None:
        # Without sponsored a single activity returns a bare bubble; adding
        # a sponsored entry must promote it to a carousel.
        carousel = activity_carousel.build_activity_carousel(
            [_make_activity("generated")], ["K1"], sponsored=_make_sponsored()
        )
        assert carousel["type"] == "carousel"
        assert len(carousel["contents"]) == 2  # type: ignore[index]

    def test_no_sponsored_keeps_existing_behaviour(self) -> None:
        bubble = activity_carousel.build_activity_carousel(
            [_make_activity("generated")], ["K1"]
        )
        assert bubble["type"] == "bubble"
