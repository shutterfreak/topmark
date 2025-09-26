<!--
topmark:header:start

  project      : TopMark
  file         : dev-validation.md
  file_relpath : docs/ci/dev-validation.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Developer validation (optional)

TopMark provides opt-in developer-time validations to catch subtle registry
or placement regressions during refactoring or when adding new processors.
Enable it by setting `TOPMARK_VALIDATE=1`.

```bash
TOPMARK_VALIDATE=1 pytest -q
# or when running the CLI during development
TOPMARK_VALIDATE=1 topmark processors --format json
```

## What it checks

- **Registry integrity**: every registered header processor maps to an existing
  `FileType` name.
- **Placement strategy for XML/HTML**: processors based on `XmlHeaderProcessor`
  must signal the **character-offset** strategy by returning `NO_LINE_ANCHOR`
  from `get_header_insertion_index()`.

These checks run at most once per process and are **no-ops by default**.
They do not affect end users.

## Why it matters

- Prevents accidental miswiring (e.g., a processor registered under a typo key).
- Ensures XML/HTML-like processors don’t regress into line-based insertion,
  which can cause double-wrapped `<!-- -->` header blocks.
- Mirrors guardrails used by mature Python projects for safer refactors.

## CI usage (example)

Add a dev job in your GitHub Actions workflow to run validations alongside tests:

```yaml
jobs:
  tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - run: pip install -e .[dev]
      - name: Run tests with developer validation
        run: TOPMARK_VALIDATE=1 pytest -q
```

## Scope and overhead

- Validation is **lightweight** and only performs simple mapping/strategy checks.
- It does not parse files or run the pipeline; it inspects the composed registry
  during import time for `topmark.registry.processors`.
- No runtime overhead for end users unless `TOPMARK_VALIDATE` is set.
