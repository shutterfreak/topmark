<!--
topmark:header:start

  project      : TopMark
  file         : documentation-conventions.md
  file_relpath : docs/dev/documentation-conventions.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Documentation Conventions

This document defines the documentation structure, terminology, and authoring conventions used
throughout the TopMark documentation system.

The goal is to preserve:

- documentation discoverability
- structural consistency
- terminology consistency
- predictable navigation
- maintainable documentation reuse
- alignment between CLI behavior and documentation behavior

These conventions intentionally favor:

- consistency over novelty
- maintainability over abstraction
- predictable page structure over stylistic variation
- explicitness over cleverness

This document applies to:

- repository-level documentation
- generated MkDocs documentation
- reusable documentation snippets
- generated command documentation
- documentation validation tooling

It does not redefine:

- public CLI contracts
- machine-readable contracts
- configuration schema contracts
- API architecture

## Documentation Structure

TopMark documentation is organized into four primary layers.

### Repository-Level Documentation

Repository-level documentation acts as the primary onboarding and contribution surface.

These documents are intentionally duplicated in some areas from the generated site because they are
commonly consumed directly from GitHub.

Primary repository-level documents:

- `README.md`
- `INSTALL.md`
- `CONTRIBUTING.md`
- `CHANGELOG.md`

Repository-level documentation should:

- remain concise and discoverable
- prioritize onboarding and contributor ergonomics
- link to the generated documentation site for deeper reference material
- avoid becoming a full replacement for the generated documentation site

### Generated Documentation Site

The generated documentation site under `docs/` is the canonical documentation surface.

The generated site is organized around:

- user workflows
- command reference documentation
- configuration documentation
- output and contract documentation
- development and architecture documentation
- generated reference material

### User Documentation

User documentation should focus on:

- task-oriented workflows
- command usage
- configuration behavior
- output behavior
- examples
- troubleshooting

User documentation should avoid implementation details unless they directly affect user-facing
behavior.

### Development Documentation

Development documentation should focus on:

- architecture
- generation pipelines
- tooling
- internal conventions
- contributor workflows
- implementation rationale

Development documentation should not duplicate end-user command documentation unless necessary for
implementation context.

## Navigation Conventions

Navigation should prioritize discoverability over strict architectural separation.

Navigation groups should remain stable over time.

Recommended top-level grouping:

- Usage
- Configuration
- Reference
- Development

The exact top-level grouping may evolve over time, but conceptual separation should remain stable
once navigation patterns are established.

Navigation labels should:

- use title case
- remain concise
- avoid implementation jargon
- avoid redundant prefixes

Examples:

- `Machine-readable output`
- `Exit codes`
- `Registry reference`
- `Documentation pipeline`

Avoid inconsistent variants such as:

- `Machine Output`
- `JSON Output`
- `Output Formats`

### Sidebar and Table-of-Contents Density

Navigation and table-of-contents density should be managed primarily through page structure rather
than global theme configuration.

TopMark should avoid setting a restrictive global `toc_depth` unless the majority of pages benefit
from the same depth. API reference pages, generated reference pages, architecture pages, and long
configuration pages may legitimately need deeper table-of-contents navigation.

Overview pages should avoid deep heading hierarchies when the sidebar already provides equivalent
navigation.

Prefer:

- shallow overview pages
- tables for command maps
- short linked lists for related commands
- bold lead-in labels for compact summaries
- sidebar navigation for command-family browsing

over repeating the full command hierarchy in both the sidebar and the page table of contents.

Avoid creating `h3` or deeper headings solely to make repeated command summaries scannable. If a
page already has command navigation in the sidebar, prefer a table or definition-style list for
command summaries.

Per-page table-of-contents customization should not be introduced unless repeated rendered-site
reviews show a clear need. Theme overrides for per-page TOC behavior add documentation tooling
complexity and should be treated as a post-1.0 consideration.

### Command Grouping Semantics

Command-related documentation should be grouped by user-facing purpose rather than implementation
source or generation mechanism.

Use the following navigation semantics:

- `Command overview` introduces CLI structure, common workflows, and command discovery.
- `Commands` contains primary command and subcommand reference pages.
- `Guides` contains task-oriented usage documentation.
- `Registry reference` contains generated registry and discovery reference pages.
- `Shared options` contains cross-cutting CLI option behavior.
- `Exit codes` contains cross-cutting command result semantics.

Cross-cutting operational topics that apply to multiple commands should generally live outside
individual command pages.

Do not place generated registry pages directly inside `Commands`.

Do not place task-oriented guides inside `Commands`.

