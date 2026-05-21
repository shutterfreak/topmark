<!--
topmark:header:start

  project      : TopMark
  file         : index.md
  file_relpath : docs/api/index.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# API documentation

This section documents TopMark's stable public Python API and generated internal API reference.

The public API is exposed through `topmark.api` and is the supported integration surface for Python
callers. Internal modules are documented for maintainers and advanced contributors, but they are not
part of the stable public API compatibility contract unless explicitly documented otherwise.

______________________________________________________________________

## Public API

- [Public API overview](public.md)
- [`topmark.api` reference](reference/topmark.api.md)
- [`topmark.registry` reference](reference/topmark.registry.md)

______________________________________________________________________

## Internal reference

- [Internal API overview](internals.md)
- [Generated internal reference](internals/topmark/index.md)

______________________________________________________________________

## Related documentation

- [API stability and snapshot policy](../dev/api-stability.md)
- [Registry model](../dev/registry-model.md)
- [Plugins and extensibility](../dev/plugins.md)
