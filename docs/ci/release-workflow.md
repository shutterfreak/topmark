<!--
topmark:header:start

  project      : TopMark
  file         : release-workflow.md
  file_relpath : docs/ci/release-workflow.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Release Workflow

This page documents `.github/workflows/release.yml`.

The release workflow is TopMark's privileged package-publishing workflow. It is triggered by a
completed CI workflow run, verifies that the CI run corresponds to exactly one release tag,
downloads CI-built artifacts, and publishes those artifacts to PyPI or TestPyPI.

## Purpose

The release workflow publishes prebuilt release artifacts after CI has already validated and
uploaded them. It is intentionally artifact-only: it does not rebuild the project from repository
source code in the privileged publishing context.

This separation keeps package publication distinct from source-tree validation. The CI workflow runs
repository code and builds artifacts in a lower-privilege context; the release workflow verifies and
publishes those artifacts using Trusted Publishing.

______________________________________________________________________

## Trigger Conditions

| Trigger        | When it runs                      | Purpose                                                                           |
| -------------- | --------------------------------- | --------------------------------------------------------------------------------- |
| `workflow_run` | After the `CI` workflow completes | Publish CI-built artifacts only when the completed CI run is eligible for release |

The workflow starts for completed CI runs, but publishing proceeds only when all release preflight
checks pass.

The `preflight` job requires that:

- the triggering CI run completed successfully;
- the CI run was triggered by a `push` event;
- the CI run originated from the base repository;
- exactly one release-style tag points at the CI commit.

If no matching release tag points at the CI commit, the workflow exits cleanly without publishing.
If multiple matching release tags point at the same commit, preflight fails rather than choosing a
tag implicitly.

Supported release tags include final and prerelease forms such as:

| Tag          | Channel  | Notes                                |
| ------------ | -------- | ------------------------------------ |
| `v1.0.0`     | PyPI     | Final release                        |
| `v1.0.0rc1`  | TestPyPI | Release candidate                    |
| `v1.0.0-rc1` | TestPyPI | Release candidate compatibility form |
| `v1.0.0a1`   | TestPyPI | Alpha release                        |
| `v1.0.0-a1`  | TestPyPI | Alpha compatibility form             |
| `v1.0.0b1`   | TestPyPI | Beta release                         |
| `v1.0.0-b1`  | TestPyPI | Beta compatibility form              |

Tags are normalized with `packaging.version.Version` so prerelease routing follows PEP 440
semantics.

______________________________________________________________________

## Permissions and Trust Boundary

The workflow-level permissions are:

```yaml
permissions:
  contents: read
  id-token: write
```

`id-token: write` is required for PyPI and TestPyPI Trusted Publishing through OIDC. The workflow
does not use stored PyPI API tokens.

The `github-release` job narrows its own elevated permission to:

```yaml
permissions:
  contents: write
```

That write permission is used only to create the GitHub Release for final, non-prerelease tags.

The release trust boundary is intentionally strict:

- release artifacts are built by the CI workflow;
- the release workflow downloads artifacts from the triggering CI run;
- release metadata is verified against the resolved tag;
- checksums are verified before publication;
- package indexes are checked before publishing;
- repository build logic is not executed in the publishing jobs.

The workflow uses concurrency keyed by the CI run commit SHA so repeated release attempts for the
same commit do not run concurrently.

______________________________________________________________________

## Jobs and Validation Scope

| Job               | Purpose                                                                         | Main tools                                           |
| ----------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `preflight`       | Resolve release eligibility, tag, normalized version, channel, and release name | `git`, `packaging.version.Version`                   |
| `details`         | Download CI artifacts and verify artifact metadata and package versions         | `actions/download-artifact`, Python metadata readers |
| `publish-package` | Verify checksums, validate target-index state, and publish to PyPI or TestPyPI  | `sha256sum`, `curl`, `pypa/gh-action-pypi-publish`   |
| `github-release`  | Create a GitHub Release for final releases                                      | `softprops/action-gh-release`                        |

The `preflight` job decides whether publication should proceed. It emits release context outputs
such as the resolved tag, PEP 440 version, prerelease flag, target channel, and release name.

The `details` job downloads the `topmark-dist` and `topmark-release-meta` artifacts from the CI run
that triggered the workflow. It verifies that the artifact metadata matches the resolved release tag
and that the wheel and source distribution versions match the normalized tag version.

The `publish-package` job repeats critical metadata checks before publication, verifies checksums,
confirms that the target version does not already exist on the selected package index, and publishes
with Trusted Publishing.

Final releases also check that the new version is newer than the latest final version on PyPI.
Prereleases publish to TestPyPI and skip GitHub Release creation.

______________________________________________________________________

## Artifact Handling

The release workflow consumes artifacts produced by the CI workflow. It does not build artifacts.

Required CI artifacts are:

| Artifact               | Purpose                                                |
| ---------------------- | ------------------------------------------------------ |
| `topmark-dist`         | Source distribution and wheel built by CI              |
| `topmark-release-meta` | Release tag, normalized version, and checksum metadata |

The release workflow downloads those artifacts by using the triggering CI run ID:

```yaml
run-id: ${{ github.event.workflow_run.id }}
```

This ensures the release workflow publishes the artifacts produced by the exact CI run that caused
the release workflow to start.

Before publication, the workflow verifies:

- artifact tag metadata matches the resolved release tag;
- artifact version metadata matches the normalized tag version;
- exactly one wheel and one source distribution are present where required;
- wheel and sdist metadata versions match the tag;
- checksums match `release-meta/SHA256SUMS`;
- expected filenames include the normalized version.

This artifact-only design is a core part of the release security model.

______________________________________________________________________

## Local Reproduction

The release workflow cannot be fully reproduced locally because it depends on GitHub `workflow_run`
context, CI-uploaded artifacts, package-index state, OIDC Trusted Publishing, and GitHub Release
permissions.

The closest local checks are:

```bash
nox -s docs
nox -s links_site
nox -s links_all
uv build
```

Before tagging a release, also run the project verification target:

```bash
make verify
```

To inspect local build output manually:

```bash
uv build
ls -l dist
```

Local validation can confirm that the source tree builds and passes project checks, but it cannot
exercise the Trusted Publishing, artifact-download, package-index, or GitHub Release portions of the
workflow.

______________________________________________________________________

## Maintenance Notes

Release tags must follow the expected PEP 440-compatible scheme, such as `v1.0.0`, `v1.0.0rc1`, or
`v1.0.0-a1`.

When preparing a release:

- ensure exactly one release-style tag points at the target commit;
- prefer compact PEP 440 tag forms such as `v1.0.0rc1` for new prereleases;
- keep dashed prerelease forms only as compatibility forms;
- run local verification before pushing tags;
- let CI build artifacts and let the release workflow publish them.

Do not move artifact building into the release workflow without deliberately revisiting the release
trust boundary. The workflow is intentionally designed so package publication does not rebuild from
repository source code.

GitHub Actions are pinned to commit SHAs. Use the [GitHub Action pin audit](./action-pin-audit.md)
to detect drift between workflow files and local composite actions.

______________________________________________________________________

## Related Pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
