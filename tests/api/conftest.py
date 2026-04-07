# topmark:header:start
#
#   project      : TopMark
#   file         : conftest.py
#   file_relpath : tests/api/conftest.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared fixtures and helpers for TopMark API tests.

This module centralizes tiny repo layouts, a registered Python `HeaderProcessor`,
and small utilities that are reused across tests under `tests/api/`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.conftest import make_file_type
from tests.conftest import registry_processor_class
from topmark import api
from topmark.api.runtime import select_pipeline
from topmark.api.types import PipelineKindLiteral
from topmark.api.types import PublicPolicy
from topmark.api.types import PublicReportScopeLiteral
from topmark.config.resolution.bridge import resolve_toml_sources_and_build_config_draft
from topmark.pipeline.engine import run_steps_for_files
from topmark.processors.types import BoundsKind
from topmark.processors.types import HeaderBounds
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.registry import Registry
from topmark.resolution.files import resolve_file_list
from topmark.runtime.model import RunOptions
from topmark.toml.keys import Toml

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterable
    from collections.abc import Iterator
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.config.model import Config
    from topmark.config.model import MutableConfig
    from topmark.core.exit_codes import ExitCode
    from topmark.filetypes.model import FileType
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import ProcessorDefinition
    from topmark.toml.types import TomlValue


# --- File reading ---


def read_text(path: Path) -> str:
    """Read a UTF-8 file and return its text contents."""
    return path.read_text(encoding="utf-8")


# --- Config-related helpers ---


def cfg(**overrides: TomlValue) -> dict[str, TomlValue]:
    """Build a minimal **mapping** for API calls that accept a config dict.

    This helper intentionally returns a plain dictionary shaped like the
    TOML structure (e.g., the ``[files]`` table). It is used to exercise the
    public API branch where callers pass a *mapping* instead of a fully
    constructed [`Config`][topmark.config.model.Config].

    Notes:
        * Only a tiny base is provided (``files.include_file_types = ["python"]``) so tests
          are explicit about what is enabled. Merging of ``overrides`` is **shallow**
          at the top level for convenience.
        * No defaults, no layered discovery, no path normalization, and no
          ``PatternSource`` coercion happen here—that behavior is covered by tests
          using `tests.conftest.make_config` / `tests.conftest.make_mutable_config`.

    Args:
        **overrides: Arbitrary keyword arguments collected into a ``dict[str, object]``. Keys
            correspond to top-level TOML tables (e.g., ``files``), and values may be nested
            mappings.

    Returns:
        A TOML-shaped mapping suitable for ``api.check(..., config=...)``.
    """
    base: dict[str, TomlValue] = {
        Toml.SECTION_FILES: {
            # When provided, discovery should consider only these types
            Toml.KEY_INCLUDE_FILE_TYPES: ["python"],
        },
    }
    for k, v in overrides.items():
        existing: TomlValue | None = base.get(k)

        # We use 'existing' as a local variable so Pyright can safely narrow
        # the type to dict[str, TomlValue] after the isinstance check.
        if isinstance(v, dict) and isinstance(existing, dict):
            existing.update(v)  # shallow merge for convenience in tests
        else:
            base[k] = v
    return base


# --- Pipeline helpers


def by_path_outcome(run_result: api.RunResult) -> dict[Path, str]:
    """Return a mapping of each file path to its outcome string (e.g., 'unchanged')."""
    return {fr.path: fr.outcome.value for fr in run_result.files}


def api_check_dir(
    root: Path,
    *,
    apply: bool = False,
    policy: PublicPolicy | None = None,
    report: PublicReportScopeLiteral = "all",
    include_file_types: Iterable[str] | None = None,
    exclude_file_types: Iterable[str] | None = None,
    prune: bool = False,
) -> api.RunResult:
    """Run [`topmark.api.check`][topmark.api.check] against `root / 'src'` with common defaults.

    By default, does not exclude any file types (no blacklist).

    Args:
        root: Repository-like temporary root whose `src/` subtree should be processed.
        apply: Whether to run in apply mode.
        policy: Optional public policy overlay.
        report: Report-scope selection for the returned API view.
        include_file_types: Optional whitelist of file type identifiers.
        exclude_file_types: Optional blacklist of file type identifiers.
        prune: Whether to prune heavy views in the returned `RunResult`.

    Returns:
        Result of `api.check(...)` over `root / "src"`.
    """
    paths: list[Path] = [root / "src"]
    return api.check(
        paths,
        apply=apply,
        config=None,  # let API load topmark.toml from repo root
        include_file_types=list(include_file_types) if include_file_types else None,
        exclude_file_types=list(exclude_file_types) if exclude_file_types else None,
        policy=policy,
        report=report,
        prune_views=prune,
    )


