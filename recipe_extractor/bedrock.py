from __future__ import annotations

import json
from typing import Any

import boto3

from recipe_extractor.recipe import normalize_recipe

_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "author": {"type": ["string", "null"]},
        "image_url": {"type": ["string", "null"]},
        "servings": {"type": ["string", "null"]},
        "prep_time_minutes": {"type": ["integer", "null"]},
        "cook_time_minutes": {"type": ["integer", "null"]},
        "total_time_minutes": {"type": ["integer", "null"]},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "group": {"type": ["string", "null"]},
                },
                "required": ["text", "group"],
                "additionalProperties": False,
            },
        },
        "instructions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "section": {"type": ["string", "null"]},
                },
                "required": ["text", "section"],
                "additionalProperties": False,
            },
        },
    },
    "required": [
        "title",
        "description",
        "author",
        "image_url",
        "servings",
        "prep_time_minutes",
        "cook_time_minutes",
        "total_time_minutes",
        "ingredients",
        "instructions",
    ],
    "additionalProperties": False,
}

_SYSTEM = """You extract cooking recipes from webpage text.
Only use facts explicitly present in the supplied webpage text. Never invent an ingredient,
quantity, time, yield, author, or cooking step. Ignore advertisements, navigation, comments,
affiliate copy, unrelated recommendations, and SEO prose. Preserve ingredient quantities and
units in the ingredient text. Keep instructions in the original cooking order. If a field is not
supported by the page, return null. Return only the recipe represented by the page."""


def extract_with_bedrock(
    text: str, *, source_url: str, model_id: str, client: Any | None = None
) -> dict[str, Any]:
    runtime = client or boto3.client("bedrock-runtime")
    result = runtime.converse(
        modelId=model_id,
        system=[{"text": _SYSTEM}],
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "text": (
                            f"Source URL: {source_url}\n\n"
                            "Extract the recipe from the following cleaned webpage text:\n\n"
                            f"{text}"
                        )
                    }
                ],
            }
        ],
        inferenceConfig={"maxTokens": 5000, "temperature": 0},
        outputConfig={
            "textFormat": {
                "type": "json_schema",
                "structure": {
                    "jsonSchema": {
                        "schema": json.dumps(_SCHEMA, separators=(",", ":")),
                        "name": "recipe_extraction",
                        "description": "A recipe extracted without adding unsupported facts",
                    }
                },
            }
        },
        requestMetadata={"application": "recipe-extractor", "operation": "extract"},
    )

    content = result["output"]["message"]["content"]
    text_blocks = [item["text"] for item in content if isinstance(item, dict) and "text" in item]
    if not text_blocks:
        raise RuntimeError("Bedrock returned no text output")

    payload = json.loads("".join(text_blocks))
    if not isinstance(payload, dict):
        raise RuntimeError("Bedrock output was not a JSON object")
    return normalize_recipe(payload, source_url=source_url, extraction_method="bedrock")
