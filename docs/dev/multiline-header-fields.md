<!--
topmark:header:start

  project      : TopMark
  file         : multiline-header-fields.md
  file_relpath : docs/dev/multiline-header-fields.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Multiline header field serialization

This document defines the approved serialization contract for one logical TopMark field value that
spans multiple physical header lines.

> [!IMPORTANT]
>
> This is an implementation contract for
> [GitHub issue #326](https://github.com/shutterfreak/topmark/issues/326), not a description of
> functionality available on the current `main` branch. Until #326 is implemented, field values
> remain single-line and the renderer rejects CR and LF. Folded rendering remains reserved for
> [GitHub issue #327](https://github.com/shutterfreak/topmark/issues/327).

The contract is intentionally smaller than YAML, Python, or TOML string syntax. It keeps existing
`key: value` fields unchanged, uses explicit continuation records, and does not assign structural
meaning to indentation.

______________________________________________________________________

## Design requirements

The serialization must:

- preserve the syntax and rendered bytes of existing valid single-line fields;
- distinguish ordinary, literal, and folded values without guessing from indentation;
- reconstruct literal newlines and folded text deterministically;
- preserve empty logical lines and semantic terminal newlines;
- preserve boundary whitespace without relying on invisible physical trailing spaces;
- apply the selected processor's comment affixes to every physical line;
- retain the validation boundary introduced for single-line fields;
- remain compatible with aligned and compact field rendering;
- preserve existing pre-prefix header indentation when replacing a header;
- keep semantic values represented as `Mapping[str, str]`; and
- provide a deterministic foundation for later wrapping and reflow.

An ordinary value equal to `|` or `>` must remain ordinary:

```text
label: |
other: >
```

These lines do not introduce multiline scalars.

______________________________________________________________________

## Canonical forms

### Ordinary field

Ordinary single-line fields retain the existing representation:

```text
#   project      : TopMark
```

### Literal multiline field

A literal field has an empty field opener followed by at least two literal continuation records:

```text
#   notice:
#     | First literal line.
#     | Second literal line.
```

Literal records reconstruct with semantic LF characters.

### Empty logical line

A bare `|` represents an empty logical line:

```text
#   notice:
#     | First line.
#     |
#     | Third line.
```

### Exact whitespace-sensitive line

The common form is unquoted. The `|=` form is used only when leading or trailing horizontal
whitespace must be preserved exactly:

```text
#   notice:
#     |= "  leading and trailing spaces  "
#     | Ordinary unquoted line.
```

### Folded field

Folded records are reserved for #327:

```text
#   notice:
#     > Lorem ipsum dolor sit amet, consectetur adipiscing elit,
#     > sed do eiusmod tempor incididunt ut labore.
```

The parser implemented by #326 must recognize `>` and `>=` as reserved folded syntax and diagnose
their use deterministically. It must not treat them as literal records or orphan ordinary fields.

______________________________________________________________________

## Normative grammar

The grammar applies after the processor has located the marker span, removed the physical newline,
and validated and removed its comment affixes.

```ebnf
header          = { blank-line | ordinary-field | literal-field } ;

ordinary-field  = field-name, padding, ":", [ " ", ordinary-value ] ;

literal-field   = empty-field, line-end,
                  literal-record, line-end,
                  literal-record,
                  { line-end, literal-record } ;

folded-field    = empty-field, line-end,
                  folded-record, line-end,
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

`plain-content` is nonempty permitted text with no leading or trailing horizontal whitespace.
Boundary whitespace uses the exact record form.

`quoted-character` may be any otherwise permitted Unicode scalar value except `"`, `\`, CR, LF,
Unicode category `Cc`, U+2028 LINE SEPARATOR, or U+2029 PARAGRAPH SEPARATOR. The only escapes are
`\"` and `\\`. Sequences such as `\n`, `\r`, `\t`, `\uXXXX`, and `\UXXXXXXXX` have no special
meaning and are invalid as escapes.

______________________________________________________________________

## Indentation and alignment

Continuation indentation is canonical presentation, not structure.

After processor affixes, canonical rendering uses:

```text
field-indent + field-name + padding + ":"
field-indent + two ASCII spaces + continuation-record
```

For example:

```text
#   project      : TopMark
#   long_comment :
#     | First literal line.
#     | Second literal line.
#   license      : MIT
```

Continuation tokens are not aligned with the field colon. This keeps their position independent of:

- `align_fields`;
- the longest configured field name;
- whether fields use aligned or compact presentation;
- the name of the field being continued; and
- wrapping-width calculations introduced by #327.

After affix removal, parsing ignores horizontal layout indentation before `|`, `|=`, `>`, or `>=`. A
hand-edited colon-aligned continuation is therefore semantically valid, but canonical rendering
restores the fixed two-space continuation indentation. Exact block comparison may report that
canonicalization as a formatting change.

Semantic leading whitespace is never inferred from continuation indentation. It must use an exact
record:

```text
#   notice:
#     |= "  intentionally indented text"
```

When replacing an existing indented header, the preserved pre-prefix indentation applies to the
field opener and every continuation line.

______________________________________________________________________

## Literal value semantics

Each plain, empty, or exact literal record decodes to one logical line. Given decoded records
`r0 ... rn`, the semantic value is:

```python
"\n".join([r0, ..., rn])
```

No terminal newline is implicit. Empty records make newline structure explicit:

- `| first` followed by `| second` represents `first\nsecond`.
- `|` followed by `| second` represents `\nsecond`.
- `| first`, `|`, and `| third` represent `first\n\nthird`.
- `| first` followed by `|` represents `first\n`.
- Two bare `|` records represent `\n`.
- `| first` followed by two bare `|` records represents `first\n\n`.

The physical source may use LF, CRLF, or CR. Parsing normalizes those physical separators to
semantic LF. Rendering uses the target file's selected physical header newline style.

Semantic CRLF and CR received from configuration, runtime overrides, derived values, or plugins
normalize to LF before validation and rendering. Unicode line and paragraph separators are not
alternative newline spellings and remain invalid.

______________________________________________________________________

## Folded value semantics

Folded syntax is reserved by [#326](https://github.com/shutterfreak/topmark/issues/326) and
activated only by [#327](https://github.com/shutterfreak/topmark/issues/327).

For a folded field:

- the first record contributes its decoded content;
- each subsequent plain `>` record contributes one U+0020 SPACE followed by its content; and
- each subsequent exact `>=` record contributes its decoded content without an implicit separator.

Therefore:

```text
> first fragment
> second fragment
```

reconstructs:

```text
first fragment second fragment
```

An exact record preserves a nonstandard boundary:

```text
> first fragment
>= "   second fragment"
```

reconstructs a value containing exactly three spaces between `fragment` and `second`.

The #327 wrapper may use a plain `>` boundary only where the original value contains exactly one
U+0020 SPACE. At any other boundary it must avoid the break or use `>=` with the exact boundary
content. It must never convert a literal semantic newline into folded whitespace.

______________________________________________________________________

## Parsing rules

Parsing proceeds in this order:

1. Locate the processor-specific TopMark start and end marker span.
1. Exclude block wrappers and marker lines from the field payload.
1. Remove each physical line terminator.
1. Validate and remove processor line affixes.
1. Parse ordinary fields and explicit continuation records.
1. Reconstruct the complete semantic value.
1. Apply shared and processor-specific semantic validation.

An empty ordinary field is held provisionally. It becomes a literal field only when immediately
followed by at least two valid literal continuation records. With no continuation records, it
remains the existing ordinary empty value.

While consuming a scalar:

- a record with the same mode appends content;
- an opposite-mode record is malformed mixed-mode syntax;
- a new valid field closes the scalar and begins the next field;
- a layout blank or end marker closes a completed scalar; and
- any other payload line is malformed and is not appended.

Each successfully parsed scalar increments the success count once, regardless of its number of
physical records. Each malformed scalar contributes one field error.

Duplicate fields retain the existing last-occurrence-wins mapping behavior. Changing that behavior
is outside this contract and would change currently accepted single-line headers.

______________________________________________________________________

## Malformed input

Malformed continuation syntax uses the existing `MALFORMED_ALL_FIELDS`/`MALFORMED_SOME_FIELDS`
header statuses. Marker or span corruption continues to use terminal `MALFORMED`.

Implementations should provide stable diagnostics for:

| Condition                                                                            | Diagnostic code                         |
| ------------------------------------------------------------------------------------ | --------------------------------------- |
| Continuation without a pending empty field                                           | `header:orphan-continuation`            |
| Continuation after an ordinary scalar                                                | `header:continuation-after-scalar`      |
| Fewer than two continuation records                                                  | `header:scalar-too-short`               |
| Missing record content                                                               | `header:missing-continuation-body`      |
| Invalid exact-record quoting or escape                                               | `header:invalid-continuation-string`    |
| Invalid control or Unicode separator                                                 | `header:invalid-continuation-character` |
| Literal and folded records mixed                                                     | `header:mixed-scalar-mode`              |
| Folded syntax used before [#327](https://github.com/shutterfreak/topmark/issues/327) | `header:folded-reserved`                |
| Required processor affix missing                                                     | `header:invalid-continuation-affix`     |

Diagnostics identify safe field positions and physical line numbers without reproducing unsafe
payload content.

______________________________________________________________________

## Validation boundary

Structured multiline support relaxes only the current blanket rejection of LF in field values. Field
names remain single-line.

Complete reconstructed semantic values remain subject to:

- NUL and Unicode `Cc` control rejection;
- U+2028 and U+2029 rejection;
- reserved TopMark start and end marker rejection;
- C-block `*/` rejection;
- XML/HTML/Markdown `--` rejection; and
- custom processor semantic restrictions.

The renderer must split a semantic multiline value before applying comment syntax. It validates each
encoded physical payload line before adding processor affixes. No raw CR or LF may be passed to a
helper that renders one physical line, and every emitted line must receive the selected processor's
prefix, suffix, indentation, and physical newline.

Custom processors may add semantic and encoded-physical-line restrictions. They must not replace the
shared validation orchestration or define a conflicting continuation grammar while claiming
base-format compatibility.

______________________________________________________________________

## Built-in processor examples

### Pound comments

```text
# topmark:header:start
#
#   notice:
#     | First literal line.
#     | Second literal line.
#
# topmark:header:end
```

### Slash comments

```text
// topmark:header:start
//
//   notice:
//     | First literal line.
//     | Second literal line.
//
// topmark:header:end
```

### C block comments

```text
/*
 * topmark:header:start
 *
 *   notice:
 *     | First literal line.
 *     | Second literal line.
 *
 * topmark:header:end
 */
```

### Markdown comments

```text
<!--
topmark:header:start

  notice:
    | First literal line.
    | Second literal line.

topmark:header:end
-->
```

### XML and HTML comments

```text
<!--
topmark:header:start

  notice:
    | First literal line.
    | Second literal line.

topmark:header:end
-->
```

______________________________________________________________________

## Compatibility and versioning

No explicit header format version is required:

- ordinary `key: value` syntax is unchanged;
- values equal to or beginning with `|` or `>` remain ordinary;
- continuation records are recognized only after an empty field opener;
- incomplete or approximate matches remain malformed; and
- continuation mode is explicit rather than inferred from indentation.

The semantic mapping remains `Mapping[str, str]`. Literal or folded mode is presentation state:
literal mode follows from semantic LF, while folded mode follows from the explicit #327 wrapping
policy. Existing header and render views continue to own exact physical block text.

Comparison continues to check both reconstructed semantic mappings and canonical rendered block
text. Equivalent mappings with noncanonical continuation indentation or formatting may therefore
produce a formatting-only change and converge after replacement.

Stripping remains marker/span based and does not interpret continuation records.

______________________________________________________________________

## Implementation staging

Issue [#326](https://github.com/shutterfreak/topmark/issues/326) must:

- implement ordinary, plain literal, empty literal, and exact literal records;
- reserve and diagnose folded record tokens;
- normalize semantic line endings;
- validate complete values and encoded physical lines;
- count logical fields rather than continuation records;
- support every built-in processor family;
- preserve aligned, compact, and pre-prefix-indented headers;
- retain mapping, comparison, planning, stripping, and machine-output contracts; and
- prove insert, replace, check, strip, patch, and write idempotence.

Issue [#327](https://github.com/shutterfreak/topmark/issues/327) may then activate `>` and `>=`,
provided wrapping:

- is opt-in and deterministic;
- splits only at permitted boundaries;
- reconstructs the exact original logical value;
- includes all processor syntax and indentation in width measurement;
- does not hard-split unbreakable tokens by default; and
- never reinterprets literal semantic newlines as folded whitespace.

______________________________________________________________________

## Related documentation

- [Header placement](../usage/header-placement.md)
- [Getting started](../usage/getting-started.md)
- [Plugins and extensibility](plugins.md)
- [Pipelines](pipelines.md)
