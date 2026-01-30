# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/config/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark configuration API (public re-exports).

This package defines the configuration model and the utilities to normalize and
resolve paths and pattern sources. The implementation is split for clarity:

- [`topmark.config.model`][topmark.config.model] - immutable `Config` and mutable builder
  `MutableConfig`, including merge policy and freeze/thaw.
- [`topmark.config.types`][topmark.config.types] - small value objects and aliases
  (`PatternSource`, `ArgsLike`).
- [`topmark.config.paths`][topmark.config.paths] - pure path normalization helpers
  used by loaders/CLI.

Higher-level concerns (file discovery, TOML parsing/serialization, multi-layer
load/merge) may live in dedicated modules (``loader.py``, ``discovery.py``)
and be re-exported here, keeping callers stable:

>>> from topmark.config import Config, MutableConfig, PatternSource

Path resolution policy (summary):
* Globs in config files → resolved relative to the config file directory.
* Globs passed via CLI → resolved relative to the invocation CWD.
* Path-to-file settings → resolved against their declaring source (config dir or CWD).
* ``relative_to`` is used only for header metadata (e.g. ``file_relpath``).
"""

from __future__ import annotations

from .model import Config, MutableConfig, sanitize_config
from .types import ArgsLike, PatternSource

__all__: list[str] = [
    "ArgsLike",
    "Config",
    "MutableConfig",
    "PatternSource",
    "sanitize_config",
]
