<!--
topmark:header:start

  project      : TopMark
  file         : shared-options.md
  file_relpath : docs/usage/shared-options.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Shared Output and Rendering Options

Shared options control:

- output rendering
- verbosity
- diagnostics visibility
- machine-readable formats
- color behavior
- command applicability

For CLI/configuration/API spelling conventions for multi-word option values, see
[Configuration](configuration.md#cli-configuration-and-api-value-spelling).

## Output format

TopMark supports four output formats:

These formats apply consistently across all commands that support structured output.

```bash
--output-format text        # Text output on interactive terminal (default)
--output-format markdown    # Markdown format
# Machine-readable formats:
--output-format json        # JSON object (formatted)
--output-format ndjson      # NDJSON records (1 per line)
```

- Human-facing output:
  - `text` (default): When using in an interactive terminal; if color-enabled the output will be
    rendered in color by default (disable with `--no-color`).
  - `markdown`: Generate output as Markdown (document-oriented; ignores TEXT-only verbosity
    controls).
- Machine-readable formats:
  - `json`: Return a single JSON object, formatted for easier reading.
  - `ndjson`: Returns a stream of NDJSON objects (one per line).

See also:

- [`Machine-readable output schema`](../dev/machine-output.md)
- [`Exit codes`](exit-codes.md)

______________________________________________________________________

## Verbosity

TopMark supports verbosity controls for TEXT-oriented output:

```bash
--verbose       # Increase TEXT output verbosity
-v              # Shorthand (can be repeated)
--quiet         # Suppress TEXT output (only for supported commands)
-q              # Shorthand
```

Note:

- `--quiet` is available only for commands that provide a meaningful status, inspection, or mutation
  signal (for example, [`check`](commands/check.md), [`strip`](commands/strip.md),
  [`probe`](commands/probe.md), [`config check`](commands/config/check.md),
  [`config dump`](commands/config/dump.md)).
- Pure informational content-producing commands (such as [`version`](commands/version.md),
  [`config defaults`](commands/config/defaults.md), [`config init`](commands/config/init.md), and
  registry commands) do not support `--quiet`.

In TEXT output, verbosity affects:

- Diagnostic detail
- Hint visibility and grouping
- Summary rendering
- CLI progress reporting

______________________________________________________________________

## Exit codes

- Exit codes are **not affected** by verbosity or `--quiet`.
- `--quiet` suppresses output but preserves the CLI status signal.

See also:

- [`Exit codes`](exit-codes.md)

{% include-markdown "\_snippets/output-contract.md" %}

______________________________________________________________________

## Command applicability

TopMark commands expose only options that are meaningful for that command. Known but inapplicable
options are rejected with an explicit CLI error rather than silently ignored.

See also:

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Filtering](filtering.md)

| Command family                                                                              | Applicable controls                                                                                                                             | Inapplicable controls                                                                                                                                                      |
| ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [`check`](commands/check.md)                                                                | File input, filtering, config, strictness, reporting, diff, `--apply`, write mode, header generation/update policy, generated-header formatting | N/A beyond normal validation conflicts                                                                                                                                     |
| [`strip`](commands/strip.md)                                                                | File input, filtering, config, strictness, reporting, diff, `--apply`, write mode, shared content-probe policy                                  | Header generation/update policy and generated-header formatting                                                                                                            |
| [`probe`](commands/probe.md)                                                                | File input, filtering, config, strictness, output format, shared content-probe policy                                                           | `--apply`, write mode, diff, summary/reporting, header generation/update policy, generated-header formatting, stdin option flags (use '-' plus `--stdin-filename` instead) |
| [`config check`](commands/config/check.md) / [`config dump`](commands/config/dump.md)       | Configuration loading, strictness where applicable, output format, documented config overrides                                                  | File processing, mutation, diff, reporting, positional paths                                                                                                               |
| [`config defaults`](commands/config/defaults.md) / [`config init`](commands/config/init.md) | Command-specific informational/config-scaffolding options                                                                                       | Config discovery, file processing, mutation, `--quiet`, positional paths                                                                                                   |
| `registry *` / [`version`](commands/version.md)                                             | Informational output controls                                                                                                                   | Config discovery, file processing, mutation, `--quiet`, positional paths                                                                                                   |

File-processing commands ([`check`](commands/check.md), [`strip`](commands/strip.md), and
[`probe`](commands/probe.md)) support the same input modes:

- path mode: positional paths and/or `--files-from FILE`
- file-list STDIN mode: `--files-from -`
- content STDIN mode: `-` plus `--stdin-filename NAME`

{% include-markdown "\_snippets/no-stdin-option.md" %}

In content STDIN mode, `--stdin-filename` is required so TopMark can resolve file type, processor,
and path-sensitive policy. For mutation commands, `--apply` writes the transformed content to STDOUT
and routes diagnostics to STDERR. This ensures consistent file-type resolution and header policy
behavior between path-based and STDIN inputs.

Config discovery applies to [`check`](commands/check.md), [`strip`](commands/strip.md),
[`probe`](commands/probe.md), [`config check`](commands/config/check.md), and
[`config dump`](commands/config/dump.md). It does not apply to
[`config defaults`](commands/config/defaults.md), [`config init`](commands/config/init.md), registry
commands, or [`version`](commands/version.md).

______________________________________________________________________

## Color

Color output applies only to **text output format**.

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

______________________________________________________________________

## Related pages

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Exit codes](exit-codes.md)
- [Machine-readable output schema](../dev/machine-output.md)
