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
1. configuration-source identity normalization
1. staged configuration-loading validation
1. layered configuration deserialization and merging
1. runtime configuration resolution
1. runtime overlay application
1. runtime policy evaluation
1. filesystem-identity evaluation
1. processing-path selection
1. runtime pipeline gatekeeping and execution

Configuration-source identity and filesystem identity are intentionally distinct.

File-backed configuration sources are normalized to resolved configuration targets before
precedence, scope applicability, and layered provenance evaluation. Runtime file processing
similarly operates on selected processing paths derived from filesystem-identity evaluation.

Filesystem-identity evaluation includes:

- filesystem-identity normalization (for example symlink-path normalization and processing-path
  selection); and
- filesystem-identity eligibility checks (for example hard-link policy enforcement).

These normalization stages occur before runtime policy evaluation and pipeline execution.

Reporting, API surfaces, and machine-readable output expose a flattened compatibility view derived
from these internal runtime stages.

This layered runtime model keeps behavior deterministic while preserving stable configuration,
policy, filesystem-identity, diagnostics, and machine-readable compatibility contracts.
