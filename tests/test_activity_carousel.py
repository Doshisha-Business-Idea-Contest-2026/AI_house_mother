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


def _collect_texts(bubble: dict[str, object]) -> list[str]:
    body = bubble["body"]  # type: ignore[index]
    contents = body["contents"]  # type: ignore[index]
    return [c["text"] for c in contents if c.get("type") == "text"]


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
