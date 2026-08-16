from __future__ import annotations

from typing import Any

from recipe_extractor import config
from recipe_extractor.aws import table_resource
from recipe_extractor.http import response


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    recipe_id = (event.get("pathParameters") or {}).get("recipe_id")
    if not isinstance(recipe_id, str) or len(recipe_id) != 64:
        return response(400, {"error": "INVALID_RECIPE_ID"})

    item = table_resource(config.TABLE_NAME).get_item(Key={"recipe_id": recipe_id}).get("Item")
    if not item:
        return response(404, {"error": "NOT_FOUND"})

    body: dict[str, Any] = {"recipe_id": recipe_id, "status": item.get("status", "UNKNOWN")}
    if item.get("status") == "COMPLETE" and isinstance(item.get("recipe"), dict):
        body["recipe"] = item["recipe"]
    elif item.get("status") == "ERROR":
        body["error"] = item.get("error_code", "EXTRACTION_FAILED")
        body["message"] = "The recipe could not be extracted from that page."
    return response(200, body)
