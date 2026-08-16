.PHONY: test lint lock local local-up local-down local-bedrock build-DependenciesLayer \
	build-SubmitFunction build-GetRecipeFunction build-FetchPageFunction \
	build-ParsePageFunction build-BedrockExtractFunction build-SaveRecipeFunction \
	build-MarkFailedFunction

FUNCTIONS := SubmitFunction GetRecipeFunction FetchPageFunction ParsePageFunction BedrockExtractFunction SaveRecipeFunction MarkFailedFunction

lock:
	poetry lock

test:
	poetry run pytest

lint:
	poetry run ruff check recipe_extractor tests

local:
	poetry run python -m recipe_extractor.local_server

local-up:
	docker compose up --build

local-bedrock:
	docker compose -f compose.yaml -f compose.bedrock.yaml up --build

local-down:
	docker compose down


# SAM's makefile builder passes ARTIFACTS_DIR. The dependency layer is built from
# Poetry's resolved main dependencies; application source is copied separately.
build-DependenciesLayer:
	poetry install --only main --no-root --sync --no-interaction
	mkdir -p "$(ARTIFACTS_DIR)/python"
	SITE_PACKAGES="$$(poetry run python -c 'import site; print(site.getsitepackages()[0])')"; \
		cp -R "$$SITE_PACKAGES"/. "$(ARTIFACTS_DIR)/python/"
	# Keep the layer lean; these are build-only caches/metadata.
	find "$(ARTIFACTS_DIR)/python" -type d -name '__pycache__' -prune -exec rm -rf {} + || true
	find "$(ARTIFACTS_DIR)/python" -type d -name 'tests' -prune -exec rm -rf {} + || true

# All functions share the same source package; dependencies are in DependenciesLayer.
define COPY_FUNCTION_SOURCE
	mkdir -p "$(ARTIFACTS_DIR)"
	cp -R recipe_extractor "$(ARTIFACTS_DIR)/recipe_extractor"
endef

build-SubmitFunction:
	$(COPY_FUNCTION_SOURCE)

build-GetRecipeFunction:
	$(COPY_FUNCTION_SOURCE)

build-FetchPageFunction:
	$(COPY_FUNCTION_SOURCE)

build-ParsePageFunction:
	$(COPY_FUNCTION_SOURCE)

build-BedrockExtractFunction:
	$(COPY_FUNCTION_SOURCE)

build-SaveRecipeFunction:
	$(COPY_FUNCTION_SOURCE)

build-MarkFailedFunction:
	$(COPY_FUNCTION_SOURCE)
