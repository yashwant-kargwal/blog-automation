"""Publication-quality Markdown checks."""

import re

AI_WORDING = (
    "as an ai",
    "as a language model",
    "in today's fast-paced world",
    "delve into",
    "in conclusion",
    "it's important to note",
    "unlock the power",
    "seamlessly",
    "comprehensive guide",
)


def count_words(markdown: str) -> int:
    """Count prose words while ignoring Markdown punctuation."""
    return len(re.findall(r"\b[\w][\w'-]*\b", markdown))


def validate_markdown(markdown: str, minimum_words: int, maximum_words: int) -> list[str]:
    """Return all quality violations found in generated Markdown."""
    errors: list[str] = []
    words = count_words(markdown)
    if words < minimum_words:
        errors.append(f"minimum word count is {minimum_words}; generated {words}")
    if words > maximum_words:
        errors.append(f"maximum word count is {maximum_words}; generated {words}")
    if len(re.findall(r"^# [^#].*$", markdown, flags=re.MULTILINE)) != 1:
        errors.append("document must contain exactly one H1")
    if not re.search(r"^## .+$", markdown, flags=re.MULTILINE):
        errors.append("document must contain at least one H2")
    if not re.search(r"^### .+$", markdown, flags=re.MULTILINE):
        errors.append("document must contain at least one H3")
    if not re.search(r"(?:^|\n)\s*[-*+] .+", markdown):
        errors.append("document must contain a bullet list")
    if not re.search(r"\|[^\n]+\|\n\|\s*:?-{3,}", markdown):
        errors.append("document must contain a Markdown table")
    if not re.search(r"(?i)\b(example|for example|here's how)\b", markdown):
        errors.append("document must contain a practical example")
    if not re.search(r"(?i)\b(call to action|try this|next step|start by|learn more|sign up|contact us)\b", markdown):
        errors.append("document must contain a call to action")
    lowered = markdown.casefold()
    errors.extend(f"contains AI-style wording: {phrase}" for phrase in AI_WORDING if phrase in lowered)
    return errors
