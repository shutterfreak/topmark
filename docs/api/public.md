<!--
topmark:header:start

  project      : TopMark
  file         : public.md
  file_relpath : docs/api/public.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# API Reference

These pages are auto‑generated using [mkdocstrings](https://mkdocstrings.github.io/), pulling
docstrings directly from the TopMark source code.

The API reference complements the higher‑level usage guides:

- [Installation](../install.md)
- [Pre‑commit integration](../usage/pre-commit.md)
- [Header placement rules](../usage/header-placement.md)
- [Supported file types](../usage/filetypes.md)

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

result = api.check(
    ["src"],
    config={
        "fields": {"project": "TopMark", "license": "MIT"},
        "header": {"fields": ["file", "project", "license"]},
        "formatting": {"align_fields": True},
        "files": {"file_types": ["python"], "exclude_patterns": [".venv"]},
    },
)
```

This design keeps the public surface small and semver-stable while allowing flexible per-call
configuration.

### Registries and extensibility (read‑only by default)

The public API exposes **read‑only** registries for file types and header processors.
They are returned as `Mapping` views (backed by `MappingProxyType`) to enforce immutability:

- `api.get_file_type_registry() -> Mapping[str, FileType]`
- `api.get_header_processor_registry() -> Mapping[str, HeaderProcessor]`

If you need dynamic extensions in plugins or tests, use the **advanced** registries in
`topmark.registry`:

- `topmark.registry.FileTypeRegistry.register(ft, processor=...)`
- `topmark.registry.FileTypeRegistry.unregister(name)`
- `topmark.registry.HeaderProcessorRegistry.register(name, processor_cls)`
- `topmark.registry.HeaderProcessorRegistry.unregister(name)`

These mutation helpers apply **overlay-only changes**: they do not mutate the internal
base mappings (built‑ins + entry points). Overlays are process‑local, thread‑safe (via
an internal lock), and can be removed with `unregister(...)`. For long‑term or
redistributable extensions, prefer publishing a plugin with an entry point group
`topmark.filetypes`.

::: topmark.api
options:
heading_level: 2
show_root_heading: false
members_order: source
filters:
\- "!^\_"

::: topmark.registry
options:
heading_level: 2
show_root_heading: false
members_order: source
filters:
\- "!^\_"

______________________________________________________________________

**Stability note:** See [API Stability](../dev/api-stability.md) for how we guard the
public surface with a JSON snapshot across Python 3.10–3.13.
