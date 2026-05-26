<!--
topmark:header:start

  project      : TopMark
  file         : documentation-conventions.md
  file_relpath : docs/dev/documentation-conventions.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Documentation conventions

This document defines TopMark's stable documentation structure, terminology, reuse rules, page
templates, and validation expectations for the 1.x line.

These conventions apply to:

- repository-level Markdown files;
- generated MkDocs documentation under `docs/`;
- reusable documentation snippets;
- generated command and API documentation;
- documentation validation tooling;
- Python comments, docstrings, and prose-oriented string literals where they feed generated
  documentation, CLI output, or developer-facing diagnostics.

They intentionally favor:

- discoverability over strict architectural taxonomy;
- consistency over local stylistic variation;
- explicit structure over clever abstraction;
- stable terminology over synonym drift;
- local clarity over unnecessary reuse;
- small, meaningful snippets over heavy content composition.

This page defines authoring and structure conventions only. It does not redefine public CLI,
machine-readable output, configuration schema, terminology, API, release-process, or compatibility
contracts. Those contracts belong in their dedicated reference pages.

______________________________________________________________________

## Documentation Surfaces

TopMark documentation is split across repository-facing files, generated user documentation,
development documentation, generated reference pages, CI/release documentation, and reusable
snippets.

| Surface                  | Location                                                     | Primary audience             | Role                                                             |
| ------------------------ | ------------------------------------------------------------ | ---------------------------- | ---------------------------------------------------------------- |
| Repository landing pages | `README.md`, `INSTALL.md`, `CONTRIBUTING.md`, `CHANGELOG.md` | GitHub and PyPI readers      | Onboarding, release notes, contribution entry points             |
| User documentation       | `docs/usage/`, `docs/configuration/`                         | CLI users                    | Task-oriented usage, configuration, policies, troubleshooting    |
| CI and validation docs   | `docs/ci/`                                                   | contributors and maintainers | Workflow responsibilities, triggers, validation paths            |
| Development docs         | `docs/dev/`                                                  | contributors and maintainers | Architecture, terminology, conventions, tooling, release process |
| Generated reference      | generated under `docs/api/` and generated reference pages    | API and advanced users       | Discoverable API and registry reference                          |
| Snippets                 | `docs/_snippets/`                                            | documentation maintainers    | Short reusable contract text                                     |

Repository-level documentation may intentionally summarize information that also appears in the
generated documentation site because these files are often read directly on GitHub or PyPI.

Keep repository-level files concise and release-oriented. Link to the generated documentation site
or stable repository documentation for deeper reference material.

______________________________________________________________________

## Page Structure

### Section separators

Level-2 sections should be visually separated with a horizontal rule after the opening page
introduction.

Use:

```markdown
______________________________________________________________________

## Section Title
```

The first level-2 section on a page does not need a preceding separator when it directly follows the
page introduction. Subsequent level-2 sections are validated by `make docs-hygiene` for files where
this convention applies.

This convention keeps long Markdown files easier to scan and gives generated and handwritten pages a
consistent source rhythm.

### Heading style

Headings should be stable, searchable, and anchor-friendly.

Use:

- clear sentence-style or title-style text according to the local page pattern;
- descriptive headings that stand on their own;
- plain text without decorative symbols.

Do not use emoji in headings, page titles, navigation labels, command names, or related-link labels.

### Overview pages

Overview pages should improve discovery rather than repeat an entire navigation tree.

Prefer:

- shallow section structure;
- compact tables;
- short linked lists;
- concise summaries;
- links to canonical details.

Avoid creating many level-3 headings solely to make a command or workflow list scannable when the
sidebar already exposes that hierarchy.

______________________________________________________________________

## Navigation Conventions

Navigation should prioritize discoverability over strict implementation structure.

Navigation labels should:

- use stable wording;
- remain concise;
- avoid implementation jargon;
- avoid redundant prefixes;
- match page titles where practical.

Preferred labels include:

- `Machine-readable output`
- `Exit codes`
- `Registry reference`
- `Documentation pipeline`
- `Terminology and Canonical Vocabulary`
- `Test and validation architecture`

Avoid unnecessary variants such as:

- `Machine Output`
- `JSON Output`
- `Output Formats`
- `Glossary`

