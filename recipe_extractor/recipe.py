from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

from bs4 import BeautifulSoup


class RecipeValidationError(ValueError):
    pass


_DURATION_RE = re.compile(
    r"^P(?:(?P<days>\d+)D)?(?:T(?:(?P<hours>\d+)H)?(?:(?P<minutes>\d+)M)?(?:(?P<seconds>\d+)S)?)?$",
    re.I,
)


def parse_duration_minutes(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    match = _DURATION_RE.match(value.strip())
    if not match:
        return None
    parts = {name: int(number or 0) for name, number in match.groupdict().items()}
    total_seconds = (
        parts["days"] * 86400
        + parts["hours"] * 3600
        + parts["minutes"] * 60
        + parts["seconds"]
    )
    return round(total_seconds / 60)


def clean_text(value: Any, *, max_length: int = 4000) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    text = BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length] or None


def normalize_recipe(
    payload: dict[str, Any], *, source_url: str, extraction_method: str
) -> dict[str, Any]:
    title = clean_text(payload.get("title"), max_length=300)
    if not title:
        raise RecipeValidationError("Recipe title is missing")

    raw_ingredients = payload.get("ingredients")
    raw_instructions = payload.get("instructions")
    if not isinstance(raw_ingredients, list) or not isinstance(raw_instructions, list):
        raise RecipeValidationError("Recipe ingredients and instructions must be arrays")

    ingredients: list[dict[str, str | None]] = []
    for item in raw_ingredients[:200]:
        if isinstance(item, str):
            text = clean_text(item, max_length=1000)
            group = None
        elif isinstance(item, dict):
            text = clean_text(item.get("text"), max_length=1000)
            group = clean_text(item.get("group"), max_length=150)
        else:
            continue
        if text:
            ingredients.append({"text": text, "group": group})

    instructions: list[dict[str, Any]] = []
    for index, item in enumerate(raw_instructions[:200], start=1):
        if isinstance(item, str):
            text = clean_text(item, max_length=2000)
            section = None
        elif isinstance(item, dict):
            text = clean_text(item.get("text"), max_length=2000)
            section = clean_text(item.get("section"), max_length=150)
        else:
            continue
        if text:
            instructions.append({"step": len(instructions) + 1, "text": text, "section": section})

    if not ingredients:
        raise RecipeValidationError("No ingredients were found")
    if not instructions:
        raise RecipeValidationError("No recipe instructions were found")

    return {
        "title": title,
        "description": clean_text(payload.get("description"), max_length=1200),
        "author": clean_text(payload.get("author"), max_length=300),
        "image_url": _safe_optional_url(payload.get("image_url")),
        "servings": clean_text(payload.get("servings"), max_length=100),
        "prep_time_minutes": _optional_nonnegative_int(payload.get("prep_time_minutes")),
        "cook_time_minutes": _optional_nonnegative_int(payload.get("cook_time_minutes")),
        "total_time_minutes": _optional_nonnegative_int(payload.get("total_time_minutes")),
        "ingredients": ingredients,
        "instructions": instructions,
        "source_url": source_url,
        "extraction_method": extraction_method,
        "extracted_at": datetime.now(UTC).isoformat(),
    }


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if 0 <= number <= 100_000 else None


def _safe_optional_url(value: Any) -> str | None:
    text = clean_text(value, max_length=2000)
    if text and text.startswith(("https://", "http://")):
        return text
    return None
