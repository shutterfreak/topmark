<!--
topmark:header:start

  project      : TopMark
  file         : shared-options.md
  file_relpath : docs/usage/shared-options.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Shared output and rendering options

Shared options control:

- output rendering
- verbosity
- diagnostics visibility
- machine-readable JSON and NDJSON output
- color behavior
- command applicability semantics and input modes

{% include-markdown "\_snippets/terminology.md" %}

For CLI/configuration/API spelling conventions for multi-word option values, see
[Configuration discovery, precedence, and policy](configuration.md#cli-configuration-and-api-value-spelling).

## Output format

TopMark supports four output formats:

These formats apply consistently across all commands that support machine-readable output.

```bash
--output-format text        # Text output on interactive terminal (default)
--output-format markdown    # Markdown format
# Machine-readable formats:
--output-format json        # JSON object (formatted)
--output-format ndjson      # NDJSON records (1 per line)
```

- Human-facing output:
  - `text` (default): intended for interactive terminal use; when color is enabled, output is
    rendered in color by default (disable with `--color never`).
  - `markdown`: document-oriented Markdown output; ignores TEXT-oriented verbosity controls.
- Machine-readable formats:
  - `json`: emits a single machine-readable JSON document formatted for readability.
  - `ndjson`: emits one machine-readable NDJSON record per line.

______________________________________________________________________

## Shared output controls (TEXT output)

### Color

Color output applies only to the `text` output format.

```bash
--color auto
--color always
--color never
```

- `auto` (default): enable color in interactive terminals
- `always`: force color
- `never`: disable color

Color has no effect on `markdown` or machine-readable output formats (`json` or `ndjson`).

TopMark also respects the standard `NO_COLOR` environment variable.

### Verbosity

TopMark supports verbosity controls for TEXT-oriented human-readable output.

```bash
--verbose       # Increase TEXT output verbosity
-v              # Shorthand (can be repeated)
```

In TEXT output, verbosity affects:

- diagnostic detail
- hint visibility and grouping
- summary rendering
- CLI progress reporting

### Quiet mode

TopMark supports quiet mode for TEXT-oriented human-readable output.

```bash
--quiet         # Suppress TEXT output (only for supported commands)
-q              # Shorthand
```

Note:

- `--quiet` is available only for commands that provide a meaningful semantic status, inspection, or
  mutation signal (for example, [`check`](commands/check.md), [`strip`](commands/strip.md),
  [`probe`](commands/probe.md), [`config check`](commands/config/check.md),
  [`config dump`](commands/config/dump.md)).
- Purely informational content-producing commands (such as [`version`](commands/version.md),
  [`config defaults`](commands/config/defaults.md), [`config init`](commands/config/init.md), and
  registry commands) do not support `--quiet`.

______________________________________________________________________

## Exit-code behavior

- Exit codes are not affected by verbosity or `--quiet`.
- `--quiet` suppresses human-readable output while preserving CLI semantic status behavior.

See also:

- [`Exit codes`](exit-codes.md)

{% include-markdown "\_snippets/output-contract.md" %}

______________________________________________________________________

## Command applicability

TopMark commands expose only options applicable to that command family. Known but inapplicable
options are rejected as explicit CLI usage errors rather than silently ignored.

Related docs:

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Filtering](filtering.md)

### Command-family applicability

| Command family                                                                              | Applicable controls                                                                                                                                            | Inapplicable controls                                                                                                                                                                     |
| ------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`check`](commands/check.md)                                                                | File input, filtering, configuration loading, strictness, reporting, diff, `--apply`, write mode, header generation/update policy, generated-header formatting | N/A beyond normal validation conflicts                                                                                                                                                    |
| [`strip`](commands/strip.md)                                                                | File input, filtering, configuration loading, strictness, reporting, diff, `--apply`, write mode, shared content-probe runtime policy                          | Header generation/update policy and generated-header formatting                                                                                                                           |
| [`probe`](commands/probe.md)                                                                | File input, filtering, configuration loading, strictness, output format, shared content-probe runtime policy                                                   | `--apply`, write mode, diff, human-readable summary/reporting, header generation/update policy, generated-header formatting, stdin option flags (use '-' plus `--stdin-filename` instead) |
| [`config check`](commands/config/check.md) / [`config dump`](commands/config/dump.md)       | Configuration loading, strictness where applicable, output format, and documented configuration overrides                                                      | File processing, mutation, diff, reporting, positional paths                                                                                                                              |
| [`config defaults`](commands/config/defaults.md) / [`config init`](commands/config/init.md) | Command-specific informational/configuration-scaffolding options                                                                                               | Configuration discovery, file processing, mutation, `--quiet`, positional paths                                                                                                           |
| `registry *` / [`version`](commands/version.md)                                             | Human-readable informational output controls                                                                                                                   | Configuration discovery, file processing, mutation, `--quiet`, positional paths                                                                                                           |

### Shared input modes

File-processing commands ([`check`](commands/check.md), [`strip`](commands/strip.md), and
[`probe`](commands/probe.md)) support the same input modes:

- **Path mode**: process positional paths and/or paths loaded from `--files-from FILE`.
- **List STDIN mode**: read newline-delimited paths or patterns from STDIN using one of:
  - `--files-from -`
  - `--include-from -`
  - `--exclude-from -`
- **Content STDIN mode**: process one virtual file from STDIN content by passing `-` as the sole
  PATH and providing `--stdin-filename NAME`.

These modes are mutually exclusive: do not mix `-` (content mode) with `--files-from -`,
`--include-from -`, or `--exclude-from -` (list mode).

> [!NOTE] **STDIN input**
>
> TopMark does not provide a `--stdin` option flag. Use the POSIX-style `-` PATH sentinel together
> with `--stdin-filename` for content mode.
>
> Passing `--stdin` is treated as an invalid option and results in a CLI usage error.

In content STDIN mode, `--stdin-filename` is required so TopMark can resolve file type, processor
binding, and path-sensitive policy exactly as it would for a real file path.

For mutation commands (`check` and `strip`), `--apply` in content mode writes the transformed
content to STDOUT and routes diagnostics to STDERR. This ensures consistent file-type resolution and
runtime header-policy behavior between path-based and STDIN inputs without writing to an unknown
filesystem location.

### Configuration-loading applicability

Layered configuration loading and discovery apply to [`check`](commands/check.md),
[`strip`](commands/strip.md), [`probe`](commands/probe.md),
[`config check`](commands/config/check.md), and [`config dump`](commands/config/dump.md).

Layered configuration loading and discovery do not apply to:

- [`config defaults`](commands/config/defaults.md)
- [`config init`](commands/config/init.md)
- registry commands
- [`version`](commands/version.md)

______________________________________________________________________

## See also

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Exit codes](exit-codes.md)
- [Pre-commit integration](pre-commit.md)
- [Machine-readable output](../dev/machine-output.md)