Navigation groups may evolve, but conceptual grouping should remain stable once established.

### Sidebar and table-of-contents density

Manage navigation density primarily through page structure rather than global theme configuration.

Avoid setting a restrictive global `toc_depth` unless most pages benefit from the same depth. API
reference pages, generated pages, architecture pages, and long configuration pages may legitimately
need deeper table-of-contents navigation.

Per-page table-of-contents customization should be treated as a post-1.0 consideration unless
repeated rendered-site reviews show a clear need.

### Generated API navigation

Generated API pages should be organized according to API documentation needs rather than forced into
user-facing CLI or configuration navigation.

Generated API internals may remain outside the primary navigation when they are discoverable through
API reference indexes, mkdocstrings output, search, or direct cross-references.

Do not move generated API internals into user-facing navigation only to silence navigation warnings
or make the sidebar appear simpler.

______________________________________________________________________

## Link and Terminology Conventions

Cross-references should use stable, descriptive wording.

Prefer:

```markdown
See [Machine-readable output](../usage/machine-output.md).
```

Avoid:

```markdown
See [here](../usage/machine-output.md).
```

Use the same terminology across page titles, navigation labels, inline references, and related-links
sections. Prefer canonical project terms unless a local distinction is intentional and documented.

Preferred terms include:

- machine-readable output;
- machine-readable formats;
- exit codes;
- shared options;
- command-specific options;
- generated reference;
- configuration discovery;
- file type identifiers;
- canonical identity;
- runtime configuration;
- staged config-loading validation;
- flattened compatibility view;
- public API boundary;
- internal API boundary;
- test and validation architecture.

Avoid synonym drift unless the distinction is meaningful.

### Canonical terminology and explanations

Canonical terminology belongs in [Terminology and Canonical Vocabulary](../terminology.md).

Use that page as the normative reference for stable project-wide terms such as:

- qualified and local identifiers;
- canonical identity;
- applicability;
- runtime overlays;
- machine-readable output;
- public and internal API boundaries;
- stable, frozen, internal, deferred, and post-1.0 scope language.

Major architectural concepts should also have one canonical explanation page. Other documentation
should prefer concise local summaries with cross-references instead of duplicating long-form
explanations.

Examples:

- registry layering and bindings belong in [Registry model](registry-model.md);
- resolution scoring and ambiguity policy belong in [Resolution](resolution.md);
- machine-readable JSON and NDJSON schemas belong in
  [Machine-readable output](../usage/machine-output.md);
- output-format conventions belong in [Machine-readable format conventions](machine-formats.md);
- public/internal API boundaries belong in [API stability and snapshot policy](api-stability.md).

Contextual interpretation should remain local. A page may briefly explain how a canonical concept
applies to its workflow, command, API surface, or validation path without duplicating the canonical
definition itself.

### Frozen terminology

The term "frozen" is used in two distinct contexts throughout the TopMark documentation:

- release and contract stabilization;
- immutable runtime objects or snapshots.

When referring to release stabilization, prefer explicit wording such as:

- "frozen for 1.0";
- "contract frozen for 1.0";
- "stabilized for the 1.x series";
- "part of the stable 1.x compatibility surface".

When referring to runtime mutability, prefer "immutable" in prose unless discussing concrete types
or APIs whose names explicitly use `Frozen`.

When TopMark exposes both mutable and immutable variants of the same runtime object, use the
`MutableX` / `FrozenX` naming pair. Use `MutableX` for construction or editing state and `FrozenX`
for immutable snapshots returned from `freeze()`.

Plain `X` names are preferred for immutable value objects that do not have a mutable counterpart.

### Repository links vs hosted documentation links

Repository-facing files such as `README.md` may link to both repository-native documentation and
hosted documentation.

Use relative links for repository-native contributor or development documents:

```markdown
[Contributing](docs/contributing.md)
[Release process](docs/dev/release-process.md)
```

Use hosted documentation links for user-facing generated documentation, generated API references,
and deep canonical reference pages:

```markdown
[Configuration Guide (hosted docs)](https://topmark.readthedocs.io/en/latest/configuration/discovery/)
```

Explicitly label hosted documentation links with `(hosted docs)` in repository-static files when
that improves orientation.

______________________________________________________________________

