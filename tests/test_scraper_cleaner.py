"""Offline tests for article HTML cleanup."""

from bloggen.scraper.cleaner import normalize_markdown, sanitize_html


def test_sanitize_html_removes_site_chrome_and_scripts() -> None:
    html = """
    <html><body><header>Site header</header><nav>Links</nav>
    <article><h1>Article</h1><p>Useful content.</p></article>
    <div class="cookie-banner">Accept cookies</div><script>alert('x')</script>
    <footer>Footer</footer></body></html>
    """

    cleaned = sanitize_html(html)

    assert "Useful content" in cleaned
    assert "Site header" not in cleaned
    assert "Accept cookies" not in cleaned
    assert "alert" not in cleaned


def test_normalize_markdown_removes_duplicate_blocks() -> None:
    markdown = "# Title\n\nRepeated paragraph\n\nRepeated paragraph\n\nUnique paragraph"

    assert normalize_markdown(markdown).count("Repeated paragraph") == 1
