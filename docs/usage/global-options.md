<!--
topmark:header:start

  project      : TopMark
  file         : global-options.md
  file_relpath : docs/usage/global-options.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Global Output Options

## Output format

TopMark supports 4 output formats:

```bash
--output-format text        # Text output on interactive terminal (default)
--output-format markdown    # Markdown format
# Machine formats:
--output-format json        # JSON object (formatted)
--output-format ndjson      # NDJSON records (1 per line)
```

- Human-facing output:
  - `text` (default): When using in an interactive terminal; if color-enabled the output will be rendered in color by default (disable with `--no-color`).
  - `markdown`: Generate output as MarkDown (can be redirected to a file).
- Machine formats:
  - `json`: Return a single JSON object, formatted for easier reading.
  - `ndjson`: Returns a stream of NDJSON objects (1 per line).

______________________________________________________________________

## Verbosity

TopMark supports verbosity controls:

```bash
--verbose       # Increase verbosity level
-v              # Shorthand (can be repeated)
--quiet         # Decrease verbosity level
-q              # Shorthand (can be repeated)
```

Verbosity affects:

- Hint grouping
- Diagnostic detail
- Summary rendering

Notes:

- Machine-readable formats (`json`, `ndjson`) are not affected by verbosity.
- `--verbose` and `--quiet` are mutually exclusive

______________________________________________________________________

## Color

Color output applies only to **text output format**.

```bash
--color auto
--color always
--color never
```

- `auto` (default): enable color in interactive terminals
- `always`: force color
- `never`: disable color

Color has no effect on `markdown` or machine output formats (`json` or `ndjson`).
