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

It also enforces test isolation for TopMark's process-global registries by resetting
registry overlays and composed-view caches between tests.

Notes:
    Tests should respect the immutable/mutable configuration split:

    - Build configs using `topmark.config.model.MutableConfig ` (mutable), then
      `freeze()` into a `topmark.config.model.Config ` for **public API**
      calls (``topmark.api.check/strip``).
    - Do **not** mutate a frozen `Config`. If you need to tweak one,
      call `Config.thaw()`, edit the returned `MutableConfig`,
      then `freeze()` again.
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Mapping
from contextlib import AbstractContextManager
from typing import TYPE_CHECKING
from typing import Any
from typing import Literal
from typing import TypeAlias
from typing import cast

import pytest

from tests.helpers.config import make_config
from tests.helpers.registry import patched_effective_registries
from topmark.core import logging
from topmark.filetypes.model import FileType
from topmark.processors.base import HeaderProcessor
from topmark.registry.types import ProcessorDefinition

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import Config

AnyCallable = Callable[..., object]
DecoratorType = Callable[[AnyCallable], AnyCallable]
ScopeName = Literal["session", "package", "module", "class", "function"]


# --- Typed Wrappers ---


def as_typed_mark(mark: Any) -> DecoratorType:
    """Wrap a pytest mark so static type checkers preserve the function type.

    Args:
        mark: A pytest mark decorator such as `pytest.mark.integration`.

    Returns:
        A decorator that preserves the wrapped function's type.
    """

    def _decorator(func: AnyCallable) -> AnyCallable:
        return cast("AnyCallable", mark(func))

    return _decorator


mark_integration: DecoratorType = as_typed_mark(pytest.mark.integration)
mark_pipeline: DecoratorType = as_typed_mark(pytest.mark.pipeline)
mark_cli: DecoratorType = as_typed_mark(pytest.mark.cli)
mark_dev_validation: DecoratorType = as_typed_mark(pytest.mark.dev_validation)


def parametrize(*args: Any, **kwargs: Any) -> DecoratorType:
    """Typed wrapper for `pytest.mark.parametrize`.

    Args:
        *args: Positional arguments forwarded to `pytest.mark.parametrize`.
        **kwargs: Keyword arguments forwarded to `pytest.mark.parametrize`.

    Returns:
        A decorator that preserves the wrapped function's type.
    """
    mark: pytest.MarkDecorator = pytest.mark.parametrize(*args, **kwargs)
    return as_typed_mark(mark)


def hookimpl(*args: Any, **kwargs: Any) -> DecoratorType:
    """Typed wrapper for `pytest.hookimpl`.

    Args:
        *args: Positional arguments forwarded to `pytest.hookimpl`.
        **kwargs: Keyword arguments forwarded to `pytest.hookimpl`.

    Returns:
        A decorator that preserves the wrapped function's type.
    """
    return as_typed_mark(pytest.hookimpl(*args, **kwargs))


# --- Global Autouse Fixtures ---


@pytest.fixture(autouse=True)
def silence_topmark_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure TopMark's runtime log level is not forced via env during tests.

    This avoids accidental DEBUG/TRACE noise when the developer has exported
    TOPMARK_LOG_LEVEL in their shell. Individual tests can still raise the level
    via `pytest_configure` or `caplog`.

    Args:
        monkeypatch: Pytest monkeypatch fixture used to manipulate environment variables.
    """
    # Ensure environment never forces DEBUG during test runs
    monkeypatch.delenv("TOPMARK_LOG_LEVEL", raising=False)


@pytest.fixture(autouse=True)
def reset_registry_overlays() -> Iterator[None]:
    """Reset registry overlay state and composed-view caches for test isolation.

    TopMark registries use process-global overlay state (overrides/removals) plus
    cached composed views. If a test mutates overlays (or forces composition),
    later tests may observe stale state unless we reset between tests.

    Yields:
        None: Control is yielded to the test while registries are isolated.
    """
    from topmark.registry import processors as _processors_mod
    from topmark.registry.filetypes import FileTypeRegistry
    from topmark.registry.processors import HeaderProcessorRegistry

    def _reset() -> None:
        # Silence Pyright regarding use of private members:
        ft_reg = cast("Any", FileTypeRegistry)
        hp_reg = cast("Any", HeaderProcessorRegistry)

        # Clear overlays and composed caches.
        ft_reg._overrides.clear()
        ft_reg._removals.clear()
        ft_reg._clear_cache()

        hp_reg._overrides.clear()
        hp_reg._removals.clear()
        hp_reg._clear_cache()

        # Avoid order dependence for dev validation (intended once-per-process).
        cast("Any", _processors_mod)._validation_done = False

    _reset()
    try:
        yield
    finally:
        _reset()


# --- Other Fixtures ---


@hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:  # pylint: disable=unused-argument
    """Configure pytest settings and customize logging for the test suite.

    This function sets the logging level to TRACE for all tests,
    ensuring detailed output is captured during test execution.

    Args:
        config: The pytest configuration object. This object is used internally by pytest and
            typically holds command line options and configuration data.
    """
    logging.setup_logging(level=logging.TRACE_LEVEL)
    # Less noisy, supported by default logging module (logging.logging):
    # setup_logging(level=logging.logging.DEBUG)


@pytest.fixture
def isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run each CLI test in an isolated temporary directory.

    This keeps Click's working directory-dependent logic predictable and avoids
    scanning the repository when the test invokes commands with paths like ".".

    Args:
        tmp_path: The pytest-provided temporary directory for the test.
        monkeypatch: Fixture to change the working directory and environment.

    Returns:
        The path to the isolated temporary working directory created for the test. This directory
        serves as the simulated project root for CLI commands and contains a minimal `src/dummy.py`
        file to satisfy discovery logic.
    """
    cwd: Path = tmp_path / "proj"
    cwd.mkdir()
    (cwd / "src").mkdir()
    # create a tiny source file to satisfy any basic discovery, not processed further
    (cwd / "src" / "dummy.py").write_text("print('hello')\n", encoding="utf-8")

    monkeypatch.chdir(cwd)
    # Avoid noisy logging during tests
    monkeypatch.setenv("TOPMARK_SUPPRESS_BANNER", "1")
    return cwd


# --- Generic Test Helpers ---


@pytest.fixture
def default_config() -> Config:
    """Per-test default Config built from defaults."""
    return make_config()


# --- Fixture: effective_registries ---


EffectiveRegistries: TypeAlias = Callable[
    [Mapping[str, FileType], Mapping[str, HeaderProcessor | ProcessorDefinition]],
    AbstractContextManager[None],
]
"""Type alias for the callable returned by the effective_registries() fixture."""


@pytest.fixture
def effective_registries() -> EffectiveRegistries:
    """Return a callable that patches the effective registries for the duration of a test.

    This fixture is a thin wrapper around `patched_effective_registries` that
    integrates naturally with pytest and patches the canonical processor-key
    and file-type-key registry views together with the local-key compatibility
    view for file types.

    Example:
        ```python
        with effective_registries(filetypes, processors):
            ...
        ```

    Returns:
        Callable that takes `(filetypes, processors)` mappings and returns a context manager
        applying those registries.
    """

    def _override(
        filetypes: Mapping[str, FileType],
        processors: Mapping[str, HeaderProcessor | ProcessorDefinition],
    ) -> AbstractContextManager[None]:
        return patched_effective_registries(filetypes=filetypes, processors=processors)

    return _override
