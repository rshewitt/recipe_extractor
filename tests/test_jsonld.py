from recipe_extractor.jsonld import extract_recipe_from_html
from recipe_extractor.recipe import parse_duration_minutes


def test_parse_iso_duration():
    assert parse_duration_minutes("PT1H30M") == 90
    assert parse_duration_minutes("PT45M") == 45


def test_extract_recipe_jsonld():
    html = """
    <html><head><script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@type": "Recipe",
      "name": "Test Pasta",
      "description": "A simple pasta.",
      "recipeYield": "4 servings",
      "prepTime": "PT10M",
      "cookTime": "PT20M",
      "recipeIngredient": ["1 lb pasta", "2 tbsp olive oil"],
      "recipeInstructions": [
        {"@type":"HowToStep","text":"Boil the pasta."},
        {"@type":"HowToSection","name":"Sauce","itemListElement":[
          {"@type":"HowToStep","text":"Warm the olive oil."}
        ]}
      ]
    }
    </script></head><body>Lots of irrelevant prose</body></html>
    """
    recipe = extract_recipe_from_html(html, "https://example.com/pasta")
    assert recipe is not None
    assert recipe["title"] == "Test Pasta"
    assert recipe["prep_time_minutes"] == 10
    assert recipe["cook_time_minutes"] == 20
    assert [item["text"] for item in recipe["ingredients"]] == ["1 lb pasta", "2 tbsp olive oil"]
    assert recipe["instructions"][1]["section"] == "Sauce"
    assert recipe["extraction_method"] == "json_ld"
