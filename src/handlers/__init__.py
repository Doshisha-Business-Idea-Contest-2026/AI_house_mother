"""Handlers module.

Importing this package as a side effect registers all @handler.add
decorators with the global WebhookHandler defined in src.config.

When adding a new handler module, remember to import it here.
"""
from src.handlers import follow  # noqa: F401
from src.handlers import postback  # noqa: F401
from src.handlers import message  # noqa: F401
