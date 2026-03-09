<!--
topmark:header:start

  project      : TopMark
  file         : public.md
  file_relpath : docs/api/public.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# API Reference (%%TOPMARK_VERSION%%)

These pages are auto‑generated using [mkdocstrings](https://mkdocstrings.github.io/), pulling
docstrings directly from the TopMark source code.

The API reference complements the higher‑level usage guides:

- [Installation](../install.md)
- [Pre‑commit integration](../usage/pre-commit.md)
- [Header placement rules](../usage/header-placement.md)
- [Supported file types](../usage/generated/filetypes.md)
- [Supported header processors](../usage/generated/processors.md)

Use this section if you need details on functions, classes, or constants available in TopMark.

## Public API (stable)

### Configuration via mappings (immutable at runtime)

Public API functions accept either a plain **mapping** (that mirrors the TOML structure) or a frozen
`Config`. Internally, TopMark merges your input into a **mutable builder** and immediately
`freeze()`s it into an immutable snapshot before running, which prevents accidental mutation and
keeps results deterministic.

`MutableConfig` is **internal** and not part of the stable API. If you want to “update the config”
for a single run, pass just the keys you want to override as a mapping:

```python
from topmark import api

config = {
    "fields": {
        "project": "TopMark",
        "license": "MIT",
    },
    "header": {
        "fields": [
            "file",
            "project",
            "license",
        ]
    },
    "formatting": {
        "align_fields": True,
    },
    "files": {
        "include_file_types": ["python"],
        "exclude_patterns": [".venv"],
    },
    "policy_by_type": {
        "python": {
            "allow_header_in_empty_files": True,
        },
    }
}

run: api.runResult = api.check(
    ["src"],
    config=config,
    diff=True,
    skip_compliant=True,
)

assert run.summary.get("unchanged", 0) >= 0
```

This design keeps the public surface small and semver-stable while allowing flexible per-call
configuration.

### Recognized vs supported file types

- File types are identified by their **file type identifier**.
- A file type is **recognized** if its *file type identifier* exists in `FileTypeRegistry`.
- A file type is **supported** if it is recognized **and** has a registered `HeaderProcessor` in `HeaderProcessorRegistry`.
- A file may be *recognized* but not *supported*. In that case:
  - it participates in discovery and filtering
  - it may appear in results (unless `skip_unsupported=True`)
  - no header insertion or removal is attempted

### Registries and extensibility (read-only by default)

TopMark exposes **read-only** registries for file types and header processors via the stable
facade in [`topmark.registry.registry.Registry`][topmark.registry.registry.Registry]. These registries represent the **effective composed
view** (internal base registries + overlays − removals) and are returned as immutable
`Mapping` views (backed by `MappingProxyType`).

These registry objects are **not part of the `topmark.api` stability contract**; the supported programmatic API is defined exclusively by the symbols exported in `topmark.api.__all__`.

Most users should interact with registries through this facade and treat them as
**introspection-only**.

If you need dynamic extensions at runtime (typically in plugins or tests), use the
**advanced registries** in \[`topmark.registry`\][topmark.registry] directly:

- \[`topmark.registry.filetypes.FileTypeRegistry.register(ft, processor=processor_class)`\][topmark.registry.filetypes.FileTypeRegistry.register]
- \[`topmark.registry.filetypes.FileTypeRegistry.unregister(name)`\][topmark.registry.filetypes.FileTypeRegistry.register]
- \[`topmark.registry.processors.HeaderProcessorRegistry.register(name, processor_class)`\][topmark.registry.processors.HeaderProcessorRegistry.register]
- \[`topmark.registry.processors.HeaderProcessorRegistry.unregister(name)`\][topmark.registry.processors.HeaderProcessorRegistry]

These mutation helpers apply **overlay-only changes**: they do not mutate the internal base
registries used to construct the effective views. Overlays are process-local and thread-safe
(via an internal lock). In tests, prefer wrapping mutations in `try/finally` to ensure cleanup.

Overlay mutations automatically invalidate composed registry caches;
callers do not need to manage cache lifetimes explicitly.

For long-term or redistributable extensions, prefer publishing a plugin using the
\[`topmark.filetypes`\][topmark.filetypes] entry point group.

See the generated API reference:

- [`topmark.api`](../api/reference/topmark.api.md)
- [`topmark.registry`](../api/reference/topmark.registry.md)

______________________________________________________________________

**Stability note:** See [API Stability](../dev/api-stability.md) for how we guard the public surface
with a JSON snapshot across supported Python versions.
