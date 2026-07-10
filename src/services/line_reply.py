"""Helpers for replying and pushing messages via the LINE Messaging API."""

import logging
from typing import Optional

from linebot.v3.messaging import (
    ApiClient,
    FlexContainer,
    FlexMessage,
    MessagingApi,
    PushMessageRequest,
    QuickReply,
    ReplyMessageRequest,
    ShowLoadingAnimationRequest,
    TextMessage,
)

from src.config import configuration

logger = logging.getLogger(__name__)

# Loading indicator (docs/04 §3.5). Values below are enforced by the
# LINE API: loading_seconds must be a multiple of 5 in [5, 60].
DEFAULT_LOADING_SECONDS = 20
_LOADING_SECONDS_MIN = 5
_LOADING_SECONDS_MAX = 60


def reply_text(
    reply_token: str,
    text: str,
    quick_reply: Optional[QuickReply] = None,
) -> None:
    """Reply with a plain text message.

    Args:
        reply_token: Token from the incoming LINE event.
        text: Message body.
        quick_reply: Optional Quick Reply attached to the message.
    """
    message = TextMessage(text=text)
    if quick_reply is not None:
        message.quick_reply = quick_reply

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
) -> None:
    """Reply with a Flex message.

    Args:
        reply_token: Token from the incoming LINE event.
        alt_text: Fallback text shown in notifications.
        contents: Flex message contents (bubble or carousel dict).
        quick_reply: Optional Quick Reply attached to the message.
    """
    message = FlexMessage(alt_text=alt_text, contents=FlexContainer.from_dict(contents))
    if quick_reply is not None:
        message.quick_reply = quick_reply

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
    """
    message = TextMessage(text=text)
    if quick_reply is not None:
        message.quick_reply = quick_reply
    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.push_message(PushMessageRequest(to=line_user_id, messages=[message]))
    except Exception:
        logger.exception("push_text failed")
        if raise_on_error:
            raise


def push_texts(
    line_user_id: str,
    texts: list[str],
    quick_reply: Optional[QuickReply] = None,
    raise_on_error: bool = False,
) -> None:
    """Push several text messages to ``line_user_id`` as one push.

    The messages arrive as separate chat bubbles but only trigger a single
    push notification, which keeps a split reply (e.g. the life-consultation
    empathy / body / closing bubbles, see docs/04 §4.4) from feeling spammy.

    Args:
        line_user_id: Recipient LINE user id.
        texts: Message bodies in display order. Empty or whitespace-only
            entries are dropped; if nothing remains, no push is sent.
        quick_reply: Optional Quick Reply attached to the *last* message.
        raise_on_error: When ``True`` re-raise any exception raised by the
            LINE SDK so the caller can count failures. Defaults to ``False``
            for the fire-and-forget style used by the interactive handlers.
    """
    bodies = [text for text in texts if text and text.strip()]
    # The LINE Messaging API accepts at most 5 messages per push request.
    bodies = bodies[:5]
    if not bodies:
        return

    messages: list[TextMessage] = [TextMessage(text=body) for body in bodies]
    if quick_reply is not None:
        messages[-1].quick_reply = quick_reply
    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.push_message(PushMessageRequest(to=line_user_id, messages=messages))
    except Exception:
        logger.exception("push_texts failed")
        if raise_on_error:
            raise


def push_flex(
    line_user_id: str,
    alt_text: str,
    contents: dict,
    quick_reply: Optional[QuickReply] = None,
    raise_on_error: bool = False,
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
    """
    message = FlexMessage(alt_text=alt_text, contents=FlexContainer.from_dict(contents))
    if quick_reply is not None:
        message.quick_reply = quick_reply
    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.push_message(PushMessageRequest(to=line_user_id, messages=[message]))
    except Exception:
        logger.exception("push_flex failed")
        if raise_on_error:
            raise


def show_loading(
    line_user_id: str,
    loading_seconds: int = DEFAULT_LOADING_SECONDS,
    raise_on_error: bool = False,
) -> None:
    """Display the LINE loading indicator to ``line_user_id``.

    Consumes no ``reply_token``: the caller is expected to send the
    actual response via :func:`push_text` / :func:`push_flex` once the
    long-running work (Gemini call, seed search, ...) finishes. If the
    real response arrives before the ``loading_seconds`` timeout, LINE
    hides the indicator automatically.

    Args:
        line_user_id: Target LINE userId. The bot must have push
            permission for this user (satisfied by every friend-added
            account).
        loading_seconds: How long to keep the indicator alive.
            :data:`_LOADING_SECONDS_MIN` to :data:`_LOADING_SECONDS_MAX`
            in multiples of 5; defaults to
            :data:`DEFAULT_LOADING_SECONDS`.
        raise_on_error: When ``True`` re-raise LINE SDK exceptions so
            batch callers can count failures. Defaults to ``False`` —
            silently logging matches the fire-and-forget style of the
            other helpers in this module.

    Raises:
        ValueError: When ``loading_seconds`` is outside the LINE API
            contract (multiple of 5 within [5, 60]).
    """
    if (
        loading_seconds < _LOADING_SECONDS_MIN
        or loading_seconds > _LOADING_SECONDS_MAX
        or loading_seconds % 5 != 0
    ):
        raise ValueError(
            "loading_seconds must be a multiple of 5 in "
            f"[{_LOADING_SECONDS_MIN}, {_LOADING_SECONDS_MAX}]; "
            f"got {loading_seconds!r}"
        )

    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.show_loading_animation(
                ShowLoadingAnimationRequest(
                    chat_id=line_user_id, loading_seconds=loading_seconds
                )
            )
    except Exception:
        logger.exception("show_loading failed")
        if raise_on_error:
            raise