## Emoji and Callout Conventions

Emoji usage should be conservative and must not be structural.

Do not use emoji in:

- command reference pages;
- configuration reference pages;
- generated reference pages;
- machine-readable output documentation;
- API reference pages;
- architecture documentation;
- validation or release-policy documentation;
- headings or navigation labels.

Emoji may appear sparingly in README-style landing pages, release announcements, or informal
contributor notes when the surrounding text carries the full meaning without relying on the emoji.

Prefer GitHub-style alerts for semantic emphasis:

```markdown
> [!NOTE]
> Informational note.
```

```markdown
> [!CAUTION]
> Upgrade-impacting compatibility note.
```

Use `[!CAUTION]` for changelog breaking-change summaries. Keep the actual section heading plain and
anchor-friendly:

```markdown
> [!CAUTION] **Breaking changes**
>
> - Short upgrade-impacting summary.

### Breaking Changes - 1.0.0
```

Avoid MkDocs-specific admonition syntax when GitHub and formatter portability are more important
than theme-specific rendering.

______________________________________________________________________

## Changelog Conventions

`CHANGELOG.md` follows a Keep-a-Changelog-inspired structure with additional TopMark-specific
release-note conventions.

Release entries should use only:

- level-2 headings for release entries;
- level-3 headings for Keep-a-Changelog-compatible release sections;
- lists below level-3 headings for detailed grouping.

Do not introduce level-4 or deeper headings inside release entries. Use bold list labels instead:

```markdown
### Fixed - 1.0.0

- **Windows atomic writer failure**
  - Fixed platform-specific permission handling.
  - Preserved POSIX behavior where supported.
```

Release headings should use this shape:

```markdown
\#\# [1.0.0] - 2026-05-11
```

Prerelease headings should use the same shape:

```markdown
\#\# [1.0.0b3] - 2026-05-11
```

Keep-a-Changelog-compatible section headings should use level-3 headings with stable, plain text:

```markdown
### Added - 1.0.0b3
### Changed - 1.0.0b3
### Fixed - 1.0.0b3
### Documentation - 1.0.0b3
### Internal - 1.0.0b3
### Notes - 1.0.0b3
```

Use `### Breaking Changes - <version>` for breaking-change details. Do not use emoji headings such
as `### ⚠️ Breaking Changes`.

When a release has upgrade-impacting changes, add a GitHub-style caution block immediately before
the detailed breaking-change section:

```markdown
> [!CAUTION] **Breaking changes**
>
> - Short upgrade-impacting summary.

### Breaking Changes - 1.0.0
```

The caution block is the visual emphasis. The following level-3 heading remains plain,
anchor-friendly, and compatible with generated navigation.

Changelog entries should:

- keep release summaries concise and factual;
- avoid decorative emoji and informal markers;
- group detailed items with bold list labels instead of nested headings;
- keep the order of sections consistent with nearby release entries;
- document compatibility and migration impact explicitly when behavior changes;
- avoid documenting internal implementation details unless they explain a user-visible release
  consequence or maintainer-facing workflow change.

These conventions are enforced where practical through `tools/docs/check_docs_hygiene.py`.

______________________________________________________________________

## Command Documentation Template

Command documentation should follow a predictable structure. Consistency is more important than
local stylistic preference because command pages define stable user-facing behavior.

Use the following section order whenever applicable:

```text
Summary
Quick start
Input applicability
Configuration and validation
Filtering and file discovery
Command-specific policy options
Behavior details
Output behavior
Machine-readable output
Command-specific options
Exit codes
Typical workflows
Pre-commit integration
Related commands
Related docs
Troubleshooting
```

Sections may be omitted only when genuinely not applicable. Command families may adapt this order
when their behavior differs from file-processing pipeline commands, but related pages should remain
internally consistent.

### User-facing implementation boundaries

Command usage pages should describe observable behavior, stable semantics, compatibility contracts,
and user-facing outcomes. They should avoid implementation details unless those details are part of
the documented public contract.

Avoid exposing implementation details such as:

- internal dataclass names;
- mutable/frozen runtime object pairs;
- `freeze()` / `thaw()` mechanics;
- internal DTO names;
- bridge or helper function names;
- internal runtime object graphs.

For example, prefer user-facing lifecycle wording such as:

