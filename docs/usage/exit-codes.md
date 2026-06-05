<!--
topmark:header:start

  project      : TopMark
  file         : exit-codes.md
  file_relpath : docs/usage/exit-codes.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Exit codes

This page defines the stable CLI exit-code contract for TopMark. These codes are intended for CI,
automation, subprocess orchestration, and scripting.

TopMark follows a small, consistent set of exit codes across commands, with a few command-specific
semantic signals (notably for dry-run change detection and runtime-resolution status).

Exit codes define the stable command-line contract for:

- CI and release workflows integration
- shell scripting
- editor integration
- pre-commit hooks
- automation and orchestration
- machine-readable automation and subprocess orchestration

{% include-markdown "\_snippets/terminology.md" %}

Exit-code behavior is intentionally deterministic and stable across:

- normal CLI execution
- pre-commit execution
- CI environments
- API-driven runtime orchestration workflows

______________________________________________________________________

## Overview

| Code | Name                     | Meaning                                                                                                                            |
| ---: | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
|    0 | SUCCESS                  | Operation completed successfully.                                                                                                  |
|    1 | FAILURE                  | Generic failure (non-specific error).                                                                                              |
|    2 | -                        | Reserved for Click parser-level usage errors (e.g., unknown options or invalid option values).                                     |
|    3 | WOULD_CHANGE             | Dry-run indicates changes would be made (used by [`check`](commands/check.md) and [`strip`](commands/strip.md) without `--apply`). |
|   64 | USAGE_ERROR              | Invalid CLI usage (invalid options, incompatible flags).                                                                           |
|   65 | ENCODING_ERROR           | Text decoding/encoding error (e.g., Unicode issues).                                                                               |
|   66 | FILE_NOT_FOUND           | Explicit input path does not exist.                                                                                                |
|   69 | UNSUPPORTED_FILE_TYPE    | Unsupported, unresolved, filtered, or unavailable semantic outcome (primarily used by [`probe`](commands/probe.md)).               |
|   70 | PIPELINE_ERROR           | Internal pipeline failure or missing required processing result.                                                                   |
|   74 | IO_ERROR                 | Read/write failure (e.g., filesystem write error).                                                                                 |
|   77 | PERMISSION_DENIED        | Insufficient permissions (read/write).                                                                                             |
|   78 | CONFIG_ERROR             | Runtime configuration could not be loaded, resolved, or validated for execution.                                                   |
|  100 | VERSION_CONVERSION_ERROR | Version information could not be determined or converted.                                                                          |
|  255 | UNEXPECTED_ERROR         | Unhandled exception fallback.                                                                                                      |

Notes:

- Codes broadly follow **sysexits-style semantics** where applicable.
- Not all codes are used by every command.
- Click parser-level usage errors (for example, unknown commands, unknown options, or invalid option
  values) may exit with code `2` before command logic runs.
- Commands may short-circuit on higher-severity errors (e.g., config errors before processing).
- Configuration discovery starts from the resolved discovery anchor before runtime processing
  begins.
- Canonical file-type identifier normalization does not affect exit-code semantics.
- Ambiguous or malformed file-type identifiers are reported diagnostically and may contribute to
  configuration-loading or runtime-resolution outcomes depending on command behavior.
- Explicit missing literal paths are treated as hard input errors (66). Unmatched glob patterns are
  soft diagnostics and do not produce 66.
- Filesystem-identity evaluation occurs after configuration discovery and before runtime processing.
  It may affect processing-target eligibility. Different path spellings that resolve to the same
  filesystem target contribute to the same runtime processing outcome after filesystem-identity
  normalization. Filesystem-identity eligibility checks, such as hard-link detection, may contribute
  diagnostic outcomes without introducing command-specific exit codes.

______________________________________________________________________

## Exit codes vs machine-readable output

Exit codes and machine-readable output intentionally represent different compatibility layers.

Exit codes communicate:

- process-level runtime outcome;
- semantic change detection;
- configuration-loading status;
- runtime availability and environment failures.

Machine-readable JSON and NDJSON output communicate structured diagnostics, semantic outcomes,
runtime-resolution details, and processing metadata.

