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

from typing import TYPE_CHECKING, Any, cast

import pytest

from topmark import api
from topmark.api.public_types import PublicPolicy
from topmark.filetypes.base import FileType
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.processors.types import BoundsKind, HeaderBounds
from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Iterator
    from pathlib import Path

    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor


def cfg(**overrides: Any) -> dict[str, Any]:
    """Build a minimal **mapping** for API calls that accept a config dict.

    This helper intentionally returns a plain dictionary shaped like the
    TOML structure (e.g., the ``[files]`` table). It is used to exercise the
    public API branch where callers pass a *mapping* instead of a fully
    constructed [`Config`][topmark.config.Config].

    Notes:
        * Only a tiny base is provided (``files.include_file_types = ["python"]``) so tests
          are explicit about what is enabled. Merging of ``overrides`` is **shallow**
          at the top level for convenience.
        * No defaults, no layered discovery, no path normalization, and no
          ``PatternSource`` coercion happen here—that behavior is covered by tests
          using `tests.conftest.make_config` / `tests.conftest.make_mutable_config`.

    Args:
        **overrides (Any): Arbitrary keyword arguments collected into a
            ``dict[str, Any]``. Keys correspond to top-level TOML tables
            (e.g., ``files``), and values may be nested mappings.

    Returns:
        dict[str, Any]: A TOML-shaped mapping suitable for ``api.check(..., config=...)``.
    """
    base: dict[str, Any] = {
        "files": {
            # When provided, discovery should consider only these types
            "include_file_types": ["python"],
        },
    }
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            base[k].update(v)  # shallow merge for convenience in tests
        else:
            base[k] = v
    return base


@pytest.fixture()
def register_pair() -> Iterator[Callable[[str], tuple[str, FileType]]]:
    """Factory: register (FT + processor) under a given name; auto-cleanup after test."""
    registered: list[str] = []

    def _make(name: str) -> tuple[str, FileType]:
        ft: FileType = stub_ft(name)
        FileTypeRegistry.register(ft)
        HeaderProcessorRegistry.register(name, stub_proc_cls())
        registered.append(name)
        return name, ft

    try:
        yield _make
    finally:
        for name in registered:
            HeaderProcessorRegistry.unregister(name)
            FileTypeRegistry.unregister(name)


@pytest.fixture()
def proc_py() -> HeaderProcessor:
    """Return the registered `HeaderProcessor` for Python files (composed view)."""
    ft_name = "python"
    proc: HeaderProcessor | None = HeaderProcessorRegistry.get(ft_name)
    assert proc, f"No HeaderProcessor registered to FileType '{ft_name}'"
    return proc


@pytest.fixture()
def repo_py_with_and_without_header(tmp_path: Path) -> Path:
    """Tiny repo with two Python files: one without header, one with canonical header.

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
            add_only=True
        ),  # ensure header is inserted/normalized if missing/drifting
    )

    return tmp_path


@pytest.fixture()
def repo_py_with_header(tmp_path: Path) -> Path:
    """Tiny repo with one Python file that has a canonical TopMark header.

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
            add_only=True,  # ensure header is inserted/normalized if missing/drifting
        ),
    )

    return root


@pytest.fixture()
def repo_py_with_header_and_xyz(tmp_path: Path) -> Path:
    """Tiny repo with one headered Python file plus an unsupported '.xyz' file.

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
            add_only=True,  # ensure header is inserted/normalized if missing/drifting
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


def by_path_outcome(run_result: api.RunResult) -> dict[Path, str]:
    """Return a mapping of each file path to its outcome string (e.g., 'unchanged')."""
    return {fr.path: fr.outcome.value for fr in run_result.files}


def read_text(path: Path) -> str:
    """Read a UTF-8 file and return its text contents."""
    return path.read_text(encoding="utf-8")


def api_check_dir(
    root: Path,
    *,
    apply: bool = False,
    policy: PublicPolicy | None = None,
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
    include_file_types: Iterable[str] | None = ("python",),
    exclude_file_types: Iterable[str] | None = ("python",),
    prune: bool = False,
) -> api.RunResult:
    """Run [`topmark.api.check`][topmark.api.check] against `root / 'src'` with common defaults."""
    paths: list[Path] = [root / "src"]
    return api.check(
        paths,
        apply=apply,
        config=None,  # let API load topmark.toml from repo root
        include_file_types=list(include_file_types) if include_file_types else None,
        exclude_file_types=list(exclude_file_types) if exclude_file_types else None,
        policy=policy,
        skip_compliant=skip_compliant,
        skip_unsupported=skip_unsupported,
        prune=prune,
    )


def api_strip_dir(
    root: Path,
    *,
    apply: bool = False,
    policy: PublicPolicy | None = None,
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
    include_file_types: Iterable[str] | None = ("python",),
    exclude_file_types: Iterable[str] | None = ("python",),
    prune: bool = False,
) -> api.RunResult:
    """Run [`topmark.api.strip`][topmark.api.strip] against `root / 'src'` with common defaults."""
    paths: list[Path] = [root / "src"]
    return api.strip(
        paths,
        apply=apply,
        config=None,
        include_file_types=list(include_file_types) if include_file_types else None,
        exclude_file_types=list(exclude_file_types) if exclude_file_types else None,
        policy=policy,
        skip_compliant=skip_compliant,
        skip_unsupported=skip_unsupported,
        prune=prune,
    )


# ---- Stub types and tiny helpers for registry API tests ----


# Duck-typed stubs that satisfy just what the registry uses
class _StubFileType:
    def __init__(self, name: str, description: str = "") -> None:
        self.name: str = name
        self.description: str = description
        self.extensions: tuple[str, ...] = ()
        self.filenames: tuple[str, ...] = ()
        self.patterns: tuple[str, ...] = ()
        self.skip_processing = False
        self.has_content_matcher = False
        self.header_policy_name: str = ""


class _StubProcessor:
    def __init__(self, description: str = "") -> None:
        self.description: str = description
        self.line_prefix: str = ""
        self.line_suffix: str = ""
        self.block_prefix: str = ""
        self.block_suffix: str = ""
        # `file_type` is set by the registry upon registration


def stub_ft(name: str, description: str = "") -> FileType:
    """Return a duck-typed FileType stub cast for strict API use in tests."""
    return cast("FileType", _StubFileType(name, description=description))


def stub_proc_cls() -> type[HeaderProcessor]:
    """Return a duck-typed HeaderProcessor class for registry tests."""
    return cast("type[HeaderProcessor]", _StubProcessor)
