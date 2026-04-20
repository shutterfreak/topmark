# topmark:header:start
#
#   project      : TopMark
#   file         : __init__.py
#   file_relpath : src/topmark/config/resolution/__init__.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Layered config-resolution helpers for TopMark.

This subpackage contains the config-side resolution logic that bridges TOML
source resolution and effective per-path config construction.

Responsibilities:
    - define config provenance layer models
    - construct `ConfigLayer` records from resolved TOML sources
    - merge config provenance layers in stable precedence order
    - select which layers apply to a target path
    - build mutable config drafts, including effective per-path drafts
    - populate staged config-validation logs (TOML-source, merged-config)
      during layered resolution

This subpackage is intentionally separate from
[`topmark.toml.resolution`][topmark.toml.resolution]:

- `topmark.toml.resolution` discovers and resolves TOML sources plus
  source-local TOML options
- `topmark.config.resolution` turns layered TOML fragments into config
  provenance layers and merges them into mutable config drafts

Runtime-only override application is handled elsewhere (for example in
`topmark.config.overrides` and `topmark.runtime.*`).

Config-validation diagnostics are collected as staged validation logs and are
not flattened within this layer; flattening is performed at reporting and
output boundaries.
"""

from __future__ import annotations