Do not place command-specific behavior only in generated reference pages.

Generated reference pages should complement command documentation rather than replace narrative
command guidance.

### API and Reference Grouping

API documentation should remain a distinct navigation area while the generated API reference is
intentionally separated from user-facing CLI, configuration, and registry reference pages.

A broader `Reference` navigation group may be introduced later if TopMark grows enough distinct
reference surfaces to justify it, for example:

- CLI reference
- configuration reference
- registry reference
- public API reference

Do not move generated API internals into user-facing reference navigation only to make the top-level
navigation appear simpler or to reduce generated-page navigation warnings.

Generated API pages should be organized according to API documentation needs. User-facing reference
pages should be organized according to discoverability and task-oriented documentation needs.

Generated API internals may remain outside the primary navigation when they are discoverable through
API reference indexes, mkdocstrings output, or direct cross-references.

## Command Documentation Conventions

Command documentation should follow a predictable structure.

Consistency is more important than local stylistic preferences.

### Standard Command Page Structure

Command pages should use the following section order whenever applicable:

```text
Summary
Usage
Quick examples
Input applicability
Shared options
Command-specific options
Output behavior
Machine-readable output
Exit codes
Related commands
Related docs
```

Sections may be omitted only when genuinely not applicable.

### Standard Command Section Expectations

The following guidance defines the expected purpose of each standard command-page section.

#### Summary

The `Summary` section should:

- explain what the command does
- explain when the command should be used
- remain concise
- avoid implementation details

The summary should typically consist of one to three short paragraphs.

Command overview or index pages may use tables or compact linked lists instead of deep heading
hierarchies when summarizing many commands.

#### Usage

The `Usage` section should:

- show canonical invocation syntax
- prioritize readability over exhaustiveness
- match actual CLI behavior exactly

Usage examples should prefer:

```text
topmark check [OPTIONS] PATH...
```

over excessively expanded shell examples.

#### Quick Examples

The `Quick examples` section should:

- present the most common workflows first
- remain concise and copy-pasteable
- prefer realistic repository-oriented examples
- avoid excessive explanatory prose

Examples should generally progress from:

- simplest
- most common
- advanced

#### Input Applicability

The `Input applicability` section should explain:

- whether the command accepts paths
- whether stdin is supported
- whether recursive traversal occurs
- whether the command mutates files
- dry-run vs apply behavior

This section exists to reduce ambiguity around operational behavior.

#### Shared Options

The `Shared options` section should:

- avoid duplicating the full global-options reference
- summarize only behavior relevant to the command
- link to shared option documentation where appropriate

Shared option semantics should preferably be maintained through reusable snippets.

#### Command-Specific Options

The `Command-specific options` section should:

- document options unique to the command
- group related options together
- preserve CLI naming consistency
- avoid re-explaining globally documented semantics

Option descriptions should remain behavior-focused rather than implementation-focused.

#### Output Behavior

The `Output behavior` section should describe:

- default human-readable behavior
- verbosity behavior
- quiet-mode behavior
- color/output formatting behavior
- dry-run preview behavior

This section should focus on observable user-facing behavior.

#### Machine-Readable Output

The `Machine-readable output` section should:

- explain supported output formats
- link to machine-readable output contracts
- explain command-specific output semantics when necessary
- avoid duplicating centralized contract documentation

Stable guarantees should preferably be maintained through reusable snippets.

#### Exit Codes

The `Exit codes` section should:

- explain command-specific exit behavior
- link to centralized exit-code documentation
- avoid duplicating generic exit-code semantics unnecessarily

#### Related Commands

The `Related commands` section should:

- include only CLI commands
- prioritize operationally adjacent commands
- remain concise
- prefer fully qualified command references

Example:

```md
- [`topmark strip`](strip.md)
- [`topmark probe`](probe.md)
```

#### Related Docs

The `Related docs` section should:

- reference conceptual documentation
- reference configuration documentation
- reference generated reference pages
- reference architecture documentation only when directly relevant

Avoid using `Related docs` as a generic dumping ground for loosely related pages.

### Parent Command Groups

Parent command groups such as:

- `topmark config`
- `topmark registry`

may use a simplified structure:

```text
Summary
Subcommands
Shared behavior
Related commands
Related docs
```

### Command Naming Conventions

Commands should always be referenced using fully qualified CLI form:

```text
`topmark check`
`topmark strip`
`topmark config dump`
```

Avoid inconsistent shorthand references such as:

```text
`check`
`dump`
```

unless the surrounding context is already unambiguous.

### Usage Examples

Examples should:

