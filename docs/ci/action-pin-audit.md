<!--
topmark:header:start

  project      : TopMark
  file         : action-pin-audit.md
  file_relpath : docs/ci/action-pin-audit.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# GitHub Action Pin Audit

This page documents `.github/workflows/action-pin-audit.yml` and `tools/ci/audit_action_pins.py`.

TopMark includes a dedicated maintenance workflow and repository tool for auditing GitHub Action
version pin consistency across workflow files and local composite actions.

## Purpose

The GitHub Action pin audit validates that repeated external GitHub Actions use a single pinned ref
across workflow files and local composite actions.

The audit exists because Dependabot updates workflow files under:

```text
.github/workflows/
```

but does not reliably track nested local composite-action metadata under:

```text
.github/actions/**/action.yml
```

Without an additional audit layer, repositories using local composite actions can drift toward
inconsistent pinned action refs over time.

The audit helps prevent:

- stale action pins;
- inconsistent CI environments;
- accidental divergence after Dependabot updates;
- hidden maintenance drift inside local actions.

The workflow intentionally complements Dependabot rather than replacing it.

______________________________________________________________________

## Trigger Conditions

| Trigger             | When it runs                                                        | Purpose                                  |
| ------------------- | ------------------------------------------------------------------- | ---------------------------------------- |
| `schedule`          | Weekly cron run                                                     | Detect GitHub Action pin drift over time |
| `workflow_dispatch` | Manual maintainer run                                               | Run the audit on demand                  |
| `pull_request`      | Pull requests affecting workflows, local actions, or the audit tool | Detect pin inconsistencies before merge  |

Pull-request runs are path-filtered so unrelated repository changes do not trigger the audit.

The workflow monitors:

```text
.github/workflows/**
.github/actions/**
tools/ci/audit_action_pins.py
```

______________________________________________________________________

## Permissions and Trust Boundary

The workflow uses read-only repository permissions:

```yaml
permissions:
  contents: read
```

The workflow intentionally remains:

- read-only;
- non-mutating;
- offline;
- low-privilege.

The audit does not:

- publish packages;
- upload artifacts;
- modify repository files;
- query GitHub APIs;
- update dependencies automatically.

The audit performs static repository analysis only.

______________________________________________________________________

## Jobs and Validation Scope

| Job                 | Purpose                                                                          | Main tools                                |
| ------------------- | -------------------------------------------------------------------------------- | ----------------------------------------- |
| `audit-action-pins` | Detect divergent GitHub Action refs across workflows and local composite actions | `python`, `tools/ci/audit_action_pins.py` |

The workflow currently consists of a single lightweight audit job running on:

```yaml
runs-on: ubuntu-latest
```

The job:

1. checks out the repository;
1. runs the audit tool;
1. fails if repeated actions use inconsistent refs.

The workflow intentionally avoids network access or dependency-resolution logic beyond the standard
runner environment.

______________________________________________________________________

## Artifact Handling

This workflow does not produce, consume, or publish build artifacts.

The audit validates repository consistency only.

______________________________________________________________________

## Local Reproduction

Run the default consistency audit:

```bash
python tools/ci/audit_action_pins.py
```

Print an aggregated summary report:

```bash
python tools/ci/audit_action_pins.py --report summary
```

Print refs grouped by source file:

```bash
python tools/ci/audit_action_pins.py --report files
```

Print both reports:

```bash
python tools/ci/audit_action_pins.py --report all
```

The default command exits with:

| Exit code | Meaning                                  |
| --------- | ---------------------------------------- |
| `0`       | All repeated actions use consistent refs |
| `1`       | Divergent refs were detected             |

Example successful output:

```text
GitHub Actions pin audit
========================

External action references scanned: 25

OK: all repeated external actions use consistent refs.
```

______________________________________________________________________

## Maintenance Notes

TopMark pins GitHub Actions to full commit SHAs for reproducibility and supply-chain hardening.

Example:

```yaml
uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
```

The SHA is the actual execution target. The trailing version comment is retained only for human
readability.

When updating pinned GitHub Actions:

1. update workflow files;
1. update local composite actions;
1. run the audit locally;
1. ensure the workflow remains green.

The audit tool scans:

```text
.github/workflows/**/*.yml
.github/workflows/**/*.yaml
.github/actions/**/action.yml
.github/actions/**/action.yaml
```

and extracts external action references of the form:

```yaml
uses: owner/repo@ref
```

Local actions such as:

```yaml
uses: ./.github/actions/setup-python-nox
```

are intentionally ignored because the audit is concerned with external dependency pinning.

The tool intentionally does not:

- query GitHub APIs;
- auto-upgrade actions;
- mutate workflow files;
- resolve tags dynamically;
- replace Dependabot.

This keeps the audit deterministic, offline, reproducible, and fast enough for CI usage.

______________________________________________________________________

## Related Pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
