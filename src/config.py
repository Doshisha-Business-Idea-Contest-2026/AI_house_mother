"""Runtime configuration loaded from environment variables."""

import logging
import os
import sys

from dotenv import load_dotenv
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Required credentials
# ---------------------------------------------------------------------------
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    print(
        "error: LINE_CHANNEL_ACCESS_TOKEN and LINE_CHANNEL_SECRET must be set in .env",
        file=sys.stderr,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Optional credentials / server tuning
# ---------------------------------------------------------------------------
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning(
        "GEMINI_API_KEY is not set. Gemini-backed features will fail once introduced."
    )

FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8084"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
TZ = os.getenv("TZ", "Asia/Tokyo")

# Public base URL used to compose Sender iconUrl values (docs/04 §3.5).
# Must be reachable over HTTPS by the LINE platform; keep the trailing
# path element matching the FastAPI router prefix so that the
# ``StaticFiles`` mount lands under the Apache-proxied path.
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL", "https://linebot.kmchan.jp/ai_house_mother"
).rstrip("/")

# Sender switch presets (docs/04 §3.5). Each entry maps the SenderPreset
# name to (display name, iconUrl). ``SENDER_ICON_VERSION`` is appended as
# a query string to force LINE and any CDN in front of the origin to
# re-fetch when the underlying PNG files are replaced. Bump it whenever
# ``static/icons/*.png`` change.
SENDER_ICON_VERSION = "20260706"
SENDER_PRESETS: dict[str, tuple[str, str]] = {
    "friendly": (
        "AI寮母",
        f"{PUBLIC_BASE_URL}/static/icons/friendly.png?v={SENDER_ICON_VERSION}",
    ),
    "system": (
        "AI寮母 System",
        f"{PUBLIC_BASE_URL}/static/icons/system.png?v={SENDER_ICON_VERSION}",
    ),
    "notify": (
        "AI寮母 お知らせ",
        f"{PUBLIC_BASE_URL}/static/icons/notify.png?v={SENDER_ICON_VERSION}",
    ),
}

# When true, gemini.py returns seed-based static fallback answers instead of
# calling the Gemini API. Used for local development or during a Gemini
# outage rehearsal.
GEMINI_MOCK_MODE = os.getenv("GEMINI_MOCK_MODE", "false").lower() == "true"
# gemini-flash-lite-latest is a rolling alias for the current Flash Lite
# release. It is preferred over gemini-2.5-flash-lite because the fixed
# 2.5-lite alias is capped at 20 requests per day on the free tier
# (measured 2026-07); the rolling alias has a much larger daily quota.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

# ---------------------------------------------------------------------------
# LINE SDK singletons
# ---------------------------------------------------------------------------
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
