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

TopMark supports four output formats:

```bash
--output-format text        # Text output on interactive terminal (default)
--output-format markdown    # Markdown format
# Machine formats:
--output-format json        # JSON object (formatted)
--output-format ndjson      # NDJSON records (1 per line)
```

- Human-facing output:
  - `text` (default): When using in an interactive terminal; if color-enabled the output will be
    rendered in color by default (disable with `--no-color`).
  - `markdown`: Generate output as Markdown (document-oriented; ignores TEXT-only verbosity and
    quiet controls).
- Machine-readable formats:
  - `json`: Return a single JSON object, formatted for easier reading.
  - `ndjson`: Returns a stream of NDJSON objects (one per line).

See also:

- [`Machine output schema`](../dev/machine-output.md)

______________________________________________________________________

## Verbosity

TopMark supports TEXT output verbosity controls:

```bash
--verbose       # Increase TEXT output verbosity
-v              # Shorthand (can be repeated)
--quiet         # Suppress TEXT output
-q              # Shorthand
```

In TEXT output, verbosity affects:

- Hint grouping
- Diagnostic detail
- Summary rendering

{% include-markdown "\_snippets/output-contract.md" %}

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
