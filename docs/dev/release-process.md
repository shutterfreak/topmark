<!--
topmark:header:start

  project      : TopMark
  file         : release-process.md
  file_relpath : docs/dev/release-process.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Release Process

This page documents TopMark's maintainer release process, versioning model, release workflow, and
post-publication validation expectations.

TopMark releases are Git-tag-driven and published through GitHub Actions. The release pipeline is
intentionally split between source-tree validation, artifact creation, privileged publishing, and
published-package validation.

## Release Philosophy

TopMark's release process is designed around four principles:

- Git tags are the single source of truth for package versions.
- CI validates the source tree and builds release artifacts in an unprivileged context.
- The release workflow publishes only CI-built artifacts and does not rebuild the project.
- Published artifacts are validated separately after publication.

This keeps release automation explicit, reproducible, and easier to audit.

______________________________________________________________________

## Versioning Model

TopMark uses Semantic Versioning to describe compatibility intent:

| Change type                    | Version impact |
| ------------------------------ | -------------- |
| `fix:`                         | Patch release  |
| `feat:`                        | Minor release  |
| `feat!:` or `BREAKING CHANGE:` | Major release  |

Stable API compatibility applies to:

- `topmark.api`
- `topmark.registry.registry.Registry`

Advanced and internal APIs may change between minor versions.

TopMark uses PEP 440 package versions and derives package versions from Git tags through
`setuptools-scm`. Versions are not maintained manually in `pyproject.toml`.

______________________________________________________________________

## Release Tag Forms

Release tags use a leading `v` and a PEP 440-compatible version identifier.

Preferred tag forms are:

| Release type      | Tag form    | Example     |
| ----------------- | ----------- | ----------- |
| Alpha             | `vX.Y.ZaN`  | `v1.0.0a1`  |
| Beta              | `vX.Y.ZbN`  | `v1.0.0b1`  |
| Release candidate | `vX.Y.ZrcN` | `v1.0.0rc1` |
| Final             | `vX.Y.Z`    | `v1.0.0`    |

Legacy dashed prerelease tags remain supported for compatibility:

- `vX.Y.Z-aN`
- `vX.Y.Z-bN`
- `vX.Y.Z-rcN`

Prefer compact PEP 440 tag forms for new releases.

Between tags, development builds may report SCM-derived development versions such as:

- `1.0.0a1.dev3+g<commit>`
- `1.0.0-dev.3+g<commit>` or an equivalent project SemVer rendering, depending on CLI mode

______________________________________________________________________

## Release Channels

TopMark routes releases by normalized PEP 440 version semantics.

| Tag         | Channel  | Purpose                      |
| ----------- | -------- | ---------------------------- |
| `v1.0.0a1`  | TestPyPI | Alpha validation             |
| `v1.0.0b1`  | TestPyPI | Beta validation              |
| `v1.0.0rc1` | TestPyPI | Release-candidate validation |
| `v1.0.0`    | PyPI     | Final publication            |

Prereleases publish to TestPyPI. Final releases publish to PyPI and create a GitHub Release.

______________________________________________________________________

## Release Pipeline Architecture

The release pipeline is split across multiple workflows:

| Stage                        | Workflow                                              | Responsibility                                                             |
| ---------------------------- | ----------------------------------------------------- | -------------------------------------------------------------------------- |
| Source validation            | `.github/workflows/ci.yml`                            | Validate source, tests, docs, links, typing, and API snapshot expectations |
| Artifact build               | `.github/workflows/ci.yml`                            | Build `sdist` and wheel on version-tag pushes                              |
| Package publication          | `.github/workflows/release.yml`                       | Verify CI-built artifacts and publish to TestPyPI or PyPI                  |
| Published package validation | `.github/workflows/published-artifact-validation.yml` | Validate installability and runtime behavior from package indexes          |

This split is intentional. CI is allowed to run repository code and build artifacts in an
unprivileged context. The release workflow runs with publishing privileges but does not rebuild the
project from repository source code.

______________________________________________________________________

## Artifact Trust Boundary

On version-tag pushes, CI builds and uploads release artifacts:

- `topmark-dist`
- `topmark-release-meta`

The release workflow is triggered later through `workflow_run`. It downloads artifacts from the
exact CI run that triggered publication and verifies:

