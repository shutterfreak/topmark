<!--
topmark:header:start

  file         : index.md
  file_relpath : docs/index.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# TopMark

TopMark inspects and manages per-file headers (project/license/copyright).

- Comment-aware header insertion
- Shebang handling
- Selective removal
- Preserves original newline style (LF/CRLF/CR) and BOM
- Idempotent updates (re-running does not change already-correct files)
- CLI (Click) with `check`, `dump-config`, `show-defaults`, `init-config`, `filetypes`, `version`

## Quickstart

```bash
pip install topmark
topmark -v --summary --config topmark.toml src/*.py
```

## 📐 Header placement rules

TopMark is comment-aware and places the header block according to the file type and its policy.

### Pound-style files (e.g., Python, Shell, Ruby, Makefile, YAML, TOML, Dockerfile)

Rules:

- If a **shebang** is present (e.g., `#!/usr/bin/env python3`), place the header **after** the
  shebang and ensure **exactly one** blank line in-between.
- If a **coding/encoding line** follows the shebang (PEP 263 style), place the header **after**
  shebang **and** encoding line.
- Otherwise, place the header **at the top of the file**.
- Ensure **one trailing blank line** after the header block when the next line is not already blank.

Example (Python):

```py
#!/usr/bin/env python3

# topmark:header:start
#
#   file         : cli.py
#   file_relpath : src/topmark/cli.py
#
# topmark:header:end

print("hello")
```

### XML-style files (XML, HTML/XHTML, SVG, Vue/Svelte/Markdown via HTML comments)

Rules:

- If present, place the header **after the XML declaration** and **DOCTYPE**, with **one blank
  line** before the header block.
- Otherwise, place the header **at the top of the file**.
- The header uses the file’s native comment syntax; for XML/HTML it’s a comment block wrapper:

```html
<!--
topmark:header:start

  file         : index.html
  file_relpath : docs/index.html

topmark:header:end
-->

<html>...</html>
```

### General guarantees

- **Newline preservation:** The inserted header uses the same newline style as the file
  (LF/CRLF/CR).
- **BOM preservation:** If a UTF‑8 BOM is present, it is preserved.
- **Idempotency:** Re-running TopMark on a file with a correct header makes **no changes**.

## 🧩 Supported file types

| Processor            | File types (examples)                                                                                          |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| PoundHeaderProcessor | dockerfile, env, git-meta, ini, julia, makefile, perl, python, python-requirements, r, ruby, shell, toml, yaml |
| SlashHeaderProcessor | c, cpp, cs, go, java, javascript, kotlin, rust, swift, typescript, vscode-jsonc                                |
| XmlHeaderProcessor   | html, markdown, svelte, svg, vue, xhtml, xml, xsl, xslt, yaml                                                  |

For a complete list, please run:

```sh
topmark filetypes
```

### How TopMark resolves file types (specificity & safety)

TopMark may have multiple `FileType` definitions that **match** a given path. The resolver now:

- evaluates **all** matching file types and scores them by **specificity**,
- prefers **explicit filenames / tail subpaths** (e.g., `.vscode/settings.json`) over patterns, and
  **patterns** over simple **extensions**,
- breaks ties in favor of **headerable** types (those without `skip_processing=True`).

**Tail subpath matching.** `FileType.filenames` entries that contain a path separator (e.g.,
`".vscode/settings.json"`) are matched as **path suffixes** against `path.as_posix()`; plain names
still match the **basename** only.

**JSON vs JSONC.** Generic `json` is recognized but marked `skip_processing=True` (no comments in
strict JSON), while `vscode-jsonc` is a safe, **narrow** opt‑in that uses `//` headers. If you need
more JSON-with-comments files, add them via a dedicated `FileType` or an explicit allow‑list in
config.

**Shebang‑aware insertion.** The default insertion logic is policy‑driven and shebang‑aware (insert
after `#!` and optional encoding line). For formats like XML that need character‑precise placement,
processors provide a text‑offset path; `XmlHeaderProcessor` uses this and signals **no line
anchor**.

## Configuration

```toml
[fields]
project = "TopMark"
license = "MIT"

[header]
fields = ["file", "file_relpath", "project", "license"]

[formatting]
align_fields = true

[files]
file_types = ["python", "markdown", "env"]
relative_to = "."
```

### Notes

- `formatting.align_fields = true` vertically aligns the field names within the rendered header
  lines for readability.
- File-type specific behavior (shebang handling, XML prolog, blank line policies) is driven by
  internal **FileTypeHeaderPolicy** defaults and can be extended to new types.
