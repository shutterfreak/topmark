# topmark:header:start
#
#   project      : TopMark
#   file         : test_builtin_module_inventory.py
#   file_relpath : tests/processors/test_builtin_module_inventory.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for the built-in processor module inventory.

These tests ensure the explicit built-in processor binding inventory stays in
sync with the concrete processor modules present under
`topmark.processors.builtins`.
"""

from __future__ import annotations

import pkgutil

from topmark.processors import builtins as builtins_pkg
from topmark.processors.instances import get_builtin_processor_bindings


def test_builtin_processor_module_manifest_matches_package() -> None:
    """Ensure all built-in processor modules are listed explicitly.

    This protects against adding a new processor module under
    `topmark.processors.builtins` without also wiring it into the explicit
    built-in processor binding declarations.
    """
    discovered: set[str] = {
        f"{builtins_pkg.__name__}.{module_info.name}"
        for module_info in pkgutil.iter_modules(builtins_pkg.__path__)
        if not module_info.ispkg and not module_info.name.startswith("_")
    }

    declared: set[str] = {
        f"{binding.processor_class.__module__}" for binding in get_builtin_processor_bindings()
    }

    assert declared == discovered
