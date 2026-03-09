# topmark:header:start
#
#   project      : TopMark
#   file         : test_builtin_module_inventory.py
#   file_relpath : tests/filetypes/test_builtin_module_inventory.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for the built-in file type module inventory.

These tests ensure the explicit built-in module manifest stays in sync with the
actual definition modules present under `topmark.filetypes.builtins`.
"""

from __future__ import annotations

import pkgutil

from topmark.filetypes import builtins as builtins_pkg
from topmark.filetypes.instances import _BUILTIN_MODULES  # pyright: ignore[reportPrivateUsage]


def test_builtin_filetype_module_manifest_matches_package() -> None:
    """Ensure all built-in filetype definition modules are listed explicitly.

    This protects against adding a new module under
    `topmark.filetypes.builtins` without also wiring it into the explicit
    built-in loader manifest.
    """
    discovered: set[str] = {
        f"{builtins_pkg.__name__}.{module_info.name}"
        for module_info in pkgutil.iter_modules(builtins_pkg.__path__)
        if not module_info.ispkg and not module_info.name.startswith("_")
    }

    declared: set[str] = set(_BUILTIN_MODULES)

    assert declared == discovered
