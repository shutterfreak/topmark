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

The `version` subcommand prints the runtime-resolved TopMark package version for the active Python
environment. For installed builds, this version is derived from Git tags via `setuptools-scm` and
exposed through package metadata / the generated version module.

______________________________________________________________________

## Input applicability

`version` is informational and file-agnostic. It reports the installed TopMark package version and
performs no project-file inspection or configuration discovery.

It does not accept file-processing inputs:

- positional PATH arguments are rejected as invalid CLI usage
- `-` is not a content-STDIN sentinel for this command
- `--stdin-filename` does not apply
- file-list STDIN modes (for example, `--files-from -`) do not apply
- `--quiet` is not supported; use output-format options for machine-readable output

Runtime configuration, registry overlays, resolver state, and file type selection do not affect the
reported version output.

______________________________________________________________________

## Quick start

```bash
topmark version
# → <package version>
```

______________________________________________________________________

## Output behavior

By default, `topmark version` prints only the resolved version string, with no additional labels or
decoration.

- The default format is the package’s canonical **PEP 440** version.

- Use `--semver` to request a SemVer-compatible rendering when possible.

- For development builds between release tags, the reported version may include SCM-derived
  dev/local segments such as commit identifiers.

- Output is suitable for scripting and CI usage.

- TEXT output supports verbosity (`-v`).

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

## Command-specific options

| Option            | Description                                                                                                 |
| ----------------- | ----------------------------------------------------------------------------------------------------------- |
| `--semver`        | Render the version as SemVer instead of PEP 440 when possible (for example `rcN → -rc.N`, `devN → -dev.N`). |
| `--output-format` | Select output format (`json`, `ndjson`, or default human-readable output).                                  |

See `topmark version -h` for the full list of options supported by this command.

### Shared output controls

- `-v`, `--verbose` increases TEXT output detail.
- Markdown output ignores verbosity and always renders a complete document.
- JSON/NDJSON output is unaffected by verbosity.
- `--quiet` is not supported for this command (pure content output; see
  [shared options](../shared-options.md)).
- Positional paths and STDIN input modes are not accepted by this command.

______________________________________________________________________

## Machine-readable output

The `version` command supports machine-readable output via:

- `--output-format json`
- `--output-format ndjson`

These formats follow TopMark’s shared machine-readable output and envelope conventions. For a full
overview of machine-readable formats and envelopes, see
[`docs/dev/machine-formats.md`](../../dev/machine-formats.md).

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

- `meta` contains runtime metadata and shared machine-readable output envelope fields.
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

- Each line is a self-contained machine-readable output record.
- The `kind` field identifies the record type (`version`).

### Notes

- If SemVer conversion fails, TopMark falls back to the original PEP 440 version.
- PEP 440 output is the canonical packaging-version form used by Python packaging tooling.
- Development builds between release tags may include SCM-derived dev/local segments.
- No ANSI color codes or human formatting are emitted in machine-readable formats.
- JSON output is emitted **without** a trailing newline; NDJSON emits one record per line.

{% include-markdown "\_snippets/output-contract-no-quiet.md" %}

______________________________________________________________________

## Exit codes

`topmark version` is a purely informational/content-producing command and exits with `SUCCESS (0)`
on successful execution.

Common `version` exit codes:

| Scenario                      | Exit code                        |
| ----------------------------- | -------------------------------- |
| Version rendered successfully | `SUCCESS (0)`                    |
| Version conversion failure    | `VERSION_CONVERSION_ERROR (100)` |
| Invalid CLI usage             | `USAGE_ERROR (64)`               |

Notes:

- This command does not process project files and does not use file-processing exit codes such as
  `WOULD_CHANGE (2)`, `FILE_NOT_FOUND (66)`, or `IO_ERROR (74)`.
- Invalid positional paths or file-processing input options are reported as CLI usage errors.
- `--quiet` is not supported because the command's primary purpose is to emit content.

See [`Exit codes`](../exit-codes.md) for the complete CLI-wide exit-code contract.

The `version` command performs no file processing, configuration discovery, or state mutation.

______________________________________________________________________

## Related docs

- [Command overview](../cli.md)
- [Shared options](../shared-options.md)
- [Exit codes](../exit-codes.md)
- [Machine-readable output schema](../../dev/machine-output.md)
- [Machine-readable formats](../../dev/machine-formats.md)
- [API stability](../../dev/api-stability.md)

______________________________________________________________________

## Troubleshooting

- **Unexpected development version**: builds between release tags may include SCM-derived
  development or local-version metadata.
- **Unexpected SemVer rendering**: TopMark falls back to the original PEP 440 version when a clean
  SemVer conversion is not possible.
- **Unexpected machine-readable output formatting**: use `--output-format json` or
  `--output-format ndjson` for stable machine-readable output.
