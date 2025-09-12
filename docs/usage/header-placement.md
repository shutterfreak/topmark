<!--
topmark:header:start

  project      : TopMark
  file         : header-placement.md
  file_relpath : docs/usage/header-placement.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Header Placement Rules

TopMark is comment‑aware and places the header block according to the file type and its policy.

## Pound‑style files (e.g., Python, Shell, Ruby, Makefile, YAML, TOML, Dockerfile)

Rules:

- If a **shebang** is present (e.g., `#!/usr/bin/env python3`), place the header **after** the
  shebang and ensure **exactly one** blank line in‑between.
- If a **coding/encoding line** follows the shebang (PEP 263 style), place the header **after**
  shebang **and** encoding line.
- Otherwise, place the header **at the top of the file**.
- Ensure **one trailing blank line** after the header block when the next line is not already blank.

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

## XML‑style files (XML, HTML/XHTML, SVG, Vue/Svelte/Markdown via HTML comments)

Rules:

- If present, place the header **after the XML declaration** and **DOCTYPE**, with **one blank
  line** before the header block.
- Otherwise, place the header **at the top of the file**.
- The header uses the file’s native comment syntax; for XML/HTML it’s a comment block wrapper:

```html
<!--
topmark:header:start

  file         :
  file_relpath :

topmark:header:end
-->

<html>...</html>
```

## General guarantees

- **Newline preservation:** The inserted header uses the same newline style as the file
  (LF/CRLF/CR).
- **BOM preservation:** If a UTF‑8 BOM is present, it is preserved.
- **Idempotency:** Re‑running TopMark on a file with a correct header makes **no changes**.
