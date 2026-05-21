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
1. runtime applicability evaluation
1. runtime probing and processor resolution
1. runtime policy evaluation
1. runtime mutation planning and execution

Machine-readable diagnostics and runtime behavior expose a flattened compatibility view derived from
these internal runtime stages while preserving deterministic stable 1.x runtime behavior.
