# topmark:header:start
#
#   project      : TopMark
#   file         : test_logging.py
#   file_relpath : tests/core/test_logging.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for TopMark's core logging helpers."""

from __future__ import annotations

import importlib
import logging
from typing import TYPE_CHECKING

import pytest

import topmark.core.logging as core_logging

if TYPE_CHECKING:
    from collections.abc import Iterator
    from types import ModuleType


@pytest.fixture
def restore_root_logger() -> Iterator[None]:
    """Restore root logger state after tests that exercise setup_logging()."""
    root_logger: logging.Logger = logging.getLogger()
    original_level: int = root_logger.level
    original_handlers: list[logging.Handler] = list(root_logger.handlers)
    original_propagate: bool = root_logger.propagate

    try:
        yield
    finally:
        root_logger.handlers[:] = original_handlers
        root_logger.setLevel(original_level)
        root_logger.propagate = original_propagate


def _format_log_message(formatter: logging.Formatter, level: int) -> str:
    """Return formatted output for a representative log record."""
    record = logging.LogRecord(
        name="topmark.tests.logging",
        level=level,
        pathname="tests/core/test_logging.py",
        lineno=123,
        msg="configured",
        args=(),
        exc_info=None,
        func="test_function",
    )
    return formatter.format(record)


# --- TRACE level registration and logger class ---


def test_trace_level_is_registered_below_debug() -> None:
    """The custom TRACE level should be registered as a stable logging level."""
    assert core_logging.TRACE_LEVEL == logging.DEBUG - 5
    assert logging.getLevelName(core_logging.TRACE_LEVEL) == "TRACE"
    assert hasattr(logging, "TRACE")
    assert isinstance(logging.TRACE, int)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert logging.TRACE == core_logging.TRACE_LEVEL  # pyright: ignore[reportAttributeAccessIssue]


def test_module_reload_registers_trace_level_when_logging_lacks_attribute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reloading should defensively re-register TRACE when logging has no attribute."""
    monkeypatch.delattr(logging, "TRACE", raising=False)

    reloaded: ModuleType = importlib.reload(core_logging)

    assert reloaded.TRACE_LEVEL == core_logging.TRACE_LEVEL
    assert hasattr(logging, "TRACE")
    assert isinstance(logging.TRACE, int)  # pyright: ignore[reportAttributeAccessIssue, reportUnknownMemberType]
    assert logging.TRACE == core_logging.TRACE_LEVEL  # pyright: ignore[reportAttributeAccessIssue]
    assert logging.getLevelName(core_logging.TRACE_LEVEL) == "TRACE"


def test_get_logger_returns_topmark_logger() -> None:
    """Logger retrieval should return the project logger subtype."""
    logger: core_logging.TopmarkLogger = core_logging.get_logger("topmark.tests.logging")

    assert isinstance(logger, core_logging.TopmarkLogger)


@pytest.mark.parametrize(
    ("enabled_level", "expected_message"),
    [
        pytest.param(core_logging.TRACE_LEVEL, "trace details", id="enabled"),
        pytest.param(logging.DEBUG, None, id="disabled"),
    ],
)
def test_topmark_logger_trace_respects_effective_level(
    enabled_level: int,
    expected_message: str | None,
) -> None:
    """trace() should emit only when the logger accepts the TRACE level."""
    logger: core_logging.TopmarkLogger = core_logging.get_logger("topmark.tests.logging.trace")
    records: list[logging.LogRecord] = []

    class CapturingHandler(logging.Handler):
        """Handler that keeps emitted records in memory for assertion."""

        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    original_level: int = logger.level
    original_handlers: list[logging.Handler] = list(logger.handlers)
    original_propagate: bool = logger.propagate

    try:
        logger.handlers[:] = [CapturingHandler()]
        logger.setLevel(enabled_level)
        logger.propagate = False

        logger.trace("trace %s", "details", extra={"topmark_test": True})
    finally:
        logger.handlers[:] = original_handlers
        logger.setLevel(original_level)
        logger.propagate = original_propagate

    if expected_message is None:
        assert records == []
    else:
        assert [record.levelno for record in records] == [core_logging.TRACE_LEVEL]
        assert [record.getMessage() for record in records] == [expected_message]
        assert isinstance(records[0].topmark_test, bool)  # pyright: ignore[reportUnknownMemberType, reportAttributeAccessIssue]
        assert records[0].topmark_test is True  # pyright: ignore[reportAttributeAccessIssue]


# --- Environment log-level resolution ---


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("TRACE", core_logging.TRACE_LEVEL, id="trace-name"),
        pytest.param("debug", logging.DEBUG, id="case-insensitive-name"),
        pytest.param("WARN", logging.WARNING, id="warn-alias"),
        pytest.param("FATAL", logging.CRITICAL, id="fatal-alias"),
        pytest.param("0", logging.NOTSET, id="numeric-zero"),
        pytest.param("15", 15, id="numeric-custom"),
    ],
)
def test_resolve_env_log_level_accepts_supported_values(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
    expected: int,
) -> None:
    """Environment resolution should accept documented names, aliases, and numbers."""
    monkeypatch.setenv("TOPMARK_LOG_LEVEL", raw)

    assert core_logging.resolve_env_log_level() == expected


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("", id="empty"),
        pytest.param(" ", id="blank"),
        pytest.param("verbose", id="unknown-name"),
    ],
)
def test_resolve_env_log_level_returns_none_for_unset_or_unknown_values(
    monkeypatch: pytest.MonkeyPatch,
    raw: str,
) -> None:
    """Environment resolution should fail open for absent or unknown values."""
    monkeypatch.setenv("TOPMARK_LOG_LEVEL", raw)

    assert core_logging.resolve_env_log_level() is None


def test_resolve_env_log_level_returns_none_when_numeric_conversion_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Numeric environment resolution should fail open if conversion is rejected."""

    def reject_numeric_log_level(_value: str) -> int:
        raise ValueError("rejected numeric log level")

    monkeypatch.setenv("TOPMARK_LOG_LEVEL", "15")
    monkeypatch.setattr(core_logging, "int", reject_numeric_log_level, raising=False)

    assert core_logging.resolve_env_log_level() is None


