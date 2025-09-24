# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/filetypes/builtins/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Built-in FileType groups for TopMark.

This package contains the first-party file type definitions that ship with
TopMark. Each submodule exports a ``FILETYPES`` list with concrete
[`topmark.filetypes.base.FileType`][] instances. The aggregator in
``instances.py`` concatenates these lists to build the runtime registry.

Attributes:
    (module) FILETYPES: Not defined here. Each submodule defines its own list
        of [`topmark.filetypes.base.FileType`][] instances.
"""

from __future__ import annotations