Configuration-loading exit-code behavior is based on the effective configuration produced after
project-chain discovery from the resolved discovery anchor, explicit configuration overlays, and CLI
or API overrides have been evaluated.

For filesystem inputs, machine-readable path fields report selected processing paths. Exit codes are
derived from runtime outcomes and do not depend on whether a file was reached through a symlink or
another equivalent path spelling after filesystem-identity normalization. Filesystem-identity
eligibility checks, such as hard-link detection, affect diagnostic and processing outcomes but do
not introduce separate exit-code values.

This separation keeps automation deterministic while preserving stable machine-readable output
contracts independently from process exit semantics.

______________________________________________________________________

## Command-specific behavior

### [`check`](../usage/commands/check.md)

| Scenario                                 | Exit code |
| ---------------------------------------- | --------: |
| No differences (clean)                   |         0 |
| Differences found (dry-run)              |         3 |
| Changes applied successfully (`--apply`) |         0 |
| Configuration error                      |        78 |
| Write failure during apply               |        74 |
| CLI usage error                          |        64 |
| Missing explicit input                   |        66 |
| Unexpected or internal error             |  70 / 255 |

Notes:

- `3` is a semantic change signal, not a runtime failure: it indicates that files would change.
- In CI, treat `3` as "diff detected".
- Explicit missing input paths are reported as errors (66), even if no files are selected for
  processing.
- Unmatched glob patterns are treated as discovery diagnostics and do not cause failure.
- Files reached through symlinks contribute to the same runtime outcome as their selected processing
  target and do not introduce additional exit-code states.
- Hard-linked processing targets are reported through normal processing outcomes and diagnostics;
  they do not introduce a dedicated exit code.

______________________________________________________________________

### [`strip`](../usage/commands/strip.md)

| Scenario                                 | Exit code |
| ---------------------------------------- | --------: |
| Nothing to strip / no changes            |         0 |
| Changes would occur (dry-run)            |         3 |
| Changes applied successfully (`--apply`) |         0 |
| Configuration error                      |        78 |
| Write failure during apply               |        74 |
| CLI usage error                          |        64 |
| Missing explicit input                   |        66 |
| Unexpected or internal error             |  70 / 255 |

Notes:

- Explicit missing input paths are reported as errors (66).
- Unmatched glob patterns are treated as discovery diagnostics and do not cause failure.
- `3` is a semantic change signal, not a runtime failure: it indicates that headers would be
  stripped.
- Files reached through symlinks contribute to the same runtime outcome as their selected processing
  target and do not introduce additional exit-code states.
- Hard-linked processing targets are reported through normal processing outcomes and diagnostics;
  they do not introduce a dedicated exit code.

______________________________________________________________________

### [`probe`](../usage/commands/probe.md)

| Scenario                                      | Exit code |
| --------------------------------------------- | --------: |
| All inputs resolved successfully              |         0 |
| Any input unresolved / unsupported / filtered |        69 |
| Missing explicit input                        |        66 |
| Missing probe result / internal inconsistency |        70 |
| Configuration error                           |        78 |
| CLI usage error                               |        64 |

Notes:

- `69` indicates partial, unavailable, or filtered semantic resolution, not a runtime failure.
- This is useful for automation that requires full resolvability.
- Missing explicit input paths are treated as hard errors (66) and take precedence over semantic
  probe outcomes.
- Unmatched glob patterns are reported as filtered semantic outcomes and result in exit code 69.
- Ambiguous or unresolved file-type filtering may also contribute to semantic resolution outcomes.
- Filesystem-identity evaluation occurs before runtime probing. Exit-code semantics are based on
  probe outcomes for selected processing paths rather than the original input spelling.
- Hard-linked processing targets contribute to normal probe unsupported outcomes (`69`) and do not
  introduce a dedicated exit code.

______________________________________________________________________

### [`config check`](../usage/commands/config/check.md)

| Scenario                                     | Exit code |
| -------------------------------------------- | --------: |
| Configuration is valid                       |         0 |
| CLI usage error                              |        64 |
| Configuration is invalid (validation result) |        78 |
| Internal error                               |  70 / 255 |

Important distinction:

- Exit code `78` is used both when configuration cannot be loaded and when `config check` completes
  validation and reports configuration errors.

