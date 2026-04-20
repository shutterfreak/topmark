# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/config/io/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Config-domain I/O helpers for TopMark.

This package contains helpers that are specific to TopMark's layered config
model, rather than generic TOML document handling.

Current responsibilities include:
    - deserializing layered TOML config tables into `MutableConfig`, including
      recording merged-config validation diagnostics
    - serializing `Config` and `MutableConfig` values back into layered TOML
      tables
    - providing bundled/default TopMark config-document helpers
    - supporting config-template editing helpers where needed

This package intentionally does **not** own generic TOML concerns such as:
    - low-level TOML file loading
    - TOML source discovery
    - TOML split parsing
    - TOML rendering/normalization
    - TOML document surgery

Those responsibilities now live under [`topmark.toml`][topmark.toml].

Design goals:
    - keep config-model interpretation separate from TOML document mechanics
    - provide strongly typed helpers around `Config`, `MutableConfig`, and
      layered config tables
    - support both CLI and API code paths without reintroducing TOML parsing
      logic into the config model layer

Diagnostics model:
    - Config-loading diagnostics are recorded as staged validation logs on
      `MutableConfig`
    - This package does not flatten diagnostics; flattening is performed at
      presentation and machine-output boundaries
"""

from __future__ import annotations
