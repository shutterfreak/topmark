<!--
topmark:header:start

  project      : TopMark
  file         : dependency-review.md
  file_relpath : docs/ci/dependency-review.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Dependency review workflow

This page documents `.github/workflows/dependency-review.yml`.

TopMark uses GitHub Dependency Review as a pre-merge guardrail for dependency changes. It checks new
or updated runtime dependencies for known vulnerabilities and licenses that fall outside the
project's explicit policy.

{% include-markdown "\_snippets/terminology.md" %}

## Purpose

The workflow reviews dependency changes introduced by a pull request before they reach the default
branch. It complements Dependabot and normal CI:

- Dependabot proposes dependency and GitHub Action updates.
- Dependency Review evaluates the Python dependency diff exposed by GitHub.
- The main CI workflow tests the resulting source and resolved environment.
- Maintainers review the declared ranges and lockfile changes before merging.

Dependency Review is intentionally a change-oriented guardrail. It is not a complete audit of the
repository, source distributions, vendored code, copyright notices, or attribution obligations.

______________________________________________________________________

## Trigger conditions

| Trigger        | Path                                      | Purpose                                 |
| -------------- | ----------------------------------------- | --------------------------------------- |
| `pull_request` | `pyproject.toml`                          | Review declared dependency changes      |
| `pull_request` | `uv.lock`                                 | Review resolved dependency changes      |
| `pull_request` | `.github/workflows/dependency-review.yml` | Validate changes to the workflow itself |

Path filtering avoids an unnecessary workflow run when a pull request cannot change TopMark's Python
dependency graph or this policy.

______________________________________________________________________

## Permissions and trust boundary

The workflow has only `contents: read` permission and uses the pull request event. It does not use
repository secrets, install dependencies, execute project code, publish artifacts, or write pull
request comments.

External actions are pinned to immutable commit SHAs. Human-readable version comments remain next to
the pins, and Dependabot plus the GitHub Action pin audit provide the normal update and consistency
mechanisms.

Dependency Review obtains the dependency change information from GitHub's dependency graph and
Dependency Review API. It therefore cannot be reproduced completely from a local checkout.

______________________________________________________________________

## Policy

The workflow enforces the following policy for newly introduced or updated dependencies:

| Check                    | Policy                                                                |
| ------------------------ | --------------------------------------------------------------------- |
| Dependency scope         | Failures are limited to runtime dependencies                          |
| Vulnerability severity   | Fail on `high` or `critical` known vulnerabilities                    |
| License evaluation       | Require a license in the explicit SPDX allowlist                      |
| Unknown license metadata | Report it for maintainer review; GitHub does not fail on it by itself |

The current license allowlist is defined directly in the workflow:

```text
0BSD
Apache-2.0
BSD-2-Clause
BSD-3-Clause
ISC
MIT
MIT-0
MPL-2.0
PSF-2.0
Python-2.0
```

The list covers the permissive and weak-copyleft licenses currently accepted for TopMark's runtime
dependency graph. An allowlist is used so a new license requires an intentional policy decision.

License metadata can be missing, incomplete, or expressed as a compound SPDX expression.
Consequently:

- a passing check is a useful pre-merge signal, not legal advice or proof of license compliance;
- `NOASSERTION` or otherwise unknown metadata still requires manual review;
- a package-specific `allow-dependencies-licenses` exception must not be added merely to silence a
  failure;
- any exception should follow verification from the package's authoritative source and include a
  documented rationale in the pull request.

______________________________________________________________________

## Jobs and validation scope

The workflow contains one job:

| Job                 | Purpose                                                                                    |
| ------------------- | ------------------------------------------------------------------------------------------ |
| `dependency-review` | Review the pull request's runtime dependency diff against vulnerability and license policy |

Development, documentation, and test dependencies are outside the failure scope. Maintainers must
still inspect their `pyproject.toml` and `uv.lock` changes, and normal CI validates the resulting
tooling environment.

______________________________________________________________________

## Artifact handling

The workflow does not produce, consume, or publish build artifacts.

Results are shown in the GitHub Actions job summary and pull request checks. No additional service
account or repository secret is required.

______________________________________________________________________

## Local review

GitHub's dependency diff and advisory evaluation cannot be reproduced exactly offline. Contributors
can still inspect the resolved graph and validate the update locally:

```bash
uv tree --frozen
make verify
make test
```

Review both `pyproject.toml` and `uv.lock`. For a new or updated runtime package, verify its license
from authoritative project metadata and inspect the relevant security advisories before requesting
merge.

______________________________________________________________________

## Maintenance notes

When maintaining the workflow:

- keep external actions pinned to immutable commit SHAs;
- let Dependabot propose action updates and use the pin audit to detect inconsistent repeated refs;
- update the license allowlist only after an explicit project-policy review;
- prefer a narrow, documented package exception over broadening the global policy when reliable
  package metadata is unusually complex;
- review unexpected or unknown license results manually rather than treating absence of metadata as
  approval;
- revisit the enforced scopes if TopMark begins distributing bundled development assets or vendored
  dependencies.

The workflow is suitable as a required pull request check after it has been observed on
representative dependency updates. Branch protection is configured in GitHub rather than in this
repository.

A full license-compliance program may additionally require periodic whole-tree or SBOM analysis,
source-file and vendored-code scanning, notice generation, and legal review. Those concerns remain
outside this workflow's scope and can be evaluated separately if TopMark's distribution model or
compliance requirements change.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