- prefer realistic repository-style paths
- prefer dry-run-safe examples
- show the most common workflows first
- remain concise and copy-pasteable

Avoid:

- excessively synthetic examples
- unnecessarily verbose shell sessions
- examples that depend on undocumented setup

Examples should remain stable across platforms whenever reasonably possible.

Prefer portable shell syntax and avoid examples that depend heavily on shell-specific behavior
unless the shell dependency is directly relevant.

When examples are collected on overview pages, prefer compact grouping over creating a separate
heading for every command if the sidebar already exposes the command hierarchy.

### Related Sections

Command pages should consistently include:

- `Related commands`
- `Related docs`

`Related commands` should reference only CLI commands.

`Related docs` should reference:

- conceptual documentation
- configuration documentation
- reference pages
- architecture pages

Avoid mixing commands and conceptual pages within the same related-links section.

Related sections should generally appear near the end of the page after operational and behavioral
reference material.

## Emoji Usage Conventions

Emoji usage should be conservative and consistent.

TopMark documentation is primarily technical reference documentation for a CLI tool. Emoji should
not be used as general decoration or as a substitute for clear headings, labels, or prose.

Mature CLI documentation ecosystems generally keep command references, configuration references, and
API references visually plain. Emoji may appear occasionally in README-style introductions, feature
callouts, or project branding, but not as a structural requirement.

### Default Rule

Do not use emoji in:

- command reference pages
- configuration reference pages
- generated reference pages
- machine-readable output documentation
- API reference pages
- architecture documentation
- validation or release-policy documentation

These pages should remain plain, searchable, accessible, and easy to copy from.

### Allowed Uses

Emoji may be used sparingly in:

- README-style landing pages
- short onboarding sections
- high-level feature summaries
- release announcements
- informal contributor notes

Emoji should only be used when it improves scanning or tone without reducing clarity.

### Accessibility and Meaning

Emoji must not be the only way information is conveyed.

Prefer GitHub-style alerts or other formatter-stable structured callouts:

```md
> [!WARNING]
> Beta behavior
```

over:

```md
⚠️ Beta behavior
```

If an emoji is used, the surrounding text must carry the full meaning without relying on the emoji.

### Heading and Navigation Policy

Do not use emoji in:

- page titles
- navigation labels
- command names
- section headings in reference documentation
- related-link labels

This keeps navigation stable, searchable, and visually consistent.

### Consistency Rule

If a page uses emoji, it should do so according to a local pattern.

Avoid mixing emoji-heavy and emoji-free sections on the same page without a clear reason.

Do not add emoji to one command page unless the same pattern is intentionally applied to all
equivalent command pages.

### Preferred Alternatives

Prefer GitHub-style alerts and structured headings for semantic emphasis.

Examples:

- `> [!NOTE]`
- `> [!TIP]`
- `> [!WARNING]`
- `> [!IMPORTANT]`

MkDocs-specific admonition syntax should be avoided when it conflicts with formatter stability,
Markdown portability, or contributor ergonomics.

These are more accessible, theme-consistent, and easier to validate than ad-hoc emoji markers.

## Cross-Reference Conventions

Cross-references should use stable, descriptive wording.

### Internal Link Labels

Prefer descriptive labels over vague references.

Prefer:

```md
See [Machine-readable output](../output/machine-readable.md).
```

Avoid:

```md
See [here](../output/machine-readable.md).
```

### Terminology Consistency

The same concept should not be referenced using multiple labels unless there is a meaningful
distinction.

Preferred terminology:

- machine-readable output
- exit codes
- shared options
- command-specific options
- generated reference
- configuration discovery
- file type identifiers

Avoid unnecessary synonym drift.

### Breadcrumb Consistency

Pages within the same conceptual area should use consistent headings and labels.

Examples:

- `Machine-readable output`
- `Exit codes`
- `Shared options`

should use the same wording in:

- navigation labels
- page titles
- inline references
- related-doc sections

## Snippet Conventions

Documentation snippets exist to reduce duplication of stable contract language.

Snippets should not be used merely to reduce prose repetition.

### Snippet Inventory Philosophy

The snippet system should remain intentionally small and understandable.

Snippets are intended to centralize:

- stable behavioral guarantees
- shared CLI semantics
- repeated contract language
- repeated operational caveats

The snippet inventory should not evolve into a generalized content-composition system.

Contributors should be able to understand page structure without navigating through excessive
include indirection.

### Appropriate Snippet Usage

Good snippet candidates include:

- shared option semantics
- machine-readable output guarantees
- exit-code semantics
- configuration discovery rules
- applicability behavior
- shared warnings or notes

