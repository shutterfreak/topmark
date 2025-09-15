# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/registry/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Public registry facade and advanced registries.

This package exposes:

* [`topmark.registry.Registry`][] – the **stable, read-only facade** for integrators.
* [`topmark.registry.FileTypeRegistry`][] and
  [`topmark.registry.HeaderProcessorRegistry`][] – advanced,
  low-level registries intended for plugins and tests (no semver stability guarantee).

Most users should import from here:

```python
from topmark.registry import Registry
fts = Registry.filetypes()
procs = Registry.processors()
```

Advanced usage (mutation; global state):

```python
from topmark.registry import FileTypeRegistry, HeaderProcessorRegistry
FileTypeRegistry.register(my_ft)
HeaderProcessorRegistry.register(my_ft.name, MyProc)
```
"""

from __future__ import annotations

from .filetypes import FileTypeMeta, FileTypeRegistry
from .processors import HeaderProcessorRegistry, ProcessorMeta
from .registry import Binding, Registry, iter_bindings

__all__ = [
    # Stable facade
    "Registry",
    "Binding",
    "iter_bindings",
    # Advanced registries & meta (no stability guarantee)
    "FileTypeRegistry",
    "HeaderProcessorRegistry",
    "FileTypeMeta",
    "ProcessorMeta",
]
