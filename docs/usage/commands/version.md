<!--
topmark:header:start

  project      : TopMark
  file         : version.md
  file_relpath : docs/usage/commands/version.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark `version` Command Guide

**Purpose:** Display the TopMark version.

The `version` subcommand prints the TopMark version as installed in the active
Python environment.

______________________________________________________________________

## Quick start

```bash
topmark version
# → <package version>
```

______________________________________________________________________

## Output

By default, `topmark version` prints **only the version string**, with no
additional labels or decoration.

- The default format is the package’s **PEP 440** version.
- Use `--semver` to request a **SemVer-compatible** representation when possible.
- Output is suitable for scripting and CI usage.

Example:

```bash
topmark version --semver
# → 0.12.0-dev.6
```

### PEP 440 ↔ SemVer examples

The table below illustrates how TopMark maps common PEP 440 versions to
their SemVer-compatible equivalents when using `--semver`:

| Release type        | PEP 440       | SemVer           |
| ------------------- | ------------- | ---------------- |
| Final release       | `0.12.0`      | `0.12.0`         |
| Release candidate   | `0.12.0rc1`   | `0.12.0-rc.1`    |
| Alpha (a / alpha)   | `0.12.0a2`    | `0.12.0-alpha.2` |
| Beta (b / beta)     | `0.12.0b3`    | `0.12.0-beta.3`  |
| Development release | `0.12.0.dev6` | `0.12.0-dev.6`   |

Notes:

- PEP 440 uses short pre-release markers: `a` (alpha), `b` (beta), and `rc`
  (release candidate). SemVer conventionally uses the full identifiers
  `alpha`, `beta`, and `rc` in the pre-release segment.
- Pre-releases are mapped to SemVer using a dash and dot separator
  (e.g. `0.12.0a2` → `0.12.0-alpha.2`).
- Development releases (`.devN`) are mapped to `-dev.N`
  (e.g. `0.12.0.dev6` → `0.12.0-dev.6`).
- If a version cannot be converted cleanly, TopMark falls back to the
  original PEP 440 string.

______________________________________________________________________

## Options

| Option            | Description                                                                            |
| ----------------- | -------------------------------------------------------------------------------------- |
| `--semver`        | Render the version as SemVer instead of PEP 440 (maps `rcN → -rc.N`, `devN → -dev.N`). |
| `--output-format` | Select output format (`json`, `ndjson`, or default human-readable output).             |

See `topmark version -h` for the full list of global CLI options.

______________________________________________________________________

## Machine-readable output

The `version` command supports machine-readable output via:

- `--output-format json`
- `--output-format ndjson`

These formats follow TopMark’s shared machine-output conventions.
For a full overview of machine formats and envelopes, see
[`docs/dev/machine-formats.md`](../../dev/machine-formats.md).

### JSON format

```bash
topmark version --output-format json
```

Produces a single JSON object:

```json
{
  "meta": {
    "tool": "topmark",
    "version": "<package version>",
    "platform": "darwin"
  },
  "version_info": {
    "version": "<package version>",
    "version_format": "pep440"
  }
}
```

- `meta` contains runtime metadata.
- `version_info.version` is the resolved version string.
- `version_info.version_format` is either `pep440` or `semver`.

### NDJSON format

```bash
topmark version --output-format ndjson
```

Produces one JSON object per line:

```json
{"kind":"version","meta":{"tool":"topmark","version":"<package version>","platform":"darwin"},"version_info":{"version":"<package version>","version_format":"pep440"}}
```

- Each line is a self-contained record.
- The `kind` field identifies the record type (`version`).

### Notes

- If SemVer conversion fails, TopMark falls back to the original PEP 440 version.
- No ANSI color codes or human formatting are emitted in machine formats.
- JSON output is emitted **without** a trailing newline; NDJSON emits one record per line.

______________________________________________________________________

## Exit status

- `0` — version printed successfully.
- Non-zero exit codes are reserved for unexpected internal errors.

The `version` command performs no file processing and never modifies state.
