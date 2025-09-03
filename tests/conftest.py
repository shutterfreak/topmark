# topmark:header:start
#
#   file         : conftest.py
#   file_relpath : tests/conftest.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pytest configuration file for the Topmark test suite.

This file sets up global fixtures and customizes the logging configuration for test runs,
ensuring consistent and verbose logging output during testing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

import pytest

from topmark.config.logging import TRACE_LEVEL, setup_logging

if TYPE_CHECKING:
    from topmark.config import Config

F = TypeVar("F", bound=Callable[..., object])


def as_typed_mark(mark: Any) -> Callable[[F], F]:
    """Wrap a pytest mark so mypy knows it preserves function type."""

    def _decorator(func: F) -> F:
        return cast("F", mark(func))

    return _decorator


mark_integration = as_typed_mark(pytest.mark.integration)
mark_pipeline = as_typed_mark(pytest.mark.pipeline)
mark_cli = as_typed_mark(pytest.mark.cli)


def parametrize(*args: Any, **kwargs: Any) -> Callable[[F], F]:
    """Typed wrapper for pytest.mark.parametrize."""
    mark = pytest.mark.parametrize(*args, **kwargs)
    return as_typed_mark(mark)


def hookimpl(*args: Any, **kwargs: Any) -> Callable[[F], F]:
    """Typed wrapper for pytest.hookimpl(*, tryfirst=..., etc.)."""
    return as_typed_mark(pytest.hookimpl(*args, **kwargs))


def fixture(*args: Any, **kwargs: Any) -> Callable[[F], F]:
    """Typed wrapper for pytest.fixture(...)."""
    return as_typed_mark(pytest.fixture(*args, **kwargs))


@hookimpl(tryfirst=True)
def pytest_configure(config: Config) -> None:  # pylint: disable=unused-argument
    """Configure pytest settings and customize logging for the test suite.

    This function sets the logging level to TRACE (if available) for all tests,
    ensuring detailed output is captured during test execution.
    """
    setup_logging(level=TRACE_LEVEL)
