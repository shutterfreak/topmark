# topmark:header:start
#
#   file         : conftest.py
#   file_relpath : tests/api/conftest.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared fixtures and helpers for TopMark API tests.

This module centralizes tiny repo layouts, a registered Python `HeaderProcessor`,
and small utilities that are reused across tests under `tests/api/`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, Iterator, cast

import pytest

from topmark import api
from topmark.filetypes.base import FileType
from topmark.filetypes.registry import get_header_processor_registry
from topmark.pipeline.processors import register_all_processors
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from topmark.filetypes.base import FileType
    from topmark.pipeline.processors.base import HeaderProcessor


@pytest.fixture()
def register_pair() -> Iterator[Callable[[str], tuple[str, FileType]]]:
    """Factory: register (FT + processor) under a given name; auto-cleanup after test."""
    registered: list[str] = []

    def _make(name: str) -> tuple[str, FileType]:
        ft = stub_ft(name)
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
    """Return the registered :class:`HeaderProcessor` for Python files (idempotent)."""
    register_all_processors()
    ft_name = "python"
    proc = get_header_processor_registry().get(ft_name)
    assert proc, f"No HeaderProcessor registered to FileType '{ft_name}'"
    return proc


@pytest.fixture()
def repo_py_with_and_without_header(tmp_path: Path) -> Path:
    """Tiny repo with two Python files: one without header, one with canonical header.

    Layout:
      src/without_header.py -> Python (supported) without TopMark header
      src/with_header.py -> Python (supported) with TopMark header
    """
    root = tmp_path
    src = root / "src"
    src.mkdir()

    # Python file without header
    without_header = src / "without_header.py"
    without_header.write_text("print('hello')\n", encoding="utf-8")

    # Python file with header (insert the canonical header)
    with_header = src / "with_header.py"
    with_header.write_text("print('hello')\n", encoding="utf-8")
    _ = api.check(
        [with_header],
        apply=True,
        config=None,
        file_types=["python"],
        add_only=True,  # ensure header is inserted/normalized if missing/drifting
    )

    return tmp_path


@pytest.fixture()
def repo_py_with_header(tmp_path: Path) -> Path:
    """Tiny repo with one Python file that has a canonical TopMark header.

    Layout:
      src/with_header.py  -> will receive a canonical header via api.check(..., apply=True)
    """
    root = tmp_path
    src = root / "src"
    src.mkdir()

    # Python file with header (insert the canonical header)
    with_header = src / "with_header.py"
    with_header.write_text("print('hello')\n", encoding="utf-8")
    _ = api.check(
        [with_header],
        apply=True,
        config=None,
        file_types=["python"],
        add_only=True,  # ensure header is inserted/normalized if missing/drifting
    )

    return root


@pytest.fixture()
def repo_py_with_header_and_xyz(tmp_path: Path) -> Path:
    """Tiny repo with one headered Python file plus an unsupported '.xyz' file.

    Layout:
      src/with_header.py -> Python (supported)
      src/notes.xyz      -> Unsupported extension
    """
    root = tmp_path
    src = root / "src"
    src.mkdir()

    # Python file with header (insert the canonical header)
    with_header = src / "with_header.py"
    with_header.write_text("print('hello')\n", encoding="utf-8")
    _ = api.check(
        [with_header],
        apply=True,
        config=None,
        file_types=["python"],
        add_only=True,  # ensure header is inserted/normalized if missing/drifting
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
    root = tmp_path
    src = root / "src"
    src.mkdir()

    # Python file without header
    without_header = src / "without_header.py"
    without_header.write_text("print('hello')\n", encoding="utf-8")

    # Unsupported 'xyz' file extension without header
    (src / "note.xyz").write_text("TopMark test file\n", encoding="utf-8")

    # TOML file without header
    (src / "data.toml").write_text("[tool.example]\nkey='value'\n", encoding="utf-8")
    return root


# Helpers


def has_header(text: str, processor: HeaderProcessor) -> bool:
    """Return True if the file contents contains a TopMark header."""
    start, end = processor.get_header_bounds(text.splitlines(keepends=True))
    return start is not None and end is not None and start < end


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
    add_only: bool = False,
    update_only: bool = False,
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
    file_types: Iterable[str] | None = ("python",),
) -> api.RunResult:
    """Run :func:`topmark.api.check` against `root / 'src'` with common defaults."""
    paths = [root / "src"]
    return api.check(
        paths,
        apply=apply,
        config=None,  # let API load topmark.toml from repo root
        file_types=list(file_types) if file_types else None,
        add_only=add_only,
        update_only=update_only,
        skip_compliant=skip_compliant,
        skip_unsupported=skip_unsupported,
    )


def api_strip_dir(
    root: Path,
    *,
    apply: bool = False,
    skip_compliant: bool = False,
    skip_unsupported: bool = False,
    file_types: Iterable[str] | None = ("python",),
) -> api.RunResult:
    """Run :func:`topmark.api.strip` against `root / 'src'` with common defaults."""
    paths = [root / "src"]
    return api.strip(
        paths,
        apply=apply,
        config=None,
        file_types=list(file_types) if file_types else None,
        skip_compliant=skip_compliant,
        skip_unsupported=skip_unsupported,
    )


# ---- Stub types and tiny helpers for registry API tests ----


# Duck-typed stubs that satisfy just what the registry uses
class _StubFileType:
    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self.extensions = ()
        self.filenames = ()
        self.patterns = ()
        self.skip_processing = False
        self.has_content_matcher = False
        self.header_policy_name = ""


class _StubProcessor:
    def __init__(self, description: str = "") -> None:
        self.description = description
        self.line_prefix = ""
        self.line_suffix = ""
        self.block_prefix = ""
        self.block_suffix = ""
        # `file_type` is set by the registry upon registration


def stub_ft(name: str, description: str = "") -> "FileType":
    """Return a duck-typed FileType stub cast for strict API use in tests."""
    return cast("FileType", _StubFileType(name, description=description))


def stub_proc_cls() -> type["HeaderProcessor"]:
    """Return a duck-typed HeaderProcessor class for registry tests."""
    return cast("type[HeaderProcessor]", _StubProcessor)
