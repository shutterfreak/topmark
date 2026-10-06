<!--
topmark:header:start

  project      : TopMark
  file         : upgrading-to-2.0.md
  file_relpath : docs/usage/upgrading-to-2.0.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Upgrading to TopMark 2.0

TopMark 2.0 changes CLI, configuration, machine-output, and public-API contracts introduced in the
1.0.x line. Read this guide before upgrading CI, pre-commit hooks, scripts, output parsers, or
custom file-type providers.

If you are upgrading from 0.11.x or earlier, first complete
[Upgrading to TopMark 1.0](upgrading-to-1.0.md). See [Upgrading TopMark](upgrading.md) for the
version-boundary path.

______________________________________________________________________

## Validate before mutation

Start by checking the configuration TopMark will actually use; both commands are read-only:

```bash
topmark config check --strict
topmark config dump --show-layers
```

Then preview changes without writing files:

```bash
topmark check --report noncompliant .
```

In 2.0, a failed `config check` exits with `78` (`CONFIG_ERROR`), while a dry-run `check` or `strip`
that finds changes exits with `3` (`WOULD_CHANGE`). Reserve exit code `2` for Click parser-level
errors such as an unknown option or invalid option value. Update scripts that treated `2` as the
dry-run signal.

```bash
# Before: 1.0.x dry-run change signal
topmark check .
# test "$?" -eq 2

# After: 2.0 dry-run change signal
topmark check .
# test "$?" -eq 3
```

See [Exit codes](exit-codes.md) for the complete command contract.

______________________________________________________________________

## CLI and input planning

### Use `--` for dash-prefixed paths

Option-like positional tokens are now Click parser errors until the standard `--` delimiter. Pass a
literal file name beginning with `-` after that delimiter:

```bash
# Before: accepted as a path in some 1.0.x flows
topmark check -generated.py

# After
topmark check -- -generated.py
```

### Treat `--files-from` as input, not a filter

`--files-from FILE` now supplies processing inputs for `check`, `strip`, and `probe`; it can be the
only input source. An empty list is normal no-work behavior, not a usage error. In contrast,
`--include-from` and `--exclude-from` remain filtering-rule sources and do not provide files to
process on their own.

```bash
find src -name '*.py' > files.txt
topmark check --files-from files.txt
git ls-files | topmark probe --files-from -
```

### Use exact CLI values

Finite-choice option values must be lowercase. Multiword enum values must use kebab-case on the CLI,
while TOML and public API values remain snake_case.

| 1.0.x CLI spelling                  | 2.0 CLI spelling                    | TOML/API spelling |
| ----------------------------------- | ----------------------------------- | ----------------- |
| `--header-mutation-mode add_only`   | `--header-mutation-mode add-only`   | `add_only`        |
| `--empty-insert-mode LOGICAL-EMPTY` | `--empty-insert-mode logical-empty` | `logical_empty`   |
| `--bom-before-shebang remove_bom`   | `--bom-before-shebang remove-bom`   | `remove_bom`      |
| `--output-format JSON`              | `--output-format json`              | `json`            |

The same exact-lowercase rule applies to values such as `--color`, `--report`, and `--write-mode`.

______________________________________________________________________

## Configuration changes since 1.0.1

Existing 1.0.1 configuration remains the starting point, but 2.0 adds rendering and safety policy
settings that can change dry-run results when enabled. Compare existing files with the current
generated starter configuration:

```bash
topmark config init --root > /tmp/topmark-2.toml
diff -u topmark.toml /tmp/topmark-2.toml
```

The same table layout works under `[tool.topmark]` in `pyproject.toml` (for example,
`[tool.topmark.formatting]` and `[tool.topmark.policy]`).

Configuration discovery now resolves a symlinked discovery anchor before walking its project chain.
Likewise, a configuration file reached through a symlink uses its resolved target for precedence,
scope applicability, relative configured paths, and layered provenance. Review
`topmark config dump --show-layers` if CI, a working directory, or an explicit `--config` path uses
symlinks.

### Multiline values and field wrapping

Custom field values can now be TOML multiline strings. TopMark trims incidental leading and trailing
blank lines, renders structural `|` continuation records, and compares headers to that canonical
form. A field selected for wrapping treats nonblank input lines as prose and preserves blank-line
paragraph boundaries.

```toml
[fields]
notice = """
Copyright 2026 Example Corp.

Licensed under the Apache License, Version 2.0.
"""

[formatting]
max_header_line_length = 100
wrap_fields = ["notice"]
```

`max_header_line_length` is a positive soft width; wrapping is enabled only for fields named by
`wrap_fields`. Review generated diffs before enabling it, because existing single-line or multiline
headers can be rewritten into canonical continuation records. Leave `wrap_fields = []` (the default)
to preserve literal logical lines without reflow.

