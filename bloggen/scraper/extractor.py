"""Layered article extraction using Trafilatura and Readability."""

from bs4 import BeautifulSoup
from readability import Document
from trafilatura import extract

from bloggen.scraper.cleaner import normalize_markdown, sanitize_html, word_count
from bloggen.scraper.exceptions import ExtractionError


def extract_article(html: str, url: str) -> tuple[str, str]:
    """Return article title and clean Markdown from an HTML document."""
    sanitized = sanitize_html(html)
    title = _title(sanitized)
    markdown = extract(
        sanitized,
        url=url,
        output_format="markdown",
        include_comments=False,
        include_tables=True,
        include_images=False,
        include_links=True,
        deduplicate=True,
        favor_precision=True,
    )
    markdown = normalize_markdown(markdown or "")
    if word_count(markdown) < 20:
        readability_html = Document(sanitized).summary()
        fallback = extract(
            readability_html,
            url=url,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            include_images=False,
            include_links=True,
            deduplicate=True,
        )
        markdown = normalize_markdown(fallback or "")
    if word_count(markdown) < 20:
        raise ExtractionError("No useful article content was found on the page.")
    return title or _title(Document(sanitized).summary()), markdown


def _title(html: str) -> str:
    """Extract a clean title from common document metadata."""
    soup = BeautifulSoup(html, "html.parser")
    title = soup.find("title")
    return " ".join(title.get_text(" ", strip=True).split()) if title else ""
