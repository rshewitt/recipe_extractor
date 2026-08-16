from __future__ import annotations

from typing import Any

from recipe_extractor import config
from recipe_extractor.aws import s3_client
from recipe_extractor.cleaner import clean_page_text
from recipe_extractor.jsonld import extract_recipe_from_html
from recipe_extractor.logging import log


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    s3 = s3_client()
    obj = s3.get_object(Bucket=config.TEMP_BUCKET, Key=event["raw_key"])
    html = obj["Body"].read().decode("utf-8", errors="replace")

    recipe = extract_recipe_from_html(html, event["source_url"])
    if recipe:
        log("recipe extracted from json-ld", recipe_id=event["recipe_id"])
        return {**event, "needs_ai": False, "recipe": recipe}

    clean_text = clean_page_text(html, max_chars=config.MAX_CLEAN_TEXT_CHARS)
    if len(clean_text) < 80:
        raise ValueError("Page did not contain enough recipe-like text")

    clean_key = event["raw_key"].removesuffix(".html") + ".txt"
    s3.put_object(
        Bucket=config.TEMP_BUCKET,
        Key=clean_key,
        Body=clean_text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
    )
    log("json-ld unavailable; bedrock fallback required", recipe_id=event["recipe_id"])
    return {**event, "needs_ai": True, "clean_key": clean_key}
