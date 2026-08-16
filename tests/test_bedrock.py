import json

from recipe_extractor.bedrock import extract_with_bedrock


class FakeBedrock:
    def converse(self, **kwargs):
        payload = {
            "title": "Soup",
            "description": None,
            "author": None,
            "image_url": None,
            "servings": "2",
            "prep_time_minutes": 5,
            "cook_time_minutes": 20,
            "total_time_minutes": 25,
            "ingredients": [{"text": "2 cups stock", "group": None}],
            "instructions": [{"text": "Simmer for 20 minutes.", "section": None}],
        }
        assert kwargs["outputConfig"]["textFormat"]["type"] == "json_schema"
        return {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}


def test_bedrock_structured_output_is_normalized():
    recipe = extract_with_bedrock(
        "Soup recipe text",
        source_url="https://example.com/soup",
        model_id="fake",
        client=FakeBedrock(),
    )
    assert recipe["title"] == "Soup"
    assert recipe["extraction_method"] == "bedrock"
