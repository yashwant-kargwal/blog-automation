"""Bloggen command-line application."""

import importlib.util
import platform
import re
import time
from pathlib import Path
from typing import Annotated

import typer
from rich import box
from rich.markdown import Markdown
from rich.panel import Panel
from rich.pretty import Pretty
from rich.prompt import Confirm, Prompt
from rich.table import Table

from bloggen import __version__
from bloggen.cache.store import CacheStore
from bloggen.cli.ui import console, error_panel, format_bytes, header, section, status_table
from bloggen.config.loader import load_settings, project_root
from bloggen.core.logging import configure_logging

app = typer.Typer(help="A premium command-line workspace for Bloggen.", invoke_without_command=True)
config_app = typer.Typer(help="Inspect and validate configuration.", no_args_is_help=True)
provider_app = typer.Typer(help="Inspect configured providers.", no_args_is_help=True)
cache_app = typer.Typer(help="Inspect and clean caches.", no_args_is_help=True)
logs_app = typer.Typer(help="Inspect application logs.", no_args_is_help=True)
research_app = typer.Typer(help="Search and analyze research sources.", no_args_is_help=True)
seo_app = typer.Typer(help="Generate structured SEO plans.", no_args_is_help=True)
writer_app = typer.Typer(help="Write professional Markdown blogs.", no_args_is_help=True)
pipeline_app = typer.Typer(help="Run the complete production pipeline.", no_args_is_help=True)
for group, name in ((config_app, "config"), (provider_app, "provider"), (cache_app, "cache"), (logs_app, "logs"), (research_app, "research"), (seo_app, "seo"), (writer_app, "writer"), (pipeline_app, "pipeline")):
    app.add_typer(group, name=name)


def settings_or_exit():
    try:
        return load_settings()
    except Exception as exc:
        error_panel("Configuration could not be loaded.", str(exc))
        raise typer.Exit(code=1) from exc


@app.callback()
def main(ctx: typer.Context, verbose: Annotated[bool, typer.Option("--verbose", help="Enable debug logging.")] = False) -> None:
    """Initialize logging and render the Bloggen header."""
    settings = settings_or_exit()
    configure_logging(settings, verbose=verbose)
    ctx.ensure_object(dict)
    ctx.obj["settings"] = settings
    header(settings.app.environment, __version__)
    if ctx.invoked_subcommand is None:
        console.print(Markdown("Run **`bloggen generate`** to start the complete workflow, or **`bloggen --help`** to explore commands."))


@app.command()
def generate(topic: Annotated[str | None, typer.Argument(help="Topic to turn into a complete blog.")] = None) -> None:
    """Ask for a topic and run Search → Scrape → Research → SEO → Writer → Validator → Output."""
    from bloggen.pipeline.engine import ProductionPipeline

    settings = settings_or_exit()
    selected_topic = topic or Prompt.ask("[bloggen.brand]What topic should Bloggen research?[/bloggen.brand]")
    started = time.perf_counter()
    result = ProductionPipeline(settings).run(selected_topic)
    elapsed = time.perf_counter() - started
    section("Bloggen generation", result.topic)
    table = Table(box=box.ROUNDED, header_style="bold bright_cyan")
    table.add_column("Stage")
    table.add_column("Status")
    table.add_column("Details", ratio=3)
    for report in result.stages:
        status = report.status.value
        color = "green" if status == "succeeded" else "red" if status == "failed" else "yellow" if status == "skipped" else "white"
        table.add_row(report.stage.value, f"[{color}]{status}[/{color}]", report.error or report.detail)
    console.print(table)
    summary = Table(box=box.SIMPLE_HEAVY, show_header=False)
    summary.add_column("Metric", style="bloggen.muted")
    summary.add_column("Value")
    summary.add_row("Overall status", result.status.value)
    summary.add_row("Generated title", result.generated_title or "—")
    summary.add_row("SEO score", f"{result.seo_score:.1f}/100" if result.seo_score is not None else "—")
    summary.add_row("Confidence score", f"{result.confidence_score:.1f}/100" if result.confidence_score is not None else "—")
    summary.add_row("Execution time", f"{elapsed:.2f}s")
    summary.add_row("Project", str(result.output_directory))
    console.print(Panel(summary, title="[bloggen.brand]Run summary[/bloggen.brand]", border_style="bright_cyan" if result.status.value == "succeeded" else "red", box=box.ROUNDED))
    if result.files:
        console.print("[bloggen.info]Files:[/bloggen.info]")
        for path in result.files:
            console.print(f"  [bloggen.muted]•[/bloggen.muted] {path}")
    if result.status.value != "succeeded":
        error_panel("Generation stopped gracefully.", result.error or "An upstream stage failed.")
        raise typer.Exit(code=1)


