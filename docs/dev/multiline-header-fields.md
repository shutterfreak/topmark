<!--
topmark:header:start

  project      : TopMark
  file         : multiline-header-fields.md
  file_relpath : docs/dev/multiline-header-fields.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Multiline header field serialization and deterministic wrapping

This document defines the serialization contract for TopMark field values that span multiple
physical header lines. It also defines deterministic, opt-in wrapping and canonical reflow.

The format is intentionally smaller than YAML, Python, TOML, or Markdown string syntax. TopMark
continues to represent semantic fields as `Mapping[str, str]`. Literal and folded records are
on-disk serialization forms managed by TopMark, not separate semantic value types and not a
user-maintained layout contract.

______________________________________________________________________

## Scope and terminology

TopMark originally represented every header field on one physical line using ordinary `key: value`
syntax. Multiline serialization extends that stable baseline with two forms:

- **Literal multiline field**: the semantic value contains LF characters and is serialized through
  `|`, bare `|`, or `|=` records. Its record boundaries preserve semantic line breaks.
- **Folded multiline field**: a semantically single-line value is serialized across physical lines
  through `>` or `>=` records. Its record boundaries are presentation wrapping and do not introduce
  semantic line breaks.

The distinction is semantic rather than merely visual: literal records preserve line breaks in the
value, while folded records preserve a single-line value through canonical physical wrapping.

The remaining terminology is:

- **Semantic value**: the complete string associated with a field.
- **Physical line**: one rendered source-file line, excluding its physical line terminator when
  measuring width.
- **Ordinary single-line field**: the original `key: value` representation on one physical line.
- **Plain folded record**: a `>` record whose boundary contributes exactly one U+0020 SPACE.
- **Exact folded record**: a `>=` record whose decoded content is concatenated without an implicit
  separator.
- **Canonical rendering**: the unique output selected from the semantic value, effective
  configuration, processor, indentation, alignment, and physical newline style.

The `|`, `|=`, `>`, and `>=` tokens are publicly documented TopMark file syntax because they appear
in source files and diffs. Users may inspect or repair them, but TopMark owns their canonical
layout.

______________________________________________________________________

## Design requirements

The serialization and wrapping implementation must:

- preserve ordinary `key: value` syntax;
- preserve existing output byte-for-byte when wrapping is disabled, except when canonicalizing valid
  folded input or when a folded exact representation is required to avoid semantic loss;
- distinguish ordinary, literal, and folded values without inferring structure from indentation;
- preserve the exact semantic string;
- preserve literal LF characters and never reinterpret them as folded whitespace;
- preserve empty logical lines and semantic terminal newlines;
- preserve boundary whitespace without depending on invisible physical trailing spaces;
- apply the selected processor's affixes to every physical line;
- validate every encoded physical payload line before applying processor affixes;
- include processor affixes and indentation in width measurement;
- preserve aligned and compact field rendering;
- preserve existing pre-prefix indentation when replacing a header;
- use deterministic, cross-platform wrapping;
- avoid hard-splitting unbreakable tokens;
- converge after one successful application; and
- require no explicit header format version.

An ordinary value equal to or beginning with a continuation token remains ordinary:

```text
label: |
other: >
third: >= not a continuation here
```

Continuation syntax is activated only after an empty field opener.

______________________________________________________________________

## Single-line compatibility

The original ordinary representation remains canonical for single-line, ordinary-safe values when
automatic wrapping does not apply:

```text
# project: TopMark
# license: MIT
```

Multiline serialization is additive:

- semantic values containing LF use literal records;
- semantically single-line values selected for wrapping may use folded records;
- short single-line values with leading or trailing whitespace use one exact folded record so
  ordinary parsing cannot discard that whitespace; and
- values equal to or beginning with a continuation token remain ordinary when written after the
  field colon.

With wrapping disabled, existing ordinary-safe single-line fields retain their syntax, meaning, and
canonical output.

______________________________________________________________________

## Wrapping policy

TopMark provides these stable public configuration keys:

```toml
[formatting]
max_header_line_length = 100
wrap_fields = ["notice", "copyright"]
```

The selected contract is:

- `max_header_line_length` is an optional positive integer.
- `wrap_fields` is an ordered list of field names with an effective default of empty.
- Automatic wrapping requires both a configured width and membership in `wrap_fields`.
- Width belongs to the effective resolved configuration, not file-type policy.
- Width is measured in Unicode code points.
- The complete physical field line counts, excluding its line terminator.
- Width is a soft target.
- Unbreakable content is never hard-split.
- Only semantic values without LF are eligible for folded wrapping.
- Literal multiline values are never reflowed as folded text.
- Single-line values that fit remain ordinary unless an exact folded representation is needed to
  preserve permitted leading or trailing whitespace.
- Automatically wrapped values use canonical `>` and `>=` records.
- Valid folded syntax is accepted regardless of whether automatic wrapping is enabled.
- Parsed folded layout is not retained as semantic metadata.
- Rendering reconstructs canonical layout from the semantic value and effective configuration.
- A width or allowlist change may intentionally cause formatting-only file changes.

No mdformat-style `keep` policy is provided. Literal line breaks are semantic and are always
preserved. Folded line breaks are presentation and are always canonicalized.

______________________________________________________________________

## Normative configuration contract

### Keys and types

```toml
[formatting]
max_header_line_length = 100
wrap_fields = ["notice", "copyright"]
```

