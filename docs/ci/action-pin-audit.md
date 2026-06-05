<!--
topmark:header:start

  project      : TopMark
  file         : action-pin-audit.md
  file_relpath : docs/ci/action-pin-audit.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# GitHub Action pin audit

This page documents `.github/workflows/action-pin-audit.yml` and `tools/ci/audit_action_pins.py`.

TopMark includes a dedicated maintenance workflow and repository tool for auditing GitHub Action
version pin consistency across workflow files and local composite actions before the stable release
path depends on them.

{% include-markdown "\_snippets/terminology.md" %}

## Purpose

The GitHub Action pin audit validates that repeated external GitHub Actions use a consistent pinned
ref across workflow files and local composite actions.

The audit exists because Dependabot updates workflow files under:

```text
.github/workflows/
```

but does not reliably track nested local composite-action metadata under:

```text
.github/actions/**/action.yml
```

Without an additional audit layer, repositories using local composite actions can drift toward
inconsistent external action refs over time.

The audit helps prevent:

- stale action pins;
- inconsistent CI environments;
- accidental divergence after Dependabot updates;
- hidden maintenance drift inside local actions.

The workflow intentionally complements Dependabot rather than attempting to replace it, keeping
manual review and CI validation as the final dependency-governance gate. The repository tool also
provides an explicit `--fix` mode for maintainers who want to repair stale repeated refs after a
Dependabot update introduced drift.

______________________________________________________________________

## Trigger conditions

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

## Permissions and trust boundary

The workflow uses read-only repository permissions:

```yaml
permissions:
  contents: read
```

The workflow intentionally operates as:

- read-only;
- non-mutating;
- offline;
- low-privilege.

The scheduled, manual, and pull-request workflow runs do not:

- publish packages;
- upload artifacts;
- modify repository files;
- query GitHub APIs;
- update dependencies automatically.

The default audit performs static repository analysis only. The local tool's explicit `--fix` mode
can rewrite stale repeated refs in the working tree, but it still does not query GitHub APIs,
resolve tags dynamically, or choose versions that are not already present in the scanned files.

______________________________________________________________________

## Jobs and validation scope

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

## Artifact handling

This workflow does not produce, consume, or publish build or release artifacts.

The audit validates repository consistency only and does not participate in package publication,
release artifact validation, or published artifact validation.

______________________________________________________________________

## Local reproduction

Run the default repository consistency audit:

```bash
python tools/ci/audit_action_pins.py
```

Repair stale repeated refs when the preferred ref can be selected unambiguously from the scanned
files:

```bash
python tools/ci/audit_action_pins.py --fix
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

| Exit code | Meaning                                                                   |
| --------- | ------------------------------------------------------------------------- |
| `0`       | All repeated actions use consistent refs                                  |
| `1`       | Divergent refs remain, or `--fix` could not select a unique preferred ref |

Example successful output:

```text
GitHub Actions pin audit
========================

External action references scanned: 25

OK: all repeated external actions use consistent refs.
```

______________________________________________________________________

## Maintenance notes

TopMark pins GitHub Actions to full commit SHAs for reproducibility and supply-chain hardening.

Example:

```yaml
uses: actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd # v6.0.2
```

The SHA is the actual execution target. The trailing version comment is retained only for human
readability and maintenance review.

When updating pinned GitHub Actions for the stable release workflow set:

1. update workflow files;
1. update local composite actions, or run `python tools/ci/audit_action_pins.py --fix` after the
   workflow update;
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

The default audit intentionally does not:

- query GitHub APIs;
- auto-upgrade actions;
- mutate workflow files;
- resolve tags dynamically;
- replace Dependabot.

The explicit `--fix` mode may mutate workflow files and local composite-action metadata, but only by
rewriting stale repeated refs to the preferred ref already present for the same action. The
preferred ref must be selectable from a unique highest SemVer-like trailing version comment such as
`# v8.2.0`.

This keeps the audit deterministic, offline, reproducible, and lightweight enough for routine CI
usage.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
