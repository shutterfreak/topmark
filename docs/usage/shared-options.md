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

Shared options control stable user-facing runtime behavior such as:

- output rendering
- verbosity
- diagnostics visibility
- machine-readable JSON and NDJSON rendering
- color behavior
- command applicability behavior and runtime input modes

{% include-markdown "\_snippets/terminology.md" %}

For CLI/configuration/API spelling conventions for multi-word option values, see
[Configuration discovery, precedence, and policy](configuration.md#cli-configuration-and-api-value-spelling).

## Output format

TopMark supports four stable output formats:

```bash
--output-format text        # Interactive terminal-oriented TEXT output (default)
--output-format markdown    # Markdown document output
# Machine-readable formats:
--output-format json        # JSON object (formatted)
--output-format ndjson      # NDJSON records (1 per line)
```

These formats behave consistently across commands that support machine-readable output.

- Human-facing output:
  - `text` (default): intended for interactive terminal use; when color is enabled, output is
    rendered in color by default (disable with `--color never`).
  - `markdown`: document-oriented Markdown output; ignores TEXT-specific verbosity rendering.
- Machine-readable formats:
  - `json`: emits a single machine-readable JSON document formatted for readability and tooling.
  - `ndjson`: emits one machine-readable NDJSON record per line.

______________________________________________________________________

### TEXT vs machine-readable rendering

TopMark intentionally separates:

- TEXT-oriented interactive rendering;
- Markdown-oriented document rendering;
- machine-readable JSON and NDJSON serialization;
- process exit-code semantics.

For filesystem-processing commands, machine-readable path fields report selected processing paths
rather than preserving the original CLI path spelling. Filesystem-identity normalization resolves
equivalent path spellings, such as symlink spellings, before path serialization. Processing-target
eligibility checks such as hard-link policy are evaluated separately from path serialization and do
not alter the emitted path representation.

> [!NOTE] Verbosity, quiet mode and color rendering affect only human-facing TEXT rendering.

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

TopMark also respects the standard `NO_COLOR` environment variable for TEXT rendering.

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

TopMark supports quiet mode for TEXT-oriented human-readable rendering.

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
- `--quiet` suppresses human-readable rendering while preserving CLI semantic status behavior.

See also:

- [`Exit codes`](exit-codes.md)

{% include-markdown "\_snippets/output-contract.md" %}

______________________________________________________________________

## Command applicability

TopMark commands expose only options applicable to the selected command family. Known but
inapplicable options are rejected as explicit CLI usage errors rather than ignored silently.

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

Runtime file-processing commands ([`check`](commands/check.md), [`strip`](commands/strip.md), and
[`probe`](commands/probe.md)) support the same input modes:

- **Path mode**: process positional paths and/or paths loaded from `--files-from FILE`.
- **List STDIN mode**: read newline-delimited paths or patterns from STDIN using one of:
  - `--files-from -`
  - `--include-from -`
  - `--exclude-from -`
- **Content STDIN mode**: process one virtual runtime file from STDIN content by passing `-` as the
  sole PATH and providing `--stdin-filename NAME`.

These modes are mutually exclusive: do not mix `-` (content mode) with `--files-from -`,
`--include-from -`, or `--exclude-from -` (list mode).

For filesystem-backed inputs, TopMark evaluates filesystem identity and selects processing paths
before runtime processing begins. Filesystem-identity normalization resolves equivalent path
spellings, such as symlink spellings, to the selected processing path used for runtime processing.

Hard-link policy is evaluated as a processing-target eligibility check. If multiple selected paths
refer to the same filesystem object through hard links, each affected path is reported independently
and processing is blocked for the entire hard-link group without selecting a preferred source,
target, winner, or loser path.

> [!NOTE] **STDIN input**
>
> TopMark does not provide a `--stdin` option flag. Use the POSIX-style `-` PATH sentinel together
> with `--stdin-filename` for content mode.
>
> Passing `--stdin` is treated as an invalid option and results in a CLI usage error.

In content STDIN mode, `--stdin-filename` is required so TopMark can resolve file type, processor
binding, and path-sensitive policy exactly as it would for a real file path.

Because content mode does not reference an existing filesystem object, filesystem-identity
evaluation and processing-path selection do not apply. The supplied `--stdin-filename` acts only as
a virtual path for runtime resolution and policy evaluation.

For mutation commands (`check` and `strip`), `--apply` in content mode writes transformed content to
STDOUT and routes diagnostics to STDERR. This ensures consistent file-type resolution and runtime
header-policy evaluation behavior between path-based and STDIN inputs without writing to an unknown
filesystem location.

### Configuration-loading applicability

Layered configuration loading and discovery behavior apply to [`check`](commands/check.md),
[`strip`](commands/strip.md), [`probe`](commands/probe.md),
[`config check`](commands/config/check.md), and [`config dump`](commands/config/dump.md).

Layered configuration loading and discovery behavior do not apply to:

- [`config defaults`](commands/config/defaults.md)
- [`config init`](commands/config/init.md)
- registry commands
- [`version`](commands/version.md)

For file-backed configuration sources, configuration discovery uses configuration-source identity
based on the resolved configuration-file target. Layered provenance, applicability evaluation, and
configuration precedence are therefore based on resolved configuration targets rather than symlink
spellings.

Configuration-source identity is distinct from processing-target identity. Runtime
filesystem-processing commands evaluate selected processing paths separately, including
filesystem-identity normalization and eligibility checks such as hard-link policy. Those runtime
checks do not affect configuration discovery, layered provenance, or configuration precedence.

______________________________________________________________________

## See also

- [CLI overview](cli.md)
- [Configuration](configuration.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Exit codes](exit-codes.md)
- [Pre-commit integration](pre-commit.md)
- [Filesystem identity and processing paths](../dev/resolution.md#filesystem-identity-and-processing-paths)
- [Machine-readable output](../usage/machine-output.md)
