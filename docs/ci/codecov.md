<!--
topmark:header:start

  project      : TopMark
  file         : codecov.md
  file_relpath : docs/ci/codecov.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Codecov coverage policy

This page documents the repository-level `codecov.yml` configuration.

TopMark publishes its canonical coverage report to Codecov after the supported Python test matrix
succeeds. Codecov compares pull request coverage with the base commit, reports patch coverage, and
adds a coverage summary to pull requests when the measured coverage changes.

{% include-markdown "\_snippets/terminology.md" %}

## Purpose

The Codecov policy complements the canonical coverage job:

- GitHub Actions generates `coverage.xml`, `coverage.json`, and the HTML report.
- GitHub retains the reports as independently available workflow artifacts.
- Codecov receives only `coverage.xml` and evaluates the repository policy in `codecov.yml`.
- Maintainers review the resulting `codecov/project/default` status before merge.

Codecov is the comparison and presentation layer. The local coverage session and GitHub-hosted
artifacts remain the authoritative diagnostics when investigating an individual run.

______________________________________________________________________

## Project coverage status

The `codecov/project/default` status compares overall project coverage on the pull request head with
coverage on its base:

```yaml
coverage:
  status:
    project:
      default:
        target: auto
        threshold: 0.25%
        if_not_found: failure
        informational: false
        only_pulls: true
```

`target: auto` derives the target from the base commit. The `0.25%` threshold permits a decline of
at most 0.25 percentage points. For example, if the base reports 99.00% coverage, a head report of
98.75% can pass while 98.74% fails.

The project status is not informational: Codecov reports a failed status when the decline exceeds
the threshold. GitHub does not automatically make that status a required merge gate. Maintainers
must review the result alongside the repository's required CI checks.

The status is emitted only for pull requests with a submitted coverage report, so ordinary commits
on `main` do not receive an unnecessary project status.

`if_not_found: failure` prevents a missing head report from being treated as successful coverage.
The CI workflow nevertheless keeps the uploader's `fail_ci_if_error` disabled so an external upload
or service error remains distinguishable from a measured coverage-policy failure.

______________________________________________________________________

## Patch coverage status

The `codecov/patch/default` status reports coverage for changed lines:

```yaml
coverage:
  status:
    patch:
      default:
        target: auto
        informational: true
        only_pulls: true
```

Patch coverage is informational. It highlights untested changed lines without creating a second
merge gate that can conflict with the project-level tolerance. Reviewers should still use it to
identify focused test gaps, especially when overall project coverage remains nearly unchanged.

______________________________________________________________________

## Pull request comments

Codecov comments are configured as follows:

```yaml
comment:
  layout: "header, diff, files, footer"
  behavior: default
  require_changes: "any_change"
  require_base: true
  require_head: true
  hide_project_coverage: false
```

The comment shows project and diff coverage together with affected files. Codecov updates its
existing comment instead of creating a new comment for every upload.

`require_changes: "any_change"` avoids creating a comment for pull requests whose measured coverage
is unchanged. Existing comments can still be updated by subsequent uploads. Requiring both base and
head reports avoids presenting a comparison when one side is unavailable.

______________________________________________________________________

## CI integration

The main CI workflow treats `codecov.yml` as a Python-relevant validation input. A pull request that
changes only the Codecov policy therefore:

1. triggers the CI workflow;
1. runs the supported Python test matrix;
1. generates the canonical coverage report;
1. uploads the report so Codecov evaluates the proposed configuration.

The upload action remains pinned to an immutable commit SHA and authenticates with the
repository-scoped `CODECOV_TOKEN` secret. Contributors do not need the token for local coverage
generation, and pull requests from forks cannot read the secret.

The upload step uses `fail_ci_if_error: false`. This keeps these outcomes distinct:

- the GitHub `Coverage` job fails when local coverage generation fails;
- `codecov/project/default` fails when measured coverage exceeds the permitted decline;
- upload or Codecov service errors are reported by the integration rather than being represented as
  a local test failure.

______________________________________________________________________

## Validation and maintenance

After changing `codecov.yml`:

1. validate its syntax with Codecov's configuration validator;
1. run the repository's YAML, Markdown, header, and documentation checks;
1. confirm the pull request produces `codecov/project/default` and `codecov/patch/default`;
1. inspect the Codecov comment when coverage changes;
1. if branch protection later requires the project status, keep its exact name synchronized.

Revisit the 0.25 percentage-point tolerance deliberately. Tightening or relaxing it changes the
review policy and should be supported by recent coverage stability rather than a single pull
request. Do not turn patch coverage into a required status without separately evaluating generated
code, platform-specific branches, and other legitimate patch-coverage edge cases.

Codecov configuration controls reporting and status evaluation; it does not replace semantic test
review. High aggregate coverage can coexist with weak assertions or missing behavioral cases.

______________________________________________________________________

## GitHub repository configuration

Do not immediately add `codecov/project/default` to the required status checks for `main`. The CI
workflow uses pull request path filters and runs coverage only for Python-relevant changes. A
required external status that is not emitted for every pull request can leave an otherwise valid
pull request unable to merge.

The project status can still fail visibly and be reviewed as part of normal coverage maintenance. To
make it a required GitHub status later:

1. ensure the CI workflow triggers for every pull request that must satisfy branch protection;
1. ensure the coverage job uploads a head report on each of those pull requests, including
   documentation- and configuration-only changes;
1. observe the exact `codecov/project/default` status name on representative pull requests;
1. add only that project status to the protected `main` branch or repository ruleset.

Do not require `codecov/patch/default`, because that status is intentionally informational. Required
status settings live in GitHub and are not stored in this repository. If the Codecov status name or
CI trigger policy changes, update branch protection and this documentation together.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
