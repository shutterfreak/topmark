<!--
topmark:header:start

  project      : TopMark
  file         : python-lifecycle-audit.md
  file_relpath : docs/ci/python-lifecycle-audit.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Python lifecycle audit

This page documents `.github/workflows/python-lifecycle-audit.yml`.

The Python lifecycle audit prompts maintainers to prepare for CPython release candidates and review
final-release and end-of-life (EOL) transitions. It is a decision aid, not automated compatibility
management: it never changes package metadata, updates the supported-runtime range, or opens pull
requests.

{% include-markdown "\_snippets/terminology.md" %}

______________________________________________________________________

## Purpose

TopMark supports final CPython series receiving upstream bugfix or security updates and,
temporarily, the most recently EOL series. The audit compares the authoritative
[CPython version-status page](https://devguide.python.org/versions/) with `project.requires-python`
and the [Python support policy](../usage/python-support.md). Python.org's official release directory
supplies release-candidate discovery only.

It raises a maintainer decision when any of these is true:

- Python.org publishes a first or newer `X.Y.0rcN` candidate for an unsupported, not-yet-final
  series.
- CPython reports a newly released final series in `bugfix` or `security` status that the declared
  support range does not include.
- CPython reports a TopMark-supported series as EOL but the support policy has not recorded its
  compatibility window.

The audit ignores alphas, betas, CPython's `main` development branch, future first-release dates,
and non-final feature-development rows. A release candidate starts preparation only; it does not
promise that TopMark will add or retain support.

______________________________________________________________________

## Trigger conditions

| Trigger             | When it runs          | Purpose                                       |
| ------------------- | --------------------- | --------------------------------------------- |
| `schedule`          | Mondays at 07:23 UTC  | Detect release changes                        |
| `workflow_dispatch` | Manual maintainer run | Audit immediately or use the dry-run override |

GitHub runs scheduled workflows from the repository default branch. A maintainer can invoke the
workflow from that branch at any time. The `dry-run` dispatch input reports the issue changes that
would be made without creating or updating GitHub issues; use it to inspect a source-format or
policy change before allowing an issue update.

______________________________________________________________________

## Permissions and trust boundary

The workflow requests only the permissions it needs:

```yaml
permissions:
  contents: read
  issues: write
```

It checks out repository policy and metadata, reads the public CPython status page, and creates or
updates repository issues. It cannot push commits, change repository settings, publish packages, or
open pull requests.

______________________________________________________________________

## Workflow inputs

The manual `workflow_dispatch` trigger accepts one input:

| Input     | Default | Meaning                                                           |
| --------- | ------- | ----------------------------------------------------------------- |
| `dry-run` | `false` | Report issue creation or update decisions without mutating issues |

______________________________________________________________________

## Jobs and validation scope

The `audit-python-lifecycle` job runs the fixture-tested `tools/ci/audit_python_lifecycle.py` tool.
It reads `pyproject.toml` and `docs/usage/python-support.md`, then fetches the CPython
version-status page and Python.org release directory. It recognizes released final CPython rows only
when their branch is a `3.x` series, their status is `bugfix`, `security`, or `end-of-life`, and
their first release date has arrived.

For each required decision, the job uses a stable hidden marker in the issue body. A release
candidate and its later final release share the same series marker, so re-runs update one open
tracking issue. Each issue links the CPython source and includes the review checklist for
final-release testing, `pyproject.toml`, runtime bounds, Nox/CI and published-artifact matrices,
`uv.lock`, documentation, and `CHANGELOG.md`.

______________________________________________________________________

## Artifact handling

The workflow produces, consumes, uploads, and publishes no build artifacts. Its only persistent
output is an actionable GitHub issue when maintainer review is required.

______________________________________________________________________

## Local reproduction

Use the GitHub Actions **Run workflow** control on the default branch. Select `dry-run` first when
reviewing a change to the CPython source format or TopMark's policy files. The local repository has
no equivalent command because the workflow's intended output is a repository issue, not a source
tree change.

______________________________________________________________________

## Maintenance notes

The [CPython version-status page](https://devguide.python.org/versions/) is the final-release and
EOL authority. Python.org's [official release directory](https://www.python.org/ftp/python/)
supplies release-candidate discovery only. Keep both parsers deliberately narrow: candidates must be
`X.Y.0rcN`; neither source may turn prereleases into TopMark support claims.

The issue checklist is intentionally broader than the audit's comparison. A maintainer may decide
that a transition warrants a support change, an EOL compatibility window, or no contract change.
Only that reviewed decision can modify package metadata, validation matrices, documentation, or
release notes.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}

- [Python support policy](../usage/python-support.md)
