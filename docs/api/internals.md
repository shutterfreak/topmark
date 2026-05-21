<!--
topmark:header:start

  project      : TopMark
  file         : internals.md
  file_relpath : docs/api/internals.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Internal API reference (advanced) (%%TOPMARK_VERSION%%)

> [!WARNING]
>
> The modules listed under *Internals* are intended for contributors and advanced integrations. They
> are not covered by the stable public API compatibility contract and may evolve between minor
> releases.
>
> Prefer the [stable public API](./public.md) whenever possible.

Internals complement the stable public API.

{% include-markdown "\_snippets/terminology.md" %}

Whenever possible, prefer using:

- `topmark.api`
- documented machine-readable JSON and NDJSON contracts
- the stable `Registry` facade APIs

Internal modules should generally be used only for advanced integrations, debugging, testing, or
TopMark development.

For details on how these pages are generated and validated, see
[Development → Documentation pipeline and reference hygiene](../dev/documentation-pipeline.md).

See also:

- [Architecture](../dev/architecture.md)
- [Registry model](../dev/registry-model.md)
- [Resolution](../dev/resolution.md)
- [Plugins and extensibility](../dev/plugins.md)
- [API stability and snapshot policy](../dev/api-stability.md)
- [Machine-readable output](../dev/machine-output.md)
- [Terminology and Canonical Vocabulary](../terminology.md)

This section provides generated per-module reference pages (see `tools/docs/gen_api_pages.py`). They
are not added individually to the navigation in order to keep the sidebar compact. Use the search
box to find symbols, or browse the generated paths under `/api/internals/topmark/...`.

The generated internals span multiple architectural layers:

- TOML layer ([`topmark.toml`](internals/topmark/toml/index.md))
- Configuration layer ([`topmark.config`](internals/topmark/config/index.md))
- Runtime layer ([`topmark.runtime`](internals/topmark/runtime/index.md))
- Pipeline subsystem ([`topmark.pipeline`](internals/topmark/pipeline/index.md))
- Registry and overlay subsystems ([`topmark.registry`](internals/topmark/registry/index.md))

See [`Architecture`](../dev/architecture.md) for the conceptual overview.

Canonical file type identity semantics are documented in
[Registry model](../dev/registry-model.md#qualified-vs-local-identifiers) and
[Terminology and Canonical Vocabulary](../terminology.md).

These pages are generated automatically during the MkDocs build and should not be edited manually.

The generated reference pages reflect internal implementation structure and may evolve more
frequently than the stable public API surface or documented machine-readable contracts.

Any changes should be made in the corresponding Python source files under `src/`.

Browse the generated internals index: [`topmark` internals](internals/topmark/index.md)

Internal modules are documented for maintainers and advanced integrations, but they intentionally
evolve more flexibly than:

- `topmark.api`
- CLI contracts
- machine-readable JSON and NDJSON contracts
- canonical file type identity semantics

You can also browse the full generated tree from the sidebar under **API → Internals → Reference
(generated)**.
