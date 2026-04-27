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

The `version` subcommand prints the resolved TopMark package version for the active Python
environment.\
For installed builds, this version is derived from Git tags via `setuptools-scm` and exposed
through\
package metadata / the generated version module.

______________________________________________________________________

## Quick start

```bash
topmark version
# → <package version>
```

______________________________________________________________________

## Output

By default, `topmark version` prints **only the version string**, with no additional labels or
decoration.

- The default format is the package’s canonical **PEP 440** version.

- Use `--semver` to request a **SemVer-compatible** representation when possible.

- For development builds between release tags, the reported version may include SCM-derived
  dev/local segments such as commit identifiers.

- Output is suitable for scripting and CI usage.

- TEXT output supports verbosity (`-v`) and quiet mode (`--quiet`).

- Markdown output is document-oriented and ignores TEXT-only verbosity and quiet controls.

- JSON/NDJSON output is machine-readable and ignores TEXT-only verbosity and quiet controls.

Example:

```bash
topmark version --semver
# → 0.11.2-dev.240+gbd10c27de.d20260418
```

### PEP 440 ↔ SemVer examples

The table below illustrates how TopMark maps common PEP 440 versions to their SemVer-compatible
equivalents when using `--semver`:

| Release type        | PEP 440                 | SemVer                           |
| ------------------- | ----------------------- | -------------------------------- |
| Final release       | `1.0.0`                 | `1.0.0`                          |
| Release candidate   | `1.0.0rc1`              | `1.0.0-rc.1`                     |
| Alpha (a / alpha)   | `1.0.0a2`               | `1.0.0-alpha.2`                  |
| Beta (b / beta)     | `1.0.0b3`               | `1.0.0-beta.3`                   |
| Development release | `1.0.0.dev6`            | `1.0.0-dev.6`                    |
| Dev after alpha tag | `1.0.0a1.dev3+gabc1234` | project-defined SemVer rendering |

Notes:

- PEP 440 uses short pre-release markers: `a` (alpha), `b` (beta), and `rc` (release candidate).\
  SemVer conventionally uses `alpha`, `beta`, and `rc` in the pre-release segment.
- Pre-releases are mapped to SemVer using a dash and dot separator (for example `1.0.0a2` →\
  `1.0.0-alpha.2`).
- Development releases (`.devN`) are mapped to `-dev.N` (for example `1.0.0.dev6` →\
  `1.0.0-dev.6`).
- Development versions with local build metadata (for example commit identifiers) may require a\
  project-specific SemVer rendering.
- If a version cannot be converted cleanly, TopMark falls back to the original PEP 440 string.

______________________________________________________________________

## Options

| Option            | Description                                                                                                 |
| ----------------- | ----------------------------------------------------------------------------------------------------------- |
| `--semver`        | Render the version as SemVer instead of PEP 440 when possible (for example `rcN → -rc.N`, `devN → -dev.N`). |
| `--output-format` | Select output format (`json`, `ndjson`, or default human-readable output).                                  |
| `-q`, `--quiet`   | Suppress TEXT output while preserving exit status (ignored for non-TEXT formats).                           |

### Verbosity & quiet mode

- `-v`, `--verbose` increases TEXT output detail.
- `-q`, `--quiet` suppresses TEXT output entirely.
- Markdown output ignores these flags and always renders a complete document.
- JSON/NDJSON output is unaffected by these flags.

See `topmark version -h` for the full list of global CLI options.

______________________________________________________________________

## Machine-readable output

The `version` command supports machine-readable output via:

- `--output-format json`
- `--output-format ndjson`

These formats follow TopMark’s shared machine-output conventions. For a full overview of machine
formats and envelopes, see [`docs/dev/machine-formats.md`](../../dev/machine-formats.md).

As with human-readable output, the reported version is resolved at runtime from installed package
metadata / the generated version module rather than from a manually maintained static field in
`pyproject.toml`.

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
- PEP 440 output is the canonical packaging version form used by Python packaging tools.
- Development builds between release tags may include SCM-derived dev/local segments.
- No ANSI color codes or human formatting are emitted in machine formats.
- JSON output is emitted **without** a trailing newline; NDJSON emits one record per line.

{% include-markdown "\_snippets/output-contract.md" %}

______________________________________________________________________

## Exit status

- `0` — version printed successfully.
- Non-zero exit codes are reserved for unexpected internal errors.

The `version` command performs no file processing and never modifies state.