- "finalize validated runtime configuration";
- "produce the effective runtime configuration";
- "normalized runtime configuration snapshot".

Avoid wording such as:

- "freeze into final `FrozenConfig`";
- "build a `MutableConfig` draft";
- "call `freeze()` before execution".

Concrete implementation types may be referenced from API, architecture, or internals documentation
when they are part of the page purpose, but command usage pages should generally avoid them.

### Command section expectations

| Section                           | Purpose                                                                                                                                       |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `Summary`                         | Explain what the command does, when to use it, and the key user-facing contract.                                                              |
| `Quick start`                     | Show canonical invocation syntax and short examples matching actual CLI behavior.                                                             |
| `Input applicability`             | Explain paths, stdin support, recursion, mutation behavior, and dry-run vs apply behavior.                                                    |
| `Configuration and validation`    | Explain command-specific configuration behavior using user-facing runtime terminology and link to canonical configuration docs.               |
| `Filtering and file discovery`    | Summarize command-specific filtering and link to the filtering contract.                                                                      |
| `Command-specific policy options` | Document policy controls that affect the command.                                                                                             |
| `Behavior details`                | Explain command-specific runtime behavior not covered elsewhere.                                                                              |
| `Output behavior`                 | Describe human output, verbosity, quiet mode, color, and preview behavior.                                                                    |
| `Machine-readable output`         | Explain supported output formats and command-specific machine-readable output semantics without exposing internal DTO implementation details. |
| `Command-specific options`        | Document options unique to the command without repeating shared-option semantics.                                                             |
| `Exit codes`                      | Explain command-specific exit behavior and link to centralized exit-code docs.                                                                |
| `Typical workflows`               | Present common workflows from simple to advanced.                                                                                             |
| `Pre-commit integration`          | Document hook usage when relevant.                                                                                                            |
| `Related commands`                | Link only to operationally adjacent CLI commands.                                                                                             |
| `Related docs`                    | Link to conceptual, configuration, reference, and architecture pages.                                                                         |
| `Troubleshooting`                 | Document common failure modes and corrective actions.                                                                                         |

Parent command groups such as `topmark config` and `topmark registry` may use a simplified
structure:

```text
Summary
Subcommands
Shared behavior
Related commands
Related docs
```

Commands should always be referenced using the fully qualified CLI form:

```text
`topmark check`
`topmark strip`
`topmark config dump`
```

Avoid shorthand such as `check` or `dump` unless the surrounding context is already unambiguous.

When diagrams are useful, diagram labels should also follow user-facing terminology. Prefer labels
such as "Finalize runtime configuration" or "Emit machine-readable diagnostics" over labels that
name internal implementation classes or helper methods.

______________________________________________________________________

## Workflow Documentation Template

Workflow documentation pages describe GitHub workflows, their trigger model, trust boundary,
validation scope, artifact behavior, and maintenance responsibility.

Workflow pages should be contributor-facing. They should explain when a workflow runs, what it
validates or performs, what trust boundary it enforces, and how maintainers can reproduce or reason
about failures. They should not merely restate YAML structure.

Use the following section order whenever applicable:

```text
Purpose
Trigger conditions
Permissions and trust boundary
Workflow inputs
Jobs and validation scope
Artifact handling
Local reproduction
Maintenance notes
Related pages
```

Sections may be omitted only when genuinely not applicable. Workflows that do not handle artifacts
should still include a short explicit `Artifact handling` section stating that no artifacts are
produced, consumed, or published.

### Workflow section expectations

| Section                          | Purpose                                                                                                          |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| `Purpose`                        | Explain the workflow responsibility, the contract it enforces, and what it does not do.                          |
| `Trigger conditions`             | Explain pull-request, push, tag, scheduled, manual, or workflow-chained initiation.                              |
| `Permissions and trust boundary` | Document permissions, privilege level, repository-code execution, artifact consumption, and publishing behavior. |
| `Workflow inputs`                | Document manual `workflow_dispatch` inputs when present.                                                         |
| `Jobs and validation scope`      | Summarize jobs, tools, matrix behavior, and notable sequencing.                                                  |
| `Artifact handling`              | Explain whether artifacts are produced, consumed, uploaded, downloaded, validated, or published.                 |
| `Local reproduction`             | Provide the closest local nox, make, or repository-tool commands.                                                |
| `Maintenance notes`              | Capture workflow-specific rationale, intentional duplication, and update expectations.                           |
| `Related pages`                  | End with related CI, validation, and contributor links.                                                          |

