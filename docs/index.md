<!--
topmark:header:start

  project      : TopMark
  file         : index.md
  file_relpath : docs/index.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark documentation (%%TOPMARK_VERSION%%)

TopMark inspects, inserts, updates, removes, and validates per-file headers across repositories. It
is comment-aware, file-type-aware, and **dry-run by default** for safe local usage, CI validation,
and repository automation.

{% include-markdown "\_snippets/terminology.md" %}

TopMark provides stable and consistent behavior across:

- CLI execution and dry-run workflows
- layered TOML configuration discovery and precedence
- filesystem identity normalization and processing-path selection
- configuration-source identity and layered provenance reporting
- repository filtering and file-type resolution
- probe and diagnostics workflows
- machine-readable reporting and explainability
- pre-commit and CI integration
- stable public Python API overlays and runtime contracts

______________________________________________________________________

## Start here

| Goal                                                                 | Recommended page                                      |
| -------------------------------------------------------------------- | ----------------------------------------------------- |
| Install TopMark and complete a safe first run                        | [Getting started](usage/getting-started.md)           |
| Understand the CLI structure and shared behavior                     | [Command overview](usage/cli.md)                      |
| Configure layered runtime behavior and policies                      | [Configuration](usage/configuration.md)               |
| Understand repository filtering and file discovery                   | [Filtering](usage/filtering.md)                       |
| Understand machine-readable output, processing paths, and provenance | [Machine-readable output](usage/machine-output.md)    |
| Validate repositories in CI                                          | [CI integration](usage/ci.md)                         |
| Integrate TopMark with pre-commit                                    | [Pre-commit integration](usage/pre-commit.md)         |
| Understand stable exit-code behavior                                 | [Exit codes](usage/exit-codes.md)                     |
| Upgrade older repositories to TopMark 1.0                            | [Upgrading to TopMark 1.0](usage/upgrading-to-1.0.md) |
| Use the public Python API                                            | [Public API](api/public.md)                           |
| Contribute to TopMark                                                | [Contributing](contributing.md)                       |

______________________________________________________________________

## What it does

- Detects, inserts, updates, validates, and removes per-file headers
- Honors shebangs, XML declarations, and native comment styles
- Preserves newline style (LF/CRLF/CR) and BOM
- Uses dry-run-first workflows for safe repository automation
- Supports pre-commit and CI integration
- Explains repository filtering, file-type resolution, and processor selection via
  [`topmark probe`](usage/commands/probe.md)
- Uses deterministic filesystem-identity normalization and processing-path selection across CLI,
  API, CI, and machine-readable workflows
- Exposes layered configuration provenance via `topmark config dump --show-layers`
- Uses deterministic configuration-source identity for layered configuration evaluation
- Provides stable machine-readable JSON and NDJSON output together with canonical registry metadata
  suitable for automation and reporting
- Supports canonical qualified file type identifiers such as `topmark:python`
- Supports local identifiers such as `python` when unambiguous

______________________________________________________________________

## Commands

TopMark exposes a small set of dry-run-first CLI commands.

Filesystem-processing commands normalize filesystem identity before runtime processing. Multiple
path spellings that resolve to the same filesystem target (for example a symlink and its target) are
treated as a single processing target.

For command structure, shared options, applicability rules, and common workflows, see:

- [Command overview](usage/cli.md).

Core commands: [`check`](usage/commands/check.md), [`strip`](usage/commands/strip.md),
[`probe`](usage/commands/probe.md), [`config`](usage/commands/config.md),
[`registry`](usage/commands/registry.md), [`version`](usage/commands/version.md).

Informational commands ([`version`](usage/commands/version.md),
[`config defaults`](usage/commands/config/defaults.md),
[`config init`](usage/commands/config/init.md), and [`registry`](usage/commands/registry.md)
commands) are file-agnostic: they do not accept positional paths or STDIN input modes and reject
them as CLI usage errors before runtime processing begins.

### Exit codes (overview)

TopMark uses a small stable set of exit codes suitable for CI and scripting:

- `SUCCESS (0)` - success (no changes needed or changes applied)

- `WOULD_CHANGE (3)` - dry-run indicates changes would be made ([`check`](usage/commands/check.md),
  [`strip`](usage/commands/strip.md))

- `CONFIG_ERROR (78)` - configuration validation failed ([`check`](usage/commands/check.md),
  [`strip`](usage/commands/strip.md), [`probe`](usage/commands/probe.md),
  [`config check`](usage/commands/config/check.md))

- `USAGE_ERROR (64)` - CLI usage error (invalid options, unsupported STDIN modes, or positional
  paths on file-agnostic commands)

Additional codes are used for configuration-loading errors and runtime conditions (for example
`CONFIG_ERROR (78)`, `FILE_NOT_FOUND (66)`). These apply after CLI usage has been accepted.

See:

- [`Exit codes`](usage/exit-codes.md)
- [`check`](usage/commands/check.md)
- [`strip`](usage/commands/strip.md)

The [`probe`](usage/commands/probe.md) command also reports explicitly requested paths that were
filtered out during discovery.

File-type filtering accepts either local identifiers such as `python` or canonical qualified
identifiers such as `topmark:python`.

The [`config`](usage/commands/config.md) command has the following subcommands:
[`config check`](usage/commands/config/check.md),
[`config defaults`](usage/commands/config/defaults.md),
[`config dump`](usage/commands/config/dump.md), [`config init`](usage/commands/config/init.md).

The [`registry`](usage/commands/registry.md) command has the following subcommands:
[`registry filetypes`](usage/commands/registry/filetypes.md),
[`registry processors`](usage/commands/registry/processors.md),
[`registry bindings`](usage/commands/registry/bindings.md).

{% include-markdown "\_snippets/output-contract.md" %}

Machine-readable filesystem path fields report selected processing paths. Configuration provenance
reports resolved configuration sources. Both contracts remain stable across supported platforms.

Use [`config dump --show-layers`](usage/commands/config/dump.md) to inspect how configuration is
built from individual sources and how precedence is applied.

TopMark supports two STDIN modes:

- **List mode**: read newline-delimited paths or patterns via `--files-from -` (or
  `--include-from -` / `--exclude-from -`)
- **Content mode**: process one file's content by passing `-` as the sole PATH together with
  `--stdin-filename NAME`

See [shared input modes](usage/shared-options.md#shared-input-modes) for the full STDIN contract,
including why TopMark does not provide a `--stdin` option flag.

______________________________________________________________________

## Next steps

- [Usage documentation](usage/index.md)
- [API documentation](api/index.md)
- [Configuration documentation](configuration/index.md)
- [Development documentation](dev/index.md)
- [Installation guide](install.md)
- [Contributing](contributing.md)

Common reference pages:

- [Exit codes](usage/exit-codes.md)
- [Machine-readable output](usage/machine-output.md)
- [Configuration discovery](configuration/discovery.md)
- [CI integration](usage/ci.md)
- [Release workflow](ci/release-workflow.md)

______________________________________________________________________

For the canonical project overview and release information, see the project README on GitHub:

- <https://github.com/shutterfreak/topmark/blob/main/README.md>
