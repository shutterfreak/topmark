<!--
topmark:header:start

  project      : TopMark
  file         : plugins.md
  file_relpath : docs/dev/plugins.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Plugins and extensibility

TopMark supports extensibility via **plugins** that provide:

1. **File types** (definitions of how TopMark recognizes files), and optionally
1. **Header processors** (implementations that can detect/insert/update/strip headers for those file
   types).

This page documents the currently supported extension points and the registry/discovery rules that
matter when extending TopMark with custom file types and processor overlays.

______________________________________________________________________

## Conceptual model

TopMark uses two layers of registries:

- **Base registries** (built-ins + discovered plugins)

  - File types: loaded lazily from built-ins and the \[`topmark.filetypes`\][topmark.filetypes]
    entry point group.
  - Processors: constructed from explicit built-in processor bindings and optional runtime overlays.

- **Composed registries** (base + overlays − removals)

  - Exposed for introspection via \[`topmark.registry.*`\][topmark.registry].
  - Used by CLI and API at runtime.

The separation is intentional: **base registries must remain import-light** to avoid import cycles,
and the composed registries provide the user-facing effective views.

______________________________________________________________________

## Extension points

### File types (recommended plugin surface)

File types are discovered through Python entry points. TopMark loads:

- built-in file types from a small set of internal modules, and

- plugin file types from the entry point group:

- **Entry point group:** \[`topmark.filetypes`\][topmark.filetypes]

A plugin registers one or more `FileType` objects via that entry point.

**When loaded:** lazily, when TopMark first needs to resolve file types.

______________________________________________________________________

### Header processors (advanced / internal-facing)

Built-in header processors are declared explicitly in TopMark's internal processor binding inventory
and instantiated when the base processor registry is constructed.

Advanced integrations and tests may still register additional processor classes at runtime through
\[`topmark.registry.registry.Registry`\][topmark.registry.registry.Registry] or
\[`topmark.registry.processors.HeaderProcessorRegistry`\][topmark.registry.processors.HeaderProcessorRegistry].
These registrations are applied as **overlay-only** changes on top of the internal base registry.

______________________________________________________________________

## Registration order and runtime overlays

TopMark now uses explicit base registries plus overlay registries:

- base file types are loaded from built-ins and file-type entry points;
- base processors are constructed from explicit built-in bindings;
- runtime additions and removals are applied as overlays via
  \[`topmark.registry.*`\][topmark.registry].

This means plugin-defined file types must still be available before a processor class is registered
against them, but the processor side no longer depends on module import order or decorator side
effects. Path-based file type selection is performed by the shared scoring resolver in
\[`topmark.resolution.filetypes`\][topmark.resolution.filetypes].

______________________________________________________________________

## Writing a FileType plugin

### File type identity: name and namespace

Every `FileType` has two identity components:

- `namespace`: identifies the producer (TopMark built-ins vs. plugins)
- `name`: the file type identifier used by filtering and configuration

TopMark reserves the namespace `topmark` (the internal constant `TOPMARK_NAMESPACE`) for built-in
file types.

**Plugin guidance:**

- Set `namespace` to your package or organization identifier (for example: `"acme"`,
  `"my_company"`).
- Choose a globally-unique `name` for now (for example: `"acme_python"` rather than just
  `"python"`).

Note: `namespace` is **mandatory** for both file types and processors. The built-in namespace
`topmark` is reserved for TopMark-provided types.

Internally, a file type’s stable identity is the tuple **(namespace, name)**. Registries may still
expose or accept the *unqualified* file type name for compatibility with existing configuration and
CLI filtering, but resolution is performed through `FileTypeRegistry.resolve_filetype_id(...)`,
which understands both forms:

- `"name"` (unqualified)
- `"namespace:name"` (qualified)

Unqualified identifiers are only safe when they remain globally unique in the composed registry. If
multiple file types share the same unqualified name, callers must use the qualified
`"namespace:name"` form.

Internally, the qualified identifier `<namespace>:<name>` is considered the canonical identity and
should be treated as the stable reference for future integrations and plugins.

### 1) Create a provider function

Create a module that returns an iterable of `FileType` objects.

Example:

```python
# my_topmark_plugin/filetypes.py
from __future__ import annotations

from topmark.filetypes.model import FileType

def provide_filetypes() -> list[FileType]:
    return [
        FileType(
            name="my_plugin_my_lang",
            namespace="my_plugin",
            extensions=[".mylang"],
            filenames=[],
            patterns=[],
            description="MyLang source files",
            skip_processing=False,
        )
    ]
```

### Using the FileType factory (recommended)

TopMark provides a small helper factory that simplifies constructing multiple file types that share
the same namespace.

```python
from topmark.filetypes.factory import make_filetype_factory

make_my_ft = make_filetype_factory(namespace="my_plugin")

MY_FILETYPE = make_my_ft(
    name="my_plugin_my_lang",
    description="MyLang source files",
    extensions=[".mylang"],
)
```

