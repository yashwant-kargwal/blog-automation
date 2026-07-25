"""Offline Markdown quality checks."""

from bloggen.writer.quality import validate_markdown


def test_quality_checks_accept_required_structure() -> None:
    markdown = """# Title

## Overview

Useful transitions make this article clear and practical.

- First point
- Second point

| Option | Use |
| --- | --- |
| A | Example |

### Example

For example, start with the simplest approach.

## Next steps

Try this today as your next step.
""" + "\nUseful detail." * 80

    assert validate_markdown(markdown, 100, 1000) == []
