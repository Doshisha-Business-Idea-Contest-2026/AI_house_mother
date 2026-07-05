"""Follow event handler.

Fires when a user adds AI 寮母 as a friend. Sends the welcome message
containing the role-selection Quick Reply.

Note: The FollowEvent's reply_token expires in 30 seconds. Once Gemini
is introduced (Day 2+), a dynamic welcome should switch to push_message
instead of relying on reply_token.
"""
import logging

from linebot.v3.webhooks import FollowEvent

from src.config import handler
from src.services.line_reply import reply_text
from src.templates.flex.welcome import build_welcome_message

logger = logging.getLogger(__name__)


@handler.add(FollowEvent)
def handle_follow(event: FollowEvent) -> None:
    """Reply with the welcome message + role Quick Reply."""
    user_id = event.source.user_id
    logger.info("Follow event from %s", user_id[:8] if user_id else "?")

    text, qr = build_welcome_message()
    reply_text(event.reply_token, text, quick_reply=qr)
