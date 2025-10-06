<!--
topmark:header:start

  project      : TopMark
  file         : filetypes.md
  file_relpath : docs/usage/filetypes.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Supported File Types

TopMark supports a wide range of file types, each handled by a processor that knows how to insert
and update headers safely.

## Processors and File Types

| Processor               | Module                               | File Types                                                                                                                                                |
| ----------------------- | ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CBlockHeaderProcessor` | `topmark.pipeline.processors.cblock` | `css`, `less`, `scss`, `solidity`, `sql`, `stylus`                                                                                                        |
| `PoundHeaderProcessor`  | `topmark.pipeline.processors.pound`  | `dockerfile`, `env`, `git-meta`, `ini`, `julia`, `makefile`, `perl`, `python`, `python-requirements`, `python-stub`, `r`, `ruby`, `shell`, `toml`, `yaml` |
| `SlashHeaderProcessor`  | `topmark.pipeline.processors.slash`  | `c`, `cpp`, `cs`, `go`, `java`, `javascript`, `jsonc`, `kotlin`, `rust`, `swift`, `typescript`, `vscode-jsonc`                                            |
| `XmlHeaderProcessor`    | `topmark.pipeline.processors.xml`    | `html`, `markdown`, `svelte`, `svg`, `vue`, `xhtml`, `xml`, `xsl`, `xslt`                                                                                 |

## File types without a registered processor

The following formats are **recognized but intentionally skipped** because they lack a safe comment
syntax:

- `json`
- `license_text`
- `python-typed-marker`

Use `--skip-unsupported` to hide them from the report while keeping safety.

## Listing Supported File Types

To view the complete list supported by your installed version of TopMark, run:

```sh
topmark filetypes
```

## How TopMark Resolves File Types

TopMark may have multiple `FileType` definitions that match a given path. The resolver uses a
scoring system:

- Evaluates all matching file types and scores them by specificity.
- Prefers explicit filenames or tail subpaths (e.g., `.vscode/settings.json`) over patterns, and
  patterns over simple extensions.
- Breaks ties in favor of headerable types (those without `skip_processing = true`).

### Tail Subpath Matching

`FileType.filenames` entries that contain a path separator (e.g., `.vscode/settings.json`) are
matched as path suffixes against `path.as_posix()`. Plain names still match the basename only.

### JSON vs JSONC

- Generic `json` is recognized but marked `skip_processing = true` because strict JSON has no
  comment syntax.
- `vscode-jsonc` is a safe, narrow opt‑in that uses `//` headers.
- You can add additional JSON-with-comments formats via a dedicated `FileType` or an explicit
  allow‑list in config.

### Shebang‑Aware Insertion

The default insertion logic is policy‑driven and shebang‑aware (insert after `#!` and optional
encoding line). For formats like XML that need character‑precise placement, processors provide a
text‑offset path; `XmlHeaderProcessor` uses this and signals no line anchor.
