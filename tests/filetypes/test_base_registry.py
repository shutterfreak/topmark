# topmark:header:start
#
#   project      : TopMark
#   file         : test_base_registry.py
#   file_relpath : tests/filetypes/test_base_registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Smoke tests for the base file type registry.

These tests verify that representative built-in file types are loaded into the
cached base registry exposed by `topmark.filetypes.instances`.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import cast

import pytest

from tests.helpers.registry import make_file_type
from topmark.core.constants import TOPMARK_NAMESPACE
from topmark.filetypes.instances import _BUILTIN_MODULES  # pyright: ignore[reportPrivateUsage]
from topmark.filetypes.instances import _dedupe_by_local_key  # pyright: ignore[reportPrivateUsage]
from topmark.filetypes.instances import _generate_registry  # pyright: ignore[reportPrivateUsage]
from topmark.filetypes.instances import (
    _iter_plugin_filetypes,  # pyright: ignore[reportPrivateUsage]
)
from topmark.filetypes.instances import get_base_file_type_registry
from topmark.filetypes.model import ContentGate
from topmark.filetypes.model import FileType

if TYPE_CHECKING:
    from collections.abc import Iterable
    from types import ModuleType


def _iter_declared_builtin_filetypes() -> Iterable[FileType]:
    """Yield built-in file type declarations in manifest order."""
    for module_name in _BUILTIN_MODULES:
        module: ModuleType = import_module(module_name)
        filetypes_obj: object = getattr(module, "FILETYPES")  # noqa: B009
        assert isinstance(filetypes_obj, list)
        # Pyright cannot infer the element type of dynamically imported module globals.
        filetypes: list[object] = cast("list[object]", filetypes_obj)
        for filetype_obj in filetypes:
            assert isinstance(filetype_obj, FileType)
            yield filetype_obj


def test_base_file_type_registry_contains_expected_builtins() -> None:
    """Smoke-test that built-in file types are loaded into the base registry."""
    registry: dict[str, FileType] = get_base_file_type_registry()

    # Representative known built-ins; keep this small and stable.
    expected_names: set[str] = {
        "python",
        "markdown",
        "xml",
    }

    missing: set[str] = expected_names.difference(registry)
    assert not missing, f"Missing built-in file types: {sorted(missing)}"


def test_base_registry_preserves_declared_builtin_filetype_instances() -> None:
    """The base registry is keyed by each declared built-in local key."""
    declared: tuple[FileType, ...] = tuple(_iter_declared_builtin_filetypes())
    registry: dict[str, FileType] = get_base_file_type_registry()

    assert set(registry) >= {filetype.local_key for filetype in declared}
    for filetype in declared:
        assert registry[filetype.local_key] is filetype


def test_builtin_filetypes_use_stable_topmark_namespace_and_qualified_keys() -> None:
    """First-party file type identities remain stable for registry consumers."""
    registry: dict[str, FileType] = get_base_file_type_registry()

    for local_key, filetype in registry.items():
        assert filetype.namespace == TOPMARK_NAMESPACE
        assert filetype.local_key == local_key
        assert filetype.qualified_key == f"{TOPMARK_NAMESPACE}:{local_key}"


def test_representative_builtin_definitions_protect_resolution_contracts() -> None:
    """Representative built-ins keep their registry-facing match definitions."""
    registry: dict[str, FileType] = get_base_file_type_registry()

    assert registry["json"].skip_processing is True
    assert registry["json"].extensions == [".json"]

    json_as_jsonc: FileType = registry["json-as-jsonc"]
    assert json_as_jsonc.extensions == [".json"]
    assert json_as_jsonc.skip_processing is False
    assert json_as_jsonc.content_gate is ContentGate.IF_EXTENSION
    assert json_as_jsonc.content_matcher is not None
    assert json_as_jsonc.pre_insert_checker is not None

    vscode_jsonc: FileType = registry["vscode-jsonc"]
    assert vscode_jsonc.filenames == [
        ".vscode/settings.json",
        ".vscode/extensions.json",
    ]
    assert vscode_jsonc.matches(Path("project/.vscode/settings.json")) is True
    assert vscode_jsonc.matches(Path("project/settings.json")) is False

    dockerfile: FileType = registry["dockerfile"]
    assert dockerfile.filenames == ["Dockerfile"]
    assert dockerfile.patterns == [r"Dockerfile(\..+)?"]
    assert dockerfile.matches(Path("Dockerfile.dev")) is True

    requirements: FileType = registry["python-requirements"]
    assert requirements.patterns == [
        r"requirements.*\.(in|txt)$",
        r"constraints.*\.txt$",
    ]
    assert requirements.matches(Path("requirements-dev.in")) is True
    assert requirements.matches(Path("constraints.txt")) is True


def test_dedupe_by_local_key_keeps_first_definition() -> None:
    """Duplicate local keys are ignored before base registry generation."""
    first: FileType = make_file_type(local_key="duplicate", description="first")
    duplicate: FileType = make_file_type(local_key="duplicate", description="second")
    unique: FileType = make_file_type(local_key="unique")

    deduped: list[FileType] = _dedupe_by_local_key([first, duplicate, unique])

    assert deduped == [first, unique]


def test_generate_registry_rejects_duplicate_local_keys() -> None:
    """Direct registry generation is strict about duplicate local keys."""
    first: FileType = make_file_type(local_key="duplicate", description="first")
    duplicate: FileType = make_file_type(local_key="duplicate", description="second")

    with pytest.raises(ValueError, match="Duplicate FileType local_key: duplicate"):
        _generate_registry([first, duplicate])


def test_plugin_filetypes_ignore_non_iterable_and_non_filetype_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Entry point loading accepts only iterable FileType payloads."""
    plugin: FileType = make_file_type(local_key="plugin")

    class _NonIterableEntryPoint:
        name: str = "non-iterable"

        def load(self) -> object:
            return lambda: "not-a-filetype-iterable"

    class _MixedEntryPoint:
        name: str = "mixed"

        def load(self) -> object:
            return lambda: ["not-a-filetype", plugin]

    def _select(group: str) -> list[object]:
        assert group == "topmark.filetypes"
        return [_NonIterableEntryPoint(), _MixedEntryPoint()]

    monkeypatch.setattr(
        "topmark.filetypes.instances.entry_points",
        lambda: SimpleNamespace(select=_select),
    )

    assert list(_iter_plugin_filetypes()) == [plugin]
