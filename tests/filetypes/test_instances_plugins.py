# topmark:header:start
#
#   project      : TopMark
#   file         : test_instances_plugins.py
#   file_relpath : tests/filetypes/test_instances_plugins.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests plugin entry-point discovery integration with the registry (Google style)."""

from __future__ import annotations

from types import ModuleType
from types import SimpleNamespace
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from tests.helpers.registry import make_file_type
from topmark.filetypes.instances import (
    _iter_builtin_filetypes,  # pyright: ignore[reportPrivateUsage]
)
from topmark.filetypes.instances import (
    _iter_plugin_filetypes,  # pyright: ignore[reportPrivateUsage]
)
from topmark.filetypes.instances import get_base_file_type_registry
from topmark.registry.filetypes import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    import pytest

    from topmark.filetypes.model import FileType


def _provider() -> list[FileType]:
    return [
        make_file_type(
            local_key="pluggy",
            extensions=[".pg"],
            filenames=[],
            patterns=[],
            description="plug",
        )
    ]


def test_plugins_are_discovered(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure the fake entry point is discovered and merged into the registry."""

    class _EP:  # minimal fake
        name: str = "fake"
        load = staticmethod(lambda: _provider)

    def _select(group: str) -> list[_EP]:
        return [_EP()]

    monkeypatch.setattr(
        "topmark.filetypes.instances.entry_points",
        lambda: SimpleNamespace(select=_select),
    )

    get_base_file_type_registry.cache_clear()

    # Also clear the composed/effective registry cache so it re-composes from the
    # freshly patched entry_points() provider.
    #
    # Silence Pyright regarding use of private members:
    ft_reg = cast("Any", FileTypeRegistry)
    ft_reg._clear_cache()

    ft_registry: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()
    assert "pluggy" in ft_registry


def test_builtin_filetype_loading_skips_modules_without_filetypes_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Built-in loading skips malformed modules without failing discovery."""
    valid: FileType = make_file_type(local_key="valid-builtin")
    missing: ModuleType = ModuleType("topmark.fake_missing_filetypes")
    not_list: ModuleType = ModuleType("topmark.fake_invalid_filetypes")
    setattr(not_list, "FILETYPES", (valid,))  # noqa: B010
    valid_module: ModuleType = ModuleType("topmark.fake_valid_filetypes")
    setattr(valid_module, "FILETYPES", [valid])  # noqa: B010
    modules: dict[str, ModuleType] = {
        missing.__name__: missing,
        not_list.__name__: not_list,
        valid_module.__name__: valid_module,
    }

    monkeypatch.setattr(
        "topmark.filetypes.instances._BUILTIN_MODULES",
        tuple(modules),
    )

    def _module_name(modname: str) -> ModuleType:
        return modules[modname]

    monkeypatch.setattr(
        "topmark.filetypes.instances.import_module",
        _module_name,
    )

    assert list(_iter_builtin_filetypes()) == [valid]


def test_builtin_filetype_loading_skips_non_filetype_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Built-in loading accepts only FileType objects from FILETYPES lists."""
    valid: FileType = make_file_type(local_key="valid-builtin")
    module: ModuleType = ModuleType("topmark.fake_mixed_filetypes")
    setattr(module, "FILETYPES", ["not-a-filetype", valid])  # noqa: B010

    monkeypatch.setattr(
        "topmark.filetypes.instances._BUILTIN_MODULES",
        (module.__name__,),
    )

    def _module_name(modname: str) -> ModuleType:
        assert modname == module.__name__
        return module

    monkeypatch.setattr(
        "topmark.filetypes.instances.import_module",
        _module_name,
    )

    assert list(_iter_builtin_filetypes()) == [valid]


def test_plugin_filetype_loading_returns_empty_when_entry_points_fail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Plugin discovery fails closed when entry point metadata is unavailable."""

    def _raise_entry_points() -> object:
        raise RuntimeError("metadata unavailable")

    monkeypatch.setattr(
        "topmark.filetypes.instances.entry_points",
        _raise_entry_points,
    )

    assert list(_iter_plugin_filetypes()) == []


def test_plugin_filetype_loading_skips_broken_entry_points(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken plugin entry point does not prevent later plugins from loading."""
    valid: FileType = make_file_type(local_key="valid-plugin")

    class _BrokenEntryPoint:
        name: str = "broken"

        def load(self) -> object:
            raise RuntimeError("broken plugin")

    class _ValidEntryPoint:
        name: str = "valid"

        def load(self) -> object:
            return lambda: [valid]

    def _select(group: str) -> list[object]:
        assert group == "topmark.filetypes"
        return [_BrokenEntryPoint(), _ValidEntryPoint()]

    monkeypatch.setattr(
        "topmark.filetypes.instances.entry_points",
        lambda: SimpleNamespace(select=_select),
    )

    assert list(_iter_plugin_filetypes()) == [valid]


def test_builtin_filetype_loading_skips_modules_that_fail_to_import(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Built-in loading skips modules that fail to import."""
    valid: FileType = make_file_type(local_key="valid-builtin")
    valid_module: ModuleType = ModuleType("topmark.fake_valid_filetypes")
    setattr(valid_module, "FILETYPES", [valid])  # noqa: B010

    broken_module_name = "topmark.fake_broken_filetypes"

    monkeypatch.setattr(
        "topmark.filetypes.instances._BUILTIN_MODULES",
        (broken_module_name, valid_module.__name__),
    )

    def _module_name(modname: str) -> ModuleType:
        if modname == broken_module_name:
            raise RuntimeError("import failed")
        assert modname == valid_module.__name__
        return valid_module

    monkeypatch.setattr(
        "topmark.filetypes.instances.import_module",
        _module_name,
    )

    assert list(_iter_builtin_filetypes()) == [valid]
