<!--
topmark:header:start

  project      : TopMark
  file         : filtering.md
  file_relpath : docs/usage/filtering.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Common filtering recipes

TopMark determines which files to process using a combination of **path-based filters** and **file
type filters**.

Filtering order:

1. Path filters (include/exclude patterns, `*_from`, `files_from`)
1. File type filters (`include_file_types`, `exclude_file_types`)
1. Eligibility (supported vs unsupported)

## STDIN support

TopMark supports two STDIN modes when supplying file lists or content:

- **List mode**: provide newline-delimited paths or patterns via:
  - `--files-from -`
  - `--include-from -`
  - `--exclude-from -`
- **Content mode**: process a single file's content from STDIN by passing `-` as the sole PATH
  together with `--stdin-filename NAME`

These modes are mutually exclusive and should not be combined.

Note that STDIN handling is independent from configuration validation. Options such as `--strict` /
`--no-strict` still apply and control how configuration warnings are treated during the run.

## Recipe: Process only Python and Markdown

CLI:

```bash
topmark check --include-file-types python,markdown .
```

TOML:

```toml
[files]
include_file_types = ["python", "markdown"]
```

## Recipe: Exclude generated/virtualenv folders

TOML:

```toml
[files]
exclude_patterns = [
  ".venv/**",
  "**/__pycache__/**",
  "**/.mypy_cache/**",
  "**/.pytest_cache/**",
  "dist/**",
  "build/**",
]
```

## Recipe: Include only `src/` and `tests/`

TOML:

```toml
[files]
include_patterns = ["src/**", "tests/**"]
```

## Recipe: Use include/exclude pattern files (portable across repos)

```toml
[files]
include_from = ["include.txt"]
exclude_from = ["exclude.txt"]
```

These files may also be provided via STDIN by using `-` as the file path.

Example `include.txt`:

```text
src/**
tests/**
```

Example `exclude.txt`:

```text
.venv/**
**/__pycache__/**
```

## Recipe: Exclude a specific file type after path filtering

```toml
[files]
include_patterns = ["**/*.toml", "**/*.yaml", "**/*.yml"]
exclude_file_types = ["yaml"]
```

## Recipe: Process only a known file list (from Git)

Generate a file list:

```bash
git ls-files > files.txt
```

Then:

```bash
topmark check --files-from files.txt
```

You can also stream the file list via STDIN:

```bash
git ls-files | topmark check --files-from -
```

## Recipe: Show only actionable files (would change)

```bash
topmark check --report actionable .
```

## Recipe: Include unsupported files in reporting

```bash
topmark check --report noncompliant .
topmark strip --report noncompliant .
```

## Notes on configuration strictness

Filtering determines *which* files are processed, while configuration validation determines whether
a run is allowed to proceed.

Effective strictness is controlled by:

1. CLI override (`--strict` / `--no-strict`)
1. TOML setting (`strict_config_checking`)
1. default non-strict behaviour

When strict config checking is enabled, configuration warnings are treated as errors and may cause
the command to fail before processing files.