For workflows with multiple triggers, use a trigger table:

| Trigger             | When it runs                           | Purpose                                |
| ------------------- | -------------------------------------- | -------------------------------------- |
| `pull_request`      | Pull requests affecting selected paths | Validate proposed changes before merge |
| `push`              | Pushes to `main`                       | Validate committed source changes      |
| `push.tags`         | Tags matching `v*`                     | Build release artifacts                |
| `schedule`          | Weekly cron run                        | Detect maintenance drift               |
| `workflow_dispatch` | Manual maintainer run                  | Run the workflow on demand             |

CI workflow pages share the same related-pages block through:

```jinja
\{\% include-markdown "\_snippets/ci/related-pages.md" \%\}
```

This is an intentional exception to the general preference against related-links snippets. The CI
workflow pages form a small, tightly coupled documentation family, and the shared block keeps
navigation stable across related workflow pages.

______________________________________________________________________

## Docstring and Public API Documentation

TopMark treats public docstrings as part of the observable stable 1.x API documentation, especially
for public facades exposed through `topmark.api` and stable registry surfaces.

Public module, class, and function docstrings should:

- use Google-style sections such as `Args:`, `Returns:`, `Raises:`, and `Examples:`;
- use plain Markdown cross-references rather than Sphinx roles;
- remain import-safe and avoid runtime side effects;
- document caller-facing behavior rather than implementation mechanics;
- use `MutableX` / `FrozenX` naming consistently when documenting mutable/immutable runtime pairs;
- keep exception documentation aligned with the public API contract.

### Exception documentation

For public APIs, the `Raises:` section may document exceptions intentionally propagated from
lower-level helpers when those exceptions are part of the supported caller-facing contract at the
current abstraction level.

Accordingly:

- do not add redundant `try` / `except` / `raise` blocks solely to satisfy docstring linting;
- public façade and delegation helpers should prefer accurate `Raises:` documentation over
  artificial re-raise code;
- targeted `pydoclint` suppressions may be used when a public docstring intentionally documents
  propagated exceptions.

Example:

```python
"""Bind an existing processor definition to a registered file type.

Raises:
    UnknownFileTypeError: If `file_type_id` does not resolve.
    ProcessorBindingError: If the processor qualified key is unknown.
"""  # noqa: DOC503 - documents propagated exceptions from delegated registry helpers
```

Use this suppression sparingly and only when all of the following are true:

- the method is a public façade or delegation helper;
- the documented exceptions are part of the supported caller-facing contract;
- the exceptions originate in delegated helpers;
- adding local catch-and-reraise code would make the implementation worse.

This keeps implementations clean while preserving accurate and stable exception documentation for
callers.

### Code prose hygiene

Python comments, docstrings, and prose-oriented string literals should use ASCII punctuation for
terminal safety, copy/paste stability, generated documentation consistency, and predictable CLI
output.

Avoid smart punctuation in code-facing prose, including:

- Unicode dashes and hyphens such as en dash and em dash;
- curly single and double quotes;
- Unicode ellipses.

Use plain ASCII equivalents instead:

- `-` or `--` instead of Unicode dashes;
- `'` instead of curly apostrophes;
- `"` instead of curly double quotes;
- `...` instead of Unicode ellipses.

`tools/docs/check_code_hygiene.py` enforces this rule for Python files under `src/topmark/`,
`tests/`, and `tools/` by scanning tokenized comments and strings.

______________________________________________________________________

## Snippet Conventions

Documentation snippets exist to reduce duplication of stable contract language. They should not be
used merely to reduce ordinary prose repetition or replace links to canonical reference pages.

Use snippets when shared wording represents a stable semantic contract, warning, compatibility note,
or short navigation block that would be risky or noisy to maintain independently across multiple
pages.

Keep prose local when it explains how a contract applies to a specific workflow, command, API
surface, CI path, or troubleshooting scenario. Local context is usually more readable than excessive
content composition.

### Snippet inventory

