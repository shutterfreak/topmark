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

The `version` subcommand prints the TopMark version as installed in the active
Python environment.

______________________________________________________________________

## Quick start

```bash
topmark version
# → 0.12.0.dev2
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
# → 0.12.0-dev.2
```

______________________________________________________________________

## Options

| Option            | Description                                                                          |
| ----------------- | ------------------------------------------------------------------------------------ |
| `--semver`        | Render the version as SemVer instead of PEP 440 (maps `rc → -rc.N`, `dev → -dev.N`). |
| `--output-format` | Select output format (`json`, `ndjson`, or default human-readable output).           |

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
    "version": "0.12.0.dev2",
    "platform": "darwin"
  },
  "version_info": {
    "version": "0.12.0.dev2",
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
{"kind":"version","meta":{"tool":"topmark","version":"0.12.0.dev2","platform":"darwin"},"version_info":{"version":"0.12.0.dev2","version_format":"pep440"}}
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
