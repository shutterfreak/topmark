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

from tests.helpers.registry import make_file_type
from tests.helpers.registry import registry_processor_class
from topmark import api
from topmark.api.types import PublicPolicy
from topmark.processors.types import BoundsKind
from topmark.processors.types import HeaderBounds
from topmark.registry.bindings import BindingRegistry
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry
from topmark.registry.registry import Registry

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator
    from pathlib import Path

    from topmark.filetypes.model import FileType
    from topmark.processors.base import HeaderProcessor
    from topmark.registry.types import ProcessorDefinition


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