This avoids repeating the namespace argument and ensures that all `FileType` instances created by
the plugin share the correct identity.

The factory only **constructs** `FileType` objects; registration still happens when TopMark loads
file types through the \[`topmark.filetypes`\][topmark.filetypes] entry point group.

### 2) Register the entry point

In your plugin's `pyproject.toml`:

```toml
[project.entry-points."topmark.filetypes"]
my_topmark_plugin = "my_topmark_plugin.filetypes:provide_filetypes"
```

This registers your file type provider so TopMark can discover it.

File types are loaded lazily when TopMark first resolves file types during configuration or pipeline
execution.

______________________________________________________________________

## Writing a HeaderProcessor plugin (advanced)

Header processor plugins are currently an **advanced runtime overlay** feature, not an entry-point
discovery mechanism.

A processor class must define a stable processor identity:

- `namespace`: identifies the producer
- `key`: local processor identifier within that namespace

The qualified processor identity is `<namespace>:<key>`.

To register a processor class for a file type at runtime, use the composed registry layer:

```python
# my_topmark_plugin/processors.py
from __future__ import annotations

from topmark.processors.base import HeaderProcessor
from topmark.registry.registry import Registry


class MyLangHeaderProcessor(HeaderProcessor):
    """Example processor for MyLang."""
    namespace = "my_plugin"
    key = "my_lang"

    # Implement required HeaderProcessor methods here
    ...


Registry.register_processor("my_plugin:my_plugin_my_lang", MyLangHeaderProcessor)
```

At registration time, TopMark resolves the file type identifier through the composed file type
registry and then binds the instantiated processor to that resolved `FileType` object. Qualified
identifiers are recommended because an unqualified file type name may become ambiguous once multiple
namespaces define similarly named file types.

Important:

- file type registration must happen before processor registration;
- runtime processor registrations are overlay-only and do not mutate the internal built-in base
  registry;
- current composed processor views are still keyed by unqualified file type name, so file type names
  should remain globally unique in the effective registry for now.

______________________________________________________________________

## Runtime processor registration flow

Unlike file types, processor classes are not discovered from entry points. They are registered
explicitly through the runtime registry API when needed.

A typical advanced integration flow is:

1. expose file types through the \[`topmark.filetypes`\][topmark.registry] entry point group;
1. let TopMark discover those file types lazily;
1. register processor classes explicitly through `Registry.register_processor(...)`,
   `Registry.try_register_processor(...)`, or `HeaderProcessorRegistry.register(...)` during
   controlled initialization.

This keeps built-in registry construction deterministic and avoids relying on module-import side
effects.

______________________________________________________________________

## Recommended plugin scope for TopMark 1.x

For most integrations, providing **FileType plugins only** is sufficient.

Header processor plugins are more advanced because they currently rely on runtime overlay
registration and still assume globally-unique unqualified file type names in the composed processor
registry.

Unless you need custom header parsing or formatting logic, prefer defining custom file types that
reuse existing processors.

______________________________________________________________________

## Troubleshooting

### "Unknown file type" during processor registration

Cause: the processor registration target does not resolve through the composed file type registry.

Fix:

- Ensure the plugin file type (including its `namespace` and unique `name`) is registered via the
  \[`topmark.filetypes`\][topmark.filetypes] entry point.
- Ensure file type discovery occurs before calling `Registry.register_processor(...)`.
- Prefer qualified file type identifiers such as `"my_plugin:my_plugin_my_lang"` when registering
  processors.

### "Ambiguous file type identifier" during processor registration

Cause: an unqualified file type identifier such as `"python"` or `"html"` matched more than one file
type in the composed registry.

Fix:

- Retry with a qualified identifier such as `"topmark:html"` or `"my_plugin:django_html"`.
- Keep unqualified file type names globally unique unless ambiguity is part of an explicitly managed
  override strategy.

### Duplicate processor registration

TopMark rejects duplicate overlay registrations for the same file type name.

If you see an error indicating that a processor is already registered for a file type, decide on an
explicit overlay strategy first, for example:

- unregister the existing overlay and then register the replacement;
- leave the existing processor in place;
- fail fast and require the caller to choose a policy explicitly.

______________________________________________________________________

## Relevant internal modules

These modules are useful if you are extending TopMark deeply:

- \[`topmark.filetypes.instances`\][topmark.filetypes.instances] – base file type discovery
- \[`topmark.processors.instances`\][topmark.processors.instances] – base processor binding
  inventory and registry construction
- \[`topmark.resolution.filetypes`\][topmark.resolution.filetypes] – shared scoring-based path
  resolver
- \[`topmark.registry.filetypes`\][topmark.registry.filetypes] – composed file type registry view
  and identifier resolution
- \[`topmark.registry.processors`\][topmark.registry.processors] – composed processor registry view
  and overlay mutations
- \[`topmark.registry.registry`\][topmark.registry.registry] – stable higher-level registry facade

These composed registries provide read-only views that combine base registrations with configuration
overlays.