`max_header_line_length`:

- Type: integer.
- Effective type: `int | None`.
- Default: unset, represented as `None` internally.
- Valid values: every integer greater than zero.
- Meaning: soft maximum number of Unicode code points in a complete physical field line.

`wrap_fields`:

- Type: array of strings.
- Effective immutable type: `tuple[str, ...]`.
- Default: empty.
- Meaning: fields eligible for automatic folded wrapping.

Booleans are not integers for this contract even though Python's `bool` is an `int` subtype.

### Activation

Automatic wrapping is active for a field only when:

1. `max_header_line_length` is set; and
1. the field name occurs in `wrap_fields`.

Therefore:

| Width | Allowlist       | Automatic wrapping      |
| ----- | --------------- | ----------------------- |
| Unset | Absent or empty | Disabled                |
| Unset | Nonempty        | Disabled                |
| Set   | Absent or empty | Disabled                |
| Set   | Field absent    | Disabled for that field |
| Set   | Field present   | Enabled for that field  |

Literal serialization and parsing of valid folded syntax do not depend on this activation test.

### Invalid configuration

| Input                                            | Result                   |
| ------------------------------------------------ | ------------------------ |
| `0`                                              | Configuration error      |
| Negative integer                                 | Configuration error      |
| Boolean                                          | Configuration type error |
| Float                                            | Configuration type error |
| String                                           | Configuration type error |
| Array or table                                   | Configuration type error |
| Empty field name                                 | Configuration error      |
| Field name invalid under shared field-name rules | Configuration error      |
| Non-string allowlist member                      | Configuration type error |

There is no arbitrary minimum width. A very small positive width remains valid because the limit is
a soft target. Structural or unbreakable overflow is handled during rendering.

### Duplicate and unknown names

Duplicate names in `wrap_fields` are removed while preserving the first occurrence. Canonical
configuration output contains each name once.

A syntactically valid name that is not present in the current `header.fields` sequence is accepted
and inert. It is not an error or warning because:

- layered configuration may select fields elsewhere;
- runtime and plugin-provided fields may not be known at the original TOML source; and
- treating dormant allowlist entries as invalid would make reusable configuration fragile.

### Layered configuration

`max_header_line_length` follows scalar inheritance:

- an absent child key inherits the nearest parent value;
- an explicitly supplied child integer replaces the inherited value;
- an explicit API/runtime `None` clears the inherited value where that override surface can
  distinguish "clear" from "not supplied."

`wrap_fields` follows replacement semantics:

- an absent child key inherits the nearest parent value;
- a present nonempty array replaces the inherited array;
- a present empty array explicitly clears the inherited array.

The implementation must preserve the distinction between an absent array and a present empty array.
It must not apply the older "empty collection means unset" behavior to `wrap_fields`.

Runtime and API overrides participate at the same final-precedence stage as other formatting
overrides. They use the same validation, deduplication, replacement, freeze, thaw, and serialization
rules.

### Configuration output

The keys are stable public configuration contracts.

- `dump-config` must expose the effective values.

- `default-config` should document `wrap_fields = []`; it cannot emit a TOML null for the unset
  width, so the width remains omitted or appears as a commented example according to the command's
  established conventions.

- `starter-config` should omit both keys unless it already emits optional formatting examples.

- TOML serialization omits `max_header_line_length` when unset.

- JSON and NDJSON configuration payloads include:

  ```json
  {
    "max_header_line_length": null,
    "wrap_fields": []
  }
  ```

- Machine schemas and snapshots must be updated additively.

______________________________________________________________________

## Alternatives considered and rejected

### Apply one width to all fields

Rejected because it changes every sufficiently long field as soon as a width is configured. It
causes avoidable diff churn and gives users no way to protect identifiers, URLs, SPDX expressions,
or project-specific machine fields.

### Per-field width mapping

Example:

```toml
[formatting.wrap_fields]
notice = 100
copyright = 88
```

Rejected because it combines selection and width into a more complex merge model, makes clearing and
inheritance harder to explain, and offers little benefit before real use demonstrates that fields
need different widths.

### Per-file-type widths or policy defaults

Rejected because effective resolved configuration already accounts for the target path. Processor
affix lengths are included in the physical-line measurement automatically. No concrete problem
requires another policy layer.

### Global wrapping with exclusions

Rejected because opt-out wrapping has a larger compatibility surface. An allowlist makes every
formatting change deliberate.

### Formatter- or linter-derived width

Rejected because external formatter configuration, editor settings, discovery order, and tool
availability would make TopMark output environment-dependent.

### Hard-limit wrapping

Rejected because URLs, paths, hashes, UUIDs, SPDX identifiers, and other unbreakable tokens cannot
be split without changing their value or inventing hyphenation semantics.

### Generic word wrapping

Rejected because common `textwrap` behavior may replace, collapse, expand, or discard whitespace.
TopMark must reconstruct the original string exactly.

### Always fold selected fields

Rejected because short ordinary values are easier to read and preserve existing output. Selected
fields fold only when needed, except for the whitespace-sensitive exact representation.

### Preserve existing folded layout

Rejected because it would require retaining presentation metadata outside `Mapping[str, str]` and
defining what happens after value, width, processor, indentation, or alignment changes. That
conflicts with canonical render-from-semantics behavior.

______________________________________________________________________

## Normative grammar

The grammar applies after the processor has located the marker span, removed the physical line
terminator, and validated and removed the required comment affixes.

