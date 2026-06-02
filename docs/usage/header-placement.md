<!--
topmark:header:start

  project      : TopMark
  file         : header-placement.md
  file_relpath : docs/usage/header-placement.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Header placement rules

TopMark is comment-aware and places header blocks according to resolved file type identities and
header-processor semantics.

Different file types use different comment syntaxes and placement rules. TopMark preserves those
conventions while keeping insertion and update behavior deterministic.

Configuration-loading strictness (for example through `--strict` or `strict`) does not affect
header-placement semantics. It controls only whether a run proceeds when staged
configuration-loading validation warnings are present.

Header placement rules apply only after a file has passed runtime applicability evaluation and
runtime processor resolution. File-type-specific runtime policy overrides configured through
`policy_by_type` may influence runtime mutation eligibility and insertion behavior, but the selected
header processor controls the concrete comment syntax and placement behavior.

{% include-markdown "\_snippets/terminology.md" %}

{% include-markdown "\_snippets/path-serialization-contract.md" %}

> [!NOTE]
>
> File type identities are bound to header processors, and each processor defines how headers are
> detected, inserted, updated, and stripped for the file types bound to it. The generated registry
> pages list the file types, processors, and bindings supported by TopMark %%TOPMARK_VERSION%%:
>
> - [Supported file types](./generated/filetypes.md)
> - [Registered processors](./generated/processors.md)
> - [Registered bindings](./generated/bindings.md)

______________________________________________________________________

## Runtime placement model

TopMark intentionally separates:

1. runtime file discovery
1. runtime applicability evaluation
1. runtime file-type probing
1. runtime processor resolution
1. runtime policy evaluation
1. runtime mutation planning
1. concrete header rendering and placement

Header placement semantics are determined by the selected header processor after runtime probing,
policy evaluation, and processor resolution have completed.

This layered runtime model keeps placement behavior deterministic while preserving stable
processor-specific comment syntax and insertion semantics.

______________________________________________________________________

## Pound-style files

The `topmark:pound` processor is used for pound-prefixed line-comment formats such as Python, Python
stub files, shell scripts, Ruby, Perl, R, Julia, Makefile, Dockerfile, TOML, YAML, INI-style
configuration files, environment files, Git metadata files, and Python requirements/constraints
files.

Rules:

- If a shebang is present (e.g., `#!/usr/bin/env python3`), place the header after the shebang and
  ensure exactly one blank line between them.
- If a coding/encoding line follows the shebang (PEP 263 style), place the header after both the
  shebang and encoding line.
- Otherwise, place the header at the top of the file.
- Ensure one trailing blank line after the header block when the next line is not already blank.

Example (Python / shell-style line comments):

```bash
#!/bin/bash

# topmark:header:start
#
#   project      : ACME Project
#   file         : script.sh
#   file_relpath : tools/script.sh
#   license      : BSD
#   copyright    : (C) 2025 John Doe
#
# topmark:header:end

echo "Hello, World!"
```

Note that header path fields such as `file_relpath` use POSIX `/` separators on all platforms.

______________________________________________________________________

## Slash-style files

The `topmark:slash` processor is used for C-style line-comment formats such as C, C++, C#, Go, Java,
JavaScript, TypeScript, Kotlin, Rust, Swift, JSONC, and VS Code JSONC.

Rules:

- Place the header at the top of the file.
- Use `//` as the line prefix.
- Ensure one trailing blank line after the header block when the next line is not already blank.

Example (JavaScript / slash-style line comments):

```javascript
// topmark:header:start
//
//   project      : ACME Project
//   file         : app.js
//   file_relpath : frontend/app.js
//   license      : GPLv3
//   copyright    : (C) 2025 John Doe
//
// topmark:header:end

console.log("Hello, World!");
```

______________________________________________________________________

## C-style block-comment files

The `topmark:cblock` processor is used for C-like block-comment formats such as CSS, SCSS, Less,
Stylus, Solidity, and SQL.

Rules:

- Place the header at the top of the file.
- Wrap the header in `/* ... */`.
- Prefix header content lines with `*`.
- Ensure one trailing blank line after the header block when the next line is not already blank.

Example (CSS):

```css
/*
 * topmark:header:start
 *
 *   project      : ACME Project
 *   file         : styles.css
 *   file_relpath : styles/admin/styles.css
 *   license      : MIT
 *   copyright    : (C) 2025 John Doe
 *
 * topmark:header:end
 */

body {
  margin: 0;
}
```

______________________________________________________________________

## XML-style files

The `topmark:xml` processor is used for XML/HTML-style block-comment formats such as XML, XHTML,
HTML, SVG, XSL, XSLT, Vue, and Svelte.

Rules:

- If present, place the header after the XML declaration and DOCTYPE, with one blank line before the
  header block.
- Otherwise, place the header at the top of the file.
- The header uses the file's native comment syntax; for XML/HTML this is an XML-style block comment
  wrapper.

Example (XML):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!--
topmark:header:start

  project      : ACME Project
  file         : config.xml
  file_relpath : settings/web/config.xml
  license      : BSD
  copyright    : (C) 2025 John Doe

topmark:header:end
-->

<configuration>
  <!-- XML content here -->
</configuration>
```

Header metadata path fields are serialized with POSIX `/` separators regardless of the host
operating system.

______________________________________________________________________

## Markdown files

The `topmark:markdown` processor is used for Markdown files. It uses HTML comments like the
`topmark:xml` processor, but handles Markdown as a line-oriented documentation format.

Rules:

- Place the header at the top of the file.
- Use an HTML comment block wrapper.
- Ensure one trailing blank line after the header block when the next line is not already blank.

Example (Markdown):

```markdown
<!--
topmark:header:start

  project      : ACME Project
  file         : README.md
  file_relpath : README.md
  license      : MIT
  copyright    : (C) 2025 John Doe

topmark:header:end
-->

# Project notes
```

______________________________________________________________________

## Placement guarantees

- Path serialization: generated header path fields (`file_relpath`, `file_abspath`, `relpath`, and
  `abspath`) use POSIX `/` separators on all platforms.
- Newline preservation: the inserted header uses the same newline style as the file (LF/CRLF/CR).
- BOM preservation: if a UTF-8 BOM is present, it is preserved.
- Idempotency: re-running TopMark on a file with a compliant header produces no runtime changes.
- Unheaderable file types: some recognized file type identities intentionally have no effective
  processor binding and are skipped rather than headered, such as JSON files without comments,
  license text files, and single-token marker files.

______________________________________________________________________

## See also

- [Supported file types](./generated/filetypes.md)
- [Registered processors](./generated/processors.md)
- [Registered bindings](./generated/bindings.md)
- [`Policies`](./policies.md)
- [`Configuration overview`](../configuration/index.md)
- [`Architecture`](../dev/architecture.md)
