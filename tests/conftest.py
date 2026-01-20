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

    - Build configs using `topmark.config.MutableConfig` (mutable), then
      `freeze()` into a `topmark.config.Config` for **public API**
      calls (``topmark.api.check/strip``).
    - Do **not** mutate a frozen `Config`. If you need to tweak one,
      call `Config.thaw()`, edit the returned `MutableConfig`,
      then `freeze()` again.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Literal, TypeVar, cast

import pytest

from topmark.config import MutableConfig, PatternSource, logging
from topmark.filetypes.base import ContentGate, FileType
from topmark.pipeline.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from topmark.config import Config

AnyCallable = Callable[..., object]
DecoratorType = Callable[[AnyCallable], AnyCallable]
ScopeName = Literal["session", "package", "module", "class", "function"]

# Typed fixture wrappers for pytest.fixture
F = TypeVar("F", bound=Callable[..., object])

# --- Typed Wrappers ---


def as_typed_mark(mark: Any) -> DecoratorType:
    """Wrap a pytest mark so static type checkers preserve the function type.

    Args:
        mark (Any): A pytest mark decorator such as `pytest.mark.integration`.

    Returns:
        DecoratorType: A decorator that preserves the wrapped function's type.
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
        *args (Any): Positional arguments forwarded to `pytest.mark.parametrize`.
        **kwargs (Any): Keyword arguments forwarded to `pytest.mark.parametrize`.

    Returns:
        DecoratorType: A decorator that preserves the wrapped function's type.
    """
    mark: pytest.MarkDecorator = pytest.mark.parametrize(*args, **kwargs)
    return as_typed_mark(mark)


