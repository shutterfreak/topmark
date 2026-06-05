<!--
topmark:header:start

  project      : TopMark
  file         : runtime-validation-model.md
  file_relpath : docs/_snippets/runtime-validation-model.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

TopMark intentionally separates:

1. staged configuration-loading validation
1. layered runtime configuration resolution
1. workspace-root and configuration-discovery evaluation
1. filesystem-identity evaluation
1. runtime applicability evaluation
1. runtime probing and processor resolution
1. runtime policy evaluation
1. runtime mutation planning and execution

Machine-readable diagnostics and runtime behavior expose a flattened compatibility view derived from
these internal runtime stages while preserving deterministic stable 1.x runtime behavior.

Filesystem-identity evaluation occurs before runtime processing begins and includes:

- filesystem-identity normalization (for example processing-path selection for equivalent path
  spellings such as symlinks); and
- filesystem-identity eligibility checks (for example hard-link policy enforcement).

Configuration-source identity is evaluated independently during configuration loading and layered
configuration resolution.

Workspace-root discovery and configuration-discovery evaluation are distinct from both
configuration-source identity and filesystem-identity evaluation. Configuration discovery may use
resolved filesystem locations to determine configuration search anchors, while compatibility
contracts continue to expose a flattened runtime view rather than these internal discovery stages.
