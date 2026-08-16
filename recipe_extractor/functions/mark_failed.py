from __future__ import annotations

import time
from typing import Any

from recipe_extractor import config
from recipe_extractor.aws import s3_client, table_resource
from recipe_extractor.logging import log


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    recipe_id = event.get("recipe_id")
    if not isinstance(recipe_id, str):
        return {"status": "ERROR"}

    error = event.get("error") if isinstance(event.get("error"), dict) else {}
    internal_error = str(error.get("Error") or "EXTRACTION_FAILED")[:200]
    log("recipe extraction failed", recipe_id=recipe_id, workflow_error=internal_error)

    now = int(time.time())
    table_resource(config.TABLE_NAME).update_item(
        Key={"recipe_id": recipe_id},
        UpdateExpression=(
            "SET #s = :error, error_code = :code, updated_at = :now, "
            "expires_at = :expires"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":error": "ERROR",
            ":code": "EXTRACTION_FAILED",
            ":now": now,
            ":expires": now + 3600,
        },
    )

    s3 = s3_client()
    for field in ("raw_key", "clean_key"):
        key = event.get(field)
        if isinstance(key, str):
            try:
                s3.delete_object(Bucket=config.TEMP_BUCKET, Key=key)
            except Exception:
                pass
    return {"recipe_id": recipe_id, "status": "ERROR"}
