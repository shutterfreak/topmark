<!--
topmark:header:start

  project      : TopMark
  file         : exit-codes.md
  file_relpath : docs/usage/exit-codes.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Exit Codes

This page defines the **stable CLI exit-code contract** for TopMark. These codes are intended for
use in CI/CD, scripting, and automation.

TopMark follows a **small, consistent set of exit codes** across commands, with a few
command-specific signals (notably for dry-run differences and probe resolution status).

______________________________________________________________________

## Overview

| Code | Name                  | Meaning                                                                                                         |
| ---: | --------------------- | --------------------------------------------------------------------------------------------------------------- |
|    0 | SUCCESS               | Operation completed successfully; no changes needed (or changes applied successfully).                          |
|    1 | VALIDATION_FAILED     | Command completed, but reported a failing validation result (used by `config check`).                           |
|    2 | WOULD_CHANGE          | Dry-run indicates changes would be made (used by `check` and `strip` without `--apply`).                        |
|   64 | USAGE_ERROR           | Invalid CLI usage (invalid options, incompatible flags).                                                        |
|   66 | INPUT_ERROR           | Input problem (e.g., missing file, unreadable path).                                                            |
|   69 | UNAVAILABLE / PARTIAL | Requested operation could not be fully satisfied (e.g., unsupported, filtered, or unresolved input in `probe`). |
|   70 | INTERNAL_ERROR        | Unexpected internal failure or missing required pipeline result.                                                |
|   74 | IO_ERROR              | Write/apply failure (e.g., filesystem write error).                                                             |
|   78 | CONFIG_ERROR          | Configuration could not be loaded or validated for execution.                                                   |
|  100 | VERSION_ERROR         | Version information could not be determined (rare; see `version`).                                              |
|  255 | UNHANDLED_ERROR       | Unhandled exception fallback.                                                                                   |

Notes:

- Codes broadly follow **sysexits-style semantics** where applicable.
- Not all codes are used by every command.
- Commands may short-circuit on higher-severity errors (e.g., config errors before processing).

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
| Unexpected/internal error                |  70 / 255 |

Notes:

- `2` is a **signal**, not an error: it indicates that files would change.
- In CI, treat `2` as "diff detected".

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
| Unexpected/internal error                |  70 / 255 |

______________________________________________________________________

### [`probe`](../usage/commands/probe.md)

| Scenario                                      | Exit code |
| --------------------------------------------- | --------: |
| All inputs resolved successfully              |         0 |
| Any input unresolved / unsupported / filtered |        69 |
| Missing probe result / internal inconsistency |        70 |
| Configuration error                           |        78 |
| CLI usage error                               |        64 |

Notes:

- `69` indicates **partial or unavailable resolution**, not a crash.
- This is useful for automation that requires full resolvability.

______________________________________________________________________

### [`config check`](../usage/commands/config/check.md)

| Scenario                                     | Exit code |
| -------------------------------------------- | --------: |
| Configuration is valid                       |         0 |
| Configuration is invalid (validation result) |         1 |
| CLI usage error                              |        64 |
| Internal error                               |  70 / 255 |

Important distinction:

- Exit code `1` is **not a runtime/config loading error**.
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

- These commands are **purely informational**.

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
- Treat `1` (from `config check`) as a **failing validation result**.
- Treat `64`, `66`, `69`, `70`, `74`, `78`, `255` as errors.

Example:

```sh
# Detect formatting/header drift without applying changes
if ! topmark check .; then
  if [ $? -eq 2 ]; then
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
- It only suppresses output.
- This ensures scripts remain reliable.

______________________________________________________________________

## Stability guarantee

The exit-code contract defined on this page is considered **stable for 1.0 and beyond**.

Future changes will:

- preserve existing codes,
- only introduce new codes in a backward-compatible manner, or
- require a major version bump.