Reusable snippets live in `docs/_snippets/`.

| Snippet                       | Purpose                                                                                                                          | Status           |
| ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------- | ---------------- |
| `api-internal-overrides.md`   | Explains the API-only internal override boundary for configuration behavior.                                                     | Keep             |
| `config-strictness.md`        | Defines the short reusable staged config-loading strictness contract.                                                            | Keep             |
| `file-type-identifiers.md`    | Defines the short reusable local/qualified file type identifier contract.                                                        | Keep             |
| `option-spelling.md`          | Explains CLI, TOML, and API option spelling conventions.                                                                         | Keep             |
| `output-contract.md`          | Defines shared TEXT, quiet-mode, Markdown, and machine-readable output guarantees for commands that support quiet mode.          | Keep             |
| `output-contract-no-quiet.md` | Defines shared TEXT, Markdown, and machine-readable output guarantees for informational commands that do not support quiet mode. | Keep             |
| `report-scope.md`             | Defines shared report-scope behavior for sibling mutation commands.                                                              | Keep but monitor |
| `terminology.md`              | Defines the shared terminology note that links to the project-wide canonical vocabulary page.                                    | Keep             |
| `ci/related-pages.md`         | Defines the shared related-pages block for CI workflow documentation pages.                                                      | Keep             |

`docs/_snippets/.markdownlint.jsonc` configures Markdown linting for snippet files and is not a
reusable content snippet.

### Appropriate snippet usage

Good snippet candidates include:

- normative contracts reused across several pages;
- canonical short-form semantics whose wording must remain identical;
- shared output guarantees;
- shared strictness or compatibility warnings;
- compact CLI/API/configuration equivalence wording;
- short applicability notes shared by sibling commands;
- exact related-page navigation blocks shared by a small documentation family.

A snippet is usually justified when it is used in three or more pages, or when two closely related
sibling pages share an exact behavioral contract.

Avoid snippets for:

- page summaries;
- page skeletons;
- workflow-specific examples;
- contextual interpretation of canonical concepts;
- command-specific behavior;
- large conceptual sections;
- machine-readable schemas;
- canonical terminology pages themselves;
- page-specific applicability notes;
- operational rationale;
- troubleshooting guidance;
- long reference documentation;
- prose that benefits from local adaptation.

### Snippet structure and links

Snippet names should:

- remain concise;
- describe behavior, not location;
- use kebab-case;
- avoid vague names such as `common.md`, `shared.md`, or `notes.md`.

Snippets should generally be context-independent. They should not assume a specific heading level,
preceding paragraph, or command page. Snippets should avoid headings; if reusable content needs its
own heading, it usually belongs in a canonical reference page with local cross-references.

Snippets must not include other snippets.

### Snippet links

Snippets may contain relative Markdown links when those links are intended to resolve from the
including page. TopMark uses `mkdocs-include-markdown-plugin`; during MkDocs rendering, relative
links inside included snippets are resolved against the including page context. Depth-specific
snippet variants are therefore usually unnecessary.

Shared navigation snippets named `related-pages*.md` are also allowed to contain relative links when
they centralize navigation for a tightly scoped documentation family.

### Include path conventions

Snippet includes use `mkdocs-include-markdown-plugin` and are resolved from `docs/`.

Use docs-root-relative include paths with the underscore escaped for formatter stability:

```text
\{\% include-markdown "\_snippets/config-strictness.md" \%\}
```

Do not rewrite snippet includes to relative paths such as:

```text
\{\% include-markdown "../../_snippets/config-strictness.md" \%\}
```

The escaped underscore is intentional and should be preserved.

______________________________________________________________________

## Generated Documentation Conventions

Generated documentation should:

- clearly identify itself as generated when appropriate;
- remain navigable without understanding the generation pipeline;
- preserve stable URLs whenever possible;
- avoid exposing internal implementation details unnecessarily;
- follow the same structural conventions as manually authored pages.

Generated command and registry reference pages should complement narrative documentation rather than
replace it.

Generated API internals should prefer package-level sidebar navigation over exhaustive flat module
lists. Nested packages and modules should generally remain discoverable through generated package
indexes, breadcrumbs, direct cross-references, and search.

______________________________________________________________________

## Documentation Validation

