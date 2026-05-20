<!--
topmark:header:start

  project      : TopMark
  file         : release-workflow.md
  file_relpath : docs/ci/release-workflow.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Release workflow

This page documents `.github/workflows/release.yml`.

The release workflow is TopMark's privileged package-publishing workflow. It is triggered by a
completed CI workflow run, verifies that the CI run corresponds to exactly one release tag,
downloads CI-built artifacts, publishes those artifacts to PyPI or TestPyPI, and creates the
corresponding GitHub release or prerelease.

{% include-markdown "\_snippets/terminology.md" %}

## Purpose

The release workflow publishes prebuilt release artifacts after CI has already validated and
uploaded them. It intentionally operates as an artifact-only publishing workflow: it does not
rebuild the project from repository source code inside the privileged publishing context.

This separation keeps package publication distinct from repository-source validation. The CI
workflow runs repository code and builds artifacts in a lower-privilege context; the release
workflow verifies and publishes those artifacts using Trusted Publishing through OIDC.

Coverage reporting is intentionally separate from the release workflow. Coverage artifacts are
published by the CI workflow as lightweight diagnostic outputs and are not consumed by release
publication jobs.

______________________________________________________________________

## Trigger conditions

| Trigger        | When it runs                      | Purpose                                                                           |
| -------------- | --------------------------------- | --------------------------------------------------------------------------------- |
| `workflow_run` | After the `CI` workflow completes | Publish CI-built artifacts only when the completed CI run is eligible for release |

The workflow starts for completed CI runs, but publication proceeds only when all release preflight
checks pass.

The `preflight` job requires that:

- the triggering CI run completed successfully;
- the CI run was triggered by a `push` event;
- the CI run originated from the base repository;
- exactly one release-style tag points at the CI commit.

If no matching release tag points at the CI commit, the workflow exits cleanly without attempting
publication.

If multiple matching release tags point at the same commit, preflight fails rather than selecting a
tag implicitly.

Supported release tags include final and prerelease forms such as:

| Tag          | Channel  | Notes                                   |
| ------------ | -------- | --------------------------------------- |
| `v1.0.0`     | PyPI     | Final release                           |
| `v1.0.0rc1`  | TestPyPI | Release candidate                       |
| `v1.0.0-rc1` | TestPyPI | Legacy compatibility form (with hyphen) |
| `v1.0.0a1`   | TestPyPI | Alpha release                           |
| `v1.0.0-a1`  | TestPyPI | Alpha compatibility form                |
| `v1.0.0b1`   | TestPyPI | Beta release                            |
| `v1.0.0-b1`  | TestPyPI | Beta compatibility form                 |

Tags are normalized through `packaging.version.Version`, so prerelease routing follows PEP 440
semantics.

______________________________________________________________________

## Permissions and trust boundary

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

That write permission is used only to create the GitHub Release object. Prerelease tags create
GitHub prereleases; final tags create normal GitHub releases.

The release trust boundary is intentionally strict, explicit, and deterministic:

- release artifacts are built by the CI workflow;
- the release workflow downloads artifacts from the triggering CI run;
- release metadata is verified against the resolved tag;
- CI Python metadata is verified and reported as release provenance;
- checksums are verified before publication;
- package indexes are checked before publishing;
- repository build logic is not executed in the publishing jobs.

The workflow uses concurrency keyed by the CI run commit SHA so repeated release attempts for the
same commit cannot run concurrently.

______________________________________________________________________

## Jobs and validation scope

| Job               | Purpose                                                                         | Main tools                                           |
| ----------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `preflight`       | Resolve release eligibility, tag, normalized version, channel, and release name | `git`, `packaging.version.Version`                   |
| `details`         | Download CI artifacts and verify artifact metadata and package versions         | `actions/download-artifact`, Python metadata readers |
| `publish-package` | Verify checksums, validate target-index state, and publish to PyPI or TestPyPI  | `sha256sum`, `curl`, `pypa/gh-action-pypi-publish`   |
| `github-release`  | Create a GitHub Release or GitHub prerelease for the resolved tag               | `softprops/action-gh-release`                        |

The `preflight` job decides whether publication should proceed. It emits release context outputs
such as the resolved tag, PEP 440 version, prerelease flag, target channel, and release name.