```ebnf
header          = { blank-line
                  | ordinary-field
                  | literal-field
                  | folded-field } ;

ordinary-field  = field-name, padding, ":", [ " ", ordinary-value ] ;

literal-field   = empty-field, line-end,
                  literal-record, line-end,
                  literal-record,
                  { line-end, literal-record } ;

folded-field    = empty-field, line-end,
                  folded-record,
                  { line-end, folded-record } ;

empty-field     = field-name, padding, ":" ;

literal-record  = layout-indent,
                  ( literal-plain | literal-empty | literal-exact ) ;

folded-record   = layout-indent,
                  ( folded-plain | folded-exact ) ;

literal-plain   = "|", " ", plain-content ;
literal-empty   = "|" ;
literal-exact   = "|=", " ", quoted-content ;

folded-plain    = ">", " ", plain-content ;
folded-exact    = ">=", " ", quoted-content ;

quoted-content  = '"',
                  { quoted-character | escaped-quote | escaped-backslash },
                  '"' ;

escaped-quote   = '\"' ;
escaped-backslash = '\\' ;

padding         = { " " } ;
layout-indent   = { " " | TAB } ;
```

A literal field requires at least two continuation records. A folded field requires at least one.

This intentional asymmetry follows from the semantics:

- one literal record would contain no semantic LF and therefore needlessly competes with ordinary or
  exact folded serialization;
- one exact folded record is necessary to preserve a short single-line value with leading or
  trailing permitted whitespace without adding a meaningless `>= ""` record.

`plain-content` is nonempty permitted text with no boundary whitespace that would be lost or
reinterpreted by parsing. Boundary-sensitive content uses the exact form.

`quoted-character` may be any otherwise permitted Unicode scalar value except `"`, `\`, CR, LF,
Unicode category `Cc`, U+2028 LINE SEPARATOR, or U+2029 PARAGRAPH SEPARATOR. The only escapes are
`\"` and `\\`.

Sequences such as `\n`, `\r`, `\t`, `\uXXXX`, and `\UXXXXXXXX` are invalid escapes. A nonbreaking
space or other permitted Unicode character must occur as that actual character.

______________________________________________________________________

## Canonical forms

### Ordinary field

```text
#   project      : TopMark
```

### Literal multiline field

```text
#   notice:
#     | First literal line.
#     | Second literal line.
```

### Empty literal logical line

```text
#   notice:
#     | First line.
#     |
#     | Third line.
```

### Exact literal line

```text
#   notice:
#     |= "  intentionally indented text  "
#     | Ordinary line.
```

### Automatically folded field

```text
#   notice:
#     > Lorem ipsum dolor sit amet, consectetur adipiscing
#     > elit, sed do eiusmod tempor incididunt ut labore.
```

### Exact folded boundary

```text
#   notice:
#     > Words separated before the preserved boundary
#     >= "   continue here"
```

The value contains exactly three spaces between `boundary` and `continue`.

### Short whitespace-sensitive value

```text
#   notice:
#     >= "   Indented"
```

This is valid and canonical. It represents the single-line value `···Indented`, where each `·`
stands for U+0020 SPACE. No empty `>= ""` record is emitted.

Further examples:

```text
#   notice:
#     >= "Trailing   "
```

```text
#   notice:
#     >= "  Both sides  "
```

```text
#   notice:
#     >= " "
```

Existing two-record input such as:

```text
#   notice:
#     >= ""
#     >= "   Indented"
```

remains valid, reconstructs the same semantic value, and canonicalizes to the one-record form.

______________________________________________________________________

## Literal value semantics

Each literal record decodes to one logical line. Given records `r0 ... rn`, the semantic value is:

```python
"\n".join([r0, ..., rn])
```

No terminal newline is implicit.

Examples:

- `| first` followed by `| second` represents `first\nsecond`.
- `|` followed by `| second` represents `\nsecond`.
- `| first`, `|`, and `| third` represent `first\n\nthird`.
- `| first` followed by `|` represents `first\n`.
- Two bare `|` records represent `\n`.
- `| first` followed by two bare `|` records represents `first\n\n`.

Physical LF, CRLF, and CR separators all reconstruct semantic LF. Rendering uses the selected
physical newline style of the target file.

Semantic CRLF and CR received from TOML, runtime overrides, derived values, or plugins normalize to
LF before validation and serialization.

Unicode U+2028 LINE SEPARATOR and U+2029 PARAGRAPH SEPARATOR are not alternative newline spellings
and remain invalid.

______________________________________________________________________

## Folded value semantics

For decoded folded records `r0 ... rn`:

- the first record contributes `r0`;
- every subsequent plain `>` record contributes one U+0020 SPACE followed by its decoded content;
- every subsequent exact `>=` record contributes its decoded content without an implicit separator.

Examples:

```text
> first fragment
> second fragment
```

reconstructs:

```text
first fragment second fragment
```

```text
> first fragment
>= "   second fragment"
```

reconstructs a value containing exactly three U+0020 spaces at that boundary.

```text
>= "   Indented"
```

reconstructs a value beginning with exactly three U+0020 spaces.

A first `>` record has no implicit leading space. A first `>=` record likewise contributes exactly
its decoded content.

______________________________________________________________________

## Width-measurement contract

### Metric

Width is the number of Unicode code points in the complete physical line after applying:

- preserved pre-prefix indentation;
- processor line prefix;
- processor post-prefix indentation;
- field name;
- alignment padding;
- colon and ordinary separator;
- empty field opener syntax;
- fixed continuation indentation;
- continuation token and separator;
- exact-record quotes and escapes; and
- processor line suffix.

The physical LF, CRLF, or CR terminator is excluded.

This is equivalent to counting Unicode scalar/code-point units in the final Python string, not
bytes, grapheme clusters, or display cells.

### Consequences

- A combining sequence counts each code point.
- A wide CJK character counts as one code point.
- A single-code-point emoji counts as one.
- A multi-code-point emoji sequence counts every constituent code point.
- Quoted `"` and `\` characters count twice when escaped in an exact record.
- A structural tab counts as one code point.
- Semantic tabs are rejected as control characters and never become breakpoints.
- UTF-8, UTF-16, and other encoded byte lengths do not affect wrapping.
- Terminal font and display-column behavior do not affect wrapping.

Unicode code points are selected because TopMark formats source text rather than terminal cells.
They are deterministic across encodings and do not require terminal, locale, font, or grapheme-width
libraries.

### Lines subject to the target

The width target applies to:

- an eligible field's candidate ordinary line;
- its empty folded opener; and
- each automatically generated folded continuation line.

It does not reflow or constrain:

- marker lines;
- block wrapper lines;
- separator or blank lines;
- literal continuation records;
- unselected existing ordinary fields; or
- source-file body content.

All physical lines remain subject to processor validation regardless of width eligibility.

______________________________________________________________________

## Canonical wrapping and reflow algorithm

### 1. Normalize and validate

For every selected semantic value:

1. Normalize semantic CRLF and CR to LF.
1. Apply shared semantic validation.
1. Apply processor-specific semantic validation.
1. Choose a serialization mode.
1. Encode every physical payload line.
1. Apply processor encoded-line validation.
1. Apply processor affixes and the selected physical newline style.

Wrapping never makes invalid semantic content valid.

### 2. Select the serialization mode

Given field name `name`, semantic value `value`, and effective configuration:

1. If `value` contains LF, render it literally using `|`, bare `|`, and `|=`.
1. Otherwise, determine whether ordinary serialization round-trips the value exactly.
1. If ordinary serialization cannot round-trip the value because of permitted leading or trailing
   whitespace, use folded exact serialization regardless of whether automatic wrapping is active.
1. If wrapping is inactive for the field, render it ordinarily when that is semantically safe.
1. If wrapping is active and the complete ordinary line fits, render it ordinarily.
1. If wrapping is active and the ordinary line exceeds the target, attempt folded wrapping.
1. If wrapping cannot produce at least two useful continuation records, retain the ordinary form,
   except where a single exact folded record is required for semantic fidelity.

A value consisting solely of permitted whitespace uses one exact folded record when exact folded
serialization is required.

An empty string remains an ordinary empty value. It is not automatically folded.

### 3. Identify breakpoints

Automatic wrapping may break only at an internal run of one or more U+0020 SPACE characters.

It must not break at:

- tabs;
- nonbreaking spaces;
- Unicode whitespace other than U+0020;
- punctuation without an adjacent U+0020 run;
- slashes in URLs or paths;
- hyphens;
- underscores; or
- arbitrary code-point positions.

A run of one U+0020 may be represented by the implicit separator of a following plain `>` record.

A run of two or more U+0020 characters must be preserved explicitly in a following exact `>=`
record, normally as leading content in that record.

Other whitespace is part of the adjacent unbreakable content.

### 4. Compute budgets from actual encoding

The implementation must measure candidate rendered lines, not estimate width from the semantic
substring alone.

For each candidate:

```text
ordinary_length =
    codepoint_length(render_complete_physical_field_line(ordinary_payload))

opener_length =
    codepoint_length(render_complete_physical_field_line(empty_opener))

record_length =
    codepoint_length(render_complete_physical_field_line(encoded_record))
```

The line terminator is removed before measurement.

For an exact record, quoting and escaping occur before measuring. This prevents a fragment
containing quotes or backslashes from unexpectedly exceeding the target after encoding.

### 5. Choose breaks greedily

Wrapping is greedy and stable:

1. Start at the beginning of the remaining semantic value.
1. Consider internal U+0020 runs in source order.
1. Construct the exact plain or exact folded record that each candidate boundary would require.
1. Choose the furthest candidate whose fully rendered record does not exceed the target.
1. Emit that record and continue.
1. If no candidate fits, emit the smallest next unbreakable unit needed to make progress, even if
   its rendered line exceeds the target.
1. Continue until the entire value is represented.
1. Verify by reconstructing the records and requiring exact equality with the input semantic value.

The algorithm must not call a generic wrapping function that collapses or substitutes whitespace.

### 6. Select plain versus exact records

Use plain `>` only when its boundary represents exactly one U+0020 SPACE and its content satisfies
plain-record grammar.

Use `>=` when:

- a boundary contains multiple U+0020 spaces;
- decoded record content begins or ends with whitespace that plain syntax cannot preserve;
- a short value has permitted leading or trailing whitespace; or
- exact encoding is otherwise necessary for lossless reconstruction.

Exact records are not chosen merely because their content contains quotes or backslashes. Those
characters may remain in plain content when plain grammar permits them. When an exact record is
otherwise required, `"` and `\` are escaped and their expanded encoded length counts.

### 7. Require useful automatic folding

