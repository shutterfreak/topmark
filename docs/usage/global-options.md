<!--
topmark:header:start

  project      : TopMark
  file         : global-options.md
  file_relpath : docs/usage/global-options.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Global Output Options

## Output format

TopMark supports four output formats:

```bash
--output-format text        # Text output on interactive terminal (default)
--output-format markdown    # Markdown format
# Machine formats:
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

- [`Machine output schema`](../dev/machine-output.md)
- [`Exit codes`](exit-codes.md)

______________________________________________________________________

## Verbosity

TopMark supports TEXT output verbosity controls:

```bash
--verbose       # Increase TEXT output verbosity
-v              # Shorthand (can be repeated)
--quiet         # Suppress TEXT output (only for supported commands)
-q              # Shorthand
```

Note:

- `--quiet` is available only for commands that provide a meaningful status, inspection, or mutation
  signal (for example, `check`, `strip`, `probe`, `config check`, `config dump`).
- Pure informational content-producing commands (such as `version`, `config defaults`,
  `config init`, and registry commands) do not support `--quiet`.

In TEXT output, verbosity affects:

- Hint grouping
- Diagnostic detail
- Summary rendering

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

| Command family                    | Applicable controls                                                                                                                             | Inapplicable controls                                                                                                                                                      |
| --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `check`                           | File input, filtering, config, strictness, reporting, diff, `--apply`, write mode, header generation/update policy, generated-header formatting | N/A beyond normal validation conflicts                                                                                                                                     |
| `strip`                           | File input, filtering, config, strictness, reporting, diff, `--apply`, write mode, shared content-probe policy                                  | Header generation/update policy and generated-header formatting                                                                                                            |
| `probe`                           | File input, filtering, config, strictness, output format, shared content-probe policy                                                           | `--apply`, write mode, diff, summary/reporting, header generation/update policy, generated-header formatting, stdin option flags (use '-' plus `--stdin-filename` instead) |
| `config check` / `config dump`    | Configuration loading, strictness where applicable, output format, documented config overrides                                                  | File processing, mutation, diff, reporting, positional paths                                                                                                               |
| `config defaults` / `config init` | Command-specific informational/config-scaffolding options                                                                                       | Config discovery, file processing, mutation, `--quiet`, positional paths                                                                                                   |
| `registry *` / `version`          | Informational output controls                                                                                                                   | Config discovery, file processing, mutation, `--quiet`, positional paths                                                                                                   |

File-processing commands (`check`, `strip`, and `probe`) support the same input modes:

- path mode: positional paths and/or `--files-from FILE`
- file-list STDIN mode: `--files-from -`
- content STDIN mode: `-` plus `--stdin-filename NAME`

TopMark does not provide a `--stdin` option flag. Instead, the POSIX-style `-` sentinel is used to
indicate content read from STDIN. Using `--stdin` is treated as an invalid option and results in a
CLI usage error. Use `-` together with `--stdin-filename` instead.

In content STDIN mode, `--stdin-filename` is required so TopMark can resolve file type, processor,
and path-sensitive policy. For mutation commands, `--apply` writes the transformed content to STDOUT
and routes diagnostics to STDERR. This ensures consistent file-type resolution and header policy
behavior between path-based and STDIN inputs.

Config discovery applies to `check`, `strip`, `probe`, `config check`, and `config dump`. It does
not apply to `config defaults`, `config init`, registry commands, or `version`.

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

Color has no effect on `markdown` or machine output formats (`json` or `ndjson`).