def api_strip_dir(
    root: Path,
    *,
    apply: bool = False,
    policy: PublicPolicy | None = None,
    report: PublicReportScopeLiteral = "all",
    include_file_types: Iterable[str] | None = None,
    exclude_file_types: Iterable[str] | None = None,
    prune: bool = False,
) -> api.RunResult:
    """Run [`topmark.api.strip`][topmark.api.strip] against `root / 'src'` with common defaults.

    By default, does not exclude any file types (no blacklist).

    Args:
        root: Repository-like temporary root whose `src/` subtree should be processed.
        apply: Whether to run in apply mode.
        policy: Optional public policy overlay.
        report: Report-scope selection for the returned API view.
        include_file_types: Optional whitelist of file type identifiers.
        exclude_file_types: Optional blacklist of file type identifiers.
        prune: Whether to prune heavy views in the returned `RunResult`.

    Returns:
        Result of `api.strip(...)` over `root / "src"`.
    """
    paths: list[Path] = [root / "src"]
    return api.strip(
        paths,
        apply=apply,
        config=None,
        include_file_types=list(include_file_types) if include_file_types else None,
        exclude_file_types=list(exclude_file_types) if exclude_file_types else None,
        policy=policy,
        report=report,
        prune_views=prune,
    )


# --- Test fixtures


@pytest.fixture()
def register_pair() -> Iterator[Callable[[str], tuple[str, FileType, str]]]:
    """Factory: register a file type, processor definition, and binding; auto-cleanup after test."""
    registered: list[tuple[str, str]] = []

    def _make(name: str) -> tuple[str, FileType, str]:
        ft: FileType = make_file_type(local_key=name)
        FileTypeRegistry.register(ft)
        proc_def: ProcessorDefinition = HeaderProcessorRegistry.register(
            processor_class=registry_processor_class(),
        )
        BindingRegistry.bind(
            file_type_key=ft.qualified_key,
            processor_key=proc_def.qualified_key,
        )
        registered.append((name, proc_def.qualified_key))
        return name, ft, proc_def.qualified_key

    try:
        yield _make
    finally:
        for name, processor_qualified_key in registered:
            ft_obj: FileType | None = FileTypeRegistry.resolve_filetype_id(name)
            if ft_obj is not None:
                BindingRegistry.unbind(ft_obj.qualified_key)
            HeaderProcessorRegistry.unregister(processor_qualified_key)
            FileTypeRegistry.unregister_by_local_key(name)


@pytest.fixture()
def proc_py() -> HeaderProcessor:
    """Return a runtime Python header processor bound to the Python file type."""
    proc: HeaderProcessor | None = Registry.resolve_processor("python")
    assert proc is not None
    assert proc.file_type is not None
    assert proc.file_type.local_key == "python"
    return proc


@pytest.fixture()
def repo_py_with_and_without_header(tmp_path: Path) -> Path:
    """Tiny repo with two Python files: one without header, one with canonical header.

    We use the API apply mode to add the header to the file.

    Layout:
      src/without_header.py -> Python (supported) without TopMark header
      src/with_header.py -> Python (supported) with TopMark header
    """
    root: Path = tmp_path
    src: Path = root / "src"
    src.mkdir()

    # Python file without header
    without_header: Path = src / "without_header.py"
    without_header.write_text("print('hello')\n", encoding="utf-8")

    # Python file with header (insert the canonical header)
    with_header: Path = src / "with_header.py"
    with_header.write_text("print('hello')\n", encoding="utf-8")
    _run_result: api.RunResult = api.check(
        [with_header],
        apply=True,
        config=None,
        include_file_types=["python"],
        policy=PublicPolicy(
            header_mutation_mode="add_only",
        ),  # ensure header is inserted/normalized if missing/drifting
    )

    return tmp_path


@pytest.fixture()
def repo_py_with_header(tmp_path: Path) -> Path:
    """Tiny repo with one Python file that has a canonical TopMark header.

    We use the API apply mode to add the header to the file.

    Layout:
      src/with_header.py  -> will receive a canonical header via api.check(..., apply=True)
    """
    root: Path = tmp_path
    src: Path = root / "src"
    src.mkdir()

    # Python file with header (insert the canonical header)
    with_header: Path = src / "with_header.py"
    with_header.write_text("print('hello')\n", encoding="utf-8")
    _run_result: api.RunResult = api.check(
        [with_header],
        apply=True,
        config=None,
        include_file_types=["python"],
        policy=PublicPolicy(
            header_mutation_mode="add_only",
            # ensure header is inserted/normalized if missing/drifting
        ),
    )

    return root


