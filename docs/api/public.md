<!--
topmark:header:start

  file         : public.md
  file_relpath : docs/api/public.md
  project      : TopMark
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

::: topmark.api
    options:
      heading_level: 2
      show_root_heading: false
      members_order: source
      filters:
        - "!^_"

::: topmark.registry
    options:
      heading_level: 2
      show_root_heading: false
      members_order: source
      filters:
        - "!^_"

---

**Stability note:** See [API Stability](../dev/api-stability.md) for how we guard the
public surface with a JSON snapshot across Python 3.10–3.13.
