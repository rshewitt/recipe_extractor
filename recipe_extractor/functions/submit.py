from __future__ import annotations

import hashlib
import json
import time
import uuid
from typing import Any

import boto3
from botocore.exceptions import ClientError

from recipe_extractor import config
from recipe_extractor.aws import table_resource
from recipe_extractor.http import parse_json_body, response
from recipe_extractor.logging import log
from recipe_extractor.url_safety import UnsafeUrlError, normalize_url


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        body = parse_json_body(event)
        normalized_url = normalize_url(body.get("url", ""))
    except (ValueError, UnsafeUrlError) as exc:
        return response(400, {"error": "INVALID_URL", "message": str(exc)})

    now = int(time.time())
    recipe_id = hashlib.sha256(normalized_url.encode("utf-8")).hexdigest()
    table = table_resource(config.TABLE_NAME)

    existing = table.get_item(Key={"recipe_id": recipe_id}, ConsistentRead=True).get("Item")
    if existing and int(existing.get("expires_at", 0)) > now:
        status = existing.get("status")
        if status == "COMPLETE":
            return response(200, _public_status(existing))
        if status == "PROCESSING" and int(existing.get("updated_at", 0)) >= (
            now - config.PROCESSING_STALE_SECONDS
        ):
            return response(202, _public_status(existing))

    item = {
        "recipe_id": recipe_id,
        "source_url": normalized_url,
        "status": "PROCESSING",
        "created_at": now,
        "updated_at": now,
        "expires_at": now + config.PROCESSING_TTL_SECONDS,
    }

    try:
        table.put_item(
            Item=item,
            ConditionExpression=(
                "attribute_not_exists(recipe_id) OR expires_at < :now OR #s = :error "
                "OR (#s = :processing AND updated_at < :stale)"
            ),
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":now": now,
                ":error": "ERROR",
                ":processing": "PROCESSING",
                ":stale": now - config.PROCESSING_STALE_SECONDS,
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        current = table.get_item(Key={"recipe_id": recipe_id}, ConsistentRead=True).get("Item")
        if current:
            status_code = 200 if current.get("status") == "COMPLETE" else 202
            return response(status_code, _public_status(current))
        raise

    try:
        sfn = boto3.client("stepfunctions")
        execution_name = f"extract-{recipe_id[:32]}-{uuid.uuid4().hex[:12]}"
        sfn.start_execution(
            stateMachineArn=config.STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(
                {"recipe_id": recipe_id, "source_url": normalized_url}, separators=(",", ":")
            ),
        )
    except Exception:
        table.update_item(
            Key={"recipe_id": recipe_id},
            UpdateExpression="SET #s = :error, error_code = :code, updated_at = :now",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":error": "ERROR",
                ":code": "WORKFLOW_START_FAILED",
                ":now": int(time.time()),
            },
        )
        raise

    log(
        "recipe extraction submitted",
        recipe_id=recipe_id,
        source_host=normalized_url.split("/")[2],
    )
    return response(202, _public_status(item))


def _public_status(item: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {
        "recipe_id": item["recipe_id"],
        "status": item["status"],
    }
    if item.get("status") == "COMPLETE" and isinstance(item.get("recipe"), dict):
        result["recipe"] = item["recipe"]
    if item.get("status") == "ERROR":
        result["error"] = item.get("error_code", "EXTRACTION_FAILED")
        result["message"] = "The recipe could not be extracted from that page."
    return result

