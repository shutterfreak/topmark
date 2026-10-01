<!--
topmark:header:start

  project      : TopMark
  file         : documentation-pipeline.md
  file_relpath : docs/dev/documentation-pipeline.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Documentation pipeline and reference hygiene

This page documents how TopMark's stable documentation is generated, validated, and kept consistent
using the tooling under `tools/docs/`.

{% include-markdown "\_snippets/terminology.md" %}

It is intended for contributors and maintainers working on:

- API documentation
- Internal architecture docs
- Docstring quality and reference hygiene
- MkDocs and `mkdocs-gen-files` integration

This page focuses on the documentation-generation and validation pipeline itself rather than general
documentation authoring conventions. Detailed writing conventions, workflow-page structure, heading
policy, and snippet usage rules are documented in
[Documentation Conventions](documentation-conventions.md).

______________________________________________________________________

## Scope of this document

This page documents:

- generated documentation architecture;
- MkDocs integration and generation hooks;
- API and docstring scanning behavior;
- documentation hygiene validation;
- snippet and draft handling;
- strict-mode and validation behavior;
- reference-hygiene enforcement.

It intentionally does not redefine authoring conventions already covered by:

- [Documentation Conventions](documentation-conventions.md)

______________________________________________________________________

## Overview

This pipeline supports both:

- the stable public API documentation (`topmark.api`)
- internal module documentation (`topmark.*`)

and is aligned with TopMark's layered runtime and configuration architecture:

- TOML → FrozenConfig → runtime → pipeline

See [`Architecture`](./architecture.md) for the conceptual overview.

TopMark's documentation build consists of three coordinated layers:

1. **Handwritten Markdown**
   - Located under `docs/`
   - Includes DEV documentation, guides, and architecture notes
1. **Generated Markdown**
   - Produced at build time by `mkdocs-gen-files`
   - Includes CLI/configuration reference output
1. **Generated API internals**
   - Produced from `src/topmark/` by `api-autonav`
1. **Build-time validation and hygiene**
   - Enforced via MkDocs hooks, custom tooling, and shared helpers
   - Ensures symbol references, snippet includes, and generated pages remain consistent,
     deterministic, and maintainable

All tooling lives under:

```text
tools/docs/
```

and is executed only during documentation builds.

Documentation validation is also integrated into local contributor workflows, CI verification, and
stable-release validation through `make verify`, `nox`, and GitHub Actions.

### Zensical compatibility pilot

The production MkDocs build and Read the Docs deployment remain authoritative. The Zensical path is
an exploratory compatibility pilot: it builds an ignored, disposable `.zensical/` tree and does not
publish a site, replace MkDocs in CI, or modify the source `docs/` tree.

Zensical is intentionally isolated in the `zensical` optional dependency extra. Production MkDocs
and Read the Docs builds install `.[docs]`; the pilot Nox sessions install `.[docs,zensical]`. For
direct local Zensical commands, install that pair with `make venv-sync-zensical`.

Use the pilot commands through Make or Nox:

```bash
make zensical-prepare
make zensical-build
make zensical-serve
make zensical-clean

nox -s zensical
nox -s zensical_serve
```

`zensical-build` and its Nox session prepare the staging tree automatically. `zensical-serve` does
the same once before starting the server; because it watches staged inputs rather than the source
tree, rerun it after changing source documentation. `zensical-clean` removes the ignored, disposable
`.zensical/` staging tree, including its generated site and cache.

#### Compatibility bridges

The preparation step preserves the current site output by deliberately bridging the Zensical gaps
that TopMark uses today:

| Existing MkDocs behavior                                                                 | Pilot bridge                                                                                                                                   | Ownership and removal condition                                                                                                                                          |
| ---------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Virtual CLI/configuration pages via `mkdocs-gen-files`                                   | Materialize TopMark-owned CLI/configuration pages in `.zensical/docs` through the filesystem-capable generator backend.                        | Keep while TopMark's CLI Markdown exporters remain custom.                                                                                                               |
| Internal API pages and navigation via `api-autonav`                                      | Reuse the shared `api-autonav` configuration after rewriting its `src/topmark` path for `.zensical/`.                                          | Native Zensical support owns this tree; keep the shared route root aligned with MkDocs.                                                                                  |
| `%%TOPMARK_VERSION%%` and GitHub-alert conversion via `mkdocs-simple-hooks`              | Expand the version macro during staging; enable Zensical-native `callouts` for `> [!NOTE]` syntax.                                             | Version expansion remains a project build transform. Remove callout bridging once the shared configuration can express it directly.                                      |
| Local snippet inclusion and `rewrite_relative_urls` via `mkdocs-include-markdown-plugin` | Expand TopMark's local Markdown snippets recursively, rewrite their relative links for each destination page, then remove staged `_snippets/`. | A narrow temporary adapter; remove when Zensical supports the required plugin behavior. It rejects unsupported plugin options, remote files, escaping paths, and cycles. |
| `draft_docs` and excluding private snippets from published pages                         | Skip drafts while copying and remove snippets after expansion.                                                                                 | Keep until equivalent Zensical configuration is available and verified.                                                                                                  |

