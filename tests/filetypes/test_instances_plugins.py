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

from types import SimpleNamespace
from typing import TYPE_CHECKING

from topmark.filetypes.base import FileType
from topmark.filetypes.instances import get_file_type_registry

if TYPE_CHECKING:
    import pytest


def _provider() -> list[FileType]:
    return [
        FileType(
            name="pluggy",
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
    # clear cache
    get_file_type_registry.cache_clear()  # type: ignore[attr-defined]
    reg: dict[str, FileType] = get_file_type_registry()
    assert "pluggy" in reg
