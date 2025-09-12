# topmark:header:start
#
#   project      : TopMark
#   file         : conftest.py
#   file_relpath : tests/conftest.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pytest configuration for the Topmark test suite.

This file sets up global fixtures and customizes the logging configuration for test runs,
ensuring consistent and verbose logging output during testing.

Notes:
    Tests should respect the immutable/mutable configuration split:

    - Build configs using `topmark.config.MutableConfig` (mutable), then
      `freeze()` into a `topmark.config.Config` for **public API**
      calls (``topmark.api.check/strip``).
    - Do **not** mutate a frozen `Config`. If you need to tweak one,
      call `Config.thaw()`, edit the returned `MutableConfig`,
      then `freeze()` again.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, TypeVar, cast

import pytest

from topmark.config import MutableConfig
from topmark.config.logging import TRACE_LEVEL, setup_logging

if TYPE_CHECKING:
    from pathlib import Path

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


@pytest.fixture
def isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each CLI test in an isolated temporary directory.

    This keeps Click's working directory-dependent logic predictable and avoids
    scanning the repository when the test invokes commands with paths like ".".
    """
    cwd = tmp_path / "proj"
    cwd.mkdir()
    (cwd / "src").mkdir()
    # create a tiny source file to satisfy any basic discovery, not processed further
    (cwd / "src" / "dummy.py").write_text("print('hello')\n", encoding="utf-8")

    monkeypatch.chdir(cwd)
    # Avoid noisy logging during tests
    monkeypatch.setenv("TOPMARK_SUPPRESS_BANNER", "1")
    return cwd


def cfg(**overrides: Any) -> dict[str, Any]:
    """Build a minimal **mapping** for API calls (public surface).

    The shape mirrors the TOML structure (e.g., `[files]` table). Callers can
    override nested keys by passing dictionaries that will be merged shallowly.
    """
    base: dict[str, Any] = {
        "files": {
            # When provided, file discovery should consider only these types
            "file_types": ["python"],
        },
        # Other top-level keys are added as needed by tests via overrides
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)  # shallow merge for convenience in tests
        else:
            base[k] = v
    return base


def make_config(**overrides: Any) -> Config:
    """Return a **frozen** `Config` built from defaults and overrides.

    Recommended for public API calls in tests. Edits are applied on a mutable
    builder and then frozen for use by the pipeline.
    """
    m = MutableConfig.from_defaults()
    # apply overrides on the mutable builder
    for k, v in overrides.items():
        setattr(m, k, v)  # or a safer mapping of supported keys
    return m.freeze()


def make_mutable_config(**overrides: Any) -> MutableConfig:
    """Return a **mutable** builder for scenarios that need staged edits.

    Use this in tests that exercise merge logic. For public API calls, prefer
    `make_config` or provide a mapping to the API directly.
    """
    m = MutableConfig.from_defaults()
    for k, v in overrides.items():
        setattr(m, k, v)
    return m
