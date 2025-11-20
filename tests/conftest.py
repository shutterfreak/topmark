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

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

import pytest

from topmark.config import MutableConfig, PatternSource, logging

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.config import Config

F = TypeVar("F", bound=Callable[..., object])

# This defines the type for the decorator function itself:
# It takes a Callable (F) and returns the same Callable (F).
DecoratorType = Callable[[F], F]


def as_typed_mark(mark: Any) -> DecoratorType[Any]:
    """Wrap a pytest mark so static type checkers preserve the function type.

    Args:
        mark (Any): A pytest mark decorator such as `pytest.mark.integration`.

    Returns:
        DecoratorType[Any]: A decorator that preserves the wrapped function's type.
    """

    def _decorator(func: F) -> F:
        return cast("F", mark(func))

    return _decorator


mark_integration: DecoratorType[Any] = as_typed_mark(pytest.mark.integration)
mark_pipeline: DecoratorType[Any] = as_typed_mark(pytest.mark.pipeline)
mark_cli: DecoratorType[Any] = as_typed_mark(pytest.mark.cli)
mark_dev_validation: DecoratorType[Any] = as_typed_mark(pytest.mark.dev_validation)


def parametrize(*args: Any, **kwargs: Any) -> Callable[[F], F]:
    """Typed wrapper for `pytest.mark.parametrize`.

    Args:
        *args (Any): Positional arguments forwarded to `pytest.mark.parametrize`.
        **kwargs (Any): Keyword arguments forwarded to `pytest.mark.parametrize`.

    Returns:
        Callable[[F], F]: A decorator that preserves the wrapped function's type.
    """
    mark: pytest.MarkDecorator = pytest.mark.parametrize(*args, **kwargs)
    return as_typed_mark(mark)


def hookimpl(*args: Any, **kwargs: Any) -> Callable[[F], F]:
    """Typed wrapper for `pytest.hookimpl`.

    Args:
        *args (Any): Positional arguments forwarded to `pytest.hookimpl`.
        **kwargs (Any): Keyword arguments forwarded to `pytest.hookimpl`.

    Returns:
        Callable[[F], F]: A decorator that preserves the wrapped function's type.
    """
    return as_typed_mark(pytest.hookimpl(*args, **kwargs))


def fixture(*args: Any, **kwargs: Any) -> Callable[[F], F]:
    """Typed wrapper for `pytest.fixture`.

    Args:
        *args (Any): Positional arguments forwarded to `pytest.fixture`.
        **kwargs (Any): Keyword arguments forwarded to `pytest.fixture`.

    Returns:
        Callable[[F], F]: A decorator that preserves the wrapped function's type.
    """
    return as_typed_mark(pytest.fixture(*args, **kwargs))


@pytest.fixture(autouse=True)
def silence_topmark_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure TopMark's runtime log level is not forced via env during tests.

    This avoids accidental DEBUG/TRACE noise when the developer has exported
    TOPMARK_LOG_LEVEL in their shell. Individual tests can still raise the level
    via `pytest_configure` or `caplog`.

    Args:
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture used to manipulate
            environment variables.
    """
    # Ensure environment never forces DEBUG during test runs
    monkeypatch.delenv("TOPMARK_LOG_LEVEL", raising=False)


@hookimpl(tryfirst=True)
def pytest_configure(config: pytest.Config) -> None:  # pylint: disable=unused-argument
    """Configure pytest settings and customize logging for the test suite.

    This function sets the logging level to TRACE for all tests,
    ensuring detailed output is captured during test execution.

    Args:
        config (pytest.Config): The pytest configuration object. This object
            is used internally by pytest and typically holds command line options
            and configuration data.
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
        tmp_path (Path): The pytest-provided temporary directory for the test.
        monkeypatch (pytest.MonkeyPatch): Fixture to change the working directory and environment.

    Returns:
        Path: The path to the isolated temporary working directory created
            for the test. This directory serves as the simulated project root
            for CLI commands and contains a minimal `src/dummy.py` file to
            satisfy discovery logic.
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


def to_pattern_sources(values: Sequence[str | Path | PatternSource]) -> list[PatternSource]:
    """Coerce a sequence of strings/Paths or PatternSource into PatternSource list.

    Public test helper: converts strings and Paths into absolute `PatternSource`
    instances (with `base` set to `path.parent`). Existing `PatternSource`
    instances are returned unchanged.

    Args:
        values (Sequence[str | Path | PatternSource]): Items to coerce.

    Returns:
        list[PatternSource]: Coerced list of `PatternSource` instances.
    """
    if not values:
        return []
    out: list[PatternSource] = []
    for item in values:
        if isinstance(item, PatternSource):
            out.append(item)
            continue
        p: Path = Path(item).resolve()
        out.append(PatternSource(path=p, base=p.parent))
    return out


def make_config(**overrides: Any) -> Config:
    """Return a frozen `Config` built from defaults and overrides.

    Recommended for public API calls in tests. Edits are applied on a mutable
    builder and then frozen for use by the pipeline.

    Args:
        **overrides (Any): Keyword overrides applied to the mutable builder before freezing.

    Returns:
        Config: An immutable configuration snapshot for use in tests.
    """
    m: MutableConfig = make_mutable_config(**overrides)
    return m.freeze()


def make_mutable_config(**overrides: Any) -> MutableConfig:
    """Return a mutable builder for scenarios that need staged edits.

    Use this in tests that exercise merge logic. For public API calls, prefer
    `make_config` or provide a mapping to the API directly.

    Args:
        **overrides (Any): Keyword overrides to apply to the mutable builder.
            Keys `include_from`, `exclude_from`, and `files_from` may be sequences of
            strings, `Path`, or `PatternSource`; these are coerced to `PatternSource`.

    Returns:
        MutableConfig: A mutable configuration object ready to be frozen or further edited.
    """
    m: MutableConfig = MutableConfig.from_defaults()

    # Coerce path-to-file overrides to PatternSource where needed
    if "include_from" in overrides:
        m.include_from = to_pattern_sources(overrides.pop("include_from"))
    if "exclude_from" in overrides:
        m.exclude_from = to_pattern_sources(overrides.pop("exclude_from"))
    if "files_from" in overrides:
        m.files_from = to_pattern_sources(overrides.pop("files_from"))

    # Apply remaining overrides verbatim (files, patterns, types, etc.)
    for k, v in overrides.items():
        setattr(m, k, v)  # still allow direct overrides for convenience

    return m