Ordinary overlength content is automatically folded only if the result contains at least two
continuation records.

A single folded continuation is not used merely to move an unbreakable value below an empty opener.
That would add physical lines without improving readability or satisfying the target.

The single-record folded form is reserved for cases in which exact serialization is required to
preserve the semantic value.

### 8. Verify semantic identity

After constructing folded records, the renderer must reconstruct their semantic value using the
folded decoding rules and require code-point-for-code-point equality with the normalized input.

Failure of this internal invariant is an implementation error, not a recoverable formatting choice.

______________________________________________________________________

## Canonicalization after parsing

Valid folded syntax is accepted even when wrapping is disabled.

Parsing produces only the semantic `Mapping[str, str]`. It does not retain:

- original folded breakpoints;
- original continuation indentation;
- whether an equivalent boundary used `>` or `>=`;
- redundant empty exact records; or
- the original number of folded records.

Canonical rendering then follows the effective policy:

| Semantic value and policy                            | Canonical result           |
| ---------------------------------------------------- | -------------------------- |
| Contains LF                                          | Literal                    |
| Single-line, unselected, ordinary-safe               | Ordinary                   |
| Single-line, selected, fits, ordinary-safe           | Ordinary                   |
| Single-line, boundary-whitespace-sensitive           | Single exact folded record |
| Single-line, selected, over target, safely breakable | Canonically folded         |
| Single-line, selected, over target, unbreakable      | Ordinary overlong line     |
| Previously folded, now fits, ordinary-safe           | Ordinary                   |
| Manually folded, unselected, ordinary-safe           | Ordinary                   |
| Manually folded, noncanonical boundaries             | Reconstructed and reflowed |
| Folded value requiring exact form to avoid loss      | Exact folded form          |

Changing `max_header_line_length`, `wrap_fields`, alignment, processor affixes, or preserved
indentation may therefore produce a formatting-only change.

______________________________________________________________________

## Boundary behavior

| Value or condition                           | Canonical behavior                                                       |
| -------------------------------------------- | ------------------------------------------------------------------------ |
| Exactly one U+0020                           | One `>= " "` record when exact folded serialization is required          |
| Multiple leading spaces                      | One or more exact folded records preserving every space                  |
| Multiple trailing spaces                     | Exact folded record preserving every space                               |
| Leading and trailing spaces                  | Exact folded serialization                                               |
| Internal single U+0020                       | Preferred automatic breakpoint                                           |
| Internal multiple U+0020                     | May break using `>=` with the complete run preserved                     |
| Tab                                          | Invalid semantic control character                                       |
| Nonbreaking space                            | Preserved; not an automatic breakpoint                                   |
| Other permitted Unicode whitespace           | Preserved; not an automatic breakpoint                                   |
| Mixed whitespace run                         | Treated as unbreakable except for independently usable U+0020 boundaries |
| Empty string                                 | Ordinary empty field                                                     |
| Starts with `>` or `>=`                      | Ordinary unless wrapping is otherwise required                           |
| Starts with a literal continuation token     | Ordinary unless wrapping is otherwise required                           |
| URL                                          | Break only at U+0020 outside the URL                                     |
| Filesystem path                              | Never split internally                                                   |
| SPDX expression                              | Break only at existing U+0020 boundaries                                 |
| Hash or UUID                                 | Never split internally                                                   |
| Long identifier                              | Remains overlong                                                         |
| Punctuation adjacent to a space              | The space remains an eligible boundary                                   |
| Combining sequence                           | May be separated only if an eligible U+0020 boundary occurs there        |
| Emoji sequence                               | Same rule; never split merely because it is wide                         |
| Semantic LF                                  | Literal serialization only                                               |
| Semantic CRLF or CR                          | Normalize to LF, then literal serialization                              |
| Quote or backslash in exact content          | Escape as `\"` or `\\`                                                   |
| `*/` in C-block value                        | Processor validation error                                               |
| `--` in XML/HTML/Markdown value              | Processor validation error                                               |
| Reserved TopMark marker                      | Shared validation error                                                  |
| Empty opener exceeds width                   | Fold if useful; opener remains overlong                                  |
| Continuation syntax leaves no content budget | Do not auto-fold; retain ordinary overlong form                          |
| Different affix lengths                      | Produce different available budgets deterministically                    |
| Preserved nested indentation                 | Counts toward width                                                      |
| LF, CRLF, or CR physical file                | Same wrapping decisions; only emitted terminators differ                 |

______________________________________________________________________

## Overlong and impossible-width behavior

The configured width is a soft target, not a validity condition.

An overlong physical field line remains valid when caused by:

- an unbreakable token;
- exact quoting or escaping overhead;
- a field opener longer than the target;
- processor affixes or indentation;
- a continuation structure that leaves no content budget; or
- a combination of those conditions.

TopMark must not:

- hard-split the semantic value;
- insert hyphens;
- remove or normalize whitespace;
- fail processing solely because the target cannot be met; or
- repeatedly rewrite an already canonical overlong line.

TopMark should emit at most one non-failing informational hint per affected field, using a stable
code such as:

```text
render:soft-width-exceeded
```

The diagnostic must identify the field safely and may report the target and maximum rendered
code-point length. It must not reproduce unsafe field content.

The hint is informational:

- it does not make configuration invalid;
- it does not make rendering fail;
- it does not become an error in strict mode;
- it does not prevent apply, check, dry-run, or machine output; and
- it does not prevent convergence.

