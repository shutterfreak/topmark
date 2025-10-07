<!--
topmark:header:start

  project      : TopMark
  file         : dev-validation.md
  file_relpath : docs/ci/dev-validation.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# 🧩 Developer Validation Marker

TopMark defines an internal **pytest marker** `@mark_dev_validation`, used for selective validation of developer-only integrity tests (e.g., registry consistency).

## Purpose

This marker distinguishes tests that check **internal invariants** rather than user-facing behavior.

Typical use cases:

- Registry consistency between processors and file types
- Sanity checks for internal plugin mappings or invariants

Example:

```python
from tests.conftest import mark_dev_validation

@mark_dev_validation
def test_registered_processors_map_to_existing_filetypes():
    ...
```

## Execution

Currently, these tests are **run with all other tests** (no separate tox job).\
In earlier versions, a dedicated `dev-validation` CI job existed, but this was merged into the general test suite for simplicity.

To run only these tests locally:

```bash
TOPMARK_VALIDATE=1 pytest -q
# or when running the CLI during development
TOPMARK_VALIDATE=1 topmark processors --format json
# or:
pytest -m dev_validation
```

## What it checks

- **Registry integrity**: every registered header processor maps to an existing `FileType` name.
- **Placement strategy for XML/HTML**: processors based on `XmlHeaderProcessor` must signal the
  **character-offset** strategy by returning `NO_LINE_ANCHOR` from `get_header_insertion_index()`.

These checks run at most once per process and are **no-ops by default**. They do not affect end
users.

## Why it matters

- Prevents accidental miswiring (e.g., a processor registered under a typo key).
- Ensures XML/HTML-like processors don’t regress into line-based insertion, which can cause
  double-wrapped `<!-- -->` header blocks.
- Mirrors guardrails used by mature Python projects for safer refactors.

## Scope and overhead

- Validation is **lightweight** and only performs simple mapping/strategy checks.
- It does not parse files or run the pipeline; it inspects the composed registry during import time
  for `topmark.registry.processors`.
- No runtime overhead for end users unless `TOPMARK_VALIDATE` is set.
