"""Helpers for replying and pushing messages via the LINE Messaging API.

All four wrappers accept an optional ``sender: SenderPreset`` argument
implementing the "Sender switch" spec (docs/04 §3.5). When omitted or
``None`` the message falls back to the ``friendly`` preset so existing
call sites keep the same visual identity without changes.
"""
import logging
from typing import Literal, Optional

from linebot.v3.messaging import (
    ApiClient,
    FlexContainer,
    FlexMessage,
    MessagingApi,
    PushMessageRequest,
    QuickReply,
    ReplyMessageRequest,
    Sender,
    TextMessage,
)

from src.config import SENDER_PRESETS, configuration

logger = logging.getLogger(__name__)

SenderPreset = Literal["friendly", "system", "notify"]
_DEFAULT_PRESET: SenderPreset = "friendly"


def _build_sender(preset: SenderPreset | None) -> Sender:
    """Return the ``Sender`` object for ``preset`` (defaults to friendly)."""
    key = preset or _DEFAULT_PRESET
    try:
        name, icon_url = SENDER_PRESETS[key]
    except KeyError:
        logger.warning("Unknown sender preset %r, falling back to %s", preset, _DEFAULT_PRESET)
        name, icon_url = SENDER_PRESETS[_DEFAULT_PRESET]
    return Sender(name=name, icon_url=icon_url)


def reply_text(
    reply_token: str,
    text: str,
    quick_reply: Optional[QuickReply] = None,
    sender: SenderPreset | None = None,
) -> None:
    """Reply with a plain text message.

    Args:
        reply_token: Token from the incoming LINE event.
        text: Message body.
        quick_reply: Optional Quick Reply attached to the message.
        sender: Sender switch preset. Defaults to ``"friendly"``.
    """
    message = TextMessage(text=text)
    if quick_reply is not None:
        message.quick_reply = quick_reply
    message.sender = _build_sender(sender)

    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[message])
            )
    except Exception:
        logger.exception("reply_text failed")


def reply_flex(
    reply_token: str,
    alt_text: str,
    contents: dict,
    quick_reply: Optional[QuickReply] = None,
    sender: SenderPreset | None = None,
) -> None:
    """Reply with a Flex message.

    Args:
        reply_token: Token from the incoming LINE event.
        alt_text: Fallback text shown in notifications.
        contents: Flex message contents (bubble or carousel dict).
        quick_reply: Optional Quick Reply attached to the message.
        sender: Sender switch preset. Defaults to ``"friendly"``.
    """
    message = FlexMessage(alt_text=alt_text, contents=FlexContainer.from_dict(contents))
    if quick_reply is not None:
        message.quick_reply = quick_reply
    message.sender = _build_sender(sender)

    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=[message])
            )
    except Exception:
        logger.exception("reply_flex failed")


def push_text(
    line_user_id: str,
    text: str,
    quick_reply: Optional[QuickReply] = None,
    raise_on_error: bool = False,
    sender: SenderPreset | None = None,
) -> None:
    """Push a plain text message to ``line_user_id``.

    Args:
        line_user_id: Recipient LINE user id.
        text: Message body.
        quick_reply: Optional Quick Reply attached to the message.
        raise_on_error: When ``True`` re-raise any exception raised by
            the LINE SDK so the caller can count failures. Defaults to
            ``False`` for the fire-and-forget style used by the
            interactive handlers.
        sender: Sender switch preset. Defaults to ``"friendly"``.
    """
    message = TextMessage(text=text)
    if quick_reply is not None:
        message.quick_reply = quick_reply
    message.sender = _build_sender(sender)
    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.push_message(
                PushMessageRequest(to=line_user_id, messages=[message])
            )
    except Exception:
        logger.exception("push_text failed")
        if raise_on_error:
            raise


def push_flex(
    line_user_id: str,
    alt_text: str,
    contents: dict,
    quick_reply: Optional[QuickReply] = None,
    raise_on_error: bool = False,
    sender: SenderPreset | None = None,
) -> None:
    """Push a Flex message to ``line_user_id``.

    Args:
        line_user_id: Recipient LINE user id.
        alt_text: Fallback text shown in notifications.
        contents: Flex message contents (bubble or carousel dict).
        quick_reply: Optional Quick Reply attached to the message.
        raise_on_error: When ``True`` re-raise any exception raised by
            the LINE SDK so the caller can count failures. Defaults to
            ``False`` for the fire-and-forget style used by the
            interactive handlers.
        sender: Sender switch preset. Defaults to ``"friendly"``.
    """
    message = FlexMessage(alt_text=alt_text, contents=FlexContainer.from_dict(contents))
    if quick_reply is not None:
        message.quick_reply = quick_reply
    message.sender = _build_sender(sender)
    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.push_message(
                PushMessageRequest(to=line_user_id, messages=[message])
            )
    except Exception:
        logger.exception("push_flex failed")
        if raise_on_error:
            raise
