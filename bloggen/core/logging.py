"""Centralized Loguru logging with Rich console output and pipeline tracing."""

import inspect
import sys
import time
from collections.abc import Callable
from functools import wraps
from pathlib import Path
from typing import Any, TypeVar, cast

from loguru import logger
from rich.console import Console
from rich.text import Text

from bloggen.config.settings import Settings

F = TypeVar("F", bound=Callable[..., Any])
_console = Console()


def _rich_sink(message: Any) -> None:
    """Render Loguru records as readable, non-interfering Rich console lines."""
    record = message.record
    level = record["level"].name
    color = {"TRACE": "dim", "DEBUG": "cyan", "INFO": "green", "SUCCESS": "bold green", "WARNING": "yellow", "ERROR": "red", "CRITICAL": "bold red"}.get(level, "white")
    line = Text()
    line.append(record["time"].strftime("%H:%M:%S"), style="dim")
    line.append(f" │ {level:<8} ", style=color)
    line.append(record["message"])
    _console.print(line)


def configure_logging(settings: Settings, *, verbose: bool = False) -> None:
    """Configure Rich console, daily application, error, and optional debug logs."""
    log_directory = settings.logging.log_directory
    log_directory.mkdir(parents=True, exist_ok=True)
    logger.remove()
    debug_mode = verbose or settings.app.debug
    console_level = "DEBUG" if debug_mode else settings.logging.level
    logger.add(_rich_sink, level=console_level, colorize=False, enqueue=True, catch=True)
    logger.add(
        log_directory / "bloggen.log",
        level=settings.logging.level,
        rotation="00:00",
        retention=settings.logging.retention,
        compression="zip",
        enqueue=True,
        encoding="utf-8",
        backtrace=settings.app.debug,
        diagnose=settings.app.debug,
    )
    logger.add(
        log_directory / settings.logging.error_file,
        level="ERROR",
        rotation="00:00",
        retention=settings.logging.retention,
        compression="zip",
        enqueue=True,
        encoding="utf-8",
        backtrace=True,
        diagnose=settings.app.debug,
    )
    if debug_mode:
        logger.add(
            log_directory / settings.logging.debug_file,
            level="DEBUG",
            rotation="00:00",
            retention=settings.logging.retention,
            compression="zip",
            enqueue=True,
            encoding="utf-8",
            backtrace=settings.app.debug,
            diagnose=settings.app.debug,
        )
    logger.info("logging.configured debug_mode={} log_directory={}", debug_mode, log_directory)


def pipeline_step(name: str | None = None) -> Callable[[F], F]:
    """Decorate sync or async pipeline stages with start/success/error events."""
    def decorator(function: F) -> F:
        step_name = name or function.__name__
        if inspect.iscoroutinefunction(function):
            @wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                logger.info("pipeline.step.start step={}", step_name)
                try:
                    result = await function(*args, **kwargs)
                except Exception:
                    logger.exception("pipeline.step.error step={} elapsed_ms={:.1f}", step_name, (time.perf_counter() - started) * 1000)
                    raise
                logger.success("pipeline.step.success step={} elapsed_ms={:.1f}", step_name, (time.perf_counter() - started) * 1000)
                return result
            return cast(F, async_wrapper)

        @wraps(function)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            logger.info("pipeline.step.start step={}", step_name)
            try:
                result = function(*args, **kwargs)
            except Exception:
                logger.exception("pipeline.step.error step={} elapsed_ms={:.1f}", step_name, (time.perf_counter() - started) * 1000)
                raise
            logger.success("pipeline.step.success step={} elapsed_ms={:.1f}", step_name, (time.perf_counter() - started) * 1000)
            return result
        return cast(F, sync_wrapper)
    return decorator