def test_resolve_env_log_level_returns_none_when_environment_is_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing TOPMARK_LOG_LEVEL should leave level selection to setup_logging()."""
    monkeypatch.delenv("TOPMARK_LOG_LEVEL", raising=False)

    assert core_logging.resolve_env_log_level() is None


# --- Root logger setup ---


def test_setup_logging_defaults_to_critical_without_environment(
    monkeypatch: pytest.MonkeyPatch,
    restore_root_logger: None,
) -> None:
    """Default setup should be quiet and install one stdout stream handler."""
    monkeypatch.delenv("TOPMARK_LOG_LEVEL", raising=False)

    core_logging.setup_logging()

    root_logger: logging.Logger = logging.getLogger()
    assert root_logger.level == logging.CRITICAL
    assert root_logger.propagate is False
    assert len(root_logger.handlers) == 1
    handler: logging.Handler = root_logger.handlers[0]
    assert isinstance(handler, logging.StreamHandler)
    assert handler.stream is core_logging.sys.stdout  # pyright: ignore[reportUnknownMemberType]
    formatter: logging.Formatter | None = handler.formatter
    assert formatter is not None
    assert _format_log_message(formatter, logging.CRITICAL) == "[CRITICAL] configured"


def test_setup_logging_uses_environment_level_when_explicit_level_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    restore_root_logger: None,
) -> None:
    """Environment level should be honored when setup_logging() has no argument."""
    monkeypatch.setenv("TOPMARK_LOG_LEVEL", "DEBUG")

    core_logging.setup_logging()

    root_logger: logging.Logger = logging.getLogger()
    formatter: logging.Formatter | None = root_logger.handlers[0].formatter
    assert formatter is not None
    assert _format_log_message(formatter, logging.DEBUG) == (
        "[DEBUG] [test_logging.py:123] [test_function] configured"
    )


def test_setup_logging_explicit_level_overrides_environment_and_replaces_handlers(
    monkeypatch: pytest.MonkeyPatch,
    restore_root_logger: None,
) -> None:
    """Explicit setup should replace prior handlers and ignore environment fallback."""
    root_logger: logging.Logger = logging.getLogger()
    old_handler = logging.NullHandler()
    root_logger.handlers[:] = [old_handler]
    monkeypatch.setenv("TOPMARK_LOG_LEVEL", "DEBUG")

    core_logging.setup_logging(logging.INFO)

    assert root_logger.level == logging.INFO
    assert old_handler not in root_logger.handlers
    assert len(root_logger.handlers) == 1
    formatter: logging.Formatter | None = root_logger.handlers[0].formatter
    assert formatter is not None
    assert _format_log_message(formatter, logging.INFO) == "[INFO] configured"
