"""Shared premium terminal presentation helpers."""

from collections.abc import Iterable
from pathlib import Path

from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

THEME = Theme(
    {
        "bloggen.brand": "bold bright_cyan",
        "bloggen.muted": "dim white",
        "bloggen.success": "bold green",
        "bloggen.warning": "bold yellow",
        "bloggen.error": "bold red",
        "bloggen.info": "bright_blue",
    }
)
console = Console(theme=THEME)


def header(environment: str, version: str) -> None:
    """Render the application identity block."""
    title = Text.assemble(("BLOGGEN", "bloggen.brand"), ("  /  ", "bloggen.muted"), ("developer workspace", "bold white"))
    subtitle = Text(f"v{version}  •  {environment}  •  foundation mode", style="bloggen.muted")
    console.print(Panel(Group(title, subtitle), border_style="bright_cyan", box=box.ROUNDED, padding=(0, 2)))


def section(title: str, description: str | None = None) -> None:
    """Print a consistent section heading."""
    console.print()
    console.rule(f"[bloggen.brand]{title}[/bloggen.brand]", style="bright_black")
    if description:
        console.print(f"[bloggen.muted]{description}[/bloggen.muted]")


def error_panel(message: str, details: str | None = None) -> None:
    """Render an actionable error panel."""
    body = message if details is None else f"{message}\n\n[bloggen.muted]{details}[/bloggen.muted]"
    console.print(Panel(body, title="[bloggen.error]Something went wrong[/bloggen.error]", border_style="red", box=box.ROUNDED))


def status_table(rows: Iterable[tuple[str, str, str]], title: str = "Status") -> Table:
    """Build a compact status table."""
    table = Table(title=title, box=box.SIMPLE_HEAVY, header_style="bold bright_cyan", padding=(0, 1))
    table.add_column("Check", style="white")
    table.add_column("Status", justify="center")
    table.add_column("Details", style="bloggen.muted")
    for name, status, details in rows:
        table.add_row(name, status, details)
    return table


def progress() -> Progress:
    """Create the standard Bloggen progress display."""
    return Progress(
        SpinnerColumn(style="bright_cyan"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=28),
        TextColumn("{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
    )


def directory_size(path: Path) -> tuple[int, int]:
    """Return file count and byte size for a directory."""
    if not path.exists():
        return 0, 0
    files = [item for item in path.rglob("*") if item.is_file()]
    return len(files), sum(item.stat().st_size for item in files)


def format_bytes(size: int) -> str:
    """Format bytes for terminal display."""
    units = ("B", "KB", "MB", "GB")
    amount = float(size)
    for unit in units:
        if amount < 1024 or unit == units[-1]:
            return f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{size} B"