The staged configuration is derived from `mkdocs.yml` and redirects `mkdocstrings` source discovery
to `../src`. It retains unsupported plugin entries only because Zensical safely ignores them; the
preparation bridges above supply their required TopMark behavior.

#### Pilot verification

Build the staged inputs directly when diagnosing the pilot:

```bash
.venv/bin/zensical build --config-file .zensical/mkdocs.yml --strict
```

Run the local web server:

```bash
.venv/bin/zensical serve --config-file .zensical/mkdocs.yml
```

The preparation tests in `tests/dev_validation/test_zensical_docs_preparation.py` cover staged
configuration generation, filesystem-backed API generation, version expansion, snippet expansion,
link rewriting, and unsafe or unsupported include inputs. Compare rendered pages with the production
MkDocs site before declaring a compatibility gap closed.

______________________________________________________________________

## Relationship to CI and validation tooling

Documentation validation is intentionally layered and deterministic:

- MkDocs performs rendering-time validation;
- `tools/docs/` performs deterministic repository hygiene and prose-hygiene checks;
- `make verify` and `nox` integrate documentation validation into contributor workflows;
- GitHub Actions enforce documentation validation in CI.

See also:

- [CI workflow](../ci/ci-workflow.md)
- [Test and validation architecture](../ci/test-validation.md)

______________________________________________________________________

## Generated documentation

### Internals pages

Generated by `api-autonav` from `src/topmark/` under:

```text
api/internals/
```

Characteristics:

- One page per importable, non-private module under `src/topmark/`, including the supported
  `topmark.api` and `topmark.registry` facades
- Native package-aware navigation and breadcrumbs
- Stable module and package URLs rooted at `api/internals/`
- Implicit namespace packages are skipped intentionally

The generated module reference is the sole `mkdocstrings` definition for every Python module. This
avoids duplicate `mkdocs-autorefs` anchors while making the public facades discoverable in the same
native navigation and breadcrumb hierarchy as the rest of the package. The handwritten
[Public API overview](../api/public.md) remains the compatibility and usage guide; its module links
lead to the generated `topmark.api` and `topmark.registry` pages.

Public API stability expectations and snapshot validation are documented in
[API stability and snapshot policy](api-stability.md).

### CLI and configuration reference pages

Generated from live TopMark output:

```text
usage/generated/filetypes.md
usage/generated/processors.md
usage/generated/bindings.md
configuration/generated/example-config.md
configuration/generated/config-defaults.md
```

via:

```bash
python -m topmark ... --output-format markdown
```

Generated CLI reference pages are therefore treated as derived release artifacts rather than
handwritten documentation.

______________________________________________________________________

## Relationship to documentation conventions

The documentation pipeline enforces generated-page consistency and validation behavior, while stable
writing and structure conventions are documented separately.

Authoring conventions include:

- heading structure;
- snippet conventions;
- workflow-page templates;
- related-pages conventions;
- heading-style policy;
- Markdown organization rules.

See:

- [Documentation conventions](documentation-conventions.md)

______________________________________________________________________

## Docstring scanning and reference hygiene

Both handwritten Markdown and Python module docstrings are scanned for unlinked backticked symbol
references, such as:

```markdown
`topmark.registry.registry.Registry`
```

Docstring scanning is performed on raw Python source files before `mkdocstrings` renders them into
Markdown, which ensures reported line numbers always refer to the original `src/...` files.

The shared enforcement logic lives in:

```text
tools/docs/docs_utils.py
```

and is used identically by:

- `hooks.py` (Markdown scanning)
- `gen_cli_reference_pages.py` (docstring scanning)

### Why this matters

This helps ensure that documentation remains navigable and that symbol references stay valid even as
internal modules evolve.

- `mkdocs-autorefs` can only resolve symbols that are properly linked;
- backticked-but-unlinked symbols silently break cross-references;
- docstrings are rendered into the generated documentation and must follow the same hygiene rules as
  handwritten Markdown.

### What is considered a symbol

A candidate is enforced when it:

- looks like a dotted Python path;
- starts with `topmark.`;
- is **not** a filename (`.toml`, `.yaml`, ...);
- is **not** explicitly whitelisted.

This logic lives in:

```text
tools.docs.docs_utils.should_enforce_link()
```

______________________________________________________________________

## Whitelisting non-linkable symbols

Some backticked identifiers are intentional and should **not** be linked.

These are allowed through an explicit exact-match whitelist:

