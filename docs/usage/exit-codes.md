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
semantic signals (notably for dry-run differences and probe-resolution status).

Exit codes define the stable command-line contract for:

- CI and release workflows integration
- shell scripting
- editor integration
- pre-commit hooks
- automation and orchestration
- machine-readable automation and subprocess execution

The canonical vocabulary used throughout the documentation is defined in
[Terminology and Canonical Vocabulary](../terminology.md).

Exit-code behavior is intentionally deterministic and stable across:

- normal CLI execution
- pre-commit execution
- CI environments
- API-driven subprocess orchestration workflows

______________________________________________________________________

## Overview

| Code | Name                     | Meaning                                                                                                                            |
| ---: | ------------------------ | ---------------------------------------------------------------------------------------------------------------------------------- |
|    0 | SUCCESS                  | Operation completed successfully.                                                                                                  |
|    1 | FAILURE                  | Generic failure (non-specific error).                                                                                              |
|    2 | WOULD_CHANGE             | Dry-run indicates changes would be made (used by [`check`](commands/check.md) and [`strip`](commands/strip.md) without `--apply`). |
|   64 | USAGE_ERROR              | Invalid CLI usage (invalid options, incompatible flags).                                                                           |
|   65 | ENCODING_ERROR           | Text decoding/encoding error (e.g., Unicode issues).                                                                               |
|   66 | FILE_NOT_FOUND           | Explicit input path does not exist.                                                                                                |
|   69 | UNSUPPORTED_FILE_TYPE    | Unsupported, unresolved, or filtered semantic outcome (primarily used by [`probe`](commands/probe.md)).                            |
|   70 | PIPELINE_ERROR           | Internal pipeline failure or missing required processing result.                                                                   |
|   74 | IO_ERROR                 | Read/write failure (e.g., filesystem write error).                                                                                 |
|   77 | PERMISSION_DENIED        | Insufficient permissions (read/write).                                                                                             |
|   78 | CONFIG_ERROR             | Configuration could not be loaded or validated for execution.                                                                      |
|  100 | VERSION_CONVERSION_ERROR | Version information could not be determined or converted.                                                                          |
|  255 | UNEXPECTED_ERROR         | Unhandled exception fallback.                                                                                                      |

Notes:

- Codes broadly follow **sysexits-style semantics** where applicable.
- Not all codes are used by every command.
- Commands may short-circuit on higher-severity errors (e.g., config errors before processing).
- Canonical file-type identifier normalization does not affect exit-code semantics.
- Ambiguous or malformed file-type identifiers are reported diagnostically and may contribute to
  configuration-validation or semantic-resolution outcomes depending on command behavior.
- Explicit missing literal paths are treated as hard input errors (66). Unmatched glob patterns are
  soft diagnostics and do not produce 66.

______________________________________________________________________

## Command-specific behavior

### [`check`](../usage/commands/check.md)

| Scenario                                 | Exit code |
| ---------------------------------------- | --------: |
| No differences (clean)                   |         0 |
| Differences found (dry-run)              |         2 |
| Changes applied successfully (`--apply`) |         0 |
| Configuration error                      |        78 |
| Write failure during apply               |        74 |
| CLI usage error                          |        64 |
| Missing explicit input                   |        66 |
| Unexpected/internal error                |  70 / 255 |

Notes:

- `2` is a semantic change signal, not an execution failure: it indicates that files would change.
- In CI, treat `2` as "diff detected".
- Explicit missing input paths are reported as errors (66), even if no files are selected for
  processing.
- Unmatched glob patterns are treated as discovery diagnostics and do not cause failure.

______________________________________________________________________

### [`strip`](../usage/commands/strip.md)

| Scenario                                 | Exit code |
| ---------------------------------------- | --------: |
| Nothing to strip / no changes            |         0 |
| Changes would occur (dry-run)            |         2 |
| Changes applied successfully (`--apply`) |         0 |
| Configuration error                      |        78 |
| Write failure during apply               |        74 |
| CLI usage error                          |        64 |
| Missing explicit input                   |        66 |
| Unexpected/internal error                |  70 / 255 |

Notes:

- Explicit missing input paths are reported as errors (66).
- Unmatched glob patterns are treated as discovery diagnostics and do not cause failure.

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

- `69` indicates partial or unavailable semantic resolution, not a runtime failure.
- This is useful for automation that requires full resolvability.
- Missing explicit input paths are treated as hard errors (66) and take precedence over semantic
  probe outcomes.
- Unmatched glob patterns are reported as filtered semantic outcomes and result in exit code 69.
- Ambiguous or unresolved file-type filtering may also contribute to semantic resolution outcomes.

______________________________________________________________________

### [`config check`](../usage/commands/config/check.md)

| Scenario                                     | Exit code |
| -------------------------------------------- | --------: |
| Configuration is valid                       |         0 |
| Configuration is invalid (validation result) |         1 |
| CLI usage error                              |        64 |
| Internal error                               |  70 / 255 |

Important distinction:

- Exit code `1` is not a configuration-loading or runtime failure.
- It indicates that validation completed and found issues.
- Errors that prevent validation entirely use `78` (not typically surfaced here).

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

- These commands are purely informational and do not perform runtime file processing.

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
- Treat `2` as **non-error change signal** (for `check`/`strip`).
- Treat `1` (from `config check`) as a validation-failure result rather than a runtime failure.
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
the highest-priority outcome.

Priority order (highest to lowest):

This ordering ensures deterministic behavior even when multiple independent runtime conditions occur
during a single invocation.

1. Permission errors (`77`) and other filesystem access failures
1. Missing explicit inputs (`66`)
1. Write/apply failures (`74`)
1. Configuration errors (`78`)
1. Semantic/availability signals (`69`)
1. Generic failures (`1`)

This ensures that hard runtime or environment failures take precedence over informational or
semantic outcomes.

Example:

```sh
# Detect formatting/header drift without applying changes
if ! topmark check . ; then
  if [ $? -eq 2 ] ; then
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
- It only suppresses human-readable TEXT output.
- Machine-readable JSON and NDJSON output preserve identical exit-code behavior.
- This ensures scripts remain reliable.

______________________________________________________________________

## Stability guarantee

The exit-code contract defined on this page is considered stable for 1.x releases.

Future changes will:

- preserve existing codes,
- only introduce new codes in a backward-compatible manner, or
- require a major version bump.

______________________________________________________________________

## See also

- [CLI overview](cli.md)
- [Shared options](shared-options.md)
- [Filtering](filtering.md)
- [Policies](policies.md)
- [Pre-commit integration](pre-commit.md)
- [Configuration](configuration.md)
- [Configuration discovery](../configuration/discovery.md)