- the CI run completed successfully;
- the CI run was triggered by a `push` event;
- the CI run originated from the base repository;
- exactly one release-style tag points at the CI commit;
- release metadata matches the resolved tag;
- artifact versions match the normalized tag version;
- checksums match `release-meta/SHA256SUMS`;
- the target version does not already exist on the selected package index.

Final releases also verify that the new version is newer than the latest final version on PyPI.

This artifact-only publishing model avoids executing repository build logic in the privileged
release workflow.

______________________________________________________________________

## Maintainer Release Checklist

Before tagging a release:

1. Refresh `tests/api/public_api_snapshot.json` if the public API changed.

1. Update `CHANGELOG.md`.

1. Ensure release notes match the intended SemVer impact.

1. Run local verification:

   ```bash
   make verify
   make test
   ```

1. Optionally build artifacts locally for inspection:

   ```bash
   uv build
   twine check dist/*
   ```

1. Commit the release-ready changes.

1. Create and push exactly one release-style tag on the target commit:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

CI must succeed on the tag push, including release-artifact upload, before the release workflow can
publish the package.

______________________________________________________________________

## Prerelease Flow

Use prereleases to validate packaging and installation behavior before final publication.

Recommended sequence:

1. Create a prerelease tag, such as `v1.0.0b1` or `v1.0.0rc1`.
1. Push the tag.
1. Let CI build and upload artifacts.
1. Let the release workflow publish to TestPyPI.
1. Run published artifact validation against TestPyPI.
1. Fix issues and repeat with a new prerelease tag if needed.

Example validation run:

```text
version: 1.0.0rc1
index: testpypi
```

TestPyPI validation confirms the package can be installed and exercised from a consumer-like clean
environment, but TestPyPI is not a complete mirror of PyPI dependencies.

______________________________________________________________________

## Final Release Flow

Use a final release tag only after the release candidate has been validated.

Recommended sequence:

1. Confirm the intended release commit is ready.

1. Ensure no other release-style tag points at the same commit.

1. Create the final release tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

1. Let CI build release artifacts.

1. Let the release workflow publish to PyPI.

1. Confirm the GitHub Release was created.

1. Run published artifact validation against PyPI.

Example validation run:

```text
version: 1.0.0
index: pypi
```

______________________________________________________________________

## Published Artifact Validation

Published artifact validation is separate from CI and release publishing.

Use `.github/workflows/published-artifact-validation.yml` after publishing a prerelease or final
release. It validates the package as users install it from TestPyPI or PyPI across supported
platforms and Python versions.

The workflow checks:

- package installation;
- installed distribution version;
- console entry points;
- representative CLI commands;
- public API importability;
- basic runtime behavior.

This validation complements CI. CI validates the source tree and release artifacts before
publication; published artifact validation checks the package index result after publication.

______________________________________________________________________

## Recovery Notes

If CI fails on the tag push:

- do not publish manually;
- fix the issue on a new commit;
- move or recreate the release tag only if the project policy allows it and no package was
  published;
- prefer a new prerelease tag when validating fixes.

If the release workflow fails before publication:

- inspect the failed preflight, metadata, checksum, or index validation step;
- avoid rebuilding artifacts manually in the release workflow;
- prefer fixing the source or workflow issue and creating a new release attempt.

If a package was already published to PyPI:

- do not attempt to overwrite the same version;
- publish a new version instead;
- document the correction in `CHANGELOG.md` if user-visible behavior is affected.

______________________________________________________________________

## Relationship to Contributor Documentation

`CONTRIBUTING.md` should remain a concise contributor-facing guide. It may summarize release
expectations and tag conventions, but detailed release architecture belongs on this page.

The generated documentation page `docs/contributing.md` should link here for hosted documentation
readers.

______________________________________________________________________

## Related Pages

- [CI & Validation](../ci/index.md) — overview of the CI documentation family
- GitHub workflows:
  - [CI workflow](../ci/ci-workflow.md) — source-tree validation and release artifact creation
  - [Release workflow](../ci/release-workflow.md) — artifact-only package publication
  - [Published artifact validation workflow](../ci/published-artifact-validation.md) — package-index
    install validation
  - [Dependabot workflow](../ci/dependabot.md) — dependency and GitHub Actions update policy
  - [GitHub Action pin audit](../ci/action-pin-audit.md) — action pin consistency audit
- [Contributing](../contributing.md) — hosted contributor guide summary
