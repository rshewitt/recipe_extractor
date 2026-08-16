from __future__ import annotations

import json
import logging
from typing import Any

_logger = logging.getLogger("recipe_extractor")
_logger.setLevel(logging.INFO)


def log(message: str, *, level: int = logging.INFO, **fields: Any) -> None:
    payload = {"message": message, **fields}
    _logger.log(level, json.dumps(payload, default=str, separators=(",", ":")))