______________________________________________________________________

## Folded parsing

Folded parsing behaves as follows:

- `>` and `>=` become active folded records.
- A folded scalar closes successfully after one or more valid folded records.
- A literal scalar still requires two or more literal records.
- Folded reconstruction uses implicit U+0020 only for subsequent plain `>` records.
- Exact folded records concatenate without an implicit separator.
- Exact quoting and escaping remain identical to literal exact records.
- Mixed literal and folded records remain malformed.
- Each folded scalar contributes one logical success or one logical error.
- Duplicate fields retain last-occurrence-wins behavior.
- Diagnostics use safe field positions and physical line numbers without echoing unsafe payloads.

A first folded record may be plain or exact. An empty bare folded record is not part of the grammar;
empty exact content is represented as:

```text
>= ""
```

Such a record is valid where it occurs, although redundant layouts may canonicalize away.

______________________________________________________________________

## Malformed-input and diagnostic matrix

| Condition                                 | Result               | Diagnostic                              |
| ----------------------------------------- | -------------------- | --------------------------------------- |
| Continuation without pending empty opener | Field error          | `header:orphan-continuation`            |
| Continuation after ordinary scalar        | Field error          | `header:continuation-after-scalar`      |
| One literal record                        | Field error          | `header:scalar-too-short`               |
| One folded record                         | Valid                | None                                    |
| Empty opener with no records              | Ordinary empty field | None                                    |
| Literal followed by folded record         | Field error          | `header:mixed-scalar-mode`              |
| Folded followed by literal record         | Field error          | `header:mixed-scalar-mode`              |
| Missing plain/exact body                  | Field error          | `header:missing-continuation-body`      |
| Unterminated exact string                 | Field error          | `header:invalid-continuation-string`    |
| Unsupported escape                        | Field error          | `header:invalid-continuation-string`    |
| Quote inside exact body without escape    | Field error          | `header:invalid-continuation-string`    |
| Forbidden control or Unicode separator    | Field error          | `header:invalid-continuation-character` |
| Required processor affix missing          | Field error          | `header:invalid-continuation-affix`     |
| Processor-forbidden reconstructed value   | Field error          | Existing processor validation rule      |
| Soft width exceeded                       | Valid, informational | `render:soft-width-exceeded`            |

`header:scalar-too-short` now applies only to literal fields. Existing valid folded fields with
redundant records remain valid and canonicalize according to the effective policy.

Malformed fields continue to produce `MALFORMED_ALL_FIELDS` or `MALFORMED_SOME_FIELDS`. Marker or
span corruption remains terminal `MALFORMED`.

______________________________________________________________________

## Validation integration

The validation order is:

1. Normalize semantic CRLF and CR to LF.
1. Validate field names.
1. Validate the complete semantic value using shared rules.
1. Apply the processor's additive semantic hook.
1. Select ordinary, literal, or folded encoding.
1. Validate every encoded physical payload line.
1. Apply the processor's additive encoded-line hook.
1. Apply processor affixes.
1. Append the target file's physical newline.

Shared semantic validation continues to reject:

- NUL;
- forbidden Unicode category `Cc` controls;
- U+2028 and U+2029;
- reserved TopMark start and end markers; and
- invalid field names.

Processor validation continues to reject, among other constraints:

- `*/` for C-block comment processors; and
- `--` for XML, HTML, and Markdown comment processors.

Wrapping must not be used to hide a processor-invalid sequence by placing a physical boundary inside
it. Complete semantic validation occurs before wrapping.

______________________________________________________________________

## Processor and plugin contract

`HeaderProcessor` owns:

- continuation grammar;
- literal and folded decoding;
- semantic reconstruction;
- width measurement;
- breakpoint selection;
- ordinary/literal/folded mode selection;
- canonical record encoding;
- exact quoting and escaping;
- shared semantic validation orchestration; and
- shared encoded-line validation orchestration.

Processors provide effective presentation overhead through their existing behavior:

- block prefix and suffix;
- line prefix and suffix;
- post-prefix field indentation;
- preserved pre-prefix indentation; and
- runtime overrides passed by the rendering pipeline.

Width is measured from the actual complete line produced with those effective values. A separate
"overhead number" hook is unnecessary and could diverge from rendering.

Custom processors may:

- define processor affixes and indentation;
- preserve processor-specific pre-prefix indentation;
- add semantic restrictions through `validate_processor_field`;
- add encoded-line restrictions through `validate_processor_encoded_line`; and
- decline base continuation-format compatibility by implementing a separate renderer contract.

Custom processors claiming compatibility with the base continuation format must not:

- reinterpret `|`, `|=`, `>`, or `>=`;
- replace the Unicode-code-point metric;
- change automatic breakpoint selection;
- infer semantic whitespace from indentation;
- skip complete-line validation; or
- apply only some processor affixes to continuation lines.

Plugins that override the complete header renderer are outside the automatic wrapping guarantee
unless they delegate field serialization and line construction back to the base implementation.
TopMark should document that limitation rather than silently applying incompatible wrapping.

______________________________________________________________________

## Configuration-to-rendering examples

Given:

```toml
[header]
fields = ["project", "notice", "copyright"]

[fields]
project = "TopMark"
notice = "A sufficiently long notice that contains ordinary spaces and can be wrapped."
copyright = """
First literal line.
Second literal line.
"""

[formatting]
max_header_line_length = 60
wrap_fields = ["notice", "copyright"]
```

