from __future__ import annotations

import re

from bs4 import BeautifulSoup


_REMOVE = {
    "script",
    "style",
    "noscript",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "iframe",
    "svg",
    "canvas",
}


def clean_page_text(html: str, *, max_chars: int) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all(_REMOVE):
        tag.decompose()

    root = soup.find("main") or soup.find("article") or soup.body or soup
    text = root.get_text("\n", strip=True)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]

    # Remove consecutive duplicate lines, common in responsive navigation/SEO markup.
    compact: list[str] = []
    for line in lines:
        if not compact or compact[-1] != line:
            compact.append(line)

    return "\n".join(compact)[:max_chars]