@config_app.command("show")
def config_show() -> None:
    console.print(Pretty(settings_or_exit().model_dump(mode="json"), expand_all=True))


@config_app.command("validate")
def config_validate() -> None:
    settings_or_exit()
    console.print("[bloggen.success]● Configuration is valid.[/bloggen.success]")


@config_app.command("path")
def config_path() -> None:
    console.print(project_root() / "config" / "config.yaml")


@provider_app.command("list")
def provider_list() -> None:
    settings = settings_or_exit()
    console.print(status_table([(name, "● active" if name == settings.providers.active else "○ ready", "configured") for name in settings.providers.available], "Provider registry"))


@provider_app.command("current")
def provider_current() -> None:
    console.print(f"[bloggen.info]Active provider:[/bloggen.info] {settings_or_exit().providers.active}")


@provider_app.command("select")
def provider_select(provider: Annotated[str | None, typer.Argument()] = None) -> None:
    settings = settings_or_exit()
    selected = provider or Prompt.ask("Provider", choices=settings.providers.available)
    if selected not in settings.providers.available:
        error_panel(f"Provider '{selected}' is not registered.")
        raise typer.Exit(code=1)
    console.print(f"[bloggen.warning]Provider selection is preview-only:[/bloggen.warning] {selected}")


@cache_app.command("status")
def cache_status() -> None:
    root = project_root() / "data" / "cache"
    rows = [(namespace, "● ready", f"{count} entries • {format_bytes(size)}") for namespace in ("search", "pages", "ai") for count, size in [CacheStore(root, namespace).stats()]]
    console.print(status_table(rows, "Cache status"))


@cache_app.command("clear")
def cache_clear(force: Annotated[bool, typer.Option("--force")] = False, namespace: Annotated[str, typer.Option("--namespace")] = "all", expired_only: Annotated[bool, typer.Option("--expired-only")] = False) -> None:
    """Clean search, scraper, and AI caches."""
    valid = {"all", "search", "pages", "ai"}
    if namespace not in valid:
        error_panel(f"Unknown cache namespace: {namespace}")
        raise typer.Exit(code=1)
    if not force and not Confirm.ask(f"Remove cache entries from '{namespace}'?", default=False):
        console.print("[bloggen.muted]Cache unchanged.[/bloggen.muted]")
        return
    root = project_root() / "data" / "cache"
    names = ("search", "pages", "ai") if namespace == "all" else (namespace,)
    removed = sum(CacheStore(root, name).cleanup(expired_only=expired_only) for name in names)
    console.print(f"[bloggen.success]✓ Removed {removed} cache entr{'y' if removed == 1 else 'ies'}.[/bloggen.success]")


