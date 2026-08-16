from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin

import urllib3
from urllib3.util import Timeout

from recipe_extractor.url_safety import SafeTarget, resolve_safe_target


class FetchError(RuntimeError):
    pass


@dataclass(frozen=True)
class FetchResult:
    final_url: str
    body: bytes
    content_type: str


_REDIRECTS = {301, 302, 303, 307, 308}
_USER_AGENT = (
    "RecipeExtractorBot/1.0 (+https://example.invalid/recipe-extractor; "
    "purpose=recipe-metadata-extraction)"
)


def fetch_html(url: str, *, max_bytes: int, max_redirects: int) -> FetchResult:
    current = url
    for redirect_number in range(max_redirects + 1):
        target = resolve_safe_target(current)
        status, headers, body = _fetch_target(target, max_bytes=max_bytes)

        if status in _REDIRECTS:
            if redirect_number >= max_redirects:
                raise FetchError("Too many redirects")
            location = headers.get("location")
            if not location:
                raise FetchError("Redirect did not include a Location header")
            current = urljoin(target.url, location)
            continue

        if status < 200 or status >= 300:
            raise FetchError(f"Upstream returned HTTP {status}")

        content_type = headers.get("content-type", "").lower()
        media_type = content_type.split(";", 1)[0].strip()
        if media_type not in {"text/html", "application/xhtml+xml"}:
            raise FetchError("URL did not return an HTML document")

        return FetchResult(final_url=target.url, body=body, content_type=content_type)

    raise FetchError("Too many redirects")


def decode_html(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    match = re.search(r"charset\s*=\s*[\"']?([^;\s\"']+)", content_type, re.I)
    if match:
        charset = match.group(1)
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _fetch_target(target: SafeTarget, *, max_bytes: int) -> tuple[int, dict[str, str], bytes]:
    last_error: Exception | None = None
    for ip in target.addresses:
        pool: urllib3.HTTPConnectionPool | urllib3.HTTPSConnectionPool
        if target.scheme == "https":
            pool = urllib3.HTTPSConnectionPool(
                ip,
                port=target.port,
                timeout=Timeout(connect=3.0, read=8.0),
                retries=False,
                cert_reqs="CERT_REQUIRED",
                assert_hostname=target.hostname,
                server_hostname=target.hostname,
            )
        else:
            pool = urllib3.HTTPConnectionPool(
                ip,
                port=target.port,
                timeout=Timeout(connect=3.0, read=8.0),
                retries=False,
            )

        response = None
        try:
            response = pool.request(
                "GET",
                target.request_target,
                headers={
                    "Host": target.host_header,
                    "User-Agent": _USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1",
                    "Accept-Encoding": "gzip, deflate",
                },
                redirect=False,
                preload_content=False,
                decode_content=True,
            )
            chunks: list[bytes] = []
            size = 0
            for chunk in response.stream(64 * 1024, decode_content=True):
                size += len(chunk)
                if size > max_bytes:
                    raise FetchError("Page exceeded the configured download limit")
                chunks.append(chunk)
            headers = {key.lower(): value for key, value in response.headers.items()}
            return response.status, headers, b"".join(chunks)
        except (urllib3.exceptions.HTTPError, OSError, FetchError) as exc:
            last_error = exc
            if isinstance(exc, FetchError):
                raise
        finally:
            if response is not None:
                response.release_conn()
            pool.close()

    raise FetchError("Unable to connect to the resolved public address") from last_error
