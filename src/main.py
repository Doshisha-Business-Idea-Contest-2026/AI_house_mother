"""FastAPI entrypoint for the AI House Mother LINE Bot.

Boots the ASGI app, wires up logging so that uvicorn's default access
logger does not clobber application logs, and imports handler modules
for their ``@handler.add`` registration side effects.
"""

import logging
import logging.config
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from src.config import LOG_LEVEL

REPO_ROOT = Path(__file__).resolve().parents[1]


def _configure_logging() -> None:
    """Configure logging so uvicorn and app loggers coexist cleanly."""
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "stream": "ext://sys.stdout",
                },
            },
            "loggers": {
                "uvicorn": {
                    "level": LOG_LEVEL,
                    "handlers": ["console"],
                    "propagate": False,
                },
                "uvicorn.error": {
                    "level": LOG_LEVEL,
                    "handlers": ["console"],
                    "propagate": False,
                },
                "uvicorn.access": {
                    "level": LOG_LEVEL,
                    "handlers": ["console"],
                    "propagate": False,
                },
            },
            "root": {"level": LOG_LEVEL, "handlers": ["console"]},
        }
    )


_configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="AI House Mother LINE Bot")

# Serve Sender switch icons (docs/04 §3.5). Mounted under the
# router prefix so Apache's ``ProxyPass /ai_house_mother`` covers it
# without an extra rule.
app.mount(
    "/ai_house_mother/static",
    StaticFiles(directory=str(REPO_ROOT / "static")),
    name="static",
)

# Importing router (and, transitively, handlers) registers @handler.add
# decorators with the global WebhookHandler defined in src.config.
from src.router import router  # noqa: E402
from src import handlers  # noqa: E402, F401  -- side-effect imports

app.include_router(router)

logger.info("AI House Mother started")
