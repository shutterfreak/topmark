<!--
topmark:header:start

  project      : TopMark
  file         : release-process.md
  file_relpath : docs/dev/release-process.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Release process

This page documents TopMark's maintainer release process, versioning model, release workflow, and
post-publication validation expectations.

{% include-markdown "\_snippets/terminology.md" %}

TopMark releases are Git-tag-driven and published through GitHub Actions. The release pipeline is
intentionally split between source-tree validation, artifact creation, privileged publishing, and
published-package validation.

## Release philosophy

TopMark's release process is designed around four principles:

- Git tags are the canonical source of truth for package versions.
- CI validates the source tree and builds release artifacts in an unprivileged context.
- The release workflow publishes only CI-built artifacts and does not rebuild the project.
- Published artifacts are validated separately after publication.

This keeps release automation explicit, deterministic, reproducible, and easier to audit.

______________________________________________________________________

## Versioning model

TopMark uses Semantic Versioning to describe compatibility intent:

| Change type                    | Version impact |
| ------------------------------ | -------------- |
| `fix:`                         | Patch release  |
| `feat:`                        | Minor release  |
| `feat!:` or `BREAKING CHANGE:` | Major release  |

Stable 1.x compatibility guarantees apply to:

- `topmark.api`
- `topmark.registry.registry.Registry`
- documented machine-readable JSON and NDJSON contracts

Advanced and internal APIs may evolve outside the stable public 1.x compatibility surface.

TopMark uses PEP 440 package versions and derives package versions from Git tags through
`setuptools-scm`. Versions are not maintained manually in `pyproject.toml`.

______________________________________________________________________

## Release tag forms

Release tags use a leading `v` and a PEP 440-compatible version identifier.

Preferred tag forms are:

| Release type      | Tag form    | Example     |
| ----------------- | ----------- | ----------- |
| Alpha             | `vX.Y.ZaN`  | `v1.0.0a1`  |
| Beta              | `vX.Y.ZbN`  | `v1.0.0b1`  |
| Release candidate | `vX.Y.ZrcN` | `v1.0.0rc1` |
| Final             | `vX.Y.Z`    | `v1.0.0`    |

Legacy dashed prerelease tags remain supported for backward compatibility:

- `vX.Y.Z-aN`
- `vX.Y.Z-bN`
- `vX.Y.Z-rcN`

Prefer compact PEP 440 tag forms for new releases.

Between tags, development builds may report SCM-derived development versions such as:

- `1.0.0a1.dev3+g<commit>`
- `1.0.0-dev.3+g<commit>` or an equivalent project SemVer rendering, depending on CLI mode

______________________________________________________________________

## Release channels

TopMark routes releases through normalized PEP 440 version semantics and separate publication
channels.

| Tag         | Channel  | Purpose                      |
| ----------- | -------- | ---------------------------- |
| `v1.0.0a1`  | TestPyPI | Alpha validation             |
| `v1.0.0b1`  | TestPyPI | Beta validation              |
| `v1.0.0rc1` | TestPyPI | Release-candidate validation |
| `v1.0.0`    | PyPI     | Final publication            |

Prereleases publish to TestPyPI and create GitHub prereleases. Final releases publish to PyPI and
create normal GitHub releases.

______________________________________________________________________

## Release pipeline architecture

The release pipeline is split across multiple workflows:

| Stage                        | Workflow                                              | Responsibility                                                                       |
| ---------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Source validation            | `.github/workflows/ci.yml`                            | Validate source, tests, documentation, links, typing, and API snapshot expectations  |
| Artifact build               | `.github/workflows/ci.yml`                            | Build `sdist` and wheel on version-tag pushes                                        |
| Package publication          | `.github/workflows/release.yml`                       | Verify CI-built artifacts and publish to TestPyPI or PyPI through Trusted Publishing |
| Published package validation | `.github/workflows/published-artifact-validation.yml` | Validate installability and runtime behavior from TestPyPI or PyPI                   |

This split is intentional. CI is allowed to run repository code and build artifacts in an
unprivileged environment. The release workflow runs with publishing privileges but does not rebuild
the project from repository source code.

The release workflow also creates the corresponding GitHub Release object: prerelease tags create
GitHub prereleases, while final tags create normal GitHub releases.

______________________________________________________________________

## Artifact trust boundary

On version-tag pushes, CI builds and uploads release artifacts:

- `topmark-dist`
- `topmark-release-meta`

The release workflow is triggered afterward through `workflow_run`. It downloads artifacts from the
exact CI run that triggered publication and verifies:

- the CI run completed successfully;
- the CI run was triggered by a `push` event;
- the CI run originated from the base repository;
- exactly one release-style tag points at the CI commit;
- release metadata matches the resolved tag;
- artifact versions match the normalized tag version;
- checksums match `release-meta/SHA256SUMS`;
- the target version does not already exist on the selected package index.
- the package is published with PyPI/TestPyPI Trusted Publishing through OIDC.

Final releases also verify that the new version is newer than the latest final version on PyPI.
Prereleases skip that final-version ordering check and publish to TestPyPI.

This artifact-only publishing model avoids executing repository build logic inside the privileged
release workflow.

______________________________________________________________________

## Maintainer release checklist

Before tagging a release:

1. Refresh `tests/api/public_api_snapshot.json` if the public API changed.

1. Update `CHANGELOG.md`.

1. Review upgrade and migration guidance ([Upgrading to TopMark 1.0](../usage/upgrading-to-1.0.md))
   if the release changes:

   - CLI behavior or options;
   - runtime configuration structure or policy semantics;
   - machine-readable JSON or NDJSON contracts;
   - pre-commit hook behavior;
   - stable runtime or reporting contracts.

1. Ensure release notes match the intended semantic-versioning impact.

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

CI must succeed on the tag push, including release-artifact upload, before the release workflow is
allowed to publish the package.

______________________________________________________________________

## Prerelease flow

Use prereleases to validate packaging and installation behavior before final publication.

Recommended sequence:

1. Create a prerelease tag, such as `v1.0.0b1` or `v1.0.0rc1`.
1. Push the tag.
1. Let CI build and upload artifacts.
1. Let the release workflow publish to TestPyPI and create the GitHub prerelease.
1. Run published artifact validation against TestPyPI.
1. Fix issues and repeat with a new prerelease tag if needed.

Example validation run:

```text
version: 1.0.0rc1
index: testpypi
```

TestPyPI validation confirms the package can be installed and exercised from a consumer-like clean
environment, but TestPyPI is not a complete mirror of PyPI dependency behavior.

User-facing prerelease installation instructions are documented in
[`INSTALL.md`](https://github.com/shutterfreak/topmark/blob/main/INSTALL.md).

______________________________________________________________________

## Final release flow

Use a final release tag only after release-candidate validation has succeeded.

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

## Published artifact validation

Published artifact validation is intentionally separate from CI and release publishing.

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

This validation intentionally complements CI rather than replacing it.

CI validates the source tree and release artifacts before publication; published artifact validation
checks the package-index result after publication.

______________________________________________________________________

## Recovery notes

If CI fails on the tag push:

- do not publish manually;
- fix the issue on a new commit;
- move or recreate the release tag only if project policy allows it and no package was published;
- prefer a new prerelease tag when validating fixes.

If the release workflow fails before publication:

- inspect the failed metadata, checksum, publication, or package-index validation step;
- avoid rebuilding artifacts manually in the release workflow;
- prefer fixing the source or workflow issue and creating a new release attempt.

If a package was already published to PyPI:

- do not attempt to overwrite the same version;
- publish a new version instead;
- document the correction in `CHANGELOG.md` if user-visible behavior is affected.

______________________________________________________________________

## Relationship to contributor documentation

`CONTRIBUTING.md` should remain a concise contributor-facing entry point. It may summarize release
expectations and tag conventions, but detailed release architecture belongs on this page.

The generated documentation page `docs/contributing.md` should link here for hosted documentation
readers.

______________________________________________________________________

## Related pages

- [CI & Validation](../ci/index.md) - overview of the CI documentation family
- [Terminology and Canonical Vocabulary](../terminology.md)
- GitHub workflows:
  - [CI workflow](../ci/ci-workflow.md) - source-tree validation and release artifact creation
  - [Release workflow](../ci/release-workflow.md) - artifact-only package publication
  - [Published artifact validation workflow](../ci/published-artifact-validation.md) - package-index
    install validation
  - [Dependabot workflow](../ci/dependabot.md) - dependency and GitHub Actions update policy
  - [GitHub Action pin audit](../ci/action-pin-audit.md) - action pin consistency audit
- [Contributing](../contributing.md) - hosted contributor guide

______________________________________________________________________

## Summary

TopMark's release model separates:

- source-tree validation;
- release artifact creation;
- privileged package publication;
- published-package validation.

Git tags are the canonical source of truth for package versions, while CI-built artifacts are the
only artifacts eligible for publication.

This separation keeps release behavior deterministic, auditable, reproducible, and aligned with
TopMark's stable 1.x compatibility model.