Documentation validation should prioritize structural consistency, broken-reference detection,
navigation integrity, command synchronization, generated-page verification, and prose hygiene.

Automated validation includes:

- strict MkDocs builds;
- link checking;
- heading consistency checks;
- emoji-in-heading rejection;
- `mkdocs.yml` nav membership checks for files under `docs/`;
- level-2 section-separator validation;
- command-page structure validation;
- snippet include validation;
- generated-page existence validation;
- CLI/help synchronization validation;
- Python code-prose hygiene validation.

`make docs-hygiene` runs deterministic repository-hygiene checks for Markdown and snippets.
`make code-hygiene` runs deterministic prose-hygiene checks for Python comments, docstrings, and
prose-oriented string literals.

The validation fails on objective problems such as:

- broken snippet include paths;
- nested snippet includes;
- malformed docs-root-relative include paths;
- include targets that resolve outside `docs/`;
- accidental macOS `._*` resource files under documentation sources;
- Markdown files under `docs/` missing from `mkdocs.yml` nav;
- emoji in Markdown headings;
- level-2 sections that are not separated by a horizontal rule.

It reports maintainability warnings for:

- orphaned snippets;
- snippets containing headings;
- smart punctuation in Markdown prose;
- relative links inside snippets when they appear incompatible with include-markdown link rewriting;
- snippet include paths that do not use the formatter-stable `\_snippets/` prefix.

Warnings are intentionally non-fatal by default. They document possible maintainability issues
without turning every documentation-governance preference into a release blocker.

Code prose hygiene is intentionally separate from Markdown documentation hygiene. It uses Python
tokenization so it can inspect comments and string/docstring tokens without scanning identifiers,
operators, or ordinary Python syntax.

Human review remains important for onboarding ergonomics, discoverability, wording quality, example
usefulness, and navigation clarity.

______________________________________________________________________

## Documentation Reuse and Duplication

Documentation reuse should remain understandable to contributors and should not make pages harder to
read in source form.

Prefer:

- a small number of meaningful snippets;
- explicit local structure;
- predictable page layout;
- links to canonical reference pages;
- local contextual summaries that explain page-specific applicability;
- concise summaries in repository-facing documents.

Avoid abstraction layers that make pages difficult to follow or review.

Some duplication is intentional and acceptable when it improves discoverability, onboarding, local
readability, or contributor ergonomics.

Acceptable duplication includes:

- onboarding information repeated between `README.md` and generated docs;
- short command summaries repeated across index pages;
- small release or validation summaries in contributor-facing pages;
- repeated navigation-oriented explanations.

Avoid duplicating:

- full command contracts;
- large configuration lifecycle explanations;
- machine-readable schemas;
- canonical terminology definitions;
- repeated terminology cross-reference notes already provided by `_snippets/terminology.md`;
- code-prose hygiene rules already covered by this page and enforced by `check_code_hygiene.py`;
- release architecture details;
- implementation rationale already covered by a canonical development page.

Do not treat every repeated concept as a snippet candidate. Repetition is acceptable when it gives a
page-specific explanation, workflow rationale, troubleshooting advice, or command-specific context.
When in doubt, prefer local clarity over additional snippet abstraction.

______________________________________________________________________

## Stability Expectations

Documentation conventions should evolve incrementally during the stable 1.x line.

However:

- navigation structure should remain relatively stable;
- public terminology should remain stable;
- canonical terminology definitions should remain centralized in `docs/terminology.md`;
- command-page and workflow-page structures should remain stable once standardized;
- generated reference URLs should avoid unnecessary churn;
- snippet semantics should remain stable across consuming pages.

Major documentation reorganizations should be avoided during stable releases unless they provide
substantial discoverability or maintainability benefits. Prefer small, reviewable changes that keep
the documentation tree understandable in both rendered and source form.

______________________________________________________________________

## Related pages

- [Documentation pipeline and reference hygiene](documentation-pipeline.md)
- [Terminology and Canonical Vocabulary](../terminology.md)
- [API stability and snapshot policy](api-stability.md)
- [Machine-readable output](../usage/machine-output.md)
- [Configuration schema](configuration-schema.md)
- [Release process](release-process.md)
- [Test and validation architecture](../ci/test-validation.md)
- [Contributing](../contributing.md)