@logs_app.command("show")
def logs_show(lines: Annotated[int, typer.Option("--lines", min=1, max=200)] = 30, kind: Annotated[str, typer.Option("--kind", help="app, errors, or debug")] = "app") -> None:
    settings = settings_or_exit()
    files = {"app": "bloggen.log", "errors": settings.logging.error_file, "debug": settings.logging.debug_file}
    if kind not in files:
        error_panel(f"Unknown log stream: {kind}")
        raise typer.Exit(code=1)
    path = settings.logging.log_directory / files[kind]
    if not path.is_file():
        console.print("[bloggen.muted]No log entries yet.[/bloggen.muted]")
        return
    console.print("\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:]))


@logs_app.command("path")
def logs_path() -> None:
    console.print(settings_or_exit().logging.log_directory)


@app.command()
def doctor() -> None:
    settings = settings_or_exit()
    checks = [("Python", "● pass" if tuple(map(int, platform.python_version_tuple())) >= (3, 12, 0) else "● fail", platform.python_version()), ("Configuration", "● pass", "validated"), ("Project root", "● pass" if project_root().is_dir() else "● fail", str(project_root()))]
    checks.extend((f"Dependency: {name}", "● pass" if importlib.util.find_spec(name) else "● fail", "importable" if importlib.util.find_spec(name) else "not installed") for name in ("httpx", "loguru", "pydantic", "rich", "typer", "yaml", "openai", "ddgs", "bs4", "trafilatura", "readability", "markdown"))
    console.print(status_table(checks, "System health"))


@research_app.command("search")
def research_search(query: str, top: Annotated[int | None, typer.Option("--top", min=1, max=100)] = None, depth: Annotated[int | None, typer.Option("--depth", min=1, max=5)] = None, no_cache: Annotated[bool, typer.Option("--no-cache")] = False) -> None:
    from bloggen.research.engine import SearchEngine
    from bloggen.research.models import SearchRequest
    settings = settings_or_exit()
    response = SearchEngine(settings.research).search(SearchRequest(query=query, top_n=top or settings.research.default_top_n, depth=depth or settings.research.default_depth, use_cache=not no_cache))
    table = Table(box=box.ROUNDED, header_style="bold bright_cyan")
    table.add_column("#"); table.add_column("Title"); table.add_column("Source"); table.add_column("URL")
    for item in response.results: table.add_row(str(item.rank), item.title, item.source, item.url)
    console.print(table)


@research_app.command("analyze")
def research_analyze(input_files: Annotated[list[Path], typer.Option("--input", exists=True, readable=True)], topic: Annotated[str, typer.Option("--topic")] = "") -> None:
    import json
    from bloggen.research.analysis_models import StructuredResearch
    from bloggen.research.analyzer import ResearchAnalyzer
    from bloggen.scraper.models import ScrapedPage
    settings = settings_or_exit(); articles = []
    for path in input_files:
        payload = json.loads(path.read_text(encoding="utf-8")); values = payload if isinstance(payload, list) else [payload]
        articles.extend(ScrapedPage.model_validate(value) for value in values)
    result = ResearchAnalyzer(settings).analyze(articles, topic)
    project = __import__("bloggen.storage.project", fromlist=["ProjectStore"]).ProjectStore.create(settings.storage.projects_directory, result.topic)
    project.save_json("research", "research.json", result.model_dump(mode="json")); project.save_log_snapshot(settings.logging.log_directory / "bloggen.log"); project.finalize(kind="research", topic=result.topic)
    console.print(f"[bloggen.success]✓ Research project stored at {project.path}[/bloggen.success]")


@seo_app.command("generate")
def seo_generate(input_file: Annotated[Path, typer.Option("--input", exists=True, readable=True)], topic: Annotated[str, typer.Option("--topic")] = "") -> None:
    from bloggen.research.analysis_models import StructuredResearch
    from bloggen.seo.engine import SEOEngine
    settings = settings_or_exit(); research = StructuredResearch.model_validate_json(input_file.read_text(encoding="utf-8")); plan = SEOEngine(settings).generate(research, topic)
    console.print(Pretty(plan.model_dump(mode="json"), expand_all=True))


@writer_app.command("generate")
def writer_generate(research_file: Annotated[Path, typer.Option("--research", exists=True, readable=True)], seo_file: Annotated[Path, typer.Option("--seo", exists=True, readable=True)], style: Annotated[str | None, typer.Option("--style")] = None) -> None:
    from bloggen.research.analysis_models import StructuredResearch
    from bloggen.seo.models import SEOPlan
    from bloggen.writer.engine import BlogWriter
    settings = settings_or_exit(); research = StructuredResearch.model_validate_json(research_file.read_text(encoding="utf-8")); seo = SEOPlan.model_validate_json(seo_file.read_text(encoding="utf-8")); post = BlogWriter(settings).write(research, seo, style=style)
    console.print(Markdown(post.markdown))


@app.command("validate")
def validate_blog(blog_file: Annotated[Path, typer.Argument(exists=True, readable=True)], seo_file: Annotated[Path | None, typer.Option("--seo", exists=True, readable=True)] = None, research_file: Annotated[Path | None, typer.Option("--research", exists=True, readable=True)] = None) -> None:
    from bloggen.research.analysis_models import StructuredResearch
    from bloggen.seo.models import SEOPlan
    from bloggen.validation.engine import ValidationEngine
    settings = settings_or_exit(); markdown = blog_file.read_text(encoding="utf-8"); seo = SEOPlan.model_validate_json(seo_file.read_text(encoding="utf-8")) if seo_file else None; research = StructuredResearch.model_validate_json(research_file.read_text(encoding="utf-8")) if research_file else None; result = ValidationEngine().validate(markdown, seo=seo, research=research)
    console.print(status_table([("SEO", f"{result.seo.score:.1f}", result.seo.label), ("Grammar", f"{result.grammar.score:.1f}", result.grammar.label), ("Readability", f"{result.readability.score:.1f}", result.readability.label), ("Confidence", f"{result.confidence.score:.1f}", result.confidence.label), ("Duplicate risk", f"{result.duplicate_risk.score:.1f}", result.duplicate_risk.label)], "Validation"))


@pipeline_app.command("run")
def pipeline_run(topic: str, style: Annotated[str | None, typer.Option("--style")] = None, no_cache: Annotated[bool, typer.Option("--no-cache")] = False) -> None:
    from bloggen.pipeline.engine import ProductionPipeline
    settings = settings_or_exit(); result = ProductionPipeline(settings).run(topic, style=style, use_cache=not no_cache)
    for report in result.stages: console.print(f"{report.stage.value}: {report.status.value} {report.detail}")
    console.print(f"Project: {result.output_directory}\nExecution: {result.execution_seconds:.2f}s")
    if result.status.value != "succeeded": raise typer.Exit(code=1)
