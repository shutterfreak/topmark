<!--
topmark:header:start

  project      : TopMark
  file         : internals.md
  file_relpath : docs/api/internals.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Internals (advanced) (%%TOPMARK_VERSION%%)

> [!WARNING]
>
> The modules listed under *Internals* are intended for contributors and advanced users. They are
> **subject to change** and are **not** covered by the semver stability guarantees. Prefer the
> stable public API documented in **API → Public API**.

Internals complement the stable public API documented in **API → Public API**. Where possible,
prefer using `topmark.api`; internals should only be relied on when building integrations,
debugging, or contributing to TopMark itself.

For details on how these pages are generated and validated, see
[Development → Documentation Pipeline & Reference Hygiene](../dev/documentation-pipeline.md).

This section provides per‑module reference pages generated during the docs build (see
`tools/docs/gen_api_pages.py`). They are not added individually to the navigation to keep the
sidebar compact. Use the search box to find symbols, or browse the generated paths under
`/api/internals/topmark/...`.

Internals span multiple architectural layers:

- TOML layer ([`topmark.toml`](internals/topmark/toml/index.md))
- Config layer ([`topmark.config`](internals/topmark/config/index.md))
- Runtime layer ([`topmark.runtime`](internals/topmark/runtime/index.md))
- Pipeline ([`topmark.pipeline`](internals/topmark/pipeline/index.md)) subsystem
- Registry ([`topmark.registry`](internals/topmark/registry/index.md)) subsystems

See [`Architecture`](../dev/architecture.md) for a high-level overview.

These pages are generated automatically during the MkDocs build and should not be edited manually.
Any changes should be made in the corresponding Python source files under `src/`.

Browse the generated internals index: [`topmark` internals](internals/topmark/index.md)

You can also browse the full generated tree from the sidebar under **API → Internals → Reference
(generated)**.