`project` remains ordinary because it is not selected:

```text
#   project   : TopMark
```

`notice` may become folded because it is selected, contains no semantic LF, and exceeds the target:

```text
#   notice:
#     > A sufficiently long notice that contains
#     > ordinary spaces and can be wrapped.
```

`copyright` becomes literal, not folded, because the TOML value contains semantic LF:

```text
#   copyright:
#     | First literal line.
#     | Second literal line.
```

A TOML basic string containing `\n` produces semantic LF and is literal:

```toml
[fields]
notice = "First line.\nSecond line."
```

```text
#   notice:
#     | First line.
#     | Second line.
```

A TOML literal string containing the characters backslash and `n` remains one semantic line:

```toml
[fields]
notice = 'First line.\nSecond line.'
```

It remains ordinary if it fits or becomes folded only at actual U+0020 boundaries.

A selected short value with leading whitespace:

```toml
[fields]
notice = "   Indented"
```

renders:

```text
#   notice:
#     >= "   Indented"
```

No `preserve_line_breaks` setting is involved. The semantic value itself determines literal
serialization.

______________________________________________________________________

## Built-in processor examples

The exact breakpoints depend on the configured width because each processor has different affix
overhead.

### Pound comments

```text
# topmark:header:start
#
#   notice:
#     > This notice is wrapped using pound-comment
#     > continuation lines.
#
# topmark:header:end
```

### Slash comments

```text
// topmark:header:start
//
//   notice:
//     > This notice is wrapped using slash-comment
//     > continuation lines.
//
// topmark:header:end
```

### C block comments

```text
/*
 * topmark:header:start
 *
 *   notice:
 *     > This notice is wrapped using C-block
 *     > continuation lines.
 *
 * topmark:header:end
 */
```

### Markdown comments

```text
<!--
topmark:header:start

  notice:
    > This notice is wrapped using Markdown-comment
    > continuation lines.

topmark:header:end
-->
```

### XML and HTML comments

```text
<!--
topmark:header:start

  notice:
    > This notice is wrapped using XML-or-HTML
    > continuation lines.

topmark:header:end
-->
```

For an identical semantic value and target width, different processors may choose different
breakpoints because their complete physical field lines have different prefixes, suffixes, or
indentation.

______________________________________________________________________

## Canonicalization, comparison, and convergence

Semantic equality is independent of valid folded layout. Different folded layouts that reconstruct
the same string compare equal at the mapping layer.

The comparer also compares the current physical block with the newly rendered canonical block.
Therefore, any of the following may be reported as a formatting-only change:

- different valid folded breakpoints;
- redundant exact records;
- noncanonical continuation indentation;
- a folded value that now fits ordinarily;
- a manually folded unselected value;
- a changed width;
- a changed allowlist;
- changed field alignment;
- changed processor affixes; or
- changed preserved indentation.

After apply:

1. parsing reconstructs the same semantic mapping;
1. rendering produces the same canonical block;
1. exact block comparison reports unchanged; and
1. a second apply performs no write.

Check-only and dry-run modes report the same proposed formatting change without writing.

Strip behavior remains marker/span based. It removes the complete header without interpreting
continuation semantics beyond whatever scanning is already required to establish a valid span.

______________________________________________________________________

## Compatibility and versioning

No explicit header format version is required.

The change is additive:

- ordinary syntax is unchanged;
- semantic multiline values gain literal serialization;
- selected semantically single-line values gain folded serialization;
- folded fields accept one or more records;
- one-record literal fields remain malformed;
- incomplete or approximate continuation syntax remains malformed;
- folded activation requires an empty field opener; and
- semantic mappings remain `Mapping[str, str]`.

The following compatibility effects are intentional:

- Short values with leading or trailing whitespace use one exact folded record.
- Redundant two-record exact folded layouts canonicalize to one record.
- Enabling wrapping may cause formatting-only changes.
- Changing width or selected fields may cause formatting-only changes.
- Disabling wrapping restores ordinary rendering where ordinary serialization is lossless.
- Unset configuration preserves existing generated output for ordinary-safe single-line fields.

The configuration keys are public and stable after release. Renaming them, changing their types,
changing list replacement semantics, or changing the width metric would require normal public
compatibility treatment.

______________________________________________________________________

## Why there is no line-break preservation policy

TopMark has two different concepts that must remain separate:

1. Literal line breaks are characters in the semantic value.
1. Folded line breaks are canonical source presentation.

A `preserve_line_breaks` option would conflate them.

Literal LF must always survive parsing, comparison, rendering, configuration changes, and processor
changes. It is represented by literal `|` records without an opt-in policy.

Folded boundaries carry no semantic newline. Retaining their original physical positions would
require presentation metadata in addition to `Mapping[str, str]` and would weaken deterministic
canonicalization.

Markdown formatters such as mdformat can reasonably preserve author-selected paragraph line breaks
because those breaks belong to human-authored Markdown source. TopMark headers are generated
serialization derived from TOML, runtime values, plugins, and file metadata. Canonical reflow is
therefore the more appropriate default.

If practical experience later demonstrates a genuine need to retain manually authored folded layout,
it should be designed separately as an explicit mode such as `keep`, `reflow`, or `unfold`. It is
not part of this contract.

______________________________________________________________________

## Test matrix

### Configuration

Test:

