from __future__ import annotations

import os


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


TABLE_NAME = os.getenv("TABLE_NAME", "")
TEMP_BUCKET = os.getenv("TEMP_BUCKET", "")
STATE_MACHINE_ARN = os.getenv("STATE_MACHINE_ARN", "")
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
CACHE_TTL_SECONDS = env_int("CACHE_TTL_SECONDS", 60 * 60 * 24 * 30)
PROCESSING_TTL_SECONDS = env_int("PROCESSING_TTL_SECONDS", 60 * 60 * 24)
PROCESSING_STALE_SECONDS = env_int("PROCESSING_STALE_SECONDS", 60 * 15)
MAX_DOWNLOAD_BYTES = env_int("MAX_DOWNLOAD_BYTES", 2_000_000)
MAX_CLEAN_TEXT_CHARS = env_int("MAX_CLEAN_TEXT_CHARS", 120_000)
MAX_REDIRECTS = env_int("MAX_REDIRECTS", 5)