@pytest.fixture()
def repo_py_with_header_and_xyz(tmp_path: Path) -> Path:
    """Tiny repo with one headered Python file plus an unsupported '.xyz' file.

    We use the API apply mode to add the header to the file.

    Layout:
      src/with_header.py -> Python (supported)
      src/notes.xyz      -> Unsupported extension
    """
    root: Path = tmp_path
    src: Path = root / "src"
    src.mkdir()

    # Python file with header (insert the canonical header)
    with_header: Path = src / "with_header.py"
    with_header.write_text("print('hello')\n", encoding="utf-8")
    _run_result: api.RunResult = api.check(
        [with_header],
        apply=True,
        config=None,
        include_file_types=["python"],
        policy=PublicPolicy(
            header_mutation_mode="add_only",
            # ensure header is inserted/normalized if missing/drifting
        ),
    )

    # Unsupported 'xyz' file extension without header
    (src / "notes.xyz").write_text("TopMark notes\n", encoding="utf-8")

    return root


@pytest.fixture()
def repo_py_toml_xyz_no_header(tmp_path: Path) -> Path:
    """Tiny repo mixing supported and unsupported files (no headers).

    We will pass explicit file paths to the API so both are considered by discovery.
    Layout:
      src/a.py       -> supported (python)
      src/note.xyz   -> treated as unsupported by TopMark
      src/data.toml  -> supported if TOML configured
    """
    root: Path = tmp_path
    src: Path = root / "src"
    src.mkdir()

    # Python file without header
    without_header: Path = src / "without_header.py"
    without_header.write_text("print('hello')\n", encoding="utf-8")

    # Unsupported 'xyz' file extension without header
    (src / "note.xyz").write_text("TopMark test file\n", encoding="utf-8")

    # TOML file without header
    (src / "data.toml").write_text("[tool.example]\nkey='value'\n", encoding="utf-8")
    return root


# Helpers


def has_header(text: str, processor: HeaderProcessor, newline_style: str) -> bool:
    """Return True if the file contents contains a **valid** TopMark header span.

    A header is considered present only when `get_header_bounds()` returns
    `BoundsKind.SPAN` with a non-empty, exclusive-end range. Malformed shapes
    (e.g., only end marker) are **not** treated as a present header.
    """
    bounds: HeaderBounds = processor.get_header_bounds(
        lines=text.splitlines(keepends=True),
        newline_style=newline_style,
    )
    return (
        bounds.kind is BoundsKind.SPAN
        and bounds.start is not None
        and bounds.end is not None
        and bounds.start < bounds.end  # exclusive end; guarantees non-empty span
    )


def run_cli_like(
    anchor: Path,
    kind: PipelineKindLiteral,
    apply: bool = False,
    diff: bool = False,
    prune_views: bool = False,
    include_file_types: tuple[str, ...] = (),
    exclude_file_types: tuple[str, ...] = (),
) -> tuple[MutableConfig, list[Path], list[ProcessingContext]]:
    """Build config via authoritative loader to model CLI behavior.

    This helper exercises the engine using the same layered-config loading path
    as the CLI while supplying explicit invocation-wide runtime options.
    """
    _resolved, draft = resolve_toml_sources_and_build_config_draft(
        input_paths=(anchor,),
    )
    draft.files = [str(anchor)]  # seed positional inputs
    if include_file_types:
        draft.include_file_types = set(include_file_types)
    if exclude_file_types:
        draft.exclude_file_types = set(exclude_file_types)

    cfg: Config = draft.freeze()
    files: list[Path] = resolve_file_list(cfg)
    run_options: RunOptions = RunOptions(
        apply_changes=apply,
        prune_views=prune_views,
    )

    results: list[ProcessingContext]
    _exit_code: ExitCode | None
    pipeline: Sequence[Step[ProcessingContext]] = select_pipeline(kind, apply=apply, diff=diff)
    results, _exit_code = run_steps_for_files(
        run_options=run_options,
        config=cfg,
        path_configs=None,
        pipeline=pipeline,
        file_list=files,
    )
    return draft, files, results
