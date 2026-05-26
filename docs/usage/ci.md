<!--
topmark:header:start

  project      : TopMark
  file         : ci.md
  file_relpath : docs/usage/ci.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# CI integration

This page documents how to use TopMark in CI pipelines for repository header validation.

CI should normally run TopMark in dry-run mode: validate the repository, report drift, and fail the
job when files would need header updates. Do not use `--apply` in CI unless you are building a
deliberately mutating automation workflow.

## Why use TopMark in CI?

Use TopMark in CI to:

- validate repository header compliance;
- prevent header drift after local edits;
- enforce repeatable project, file, license, and copyright metadata;
- keep mutation out of CI by relying on TopMark's dry-run behavior;
- expose per-file diagnostics and machine-readable reports for automation.

## Minimal CI usage

```bash
topmark check .
```

This validates the selected files and exits with `WOULD_CHANGE (2)` when headers would need to be
inserted, updated, or removed.

If you also want to validate the TopMark configuration, either provide `--strict` to `topmark check`
or add a dedicated configuration validation step:

```bash
topmark config check --strict
```

A typical CI sequence is therefore:

```bash
topmark config check --strict
topmark check .
```

## Controlling CI output

For concise CI logs, use summary mode:

```bash
topmark check --summary .
```

Summary mode renders per-outcome bucket counts instead of per-file guidance while preserving the
same exit-code behavior.

For CI jobs that only need the exit status, use quiet mode:

```bash
topmark check -q .
```

Quiet mode suppresses TEXT rendering while preserving the command’s exit status.

Do not use `--quiet` when you want contributors to see which files need updates directly in CI logs.
For that use case, prefer default output, `--summary`, or machine-readable output consumed by a CI
annotation step.

## Exit codes

### `topmark check`

`topmark check` uses exit code `WOULD_CHANGE (2)` as a stable dry-run signal when changes would be
needed. Successful clean runs exit with `SUCCESS (0)`.

Common `check` exit codes:

| Scenario                    | Exit code                |
| --------------------------- | ------------------------ |
| Clean run                   | `SUCCESS (0)`            |
| Dry-run would add or update | `WOULD_CHANGE (2)`       |
| Missing explicit input path | `FILE_NOT_FOUND (66)`    |
| Permission failure          | `PERMISSION_DENIED (77)` |
| Configuration error         | `CONFIG_ERROR (78)`      |
| Invalid CLI usage           | `USAGE_ERROR (64)`       |

Notes:

- Explicit missing literal paths are hard input errors and produce `FILE_NOT_FOUND (66)`.
- Unmatched glob patterns are soft discovery diagnostics and do not fail `check`.
- In mixed-result runs, hard input and filesystem errors take precedence over `WOULD_CHANGE (2)`.

### `topmark config check`

`topmark config check` exits with `SUCCESS (0)` when the effective runtime configuration is valid.
It exits with `FAILURE (1)` when validation completes and reports failing diagnostics:

- errors are present, or
- effective strict config checking is enabled and warnings are present.

Common `config check` exit codes:

| Scenario                                       | Exit code           |
| ---------------------------------------------- | ------------------- |
| Valid effective runtime configuration          | `SUCCESS (0)`       |
| Validation completed with failing diagnostics  | `FAILURE (1)`       |
| Invalid CLI usage                              | `USAGE_ERROR (64)`  |
| Configuration cannot be loaded for the command | `CONFIG_ERROR (78)` |

Notes:

- `FAILURE (1)` is a validation result for this command, not an unexpected crash.
- Warning-only diagnostics exit with `SUCCESS (0)` unless strict configuration checking is enabled.
- Malformed TOML discovered by `config check` is reported as a failing validation result and exits
  with `FAILURE (1)`.
- CLI usage errors (for example, invalid options) exit with `USAGE_ERROR (64)`.

Because `config check` is file-agnostic, invalid positional paths or file-processing input options
are reported as CLI usage errors rather than as file-processing diagnostics.

See also:

- [`topmark check` exit codes](commands/check.md#exit-codes) for the complete exit-code contract for
  `topmark check`.
- [`topmark config check` exit codes](commands/config/check.md#exit-codes) for the complete
  exit-code contract for `topmark config check`.
- [`Exit codes`](exit-codes.md) for the complete CLI-wide exit-code contract.

## GitHub Actions example

TopMark can be used from GitHub Actions as a regular Python CLI installed from PyPI.

```yaml
name: TopMark

on:
  pull_request:
  push:
    branches: [main]

jobs:
  topmark:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.x"

      - name: Install TopMark
        run: python -m pip install topmark

      - name: Validate TopMark configuration
        run: topmark config check --strict

      - name: Check file headers
        run: topmark check .
```

This example is intentionally plain: it does not require a dedicated TopMark GitHub Action.

The workflow intentionally uses ordinary CLI invocation rather than a wrapper action so the executed
commands remain explicit and easy to debug.

For stricter supply-chain hardening, pin third-party actions to full commit SHAs and let Dependabot
keep them updated:

```yaml
- name: Check out repository
  uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2

- name: Set up Python
  uses: actions/setup-python@a309ff8b426b58ec0e2a45f0f869d46889d02405 # v6.2.0
  with:
    python-version: "3.x"
```

The short `@v4` / `@v5` style is easier to read, but tags are mutable. Full-length commit SHAs
provide the strongest immutable pinning. When using SHA pins, configure Dependabot for GitHub
Actions updates in `.github/dependabot.yml`:

```yaml
version: 2
updates:
  - package-ecosystem: "github-actions"
    directory: "/"
    schedule:
      interval: "weekly"
```

## GitLab CI example

GitLab CI can run TopMark in the same way: install the Python package, validate configuration, and
run `topmark check .`.

```yaml
topmark:
  image: python:3
  script:
    - python -m pip install topmark
    - topmark config check --strict
    - topmark check .
```

This example is provided as a generic CI pattern. The TopMark project currently validates GitHub
Actions workflows, not GitLab CI pipelines.

## Pre-commit vs CI

Pre-commit and CI serve complementary roles:

- pre-commit gives contributors fast local feedback before a commit is created;
- CI enforces the same expectation for pull requests, branches, and external contributions.

A practical adoption sequence is:

1. run TopMark locally and apply the initial header updates;
1. add the `topmark-check` pre-commit hook for local validation;
1. add `topmark check .` to CI for repository-level enforcement.

## Machine-readable output

CI jobs usually only need process exit codes. When you need explainability, dashboards, annotations,
or downstream automation, use machine-readable output:

```bash
topmark check . --output-format json
topmark check . --output-format ndjson
```

Machine-readable output can expose structured CI diagnostics such as:

- per-file outcomes;
- selected file type and processor information;
- diagnostics and hints;
- layered configuration information where supported by the selected command;
- stable fields for automation-friendly reporting.

This makes JSON and NDJSON output useful for CI annotations, dashboards, repository audits, policy
validation, and custom reporting pipelines.

Further reading:

- [Machine-readable output](../usage/machine-output.md)
- [`topmark check`](commands/check.md)
- [`topmark probe`](commands/probe.md)
- [`topmark config dump`](commands/config/dump.md)

## Dedicated GitHub Action

TopMark does not currently publish a dedicated GitHub Action. For most users, installing the PyPI
package in a workflow is simpler and more transparent.

This also avoids introducing an additional abstraction layer around the CLI and keeps CI behavior
aligned with local development workflows.

## Further reading

- [Getting started](getting-started.md)
- [Pre-commit integration](pre-commit.md)
- [Exit codes](exit-codes.md)
- [Configuration](configuration.md)
- [Machine-readable output](../usage/machine-output.md)
