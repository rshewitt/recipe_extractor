from __future__ import annotations

import time
from typing import Any

from recipe_extractor import config
from recipe_extractor.aws import s3_client, table_resource
from recipe_extractor.recipe import normalize_recipe


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    recipe = event.get("recipe")
    if not isinstance(recipe, dict):
        raise ValueError("Workflow produced no recipe")

    # Revalidate even deterministic/structured model output at the persistence boundary.
    validated = normalize_recipe(
        recipe,
        source_url=event["source_url"],
        extraction_method=str(recipe.get("extraction_method") or "unknown"),
    )

    now = int(time.time())
    table_resource(config.TABLE_NAME).update_item(
        Key={"recipe_id": event["recipe_id"]},
        UpdateExpression=(
            "SET #s = :complete, recipe = :recipe, source_url = :url, updated_at = :now, "
            "expires_at = :expires REMOVE error_code"
        ),
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={
            ":complete": "COMPLETE",
            ":recipe": validated,
            ":url": event["source_url"],
            ":now": now,
            ":expires": now + config.CACHE_TTL_SECONDS,
        },
    )
    _cleanup(event)
    return {"recipe_id": event["recipe_id"], "status": "COMPLETE"}


def _cleanup(event: dict[str, Any]) -> None:
    s3 = s3_client()
    for field in ("raw_key", "clean_key"):
        key = event.get(field)
        if isinstance(key, str):
            try:
                s3.delete_object(Bucket=config.TEMP_BUCKET, Key=key)
            except Exception:
                # Lifecycle expiration is the safety net; cleanup must not fail a saved recipe.
                pass
