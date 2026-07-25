"""HTML sanitization and Markdown normalization."""

import re
from collections.abc import Iterable

from bs4 import BeautifulSoup, Tag

NOISE_TAGS = {"script", "style", "noscript", "iframe", "svg", "canvas", "form", "nav", "header", "footer", "aside"}
NOISE_HINTS = re.compile(r"(?:^|[-_ ])(?:ad|ads|advert|banner|cookie|consent|dialog|footer|header|menu|modal|nav|newsletter|popup|promo|related|share|sidebar|social|subscribe)(?:$|[-_ ])", re.I)


def sanitize_html(html: str) -> str:
    """Remove known non-content elements before extraction."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup.find_all(NOISE_TAGS):
        element.decompose()
    for element in soup.find_all(True):
        if _looks_like_noise(element):
            element.decompose()
    return str(soup)


def _looks_like_noise(element: Tag) -> bool:
    """Identify common advertisement, navigation, and consent containers."""
    values = [element.get("id", ""), *element.get("class", [])]
    return bool(NOISE_HINTS.search(" ".join(str(value) for value in values)))


def normalize_markdown(markdown: str) -> str:
    """Collapse whitespace and remove repeated paragraphs or lines."""
    cleaned = markdown.replace("\r\n", "\n").replace("\r", "\n")
    blocks = re.split(r"\n\s*\n", cleaned)
    seen: set[str] = set()
    unique_blocks: list[str] = []
    for block in blocks:
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in block.splitlines()]
        normalized = "\n".join(line for line in lines if line)
        key = re.sub(r"\W+", " ", normalized).strip().casefold()
        if normalized and key and key not in seen:
            seen.add(key)
            unique_blocks.append(normalized)
    return "\n\n".join(unique_blocks).strip()


def word_count(markdown: str) -> int:
    """Count useful words in normalized Markdown."""
    return len(re.findall(r"\b[\w][\w'-]*\b", re.sub(r"[#*_`>\[\]()]", " ", markdown)))