```bash
export TOPMARK_DOCS_NONLINKED_SYMBOLS="topmark.toml,topmark.internal_thing"
```

Rules:

- Exact matches only (no prefixes)
- Applies to Markdown *and* docstrings
- Logged in debug mode for transparency

______________________________________________________________________

## Logging, debug, and strict modes

Two environment variables control documentation-validation behavior:

### `TOPMARK_DOCS_DEBUG`

When enabled:

- Emits detailed DEBUG/INFO logs
- Shows:
  - Rendered-on context
  - Edit URLs (for Markdown)
  - Alternate inline-link suggestions (`Alt:`)
  - Full symbol lists (no truncation)

### `TOPMARK_DOCS_STRICT_REFS`

When enabled:

- the build fails if any unlinked symbols are found;
- failures are aggregated and reported after processing all pages;
- `mkdocs.exceptions.Abort` is used for clean termination.

Severity behavior remains intentionally consistent between:

- `hooks.py` (Markdown scanning)
- `gen_cli_reference_pages.py` (docstring scanning)

______________________________________________________________________

## Contextual logging

All diagnostics aim to be **actionable**.

Depending on origin, logs include:

- Local repo paths (`docs/...` or `src/...`)
- Line numbers
- Rendered-on pages
- Edit URLs (when available)

Context lines are built centrally via:

```python
tools.docs.docs_utils.context_lines()
```

______________________________________________________________________

## Drafts and snippets

### Draft files

Files under:

```text
docs/_drafts/
docs/**/_drafts/
```

are:

- Ignored by MkDocs navigation
- Ignored by version control
- Safe for work-in-progress documentation
- optionally visible when serving documentation locally (marked as draft)

### Markdown snippets

Files under:

```text
docs/_snippets/
```

are:

- intended for inclusion via plugins such as `include-markdown`;
- not standalone pages;
- explicitly excluded via `exclude_docs` in `mkdocs.yml`;
- intended only for stable reusable documentation fragments.

Markdown documentation hygiene is validated through:

```bash
make docs-hygiene
```

which runs:

```bash
python tools/docs/check_docs_hygiene.py --docs-hygiene --stats
```

Python code-prose hygiene is validated separately through:

```bash
python tools/docs/check_code_hygiene.py
```

The Markdown hygiene validation performs repository-hygiene checks for:

- broken include paths;
- malformed docs-root-relative include paths;
- include targets resolving outside `docs/`;
- nested snippet includes;
- accidental macOS `._*` files under documentation sources;
- Markdown files under `docs/` missing from `mkdocs.yml` navigation;
- emoji in Markdown headings;
- missing section separators between level-2 headings.

The checker also reports maintainability warnings for:

- orphaned snippets;
- headings inside snippets;
- smart punctuation in Markdown prose;
- relative links inside reusable snippets unless include-markdown link rewriting is intentional;
- snippet include paths that do not use the formatter-stable `\_snippets/` prefix.

Shared navigation snippets such as `related-pages*.md` are intentionally allowed to contain relative
links because they centralize reusable documentation navigation behavior.

`check_code_hygiene.py` complements the Markdown-focused checks by scanning Python comments,
docstrings, and prose-oriented string literals under `src/topmark/`, `tests/`, and `tools/`. It
currently enforces ASCII-oriented punctuation hygiene for terminal-safe, deterministic, and
copy/paste-friendly generated documentation and CLI output.

These checks intentionally remain lightweight and repository-focused. They reinforce repository-wide
documentation consistency without turning every style preference into a hard release blocker.

______________________________________________________________________

## Design principles

The documentation tooling follows a few strict principles:

- **Deterministic** - no hidden state and no reliance on import order.
- **Fail-late, report-all** - especially in strict mode.
- **Shared logic, single source of truth** - no duplicated include semantics, prose-hygiene rules,
  or validation heuristics.
- **Documentation is code** - docstrings, Markdown, and generated reference material are held to the
  same standard.

______________________________________________________________________

## Summary

- documentation is generated, validated, and enforced as part of the build;
- `tools/docs/` is the authoritative location for documentation tooling;
- reference hygiene, Markdown hygiene, and Python prose hygiene are enforced consistently across
  documentation sources, comments, and docstrings;
- debug and strict modes provide both flexibility and CI-grade guarantees.

If you change how TopMark is structured, update the documentation pipeline accordingly - it is a
stable and intentionally maintained part of the project architecture.

______________________________________________________________________

## Related pages

- [Documentation conventions](documentation-conventions.md)
- [Terminology and Canonical Vocabulary](../terminology.md)
- [API stability and snapshot policy](api-stability.md)
- [CI workflow](../ci/ci-workflow.md)
- [Test and validation architecture](../ci/test-validation.md)
- [Contributing](../contributing.md)