### BOM-before-shebang and mixed-line-ending policies

2.0 makes these safety choices explicit. The defaults retain conservative behavior, so adding them
is optional unless you need remediation or preservation:

```toml
[policy]
# Reject a UTF-8 BOM directly before #! (default), or remove it during check/strip.
bom_before_shebang = "reject" # or "remove_bom"

# Reject mixed LF/CRLF/CR input (default), or preserve its non-header terminators exactly.
mixed_line_endings = "reject" # or "preserve"
```

`remove_bom` makes a BOM-only repair a real change: dry-run returns `3`, `--diff` shows it, and
`--apply` writes it. `preserve` does not normalize line endings; it merely permits processing while
retaining each existing non-header terminator. Both settings may also appear in
`[policy_by_type.<file-type>]`.

______________________________________________________________________

## CI, pre-commit, and shell automation

Update CI conditions that recognize a needed header change from `2` to `3`. Pre-commit treats any
nonzero exit status as a failure, so normal `topmark-check` behavior remains to fail when a dry-run
would change files; update custom wrappers that inspect its numeric status.

Use 2.0 CLI spellings in hook arguments:

```yaml
repos:
  - repo: https://github.com/shutterfreak/topmark
    rev: v2.0.0
    hooks:
      - id: topmark-check
        args: ["--report", "actionable", "--header-mutation-mode", "add-only"]
```

For every script, preserve the separation of data and diagnostics:

- JSON and NDJSON payloads are written only to standard output.
- Warnings, diagnostics, informational messages, and human reports when standard output is reserved
  are written to standard error.
- Parse standard output as machine data, capture standard error separately, and always inspect the
  process exit status.

______________________________________________________________________

## Machine-readable consumers

Processing `result.path` values for `check` and `strip` now use POSIX `/` separators on every
platform. Do not compare Windows output to backslash-separated golden values; treat these as
portable serialized paths.

`--diff` is now valid with JSON and NDJSON. In detail mode, replace any use of the former
`ProcessingResult.details` diff representation with structured payloads:

| Format | 2.0 diff representation                                                                                       |
| ------ | ------------------------------------------------------------------------------------------------------------- |
| JSON   | Optional `diff` object inside the affected result, containing `diff_text`.                                    |
| NDJSON | Adjacent `kind="diff"` record after the associated `kind="result"` record, containing `path` and `diff_text`. |

Machine-readable summary mode intentionally omits per-file diffs and writes a warning to standard
error. Consumers should ignore unknown fields and unknown NDJSON kinds so later additive changes do
not break parsing. See [Machine-readable output](machine-output.md) for schemas and examples.

______________________________________________________________________

## Public API and custom file types

`topmark.api.check()` and `topmark.api.strip()` now default to `report="actionable"`. Integrations
that require a result for every processed file must opt in explicitly:

```python
from topmark.api import check

result = check(["src"], report="all")
```

Custom file-type and plugin authors must treat `FileType.filenames` as relative registry matching
rules, not filesystem paths. Rules are canonicalized to POSIX `/`; construction now rejects empty,
absolute, UNC, drive-qualified, empty-segment, `.`-segment, and `..`-segment rules.

```python
# Before: platform-dependent rule spelling
filenames = ("config\\settings.py",)

# After: portable relative matching rule
filenames = ("config/settings.py",)
```

______________________________________________________________________

## Release checklist

Before adopting 2.0 in a repository:

- Run `topmark config check --strict` and inspect `topmark config dump --show-layers`.
- Review a dry-run `topmark check --report noncompliant .` before `--apply`.
- Update exit-code assertions (`WOULD_CHANGE` is `3`; `config check` failure is `78`).
- Add `--` before literal dash-prefixed paths and review `--files-from` no-work handling.
- Replace uppercase and snake_case CLI choice values with lowercase kebab-case values.
- Review multiline fields, `formatting.max_header_line_length`, and `formatting.wrap_fields` before
  enabling canonical wrapping.
- Decide whether BOM-before-shebang remediation or mixed-line-ending preservation is required.
- Regenerate JSON/NDJSON fixtures for POSIX paths and structured diff records; separate standard
  output from standard error.
- Pass `report="all"` to public API calls that require complete result lists.
- Validate custom `FileType.filenames` rules as portable relative POSIX rules.

______________________________________________________________________

## Related pages

- [Upgrading TopMark](upgrading.md)
- [Configuration](configuration.md)
- [Policies](policies.md)
- [Exit codes](exit-codes.md)
- [Pre-commit integration](pre-commit.md)
- [CI integration](ci.md)
- [Machine-readable output](machine-output.md)
