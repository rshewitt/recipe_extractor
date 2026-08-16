from __future__ import annotations

import json
from typing import Any, Iterable

from bs4 import BeautifulSoup

from recipe_extractor.recipe import clean_text, normalize_recipe, parse_duration_minutes


def extract_recipe_from_html(html: str, source_url: str) -> dict[str, Any] | None:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[dict[str, Any]] = []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text()
        if not raw or not raw.strip():
            continue
        try:
            document = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            continue
        for obj in _walk_objects(document):
            if _is_recipe(obj):
                candidates.append(obj)

    candidates.sort(key=_candidate_score, reverse=True)
    for candidate in candidates:
        try:
            return normalize_recipe(
                _convert_schema_recipe(candidate),
                source_url=source_url,
                extraction_method="json_ld",
            )
        except ValueError:
            continue
    return None


def _walk_objects(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for nested in value.values():
            yield from _walk_objects(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_objects(nested)


def _is_recipe(value: dict[str, Any]) -> bool:
    type_value = value.get("@type")
    if isinstance(type_value, str):
        return type_value.lower() == "recipe"
    if isinstance(type_value, list):
        return any(isinstance(item, str) and item.lower() == "recipe" for item in type_value)
    return False


def _candidate_score(candidate: dict[str, Any]) -> int:
    ingredients = candidate.get("recipeIngredient")
    instructions = candidate.get("recipeInstructions")
    return (len(ingredients) if isinstance(ingredients, list) else 0) + _instruction_count(
        instructions
    )


def _instruction_count(value: Any) -> int:
    if isinstance(value, str):
        return 1
    if isinstance(value, list):
        return sum(_instruction_count(item) for item in value)
    if isinstance(value, dict):
        nested = value.get("itemListElement")
        return max(1, _instruction_count(nested))
    return 0


def _convert_schema_recipe(candidate: dict[str, Any]) -> dict[str, Any]:
    ingredients = []
    for value in candidate.get("recipeIngredient", []) or []:
        text = clean_text(value, max_length=1000)
        if text:
            ingredients.append({"text": text, "group": None})

    instructions: list[dict[str, Any]] = []
    _flatten_instructions(candidate.get("recipeInstructions"), instructions, section=None)

    return {
        "title": candidate.get("name"),
        "description": candidate.get("description"),
        "author": _author(candidate.get("author")),
        "image_url": _image(candidate.get("image")),
        "servings": _yield(candidate.get("recipeYield")),
        "prep_time_minutes": parse_duration_minutes(candidate.get("prepTime")),
        "cook_time_minutes": parse_duration_minutes(candidate.get("cookTime")),
        "total_time_minutes": parse_duration_minutes(candidate.get("totalTime")),
        "ingredients": ingredients,
        "instructions": instructions,
    }


def _flatten_instructions(value: Any, result: list[dict[str, Any]], section: str | None) -> None:
    if isinstance(value, str):
        text = clean_text(value, max_length=2000)
        if text:
            result.append({"text": text, "section": section})
        return

    if isinstance(value, list):
        for item in value:
            _flatten_instructions(item, result, section)
        return

    if not isinstance(value, dict):
        return

    kind = value.get("@type")
    if isinstance(kind, list):
        kinds = {str(item).lower() for item in kind}
    else:
        kinds = {str(kind).lower()}

    if "howtosection" in kinds:
        next_section = clean_text(value.get("name"), max_length=150) or section
        _flatten_instructions(value.get("itemListElement"), result, next_section)
        return

    nested = value.get("itemListElement")
    text = clean_text(value.get("text") or value.get("name"), max_length=2000)
    if text:
        result.append({"text": text, "section": section})
    elif nested is not None:
        _flatten_instructions(nested, result, section)


def _author(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return clean_text(value.get("name"), max_length=300)
    if isinstance(value, list):
        names = [_author(item) for item in value]
        return ", ".join(name for name in names if name) or None
    return None


def _image(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        for item in value:
            found = _image(item)
            if found:
                return found
    if isinstance(value, dict):
        url = value.get("url") or value.get("contentUrl")
        return url if isinstance(url, str) else None
    return None


def _yield(value: Any) -> str | None:
    if isinstance(value, list):
        return clean_text(value[0], max_length=100) if value else None
    return clean_text(value, max_length=100)
