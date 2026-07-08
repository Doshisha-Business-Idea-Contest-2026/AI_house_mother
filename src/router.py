"""LINE webhook and health-check endpoints."""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request
from linebot.v3.exceptions import InvalidSignatureError

from src.config import handler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ai_house_mother")


@router.get("/health")
async def health() -> dict:
    """Simple liveness probe used by Apache/monitoring."""
    return {
        "status": "ok",
        "service": "ai_house_mother",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/callback")
async def callback(request: Request) -> str:
    """LINE Messaging API webhook receiver."""
    signature = request.headers.get("X-Line-Signature")
    if not signature:
        logger.warning("Missing X-Line-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")

    body = (await request.body()).decode("utf-8")
    logger.info("Webhook received: %s...", body[:100])

    try:
        # Offloading the (synchronous) LINE dispatcher lets Gemini calls
        # made inside handlers run without blocking the FastAPI event
        # loop. FastAPI's default thread pool is shared across `run_in_
        # threadpool` and `asyncio.to_thread`, capped at 40 workers, which
        # is plenty for a --workers 1 uvicorn deployment.
        await asyncio.to_thread(handler.handle, body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature")
        raise HTTPException(status_code=400, detail="Invalid signature")
    except Exception:
        # Handler-level exceptions must not surface to LINE (which would
        # retry, potentially duplicating side effects). We log the trace
        # and return 200; user-facing errors are already reported inline
        # by the handlers.
        logger.exception("Unhandled error in handler")

    return "OK"