The `details` job downloads the `topmark-dist` and `topmark-release-meta` artifacts from the CI run
that triggered the workflow. It verifies that the artifact metadata matches the resolved release
tag, that the CI Python metadata is present and well-formed, and that the wheel and source
distribution versions match the normalized tag version.

The `publish-package` job repeats critical artifact and metadata checks before publication, verifies
checksums, confirms that the target version does not already exist on the selected package index,
and publishes with Trusted Publishing.

The release workflow uses an explicit release-tooling Python version for publication tooling. It
reports the canonical Python version recorded by CI and emits a non-blocking warning if the release
tooling Python drifts from that canonical CI Python. That warning is maintenance guidance only; it
is not a publication gate.

Final releases also check that the new version is newer than the latest final version on PyPI.
Prereleases skip that final-version ordering check, publish to TestPyPI, and create GitHub
prereleases; final releases publish to PyPI and create normal GitHub releases.

______________________________________________________________________

## Artifact handling

The release workflow consumes release artifacts produced by the CI workflow. It does not build
artifacts.

Required release artifacts from CI are:

| Artifact               | Purpose                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| `topmark-dist`         | Source distribution and wheel built by CI                            |
| `topmark-release-meta` | Release tag, normalized version, checksums, and CI Python provenance |

The release workflow downloads those artifacts by using the triggering CI run ID:

```yaml
run-id: ${{ github.event.workflow_run.id }}
```

This ensures the release workflow publishes the artifacts produced by the exact CI run that caused
the release workflow to start.

Coverage artifacts produced by the CI workflow are intentionally excluded from the release workflow.
HTML coverage reports and machine-readable coverage outputs are diagnostic CI artifacts, not release
publication inputs.

Before publication, the workflow verifies:

- artifact tag metadata matches the resolved release tag;
- artifact version metadata matches the normalized tag version;
- CI Python metadata exists and contains a non-empty supported-version list;
- exactly one wheel and one source distribution are present where required;
- wheel and sdist metadata versions match the tag;
- checksums match `release-meta/SHA256SUMS`;
- expected filenames include the normalized version.

The Python metadata is release provenance from the CI run that built the artifacts. It is reported
by the release workflow, but it does not control the privileged release job's tooling runtime.

This artifact-only design is a core part of the release security model.

______________________________________________________________________

## Local reproduction

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

Local validation can confirm that the repository source tree builds and passes project checks, but
it cannot exercise the Trusted Publishing, artifact-download, package-index, or GitHub Release
portions of the workflow.

______________________________________________________________________

## Maintenance notes

Release tags must follow the expected PEP 440-compatible scheme, such as `v1.0.0`, `v1.0.0rc1`, or
`v1.0.0-a1`.

When preparing a release:

- ensure exactly one release-style tag points at the target commit;
- prefer compact PEP 440 tag forms such as `v1.0.0rc1` for new prereleases;
- keep dashed prerelease forms only as compatibility forms;
- run local verification before pushing tags;
- let CI build release artifacts and let the release workflow publish them and create the matching
  GitHub Release or prerelease.

For user-facing prerelease installation instructions, see
[`INSTALL.md`](https://github.com/shutterfreak/topmark/blob/main/INSTALL.md). For post-publication
matrix validation of prereleases from TestPyPI, use the
[Published artifact validation workflow](./published-artifact-validation.md).

Do not move artifact building into the release workflow without deliberately revisiting the release
trust boundary. The workflow is intentionally designed so package publication does not rebuild from
repository source code.

Keep the release-tooling Python explicit unless the release trust model is deliberately revisited.
CI records the supported and canonical Python versions as artifact metadata so the release workflow
can report drift without deriving its privileged runtime from repository-source metadata.

Do not couple release publication to coverage percentages or external coverage services unless the
project deliberately adopts coverage as a formal release-governance contract in a future major
workflow revision.

Do not suppress GitHub prerelease creation for alpha, beta, or release-candidate tags unless the
release visibility policy is deliberately revisited. GitHub prereleases provide the public
release-note and traceability surface for prerelease milestones, while package publication continues
to route prerelease artifacts to TestPyPI.

GitHub Actions are pinned to commit SHAs. Use the [GitHub Action pin audit](./action-pin-audit.md)
to detect drift between workflow files and local composite actions.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
