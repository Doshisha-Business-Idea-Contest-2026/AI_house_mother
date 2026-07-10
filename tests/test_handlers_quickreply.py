"""Terminal-reply Quick Reply invariant (docs/04 §3.4).

Wrong-role and session-expired branches must attach the current user's
main-menu Quick Reply, or a mistap strands the user without any next
affordance (rich menu is not part of the MVP). This test locks in the
three call-sites that were missing that argument.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch


class _StubEvent(SimpleNamespace):
    """Minimal MessageEvent / PostbackEvent shape needed by the handlers."""


def _message_event(user_id: str = "Uparent001") -> _StubEvent:
    return _StubEvent(
        reply_token="rt-parent",
        source=SimpleNamespace(user_id=user_id),
        message=SimpleNamespace(text="相談"),
    )


def _postback_event(user_id: str = "Ustudent001") -> _StubEvent:
    return _StubEvent(
        reply_token="rt-student",
        source=SimpleNamespace(user_id=user_id),
        postback=SimpleNamespace(data="profile:confirm:yes"),
    )


class TestRequireRoleWrongRoleAttachesQuickReply:
    """message._require_role must not send a terminal reply without a QR."""

    def test_wrong_role_reply_has_quick_reply_for_actual_role(self) -> None:
        from src.handlers import message as message_mod

        with (
            patch.object(message_mod, "users") as users_mock,
            patch.object(message_mod, "reply_text") as reply_mock,
            patch.object(message_mod, "main_menu_quick_reply") as qr_mock,
        ):
            users_mock.get_role.return_value = "parent"
            qr_mock.return_value = "PARENT_MENU_QR"

            ok = message_mod._require_role(
                _message_event("Uparent001"), "Uparent001", "student"
            )

            assert ok is False
            reply_mock.assert_called_once()
            _, kwargs = reply_mock.call_args
            assert kwargs.get("quick_reply") == "PARENT_MENU_QR"
            qr_mock.assert_called_once_with("parent")

    def test_role_none_still_uses_welcome_flex_no_regression(self) -> None:
        from src.handlers import message as message_mod

        with (
            patch.object(message_mod, "users") as users_mock,
            patch.object(message_mod, "reply_flex") as flex_mock,
            patch.object(message_mod, "build_welcome_message") as welcome_mock,
        ):
            users_mock.get_role.return_value = None
            welcome_mock.return_value = ("alt", "contents", "welcome-qr")

            ok = message_mod._require_role(
                _message_event("Unew001"), "Unew001", "student"
            )

            assert ok is False
            flex_mock.assert_called_once()
            # Lock in that the welcome QR really rides along, otherwise
            # the whole point of #42 could silently regress on this
            # branch.
            _, kwargs = flex_mock.call_args
            assert kwargs.get("quick_reply") == "welcome-qr"

    def test_wrong_role_symmetric_student_calling_parent_op(self) -> None:
        """Mirror case of ``test_wrong_role_reply_has_quick_reply_for_actual_role``.

        Prevents a ``label = "学生" if required == "student" else "保護者"``
        left/right swap or a role/required argument mixup from being
        detected only on one side of the pair.
        """
        from src.handlers import message as message_mod

        with (
            patch.object(message_mod, "users") as users_mock,
            patch.object(message_mod, "reply_text") as reply_mock,
            patch.object(message_mod, "main_menu_quick_reply") as qr_mock,
        ):
            users_mock.get_role.return_value = "student"
            qr_mock.return_value = "STUDENT_MENU_QR"

            ok = message_mod._require_role(
                _message_event("Ustudent001"), "Ustudent001", "parent"
            )

            assert ok is False
            reply_mock.assert_called_once()
            args, kwargs = reply_mock.call_args
            assert kwargs.get("quick_reply") == "STUDENT_MENU_QR"
            qr_mock.assert_called_once_with("student")
            # And confirm the label baked into the copy targets the
            # right side of the ternary.
            assert "保護者アカウント向けです" in args[1]


class TestProfilePostbackExpiredAttachesQuickReply:
    """student.handle_profile_postback: state=None branch must attach QR."""

    def test_state_none_reply_carries_main_menu_quick_reply(self) -> None:
        from src.handlers import student as student_mod

        with (
            patch.object(student_mod, "session") as session_mock,
            patch.object(student_mod, "users") as users_mock,
            patch.object(student_mod, "reply_text") as reply_mock,
            patch.object(student_mod, "main_menu_quick_reply") as qr_mock,
        ):
            session_mock.get_state.return_value = None
            users_mock.get_role.return_value = "student"
            qr_mock.return_value = "STUDENT_MENU_QR"

            student_mod.handle_profile_postback(
                _postback_event("Ustudent001"), "profile:grade:B1"
            )

            reply_mock.assert_called_once()
            _, kwargs = reply_mock.call_args
            assert kwargs.get("quick_reply") == "STUDENT_MENU_QR"
            qr_mock.assert_called_once_with("student")

    def test_role_unknown_falls_back_to_student(self) -> None:
        from src.handlers import student as student_mod

        with (
            patch.object(student_mod, "session") as session_mock,
            patch.object(student_mod, "users") as users_mock,
            patch.object(student_mod, "reply_text") as _reply_mock,
            patch.object(student_mod, "main_menu_quick_reply") as qr_mock,
        ):
            session_mock.get_state.return_value = None
            users_mock.get_role.return_value = None

            student_mod.handle_profile_postback(
                _postback_event("Ustudent002"), "profile:grade:B1"
            )

            qr_mock.assert_called_once_with("student")


class TestProfileConfirmYesReTapAttachesQuickReply:
    """student.handle_profile_postback: profile:confirm:yes re-tap branch."""

    def test_re_tap_without_confirm_state_carries_quick_reply(self) -> None:
        from src.handlers import student as student_mod

        with (
            patch.object(student_mod, "session") as session_mock,
            patch.object(student_mod, "users") as users_mock,
            patch.object(student_mod, "reply_text") as reply_mock,
            patch.object(student_mod, "main_menu_quick_reply") as qr_mock,
            patch.object(student_mod, "_finalize_profile") as finalize_mock,
        ):
            # State exists but is not profile.confirm -> re-tap path.
            session_mock.get_state.return_value = {"state": "profile.grade"}
            users_mock.get_role.return_value = "student"
            qr_mock.return_value = "STUDENT_MENU_QR"

            student_mod.handle_profile_postback(
                _postback_event("Ustudent003"), "profile:confirm:yes"
            )

            finalize_mock.assert_not_called()
            reply_mock.assert_called_once()
            _, kwargs = reply_mock.call_args
            assert kwargs.get("quick_reply") == "STUDENT_MENU_QR"
            # Session state must not be cleared on the re-tap: the
            # student is mid-flow and losing their profile.grade context
            # would strand them. Pins #93 (audit L2).
            session_mock.clear_state.assert_not_called()
