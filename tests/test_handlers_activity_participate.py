"""FR-S4 「参加した」 → FR-S6 post wizard bridging (docs/04 §4.3).

Locks in three invariants after fixing #43:

1. Tapping "参加した" opens the post wizard at ``post.category``.
2. Only ``source_activity_title`` / ``source_activity_key`` land in the
   session context — no summary / area / period_raw pre-fill, because
   ``_handle_post_field_text`` would just overwrite them and give the
   student the illusion of pre-fill without the effect.
3. ``_build_post_confirmation_text`` echoes the source activity as a
   "🔗 参照した活動" line when the context carries it, and stays
   backward-compatible otherwise.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


class _StubEvent(SimpleNamespace):
    """Minimal PostbackEvent shape needed by the handler."""


def _postback_event(user_id: str = "Ustudent-part-001") -> _StubEvent:
    return _StubEvent(
        reply_token="rt-part",
        source=SimpleNamespace(user_id=user_id),
        postback=SimpleNamespace(data="activity:part:key123"),
    )


class TestParticipatedEntersPostWizard:
    def test_activity_missing_returns_error_and_no_state_change(self) -> None:
        from src.handlers import student as student_mod

        with (
            patch.object(student_mod.activity_store, "resolve") as resolve_mock,
            patch.object(student_mod, "session") as session_mock,
            patch.object(student_mod, "reply_text") as reply_mock,
        ):
            resolve_mock.return_value = None

            student_mod.handle_activity_participated(_postback_event(), "gone")

            session_mock.set_state.assert_not_called()
            reply_mock.assert_called_once()
            args, _ = reply_mock.call_args
            assert "復元できませんでした" in args[1]

    def test_participated_sets_post_category_state_with_source_meta(self) -> None:
        from src.handlers import student as student_mod

        with (
            patch.object(student_mod.activity_store, "resolve") as resolve_mock,
            patch.object(student_mod, "session") as session_mock,
            patch.object(student_mod, "reply_text") as reply_mock,
            patch.object(student_mod, "post_category_quick_reply") as qr_mock,
        ):
            resolve_mock.return_value = {
                "title": "地域清掃ボランティア",
                "summary": "1 時間だけ参加できる",
                "location": "上京区",
                "when": "毎週土曜",
                "reference_type": "event",
            }
            qr_mock.return_value = "CAT_QR"

            student_mod.handle_activity_participated(
                _postback_event("Ustudent-part-002"), "key-abc"
            )

            session_mock.set_state.assert_called_once()
            args, kwargs = session_mock.set_state.call_args
            assert args[0] == "Ustudent-part-002"
            assert args[1] == "post.category"
            # Only source meta lands — no summary/area/period_raw pre-fill.
            assert kwargs == {
                "source_activity_title": "地域清掃ボランティア",
                "source_activity_key": "key-abc",
            }
            for forbidden in ("summary", "area", "period_raw"):
                assert forbidden not in kwargs

            reply_mock.assert_called_once()
            _, reply_kwargs = reply_mock.call_args
            assert reply_kwargs.get("quick_reply") == "CAT_QR"

    def test_participated_reply_mentions_activity_title(self) -> None:
        from src.handlers import student as student_mod

        with (
            patch.object(student_mod.activity_store, "resolve") as resolve_mock,
            patch.object(student_mod, "session") as _session_mock,
            patch.object(student_mod, "reply_text") as reply_mock,
            patch.object(student_mod, "post_category_quick_reply"),
        ):
            resolve_mock.return_value = {"title": "河原町 UNIQLO 手伝い"}

            student_mod.handle_activity_participated(_postback_event(), "key-xyz")

            args, _ = reply_mock.call_args
            assert "河原町 UNIQLO 手伝い" in args[1]
            assert "カテゴリを選んで" in args[1]


class TestPostConfirmationTextShowsSourceActivity:
    def _min_ctx(self) -> dict[str, object]:
        return {
            "category": "volunteer",
            "title": "掃除に参加した話",
            "summary": "地元の児童公園を掃除した",
            "learned": "小さな積み重ねが大事",
        }

    def test_no_source_activity_yields_no_reference_line(self) -> None:
        from src.handlers.student import _build_post_confirmation_text

        text = _build_post_confirmation_text(self._min_ctx())
        assert "🔗 参照した活動" not in text
        assert text.startswith("内容を確認してください")

    def test_source_activity_prepends_reference_line(self) -> None:
        from src.handlers.student import _build_post_confirmation_text

        ctx = self._min_ctx()
        ctx["source_activity_title"] = "地域清掃ボランティア"
        text = _build_post_confirmation_text(ctx)

        first_line = text.splitlines()[0]
        assert first_line == "🔗 参照した活動: 「地域清掃ボランティア」"
        assert "内容を確認してください" in text

    def test_blank_source_activity_is_ignored(self) -> None:
        from src.handlers.student import _build_post_confirmation_text

        ctx = self._min_ctx()
        ctx["source_activity_title"] = "   "
        text = _build_post_confirmation_text(ctx)
        assert "🔗 参照した活動" not in text
