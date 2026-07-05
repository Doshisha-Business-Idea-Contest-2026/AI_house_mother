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
    logger.warning("GEMINI_API_KEY is not set. Gemini-backed features will fail once introduced.")

FASTAPI_PORT = int(os.getenv("FASTAPI_PORT", "8084"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
TZ = os.getenv("TZ", "Asia/Tokyo")

# When true, gemini.py returns seed-based static fallback answers instead of
# calling the Gemini API. Used for local development or during a Gemini
# outage rehearsal.
GEMINI_MOCK_MODE = os.getenv("GEMINI_MOCK_MODE", "false").lower() == "true"
# gemini-2.5-flash-lite is the current free-tier friendly Flash Lite model.
# gemini-2.0-flash-lite returned quota errors on the free tier as of 2026-07.
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

# ---------------------------------------------------------------------------
# LINE SDK singletons
# ---------------------------------------------------------------------------
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)