- width absent;
- width positive;
- width zero;
- width negative;
- width boolean;
- width float;
- width string;
- width extremely small;
- allowlist absent;
- allowlist empty;
- allowlist populated;
- duplicate names;
- unknown valid names;
- invalid names;
- non-string members;
- parent inheritance;
- child replacement;
- explicit empty-array clearing;
- runtime/API precedence;
- freeze/thaw symmetry;
- TOML round-trip;
- default and starter output;
- dump-config output; and
- JSON/NDJSON schema and snapshots.

### Parsing

Test:

- one plain folded record;
- one exact folded record;
- two and three folded records;
- first exact record;
- subsequent exact record;
- redundant `>= ""`;
- one literal record remains malformed;
- two literal records remain valid;
- mixed literal/folded sequences in both directions;
- orphan continuation;
- continuation after ordinary field;
- missing bodies;
- malformed quotes;
- unsupported escapes;
- missing affixes;
- logical success/error counts;
- duplicate fields; and
- safe diagnostic content.

### Semantic reconstruction

Test:

- exactly one implicit U+0020 boundary;
- multiple spaces;
- leading spaces;
- trailing spaces;
- both boundary sides;
- exactly one-space value;
- nonbreaking spaces;
- other permitted Unicode whitespace;
- mixed whitespace;
- quotes;
- backslashes;
- punctuation;
- combining sequences;
- emoji sequences; and
- exact equality after reconstruction.

### Rendering

Test:

- selected field fits;
- selected field exceeds width;
- unselected field exceeds width;
- unset width;
- empty allowlist;
- no breakpoint;
- one possible breakpoint;
- multiple breakpoints;
- exact boundary changes record budget;
- opener exceeds width;
- continuation structure exceeds width;
- long URL;
- long path;
- SPDX expression;
- hash;
- UUID;
- unbreakable identifier;
- previously folded value now fits;
- manually folded unselected value;
- noncanonical breakpoints;
- alignment on and off;
- all built-in processors;
- custom affixes;
- preserved nested indentation; and
- LF, CRLF, and CR physical output.

### Validation

Test:

- every encoded physical line is validated;
- semantic `*/` rejection for C-block processors;
- semantic `--` rejection for XML, HTML, and Markdown;
- reserved marker rejection;
- forbidden control rejection;
- U+2028/U+2029 rejection;
- wrapping cannot evade semantic validation;
- plugin semantic hook;
- plugin encoded-line hook; and
- informational soft-overflow behavior.

### Pipeline and convergence

Test:

- insert;
- replace;
- check-only;
- dry-run;
- apply;
- patch generation;
- strip;
- semantic equality with different layouts;
- formatting-only change;
- second-run unchanged;
- width increase;
- width decrease;
- field selection;
- field deselection; and
- machine-output stability.

______________________________________________________________________

## Contract conformance criteria

The implementation must continue to satisfy these criteria:

- the two public configuration keys are implemented with the specified types and merge behavior;
- folded `>` and `>=` parsing is active;
- one-or-more folded records are accepted;
- two-or-more literal records remain required;
- short whitespace-sensitive values use one exact folded record;
- literal semantic LF is never folded;
- wrapping measures complete physical lines in Unicode code points;
- wrapping uses only deterministic U+0020-run breakpoints;
- exceptional whitespace boundaries round-trip through exact records;
- unbreakable content is not hard-split;
- impossible targets remain non-failing;
- all built-in processors apply affixes to every continuation line;
- custom processor validation remains additive;
- configuration and machine serialization expose the new settings;
- check, dry-run, apply, strip, and patch flows behave consistently;
- formatting changes converge after one apply; and
- the complete test matrix passes on supported Python versions.

______________________________________________________________________

## Implementation inventory

The implementation covers:

1. Configuration model fields and validation.
1. Merge, freeze, thaw, and override behavior.
1. TOML deserialization and serialization.
1. JSON/NDJSON payload and schema changes.
1. Folded parser activation.
1. Mode-specific minimum-record validation.
1. Folded semantic reconstruction.
1. Lossless whitespace-run tokenization.
1. Unicode-code-point measurement of complete physical lines.
1. Canonical ordinary/literal/folded selection.
1. Exact folded quoting and escaping.
1. Soft-overflow informational hints.
1. Processor validation integration.
1. Comparer and convergence coverage.
1. Built-in and custom processor tests.
1. CLI and end-to-end tests.
1. User-facing configuration documentation.
1. Changelog entry.

The implementation does not introduce:

- body-content wrapping;
- terminal or editor width discovery;
- hard hyphenation;
- file-type wrapping policy;
- a header format version;
- a Markdown-style `keep` mode; or
- changes to header placement.

______________________________________________________________________

## Settled decisions

The approved decisions are:

- fixed effective width plus explicit field allowlist;
- positive integer width with no arbitrary minimum;
- replacement semantics for the allowlist, including explicit empty clearing;
- Unicode code-point measurement;
- complete physical field-line accounting;
- soft-target wrapping;
- U+0020-run breakpoints;
- exact records for exceptional boundaries;
- one-or-more folded records;
- two-or-more literal records;
- canonical reflow rather than layout preservation; and
- public documentation of implementation-managed continuation syntax.

______________________________________________________________________

## Related documentation

- [Header placement](../usage/header-placement.md)
- [Getting started](../usage/getting-started.md)
- [Plugins and extensibility](plugins.md)
- [Pipelines](pipelines.md)
