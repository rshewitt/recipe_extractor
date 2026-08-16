from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from recipe_extractor import config
from recipe_extractor.bedrock import extract_with_bedrock
from recipe_extractor.cleaner import clean_page_text
from recipe_extractor.fetcher import decode_html, fetch_html
from recipe_extractor.jsonld import extract_recipe_from_html
from recipe_extractor.url_safety import UnsafeUrlError, normalize_url

HOST = os.getenv("LOCAL_HOST", "0.0.0.0")
PORT = int(os.getenv("LOCAL_PORT", "8080"))
AI_MODE = os.getenv("LOCAL_AI_MODE", "disabled").strip().lower()
FRONTEND_DIR = Path(os.getenv("LOCAL_FRONTEND_DIR", Path(__file__).resolve().parents[1] / "frontend"))

_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=int(os.getenv("LOCAL_WORKERS", "4")))


def _set_job(recipe_id: str, value: dict[str, Any]) -> None:
    with _jobs_lock:
        _jobs[recipe_id] = value


def _get_job(recipe_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        item = _jobs.get(recipe_id)
        return dict(item) if item else None


def _extract(recipe_id: str, source_url: str) -> None:
    try:
        fetched = fetch_html(
            source_url,
            max_bytes=config.MAX_DOWNLOAD_BYTES,
            max_redirects=config.MAX_REDIRECTS,
        )
        html = decode_html(fetched.body, fetched.content_type)
        recipe = extract_recipe_from_html(html, fetched.final_url)

        if recipe is None:
            clean_text = clean_page_text(html, max_chars=config.MAX_CLEAN_TEXT_CHARS)
            if len(clean_text) < 80:
                raise ValueError("Page did not contain enough recipe-like text")
            if AI_MODE != "bedrock":
                raise RuntimeError(
                    "No JSON-LD recipe was found. Start local mode with LOCAL_AI_MODE=bedrock "
                    "to test the Bedrock fallback."
                )
            recipe = extract_with_bedrock(
                clean_text,
                source_url=fetched.final_url,
                model_id=config.BEDROCK_MODEL_ID,
            )

        _set_job(recipe_id, {"recipe_id": recipe_id, "status": "COMPLETE", "recipe": recipe})
    except Exception as exc:  # local dev surface: return a useful error message
        _set_job(
            recipe_id,
            {
                "recipe_id": recipe_id,
                "status": "ERROR",
                "error": type(exc).__name__,
                "message": str(exc) or "Recipe extraction failed",
            },
        )


class Handler(BaseHTTPRequestHandler):
    server_version = "RecipeExtractorLocal/1.0"

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/api/recipes":
            self._json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})
            return

        try:
            length = int(self.headers.get("content-length", "0"))
            if length <= 0 or length > 32_768:
                raise ValueError("Request body must be between 1 byte and 32 KiB")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Request body must be a JSON object")
            source_url = normalize_url(body.get("url", ""))
        except (ValueError, json.JSONDecodeError, UnsafeUrlError) as exc:
            self._json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_URL", "message": str(exc)})
            return

        recipe_id = hashlib.sha256(source_url.encode("utf-8")).hexdigest()
        existing = _get_job(recipe_id)
        if existing and existing.get("status") in {"PROCESSING", "COMPLETE"}:
            code = HTTPStatus.OK if existing["status"] == "COMPLETE" else HTTPStatus.ACCEPTED
            self._json(code, existing)
            return

        pending = {"recipe_id": recipe_id, "status": "PROCESSING"}
        _set_job(recipe_id, pending)
        _executor.submit(_extract, recipe_id, source_url)
        self._json(HTTPStatus.ACCEPTED, pending)

    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/api/recipes/"):
            recipe_id = unquote(self.path.rsplit("/", 1)[-1])
            if len(recipe_id) != 64:
                self._json(HTTPStatus.BAD_REQUEST, {"error": "INVALID_RECIPE_ID"})
                return
            item = _get_job(recipe_id)
            if item is None:
                self._json(HTTPStatus.NOT_FOUND, {"error": "NOT_FOUND"})
                return
            self._json(HTTPStatus.OK, item)
            return

        self._serve_static()

    def _serve_static(self) -> None:
        request_path = urlsplit(self.path).path
        relative = "index.html" if request_path == "/" else request_path.lstrip("/")
        candidate = (FRONTEND_DIR / relative).resolve()
        try:
            candidate.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        if not candidate.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content = candidate.read_bytes()
        content_type, _ = mimetypes.guess_type(candidate.name)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(content)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: Any) -> None:
        print(f"[local] {self.address_string()} - {fmt % args}")


def main() -> None:
    if AI_MODE not in {"disabled", "bedrock"}:
        raise SystemExit("LOCAL_AI_MODE must be 'disabled' or 'bedrock'")
    print(f"Food Processor local site: http://localhost:{PORT}")
    print(f"AI fallback: {AI_MODE}")
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
