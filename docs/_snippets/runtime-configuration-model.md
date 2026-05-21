<!--
topmark:header:start

  project      : TopMark
  file         : runtime-configuration-model.md
  file_relpath : docs/_snippets/runtime-configuration-model.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

TopMark intentionally separates:

1. TOML-source loading
1. staged configuration-loading validation
1. layered configuration deserialization and merging
1. runtime configuration resolution
1. runtime overlay application
1. runtime policy evaluation
1. runtime pipeline gatekeeping and execution

Reporting, API surfaces, and machine-readable output expose a flattened compatibility view derived
from these internal runtime stages.

This layered runtime configuration model keeps behavior deterministic while preserving stable
configuration, policy, diagnostics, and machine-readable compatibility contracts.
