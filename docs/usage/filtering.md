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

TopMark determines which files to process using a combination of **path-based filters**
and **file type filters**.

Filtering order:

1. Path filters (include/exclude patterns, `*_from`, `files_from`)
1. File type filters (`include_file_types`, `exclude_file_types`)
1. Eligibility (supported vs unsupported)

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
topmark check --files-from files.txt --apply
```

## Recipe: Show only files that would change

```bash
topmark check --skip-compliant .
```

## Recipe: Skip unsupported files (recognized but unheaderable)

```bash
topmark check --skip-unsupported .
topmark strip --skip-unsupported .
```