Recommended reusable snippet categories include:

- shared global-option behavior
- machine-readable output guarantees
- exit-code semantics
- configuration discovery behavior
- path applicability behavior
- stdin applicability behavior
- dry-run vs apply semantics
- output-format guarantees
- recurring warnings or compatibility notes

### Inappropriate Snippet Usage

Avoid creating snippets for:

- page summaries
- contextual explanations
- workflow-specific examples
- prose that benefits from local adaptation

### Snippet Naming

Snippet names should:

- remain concise
- describe behavior, not location
- use kebab-case

Examples:

```text
shared-options.md
machine-readable-output.md
config-discovery.md
exit-code-semantics.md
```

Snippet names should describe reusable behavior rather than the command or page where the snippet is
currently used.

Avoid vague names such as:

```text
common.md
shared.md
notes.md
```

### Snippet Granularity

Prefer medium-granularity snippets.

Very small snippets increase indirection and reduce maintainability.

Very large snippets reduce local readability and flexibility.

### Preferred Snippet Inventory

The following snippet inventory categories are considered appropriate for TopMark.

This inventory is intentionally conservative.

#### Shared CLI Behavior

Examples:

```text
shared-options.md
verbosity-behavior.md
dry-run-vs-apply.md
```

#### Output and Contract Semantics

Examples:

```text
machine-readable-output.md
output-format-guarantees.md
exit-code-semantics.md
```

#### Applicability Semantics

Examples:

```text
path-input-applicability.md
stdin-applicability.md
recursive-traversal.md
```

#### Configuration Semantics

Examples:

```text
config-discovery.md
config-strictness.md
file-type-identifiers.md
```

#### Shared Warnings and Compatibility Notes

Examples:

```text
compatibility-warning.md
experimental-feature-warning.md
```

The snippet inventory should remain focused on stable reusable semantics rather than general prose
reuse.

## Generated Documentation Conventions

Generated documentation should:

- clearly identify itself as generated when appropriate
- remain navigable without understanding the generation pipeline
- preserve stable URLs whenever possible
- avoid exposing internal implementation details unnecessarily

Generated pages should follow the same structural conventions as manually authored pages.

## Documentation Validation

Documentation validation should prioritize:

- structural consistency
- broken-reference detection
- navigation integrity
- command synchronization
- generated-page verification

### Automated Validation

Appropriate automated validation includes:

- strict MkDocs builds
- link checking
- heading consistency checks
- command-page structure validation
- snippet include validation
- generated-page existence validation
- CLI/help synchronization validation

### Human Review

Human review remains important for:

- onboarding ergonomics
- discoverability
- wording quality
- example usefulness
- navigation clarity

Not all documentation quality concerns should be automated.

## Snippet Maintenance Expectations

Reusable snippets should be treated as semi-public documentation infrastructure.

Changes to heavily reused snippets may affect:

- command documentation consistency
- generated-site consistency
- wording consistency
- validation expectations
- screenshot or example stability

### Updating Shared Snippets

When modifying shared snippets:

- review all include locations
- verify wording still matches all consuming pages
- avoid introducing page-specific assumptions
- avoid expanding snippets beyond their original scope

### Snippet Discoverability

The snippet directory should remain navigable to contributors.

Avoid:

- deeply nested snippet hierarchies
- excessive fragmentation
- cryptic snippet names
- multiple snippets differing only slightly in wording

### Snippet Validation

Documentation tooling should eventually validate:

- broken snippet includes
- orphaned snippets
- malformed include paths
- duplicate snippet semantics

However, human review remains important to ensure snippet extraction does not reduce local
readability.

## Documentation Reuse Philosophy

Documentation reuse should remain understandable to contributors.

Avoid introducing abstraction layers that make pages difficult to follow.

Prefer:

- a small number of meaningful snippets
- explicit local structure
- predictable page layout

over heavily fragmented documentation composition.

## Accepted Duplication

Some duplication is intentional and acceptable.

Examples include:

- onboarding information repeated between `README.md` and generated docs
- short command summaries repeated across index pages
- repeated navigation-oriented explanations

Duplication is acceptable when it improves:

- discoverability
- onboarding
- local readability
- contributor ergonomics

## Stability Expectations

Documentation conventions are expected to evolve incrementally.

However:

- navigation structure should remain relatively stable
- public terminology should remain stable
- command-page structure should remain stable once standardized
- generated reference URLs should avoid unnecessary churn

Major documentation reorganizations should be avoided unless they provide substantial
discoverability or maintainability benefits.
