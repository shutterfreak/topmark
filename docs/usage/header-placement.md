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

TopMark is comment-aware and places header blocks according to file type and processor semantics.

Configuration-validation strictness (for example through `--strict` or `strict`) does not affect
header-placement semantics. It controls only whether a run proceeds when configuration-validation
warnings are present.

Header placement rules apply only after a file has passed applicability evaluation and processor
resolution. File-type-specific policy overrides configured through `policy_by_type` may influence
runtime mutation eligibility and insertion behavior, but the selected header processor controls the
concrete comment syntax and placement behavior.

{% include-markdown "\_snippets/terminology.md" %}

> [!NOTE]
>
> File types are bound to header processors, and each processor defines how headers are detected,
> inserted, updated, and stripped for the file types bound to it. The generated registry pages list
> the file types, processors, and bindings supported by TopMark %%TOPMARK_VERSION%%:
>
> - [Supported file types](./generated/filetypes.md)
> - [Registered processors](./generated/processors.md)
> - [Registered bindings](./generated/bindings.md)

## Pound-style files

The `topmark:pound` processor is used for pound-prefixed line-comment formats such as Python, Python
stub files, shell scripts, Ruby, Perl, R, Julia, Makefile, Dockerfile, TOML, YAML, INI-style
configuration files, environment files, Git metadata files, and Python dependency/constraints files.

Rules:

- If a shebang is present (e.g., `#!/usr/bin/env python3`), place the header after the shebang and
  ensure exactly one blank line between them.
- If a coding/encoding line follows the shebang (PEP 263 style), place the header after both the
  shebang and encoding line.
- Otherwise, place the header at the top of the file.
- Ensure one trailing blank line after the header block when the next line is not already blank.

Example (Python):

```py
#!/usr/bin/env python3

# topmark:header:start
#
#   file         :
#   file_relpath :
#
# topmark:header:end

print("hello")
```

______________________________________________________________________

## Slash-style files

The `topmark:slash` processor is used for C-style line-comment formats such as C, C++, C#, Go, Java,
JavaScript, TypeScript, Kotlin, Rust, Swift, JSONC, and VS Code JSONC.

Rules:

- Place the header at the top of the file.
- Use `//` as the line prefix.
- Ensure one trailing blank line after the header block when the next line is not already blank.

Example (JavaScript):

```js
// topmark:header:start
//
//   file         :
//   file_relpath :
//
// topmark:header:end

console.log("hello");
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
 *   file         :
 *   file_relpath :
 *
 * topmark:header:end
 */

body {
  color: black;
}
```

______________________________________________________________________

## XML-style files

The `topmark:xml` processor is used for HTML/XML-style block-comment formats such as XML, XHTML,
HTML, SVG, XSL, XSLT, Vue, and Svelte.

Rules:

- If present, place the header after the XML declaration and DOCTYPE, with one blank line before the
  header block.
- Otherwise, place the header at the top of the file.
- The header uses the file's native comment syntax; for XML/HTML this is a block comment wrapper:

```html
<!--
topmark:header:start

  file         :
  file_relpath :

topmark:header:end
-->

<html>...</html>
```

______________________________________________________________________

## Markdown files

The `topmark:markdown` processor is used for Markdown files. It uses HTML comments like the XML
processor, but handles Markdown as a line-oriented documentation format.

Rules:

- Place the header at the top of the file.
- Use an HTML comment block wrapper.
- Ensure one trailing blank line after the header block when the next line is not already blank.

Example (Markdown):

```md
<!--
topmark:header:start

  file         :
  file_relpath :

topmark:header:end
-->

# Project notes
```

______________________________________________________________________

## Placement guarantees

- Newline preservation: the inserted header uses the same newline style as the file (LF/CRLF/CR).
- BOM preservation: if a UTF-8 BOM is present, it is preserved.
- Idempotency: re-running TopMark on a file with a correct header produces no changes.
- Unheaderable file types: some recognized file types intentionally have no effective processor
  binding and are skipped rather than headered, such as JSON files without comments, license text
  files, and single-token marker files.

______________________________________________________________________

## See also

- [Supported file types](./generated/filetypes.md)
- [Registered processors](./generated/processors.md)
- [Registered bindings](./generated/bindings.md)
- [`Policies`](./policies.md)
- [`Configuration overview`](../configuration/index.md)
- [`Architecture`](../dev/architecture.md)
