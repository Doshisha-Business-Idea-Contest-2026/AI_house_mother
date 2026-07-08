"""Handlers module.

Importing this package as a side effect registers all @handler.add
decorators with the global WebhookHandler defined in src.config.

When adding a new handler module, remember to import it here.

Note: ``student`` does not register handlers directly (it is invoked by
``message.py`` and ``postback.py``), but importing it up-front keeps its
imports validated at boot time.
"""

from src.handlers import follow  # noqa: F401
from src.handlers import postback  # noqa: F401
from src.handlers import message  # noqa: F401
from src.handlers import parent  # noqa: F401
from src.handlers import student  # noqa: F401
