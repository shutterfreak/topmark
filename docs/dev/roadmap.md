<!--
topmark:header:start

  project      : TopMark
  file         : roadmap.md
  file_relpath : docs/dev/roadmap.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark 2.x roadmap

## Purpose and ownership

This page is the concise, maintainer-facing strategic-planning reference for the 2.x line. It
describes the maintenance posture, compatibility boundaries, broad directions, and explicit
deferrals that help contributors decide where work belongs.

It is not a release history or a parallel backlog:

- [GitHub issues](https://github.com/shutterfreak/topmark/issues/) are the source of truth for
  actionable work, acceptance criteria, and progress.
- `CHANGELOG.md` is the canonical record of released upgrade outcomes and compatibility notes.
- [Upgrading TopMark](../usage/upgrading.md) is the user-facing migration-guide index.
- [Road to TopMark 1.0](road-to-1.0.md) preserves the architectural rationale of the 1.0
  stabilization effort.

When a broad direction becomes reviewable work, create or update a GitHub issue and retain only its
long-lived strategic rationale here. Remove completed roadmap items unless their deferral or
compatibility context is still useful.

______________________________________________________________________

## 2.x maintenance posture

TopMark 2.x maintains the contract-oriented architecture established by 1.x while evolving only
through deliberate, compatibility-aware changes. The 2.0 migration guide and release records define
the 2.0 boundary; this roadmap does not repeat them.

Maintenance priorities are:

- preserve documented CLI, configuration, public-API, filesystem-identity, and machine-readable
  output contracts within the active major line;
- validate behavior in downstream automation and supported Python environments;
- address concrete correctness, security, usability, and maintainability findings through focused
  issues;
- keep CI, release, dependency, and documentation validation reliable and reproducible; and
- document new compatibility decisions at their canonical contract or migration surface.

Routine maintenance must not silently broaden into a new output schema, configuration model, or
architectural redesign. Such a proposal needs an issue that states its compatibility impact and
acceptance criteria before implementation begins.

______________________________________________________________________

## Strategic directions

The following directions are intentionally broad. They are not commitments, schedules, or task
lists.

### Input and pipeline boundaries

Future in-memory pipeline support remains a strategic direction. It would let TopMark process editor
buffers, generated content, CI-provided snippets, and API-driven integrations without requiring
temporary filesystem inputs. It could also make focused processing tests more isolated.

Any work in this area must preserve clear ownership of input acquisition, processing identity,
mutation eligibility, and durable results. It should treat the pipeline as a transformation over an
explicit input source rather than weakening the filesystem-identity and safety contracts that apply
to file-backed processing today.

### Extensibility and diagnostics

Consider richer registry discovery and diagnostics, plus query or filtering capabilities beyond the
compact identity-query contract, only where they improve integration and troubleshooting without
weakening qualified file-type identity or leaking unstable implementation details. Evaluate
configuration schema versioning and broader staged-diagnostic exposure by their migration and
public-contract costs.

### Presentation and documentation evolution

Improve generated command documentation, Markdown output, and documentation navigation when user
needs or recurring maintenance evidence justify it. Preserve the distinction between human
presentation and machine-readable schemas, and between source documentation and released notes.

### Workflow sustainability

Factor CI, release, and repository tooling only after repeated maintenance patterns show a durable
benefit. Preserve the artifact-based release model, supported-Python validation, and the ability to
reproduce important checks locally.

______________________________________________________________________

## Explicit deferrals

The roadmap deliberately does not define a release schedule, enumerate planned issues, or curate 2.0
release notes. It also does not create a Road to 2.0 retrospective while the 2.0 architectural story
is still represented by the migration guide, release outcomes, and issue history. Revisit that
decision after the 2.0 release only if a coherent architectural narrative would help maintainers
understand decisions that those sources cannot explain.

______________________________________________________________________

## Related pages

- [Upgrading TopMark](../usage/upgrading.md)
- [Road to TopMark 1.0](road-to-1.0.md)
- [Release process](release-process.md)
- [Documentation conventions](documentation-conventions.md)
- [API stability and snapshot policy](api-stability.md)
