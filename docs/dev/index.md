<!--
topmark:header:start

  project      : TopMark
  file         : index.md
  file_relpath : docs/dev/index.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Development documentation

This section contains maintainer-facing documentation for TopMark's architecture,
filesystem-identity evaluation model, configuration-resolution model, compatibility contracts,
release process, generated documentation pipeline, and post-1.0 governance model.

Use these pages when changing internals, reviewing compatibility boundaries, preparing releases, or
understanding how the stable 1.x runtime model is organized.

The 1.x runtime model distinguishes several independent identity domains:

- filesystem identity (normalization, processing-path selection, and eligibility checks);
- configuration-source identity;
- file type identity;
- processor identity; and
- machine-readable serialization identity.

Understanding these distinctions is important when reviewing compatibility boundaries and runtime
behavior.

______________________________________________________________________

## Architecture and runtime model

The pages in this section define TopMark's canonical runtime behavior, including filesystem-identity
evaluation, path resolution, configuration layering, file-type resolution, runtime pipelines, and
plugin integration.

- [Terminology and canonical vocabulary](../terminology.md)
- [Architecture](architecture.md)
- [Registry model](registry-model.md) - file-type, processor, and registry identity
- [Resolution](resolution.md) - filesystem-identity evaluation, processing paths, hard-link policy,
  and configuration-source identity
- [Plugins and extensibility](plugins.md)
- [Configuration schema](configuration-schema.md)
- [Pipelines](pipelines.md)
- [Pipelines reference hub](pipelines-reference.md)

______________________________________________________________________

## Compatibility and output contracts

These documents define the stable 1.x compatibility boundaries for APIs, machine-readable output,
filesystem path serialization, file-type identity, and configuration provenance.

- [API stability and snapshot policy](api-stability.md)
- [Machine-readable format conventions](machine-formats.md)

______________________________________________________________________

## Documentation and release governance

- [Documentation pipeline and reference hygiene](documentation-pipeline.md)
- [Documentation conventions](documentation-conventions.md)
- [Release process](release-process.md)
- [Road to TopMark 1.0](road-to-1.0.md)
- [TopMark 1.0 roadmap](roadmap.md)
