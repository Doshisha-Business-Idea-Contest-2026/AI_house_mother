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
    TextMessage,
)

from src.config import configuration

logger = logging.getLogger(__name__)


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
) -> None:
    """Push a plain text message to ``line_user_id``."""
    message = TextMessage(text=text)
    if quick_reply is not None:
        message.quick_reply = quick_reply
    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.push_message(
                PushMessageRequest(to=line_user_id, messages=[message])
            )
    except Exception:
        logger.exception("push_text failed")


def push_flex(
    line_user_id: str,
    alt_text: str,
    contents: dict,
    quick_reply: Optional[QuickReply] = None,
) -> None:
    """Push a Flex message to ``line_user_id``."""
    message = FlexMessage(alt_text=alt_text, contents=FlexContainer.from_dict(contents))
    if quick_reply is not None:
        message.quick_reply = quick_reply
    try:
        with ApiClient(configuration) as api_client:
            cl = MessagingApi(api_client)
            cl.push_message(
                PushMessageRequest(to=line_user_id, messages=[message])
            )
    except Exception:
        logger.exception("push_flex failed")