def hookimpl(*args: Any, **kwargs: Any) -> DecoratorType:
    """Typed wrapper for `pytest.hookimpl`.

    Args:
        *args (Any): Positional arguments forwarded to `pytest.hookimpl`.
        **kwargs (Any): Keyword arguments forwarded to `pytest.hookimpl`.

    Returns:
        DecoratorType: A decorator that preserves the wrapped function's type.
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
        monkeypatch (pytest.MonkeyPatch): Pytest monkeypatch fixture used to manipulate
            environment variables.
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
    from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry
    from topmark.registry import processors as _processors_mod

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


# --- Generic Test Helpers ---


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

    For most tests, prefer the `default_config` fixture.
    Use `make_mutable_config` only when deliberately testing config merge logic.

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


@pytest.fixture
def default_config() -> Config:
    """Per-test default Config built from defaults."""
    return make_config()


# --- FileType / Registry Helpers ---


def make_file_type(
    *,
    name: str,
    extensions: Sequence[str] | None = None,
    filenames: Sequence[str] | None = None,
    patterns: Sequence[str] | None = None,
    content_gate: ContentGate = ContentGate.NEVER,
    content_matcher: Callable[[Path], bool] | None = None,
    matches: Callable[[Path], bool] | None = None,
    skip_processing: bool = False,
) -> FileType:
    """Create a minimal duck-typed `FileType` for tests.

    This helper avoids importing/constructing the real `FileType` implementation in
    unit tests that only require its public attributes. The returned object is a
    `types.SimpleNamespace` cast to `FileType` so call sites remain statically typed
    under Pyright strict mode.

    Notes:
        - `content_matcher` is used by resolver scoring and content-gating tests.
        - `matches` is used by file discovery/filtering (`resolve_file_list`). If not
          provided, it defaults to a small matcher that checks extensions, filename tails,
          regex patterns (fullmatch), and finally falls back to `content_matcher` when available.
        - The default matcher is path-based and doesn’t read file contents unless `content_matcher`
          is provided. Extension matching is suffix-based, so `.tar.gz` rules work.

    Args:
        name (str): File type identifier.
        extensions (Sequence[str] | None): Extension rules (including leading dots, e.g. `.py`).
        filenames (Sequence[str] | None): Filename-tail rules (relative path tails).
        patterns (Sequence[str] | None): Regex patterns (strings) evaluated via fullmatch
            in the resolver.
        content_gate (ContentGate): Content gating mode.
        content_matcher (Callable[[Path], bool] | None): Optional content matcher callable.
        matches (Callable[[Path], bool] | None): Optional matcher used by file discovery
            and file-type filtering. If not provided, `matches` defaults to a small matcher
            that checks extensions, filename tails, regex patterns (fullmatch),
            then falls back to content_matcher.
        skip_processing (bool): Whether this file type is known but has no headers.

    Returns:
        FileType: A duck-typed `FileType` instance.
    """
    # `resolve_file_list()` expects FileType.matches(Path) -> bool.
    # The real FileType implementation can match on extensions, filename tails,
    # regex patterns, and (optionally) content matchers.
    ext_rules: list[str] = list(extensions or ())
    filename_rules: list[str] = list(filenames or ())
    pattern_rules: list[str] = list(patterns or ())

    def _default_matches(p: Path) -> bool:
        # Normalize for deterministic comparisons across OS path styles.
        name_str: str = p.name
        posix_str: str = p.as_posix()

        # 1) Extension rules (replicates `FileType.matches()` implementation)
        suffix: str = p.suffix
        for ext in ext_rules:
            if ext.count(".") > 1:
                # Multiple-dot suffix (e.g., `.tar.gz`)
                if name_str.endswith(ext):
                    return True
            else:
                # Single-dot suffix
                if suffix == ext:
                    return True

        # 2) Filename-tail rules (relative tails)
        #    We support both exact filename matches and path tail matches.
        for tail in filename_rules:
            if not tail:
                continue
            tail_norm: str = tail.replace("\\", "/")
            if (
                name_str == tail_norm
                or posix_str.endswith("/" + tail_norm)
                or posix_str.endswith(tail_norm)
            ):
                return True

        # 3) Regex patterns (fullmatch contract)
        if pattern_rules:
            for pat in pattern_rules:
                if not pat:
                    continue
                try:
                    if re.fullmatch(pat, name_str) or re.fullmatch(pat, posix_str):
                        return True
                except re.error:
                    # Test helper: ignore invalid regexes; production code validates.
                    continue

        # 4) Optional content matcher fallback
        if content_matcher is not None:
            try:
                return bool(content_matcher(p))
            except Exception:
                return False

        return False

    matcher: Callable[[Path], bool]
    if matches is not None:
        matcher = matches
    else:
        matcher = _default_matches

    obj = SimpleNamespace(
        name=name,
        extensions=ext_rules,
        filenames=filename_rules,
        patterns=pattern_rules,
        content_gate=content_gate,
        content_matcher=content_matcher,
        matches=matcher,
        skip_processing=skip_processing,
    )

    return cast("FileType", obj)


@contextmanager
def patched_effective_registries(
    *,
    filetypes: Mapping[str, FileType],
    processors: Mapping[str, HeaderProcessor],
) -> Iterator[None]:
    """Temporarily override the *effective* registries used by TopMark.

    This helper patches the composed registry views returned by
    `FileTypeRegistry.as_mapping()` and `HeaderProcessorRegistry.as_mapping()` by
    overriding the internal `_compose()` classmethods used to build the composed views.

    Use this in tests that need deterministic, minimal registries without
    depending on built-in file types/processors or plugin discovery.

    Notes:
        - This overrides the composition function only; overlays remain reset
          by the autouse fixture (or are irrelevant while patched).
        - Cache is cleared before patch, after patch, and again on restore.

    Args:
        filetypes (Mapping[str, FileType]): Effective file type registry
            to expose for the duration of the context.
        processors (Mapping[str, HeaderProcessor]): Effective header processor registry
            to expose for the duration of the context.

    Yields:
        None: This context manager yields control to the caller while the effective
            registries are patched.
    """
    from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry

    # Silence Pyright regarding use of private members:
    ft_reg = cast("Any", FileTypeRegistry)
    hp_reg = cast("Any", HeaderProcessorRegistry)

    ft_reg._clear_cache()
    hp_reg._clear_cache()

    orig_ft_compose = ft_reg._compose
    orig_hp_compose = hp_reg._compose
    try:
        ft_reg._compose = classmethod(lambda cls: dict(filetypes))
        hp_reg._compose = classmethod(lambda cls: dict(processors))
        ft_reg._clear_cache()
        hp_reg._clear_cache()
        yield
    finally:
        ft_reg._compose = orig_ft_compose
        hp_reg._compose = orig_hp_compose
        ft_reg._clear_cache()
        hp_reg._clear_cache()


# --- Fixture: effective_registries ---

#
# Type alias for the callable returned by the effective_registries() fixture.
EffectiveRegistries = Callable[
    [Mapping[str, FileType], Mapping[str, HeaderProcessor]],
    AbstractContextManager[None],
]


@pytest.fixture
def effective_registries() -> EffectiveRegistries:
    """Return a callable that patches the effective registries for the duration of a test.

    This fixture is a thin wrapper around `patched_effective_registries` that
    integrates naturally with pytest.

    Example:
        ```python
        with effective_registries(filetypes, processors):
            ...
        ```

    Returns:
        EffectiveRegistries: Callable that takes `(filetypes, processors)` mappings and
            returns a context manager applying those registries.
    """

    def _override(
        filetypes: Mapping[str, FileType],
        processors: Mapping[str, HeaderProcessor],
    ) -> AbstractContextManager[None]:
        return patched_effective_registries(filetypes=filetypes, processors=processors)

    return _override
