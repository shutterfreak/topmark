<!--
topmark:header:start

  project      : TopMark
  file         : dependabot.md
  file_relpath : docs/ci/dependabot.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Dependabot workflow

This page documents `.github/dependabot.yml`.

TopMark uses Dependabot to keep GitHub Actions and Python dependencies current while preserving
reproducibility, reviewability, and supply-chain safety.

{% include-markdown "\_snippets/terminology.md" %}

## Purpose

Dependabot helps maintain the repository's automation and dependency infrastructure by proposing
dependency-update pull requests for:

- GitHub Actions used by CI and release workflows;
- Python dependencies managed through the `uv`-based dependency model.

Dependabot is intentionally advisory rather than autonomous or self-merging. It proposes updates
through normal pull requests, while maintainers continue to review, validate, and merge changes
manually.

The workflow does not:

- auto-merge dependency updates;
- bypass CI validation;
- replace maintainer judgment;
- manage package versioning;
- replace lockfile review.

______________________________________________________________________

## Trigger conditions

| Trigger    | When it runs                  | Purpose                                      |
| ---------- | ----------------------------- | -------------------------------------------- |
| `schedule` | Weekly Dependabot service run | Propose dependency and GitHub Action updates |

Dependabot runs are initiated by GitHub's hosted Dependabot service rather than by a normal GitHub
Actions workflow trigger.

TopMark currently schedules:

- weekly GitHub Action update checks;
- weekly Python dependency update checks.

The configuration limits Dependabot to three concurrent open pull requests per update ecosystem to
avoid excessive maintenance churn.

______________________________________________________________________

## Permissions and trust boundary

Dependabot operates through GitHub-managed automation rather than through repository-hosted workflow
jobs.

Dependabot update pull requests:

- run through normal CI validation;
- remain subject to branch protection rules;
- require normal maintainer review;
- do not bypass repository policy.

TopMark intentionally pins GitHub Actions to full commit SHAs rather than mutable tags:

```yaml
uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5.0.1
```

The commit SHA is the actual execution target. The trailing version comment is retained only for
human readability and maintenance review.

This policy:

- improves workflow reproducibility;
- reduces supply-chain risk from mutable tags;
- aligns with GitHub's supply-chain hardening guidance.

Dependabot correctly updates SHA-pinned GitHub Actions.

______________________________________________________________________

## Jobs and validation scope

Dependabot currently manages two update ecosystems:

| Ecosystem        | Directory | Purpose                                                                   |
| ---------------- | --------- | ------------------------------------------------------------------------- |
| `github-actions` | `/`       | Update GitHub Actions used by workflows                                   |
| `uv`             | `/`       | Update Python dependencies managed through `pyproject.toml` and `uv.lock` |

Both ecosystems:

- run weekly;
- limit concurrent PRs to three;
- apply repository labels automatically.

Current labels are:

| Ecosystem        | Labels                           |
| ---------------- | -------------------------------- |
| `github-actions` | `dependencies`, `github-actions` |
| `uv`             | `dependencies`, `python`         |

Dependabot update pull requests are validated through the normal CI workflow after creation.

______________________________________________________________________

## Artifact handling

This workflow does not produce, consume, or publish build artifacts.

Dependabot only proposes repository changes through pull requests.

Artifact validation, release publication, and published-package validation are handled separately by
the CI, release, and published artifact validation workflows as part of TopMark's layered release
trust-boundary model.

______________________________________________________________________

## Local reproduction

Dependabot itself cannot be run locally because it is a GitHub-hosted service.

The closest local equivalents are the standard dependency-management and validation commands.

For Python dependency updates:

```bash
make uv-lock
make uv-lock-upgrade
make venv
make venv-sync-all
make verify
make test
```

Typical workflow:

- adjust dependency ranges in `pyproject.toml` if needed;
- refresh the lockfile with `uv`;
- run local verification;
- review resulting lockfile changes.

GitHub Action pin consistency can also be checked locally:

```bash
python tools/ci/audit_action_pins.py --report summary
```

______________________________________________________________________

## Maintenance notes

TopMark uses a `uv`-first dependency model.

The roles are:

| File             | Responsibility                       |
| ---------------- | ------------------------------------ |
| `pyproject.toml` | Declares supported dependency ranges |
| `uv.lock`        | Canonical resolved dependency graph  |

The committed lockfile remains the canonical dependency-resolution source.

TopMark also uses Git-based versioning through `setuptools-scm`:

- package versions are derived from Git tags;
- no manual package-version updates are performed in `pyproject.toml`;
- dependency updates do not directly affect package versioning.

When reviewing Dependabot PRs:

- review GitHub Action updates as infrastructure changes;
- review Python dependency updates as runtime and tooling changes;
- apply additional scrutiny to major-version updates;
- inspect release and publishing actions carefully;
- confirm CI passes before merging.

Dependabot does not reliably track nested local composite-action metadata references under:

```text
.github/actions/**/action.yml
```

TopMark therefore uses the [GitHub Action pin audit](./action-pin-audit.md) workflow and tool to
detect drift between workflow files and local composite actions.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