______________________________________________________________________

### [`config dump`](../usage/commands/config/dump.md)

| Scenario                            | Exit code |
| ----------------------------------- | --------: |
| Dump successful                     |         0 |
| Configuration cannot be constructed |        78 |
| CLI usage error                     |        64 |

Notes:

- Non-fatal diagnostics do not affect the exit code.

______________________________________________________________________

### [`config defaults`](../usage/commands/config/defaults.md) / [`config init`](../usage/commands/config/init.md)

| Scenario          | Exit code |
| ----------------- | --------: |
| Successful output |         0 |
| CLI usage error   |        64 |

______________________________________________________________________

### [`registry filetypes`](../usage/commands/registry/filetypes.md) / [`registry processors`](../usage/commands/registry/processors.md) / [`registry bindings`](../usage/commands/registry/bindings.md)

| Scenario          | Exit code |
| ----------------- | --------: |
| Successful output |         0 |
| CLI usage error   |        64 |

Notes:

- These commands are informational-only and do not perform runtime file processing.

______________________________________________________________________

### [`version`](../usage/commands/version.md)

| Scenario                       | Exit code |
| ------------------------------ | --------: |
| Version displayed successfully |         0 |
| Version resolution failure     |       100 |
| CLI usage error                |        64 |

Notes:

- Exit code `100` is rare and typically only occurs in development or broken installations.

______________________________________________________________________

## Behavior in scripts and CI

Recommended handling:

- Treat `0` as success.
- Treat `2` as a Click parser-level usage error.
- Treat `3` as **non-error change signal** (for `check`/`strip`).
- Treat `64`, `66`, `69`, `70`, `74`, `78`, `255` as errors.
- `66` indicates explicit literal input errors (e.g., missing paths), not unmatched glob patterns.

These recommendations apply equally to:

- local automation scripts
- CI pipelines
- pre-commit hooks
- editor tooling
- GitHub Actions and similar runners

______________________________________________________________________

## Exit code priority (mixed results)

When multiple conditions occur during a single invocation, TopMark selects the exit code based on
the highest-priority runtime outcome.

Priority order (highest to lowest):

This ordering ensures deterministic behavior even when multiple independent runtime conditions and
semantic outcomes occur during a single invocation.

1. Permission errors (`77`) and other filesystem access failures
1. Missing explicit inputs (`66`)
1. Write/apply failures (`74`)
1. Configuration errors (`78`)
1. Semantic/availability signals (`69`)
1. Dry-run change signals (`3`)

This ensures that hard runtime or environment failures take precedence over informational, semantic,
or availability-oriented outcomes.

Configuration discovery has already selected project-chain configuration sources by this stage.
Symlinked discovery anchors may therefore affect which configuration-loading diagnostics exist, but
they do not introduce separate exit-code values.

Filesystem-identity evaluation and processing-path selection occur before exit-code evaluation and
do not introduce additional priority levels. Hard-link policy therefore participates through normal
processing outcomes rather than through a dedicated exit-code class.

Example:

```sh
# Detect formatting/header drift without applying changes
if ! topmark check . ; then
  if [ $? -eq 3 ] ; then
    echo "Changes required"
  else
    echo "Error during check"
    exit 1
  fi
fi
```

______________________________________________________________________

## Relationship to `--quiet`

- `--quiet` **does not affect exit codes**.
- It only suppresses human-readable TEXT rendering.
- Machine-readable JSON and NDJSON output preserve identical exit-code behavior.
- This ensures scripts remain reliable.

______________________________________________________________________

## Stability guarantee

The exit-code contract defined on this page is part of TopMark's stable CLI compatibility surface.
Changing an existing TopMark-owned semantic exit code, such as `WOULD_CHANGE`, is a breaking CLI
contract change and requires explicit release-note and migration documentation.

______________________________________________________________________

## See also

- [CLI overview](cli.md)
- [Shared options](shared-options.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Pre-commit integration](pre-commit.md)
- [Configuration](configuration.md)
- [Configuration discovery, precedence, and policy](../configuration/discovery.md)
- [Machine-readable output](machine-output.md)
- [Filesystem identity and processing paths](../dev/resolution.md#filesystem-identity-and-processing-paths)
