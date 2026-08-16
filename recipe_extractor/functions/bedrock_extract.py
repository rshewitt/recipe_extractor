from __future__ import annotations

from typing import Any

from recipe_extractor import config
from recipe_extractor.aws import s3_client
from recipe_extractor.bedrock import extract_with_bedrock
from recipe_extractor.logging import log


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    obj = s3_client().get_object(Bucket=config.TEMP_BUCKET, Key=event["clean_key"])
    text = obj["Body"].read().decode("utf-8", errors="replace")
    recipe = extract_with_bedrock(
        text,
        source_url=event["source_url"],
        model_id=config.BEDROCK_MODEL_ID,
    )
    log("recipe extracted with bedrock", recipe_id=event["recipe_id"])
    return {**event, "recipe": recipe}
