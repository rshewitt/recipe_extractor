# Food Processor — AWS serverless recipe cleaner

A production-oriented implementation of **Food Processor**, a recipe-cleaning web app that turns a recipe webpage URL into clear ingredients and instructions. It first attempts deterministic Schema.org/JSON-LD extraction and only invokes Amazon Bedrock when the structured recipe metadata is missing or unusable.

## Branded frontend

The static frontend includes the Food Processor mascot, carrot-chef favicon/app icons, responsive landing page, extraction status states, feature cards, and the clean recipe result view. These assets are deployed with the existing S3/CloudFront flow and are also served by the local development server.

## Architecture

```text
Browser
  |
CloudFront
  |-- /        -> private S3 frontend (OAC)
  `-- /api/*   -> API Gateway HTTP API
                     |
                Submit Lambda ---- DynamoDB cache
                     |
                Step Functions
                     |
          +----------+-----------+
          |                      |
     Fetch Lambda            failure path
          |                      |
    temporary S3                 v
          |                 MarkFailed Lambda
     Parse Lambda
       /      \
 JSON-LD     cleaned text -> temporary S3 -> Bedrock Lambda
       \                              /
        +---------- Save Lambda ------+
                       |
                    DynamoDB
```

The state machine passes S3 object keys rather than full webpage bodies, avoiding Step Functions payload-size pressure. Temporary source data expires from S3 after one day and is deleted early on successful or failed workflows when possible.

## Production-oriented properties

- **AI is a fallback.** Valid Schema.org `Recipe` JSON-LD is used directly, which reduces model cost and avoids unnecessary generation.
- **Structured Bedrock responses.** The fallback uses the Converse API with a JSON Schema output format and then validates again at the persistence boundary.
- **SSRF resistance.** Only HTTP(S) on ports 80/443 is allowed. Credentials in URLs are rejected. DNS results must all be public IPs. The HTTP client connects to the already-validated IP while retaining the original hostname for `Host`, TLS SNI, and certificate verification, which closes the usual DNS-rebinding gap between validation and connection. Redirects go through the same validation again.
- **Bounded retrieval.** Fetches have connection/read timeouts, redirect limits, content-type checks, and a 2 MB decompressed-body limit.
- **Idempotency and cache.** The normalized URL's SHA-256 is the recipe ID. DynamoDB conditional writes prevent concurrent duplicate workflows. Completed recipes are cached for 30 days by default.
- **Asynchronous API.** `POST /api/recipes` returns `PROCESSING`; the frontend polls `GET /api/recipes/{recipe_id}`.
- **Small Step Functions state.** HTML and cleaned page text are kept in a short-lived private S3 bucket, not the workflow payload.
- **Private frontend bucket.** CloudFront reads S3 with Origin Access Control; the bucket is not public.
- **Security headers.** CloudFront applies HSTS, CSP, frame denial, MIME sniffing protection, and a referrer policy.
- **Data durability.** DynamoDB uses point-in-time recovery and is retained if the stack is deleted.
- **Failure visibility.** The workflow has X-Ray tracing, retained CloudWatch log groups, Step Functions error logging, and a CloudWatch alarm for failed state-machine executions.

## Prerequisites

- AWS CLI configured for the target account
- AWS SAM CLI
- Poetry 2.x
- Python 3.12
- Bedrock model access in your target AWS account/Region

The default model parameter is `us.anthropic.claude-haiku-4-5-20251001-v1:0`. You can supply any model/inference profile that supports Bedrock Converse structured outputs.

## Install and test

```bash
poetry lock
poetry install
poetry run pytest
poetry run ruff check recipe_extractor tests
```

`poetry.lock` is intentionally generated in your environment so the first lock captures dependency builds available for your deployment platform. Commit that generated lock file before treating a deployment as immutable/reproducible.

## Deploy

The deployment helper builds/deploys SAM, uploads the static frontend to the created private S3 bucket, and invalidates CloudFront:

```bash
AWS_REGION=us-west-2 \
STACK_NAME=recipe-extractor-prod \
ENVIRONMENT=prod \
./scripts/deploy.sh
```

To use a different structured-output-capable Bedrock model:

```bash
BEDROCK_MODEL_ID='your-model-or-inference-profile-id' ./scripts/deploy.sh
```

The script prints the CloudFront URL when deployment completes.

You can also use SAM directly:

```bash
sam build
sam deploy --guided
```

If deploying SAM manually, upload `frontend/` to the `FrontendBucketName` stack output afterward and invalidate the `DistributionId` CloudFront distribution.

## API

### Submit

```bash
curl -X POST "$SITE_URL/api/recipes" \
  -H 'content-type: application/json' \
  -d '{"url":"https://example.com/a-recipe"}'
```

Typical response:

```json
{
  "recipe_id": "<sha256>",
  "status": "PROCESSING"
}
```

### Read status/result

```bash
curl "$SITE_URL/api/recipes/<recipe_id>"
```

Completed response shape:

```json
{
  "recipe_id": "<sha256>",
  "status": "COMPLETE",
  "recipe": {
    "title": "Example recipe",
    "servings": "4 servings",
    "prep_time_minutes": 15,
    "cook_time_minutes": 30,
    "ingredients": [
      {"text": "2 lb chicken thighs", "group": null}
    ],
    "instructions": [
      {"step": 1, "text": "Heat the oven.", "section": null}
    ],
    "source_url": "https://example.com/a-recipe",
    "extraction_method": "json_ld"
  }
}
```

## Important operational notes

### Respect source sites

This project is intentionally conservative: it caches results, limits redirects and response sizes, and identifies itself with a dedicated user agent. Before operating it publicly, define a source-site policy for robots directives, publisher terms, rate limits, takedown requests, attribution, and storage/redistribution of recipe text. Do not use the service to bypass authentication or paywalls.

### Bedrock IAM

The example allows `bedrock:InvokeModel` on `*` because inference-profile IAM scoping can require permissions for both the profile and its destination foundation models. For a fixed production model and fixed set of regions, tighten this policy to the exact inference profile and underlying foundation-model ARNs allowed by your account policy.

### Stronger abuse controls

API Gateway stage throttling is included. For a public launch, add AWS WAF, bot/rate rules, and—if anonymous usage becomes expensive—an application-level quota mechanism or authentication. CloudFront-scoped WAF resources have deployment-region considerations, so they are intentionally not hard-wired into this single-region SAM stack.

### Cost controls

The biggest variable cost is Bedrock, which is avoided on pages with usable JSON-LD. Additional controls worth adding before a high-traffic launch include AWS Budgets, Bedrock invocation logging/metrics, per-IP/user quotas, and a maximum daily extraction count.

## Repository layout

```text
.
├── frontend/                    # static browser UI
├── recipe_extractor/
│   ├── functions/               # Lambda handlers
│   ├── bedrock.py               # structured-output fallback
│   ├── fetcher.py               # pinned-IP HTTP fetcher
│   ├── jsonld.py                # deterministic Recipe parser
│   ├── cleaner.py               # webpage text cleanup
│   ├── recipe.py                # validation/normalization
│   └── url_safety.py            # URL + SSRF validation
├── scripts/deploy.sh
├── statemachine/extract_recipe.asl.json
├── tests/
├── Makefile                     # SAM makefile builds + Poetry layer
├── pyproject.toml
└── template.yaml                # AWS SAM / CloudFormation
```

## Local development

The fastest local loop deliberately does **not** emulate Step Functions, DynamoDB, S3, or API Gateway. Instead, `recipe_extractor.local_server` serves the static frontend and exposes the same `/api/recipes` HTTP contract while reusing the production URL-safety, page-fetching, JSON-LD, cleaning, recipe-normalization, and optional Bedrock code. This makes local UI/extraction testing fast while keeping AWS integration testing for a deployed `dev` SAM stack.

### Docker Compose — deterministic extraction only

This mode requires only Docker and can extract recipes from pages that expose usable Schema.org/JSON-LD recipe data:

```bash
docker compose up --build
```

Open <http://localhost:8080>.

The default compose file sets `LOCAL_AI_MODE=disabled`. If a page does not contain a usable JSON-LD recipe, the UI returns a clear message rather than making an AWS call.

Stop it with:

```bash
docker compose down
```

The same commands are available as `make local-up` and `make local-down`.

### Docker Compose — with the real Bedrock fallback

If your AWS CLI credentials can invoke the configured Bedrock model, run:

```bash
AWS_PROFILE=default AWS_REGION=us-west-2 \
  docker compose -f compose.yaml -f compose.bedrock.yaml up --build
```

The Bedrock compose override mounts `${HOME}/.aws` read-only into the container. If you use a different profile or region, change `AWS_PROFILE` / `AWS_REGION`. You can also override the model:

```bash
BEDROCK_MODEL_ID='<model-or-inference-profile-id>' \
AWS_PROFILE=default AWS_REGION=us-west-2 \
  docker compose -f compose.yaml -f compose.bedrock.yaml up --build
```

The shortcut is `make local-bedrock`.

### Run directly with Poetry

You do not need Docker if you already have Python 3.12 and Poetry:

```bash
poetry install
poetry run python -m recipe_extractor.local_server
```

Then open <http://localhost:8080>. To enable the real Bedrock fallback:

```bash
LOCAL_AI_MODE=bedrock \
AWS_PROFILE=default \
AWS_REGION=us-west-2 \
poetry run python -m recipe_extractor.local_server
```

### What local mode does and does not test

Local mode tests the complete browser flow and the core recipe extraction behavior. Its job/status cache is in memory and resets when the process restarts. It does not emulate IAM, API Gateway, Step Functions retries, DynamoDB conditional writes/TTL, S3 lifecycle behavior, CloudFront, WAF, or CloudWatch. Use a separately deployed SAM stack with `Environment=dev` for those integration tests rather than depending on a large local AWS emulator.

### TODO 
- gather other steps if not provided (e.g. prep time) 