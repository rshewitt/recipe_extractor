from __future__ import annotations

import uuid
from typing import Any

from recipe_extractor import config
from recipe_extractor.aws import s3_client
from recipe_extractor.fetcher import decode_html, fetch_html
from recipe_extractor.logging import log


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    result = fetch_html(
        event["source_url"],
        max_bytes=config.MAX_DOWNLOAD_BYTES,
        max_redirects=config.MAX_REDIRECTS,
    )
    html = decode_html(result.body, result.content_type)
    key = f"jobs/{event['recipe_id']}/{uuid.uuid4().hex}.html"
    s3_client().put_object(
        Bucket=config.TEMP_BUCKET,
        Key=key,
        Body=html.encode("utf-8"),
        ContentType="text/html; charset=utf-8",
    )
    log("page fetched", recipe_id=event["recipe_id"], bytes=len(result.body))
    return {
        "recipe_id": event["recipe_id"],
        "source_url": result.final_url,
        "raw_key": key,
    }
