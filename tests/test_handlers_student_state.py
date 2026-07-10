"""Regression tests for student conversation state routing."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


class _StubEvent(SimpleNamespace):
    """Minimal MessageEvent/PostbackEvent shape needed by student handlers."""


def _message_event(
    user_id: str = "Ustudent-state-001", text: str = "長い生活相談です"
) -> _StubEvent:
    return _StubEvent(
        reply_token="rt-state",
        source=SimpleNamespace(user_id=user_id),
        message=SimpleNamespace(text=text),
    )


def _postback_event(user_id: str = "Ustudent-state-001") -> _StubEvent:
    return _StubEvent(
        reply_token="rt-state",
        source=SimpleNamespace(user_id=user_id),
        postback=SimpleNamespace(data="menu:want_events"),
    )


class TestWantToDoStateReset:
    def test_failed_activity_branch_clears_stale_session(self) -> None:
        from src.handlers import student as student_mod

        with (
            patch.object(student_mod.session, "clear_state") as clear_mock,
            patch.object(student_mod.session, "set_state") as set_state_mock,
            patch.object(student_mod.profiles, "get_profile") as profile_mock,
            patch.object(student_mod.usage_stats, "record") as record_mock,
            patch.object(student_mod, "show_loading") as loading_mock,
            patch.object(student_mod.gemini, "propose_activities") as propose_mock,
            patch.object(student_mod, "push_text") as push_mock,
        ):
            profile_mock.return_value = {"interests": ["地域活動"]}
            propose_mock.return_value = []

            student_mod.handle_want_events(_postback_event("Ustudent-state-002"))

            clear_mock.assert_called_once_with("Ustudent-state-002")
            record_mock.assert_called_once_with("Ustudent-state-002", "activity")
            loading_mock.assert_called_once_with("Ustudent-state-002")
            push_mock.assert_called_once()
            set_state_mock.assert_not_called()

    def test_successful_activity_branch_does_not_create_dead_session_state(
        self,
    ) -> None:
        from src.handlers import student as student_mod

        with (
            patch.object(student_mod.session, "clear_state") as clear_mock,
            patch.object(student_mod.session, "set_state") as set_state_mock,
            patch.object(student_mod.profiles, "get_profile") as profile_mock,
            patch.object(student_mod.usage_stats, "record"),
            patch.object(student_mod, "show_loading"),
            patch.object(student_mod.gemini, "propose_activities") as propose_mock,
            patch.object(student_mod.activity_store, "remember") as remember_mock,
            patch.object(student_mod.sponsored, "match_for_profile") as sponsored_mock,
            patch.object(student_mod, "build_activity_carousel") as carousel_mock,
            patch.object(student_mod, "push_flex") as push_flex_mock,
            patch.object(student_mod, "push_text") as push_text_mock,
        ):
            profile = {"interests": ["地域活動"]}
            activities = [{"title": "地域清掃", "reference_type": "event"}]
            profile_mock.return_value = profile
            propose_mock.return_value = activities
            remember_mock.return_value = ["key123"]
            sponsored_mock.return_value = None
            carousel_mock.return_value = {"type": "bubble"}

            student_mod.handle_want_events(_postback_event("Ustudent-state-003"))

            clear_mock.assert_called_once_with("Ustudent-state-003")
            remember_mock.assert_called_once_with("Ustudent-state-003", activities)
            set_state_mock.assert_not_called()
            push_flex_mock.assert_called_once()
            push_text_mock.assert_called_once()


class TestLifeConsultationProfileGate:
    def test_missing_profile_prompts_registration_without_gemini_call(self) -> None:
        from src.handlers import student as student_mod

        with (
            patch.object(student_mod.profiles, "get_profile") as profile_mock,
            patch.object(student_mod.session, "clear_state") as clear_mock,
            patch.object(student_mod.usage_stats, "record") as record_mock,
            patch.object(student_mod.gemini, "answer_life_question") as gemini_mock,
            patch.object(student_mod, "reply_text") as reply_mock,
            patch.object(student_mod, "profile_start_quick_reply") as qr_mock,
        ):
            profile_mock.return_value = None
            qr_mock.return_value = "PROFILE_QR"

            student_mod.handle_life_consultation(
                _message_event("Ustudent-state-004", "大学生活が不安で相談したいです")
            )

            clear_mock.assert_called_once_with("Ustudent-state-004")
            record_mock.assert_not_called()
            gemini_mock.assert_not_called()
            reply_mock.assert_called_once()
            _, kwargs = reply_mock.call_args
            assert kwargs.get("quick_reply") == "PROFILE_QR"
