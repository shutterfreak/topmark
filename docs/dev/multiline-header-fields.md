<!--
topmark:header:start

  project      : TopMark
  file         : multiline-header-fields.md
  file_relpath : docs/dev/multiline-header-fields.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Multiline header field rendering

This document defines the target rendering contract for TopMark fields that span multiple physical
header lines. It supersedes the literal-versus-folded serialization design introduced by issues
[#325](https://github.com/shutterfreak/topmark/issues/325),
[#326](https://github.com/shutterfreak/topmark/issues/326), and
[#327](https://github.com/shutterfreak/topmark/issues/327), and implemented by pull requests
[#329](https://github.com/shutterfreak/topmark/pull/329),
[#330](https://github.com/shutterfreak/topmark/pull/330),
[#331](https://github.com/shutterfreak/topmark/pull/331), and
[#332](https://github.com/shutterfreak/topmark/pull/332).

> [!NOTE]
>
> This is the design for [#339](https://github.com/shutterfreak/topmark/issues/339). It is
> intentionally documented before its implementation. No release contains the predecessor
> continuation feature, so this contract requires no public migration compatibility.

______________________________________________________________________

## Design principles

The effective TopMark configuration is the authoritative definition of the expected header for a
processed file. In particular, `[fields]` TOML values and effective formatting settings determine
the canonical output. The marker-delimited header in the processed file is a generated artifact:
TopMark compares it with the expected block and may replace it when the configured header-mutation
flow permits an update.

Consequently, generated continuation records do not need to independently reconstruct the original
multiline value. They need only be unambiguous enough to locate and safely recognize an existing
TopMark header.

This design:

- presents one continuation form to users instead of exposing literal versus folded semantics;
- lets authors format reflowable TOML prose for readability without preserving those physical line
  boundaries in the generated header;
- preserves paragraph boundaries for selected prose fields;
- retains deterministic, processor-aware physical-width wrapping; and
- keeps generated headers structurally readable.

> [!NOTE]
>
> `policy.allow_reflow` is not part of this contract. That policy controls reflow risk in
> source-file body placement, not the formatting or replacement of header fields.

______________________________________________________________________

## Canonical header grammar

TopMark retains ordinary single-line fields:

```text
#   project: TopMark
```

Multiline fields use an empty opener and pipe-prefixed continuation records:

```text
#   notice:
#     | First continuation line.
#     | Second continuation line.
```

A bare continuation pipe is a paragraph separator:

```text
#   notice:
#     | First paragraph.
#     |
#     | Second paragraph.
```

Ignoring processor affixes, the relevant grammar is:

```text
ordinary-field = field-name, padding, ":", " ", ordinary-content ;
multiline-field = field-name, padding, ":", line-end,
                  continuation, { line-end, continuation } ;
continuation = layout-indent, "|", [ " ", continuation-content ] ;
```

A continuation must immediately follow an empty field opener or another continuation belonging to
that opener. An ordinary `field-name: value` line starts a new field. The pipe is not part of the
ordinary field grammar, so prose such as `Note: read the documentation` cannot be mistaken for a new
header field. Content may itself begin with a pipe:

```text
#     | |important detail
```

The first pipe is structural; the second is rendered content. The marker carries no literal, folded,
or whitespace-decoding meaning.

______________________________________________________________________

## TOML multiline values

The rules below apply to custom `[fields]` TOML multiline strings after TOML parsing and newline
normalization. They intentionally make TOML authoring layout distinct from rendered-header layout.

### Boundary blank lines

TopMark removes leading and trailing blank logical lines from a TOML multiline field value. This
avoids emitting accidental blank continuations caused by positioning triple-quote delimiters.

This normalization applies to TOML field values only. API overrides, plugin values, and derived
values remain explicit runtime inputs and are not silently trimmed by this TOML-specific rule.

### Unselected multiline fields

A multiline field absent from `formatting.wrap_fields` preserves each remaining logical line as a
pipe continuation. A blank logical line renders as a bare pipe. Its author-selected physical line
boundaries therefore remain visible.

```toml
[fields]
info = """
Line one.
Line two.
"""
```

```text
#   info:
#     | Line one.
#     | Line two.
```

### Selected prose fields

When a field is selected by `formatting.wrap_fields`, TopMark treats its TOML multiline value as
prose:

1. A run of one or more blank logical lines separates paragraphs.
1. Within a paragraph, each nonblank line is trimmed at its boundary and adjacent lines are joined
   with one U+0020 SPACE.
1. Each resulting paragraph is wrapped independently when `max_header_line_length` is set.
1. One bare pipe separates rendered paragraphs.

Thus, a single long TOML line, pre-wrapped TOML lines, and overlong TOML lines result in the same
canonical output for the same resolved configuration.

```toml
[fields]
notice = """
First paragraph written across
several convenient TOML lines.

Second paragraph.
"""

[formatting]
max_header_line_length = 60
wrap_fields = ["notice"]
```

```text
#   notice:
#     | First paragraph written across several convenient
#     | TOML lines.
#     |
#     | Second paragraph.
```

This prose interpretation belongs to selected TOML fields. It is not inferred from the layout of an
existing header and is not applied to unselected fields.

______________________________________________________________________

## Wrapping policy

The existing stable configuration keys retain their names and layering behavior:

```toml
[formatting]
max_header_line_length = 100
wrap_fields = ["notice", "copyright"]
```

Automatic prose wrapping is active for a field only when both conditions hold:

1. `max_header_line_length` is a positive integer; and
1. the field occurs in `wrap_fields`.

`wrap_fields` remains an ordered, deduplicated allowlist with an effective default of empty. A
present empty list clears an inherited selection. An unknown but valid field name remains inert.

The width is a soft target measured in Unicode code points across the complete physical line,
including preserved indentation, processor affixes, continuation indentation, the pipe marker, and
any processor suffix. Line terminators are excluded. TopMark wraps only at prose spaces and never
hard-splits unbreakable text such as URLs, paths, hashes, or identifiers. A long unbreakable
fragment may therefore exceed the target.

Selected values that fit on an ordinary `field: value` line remain ordinary single-line fields. The
multiline continuation form is used when a selected prose value needs more than one rendered line or
when a selected TOML value contains paragraph boundaries.

______________________________________________________________________

## Canonical rendering and updates

Canonical output is derived from the resolved field value, field selection, width, alignment,
processor affixes, preserved indentation, and target newline style. It is not derived from prior
continuation boundaries in the file.

When an existing marker-delimited header differs from the expected canonical block, normal
header-mutation configuration determines whether TopMark reports or writes the change. A permitted
update may therefore reflow a field after a width, allowlist, alignment, indentation, processor, or
TOML-layout change.

The field-formatting contract is intentionally separate from `policy.allow_reflow`: updating a
header block does not authorize reflowing adjacent source-file body content.

______________________________________________________________________

## Processor compatibility

Custom processors that use the base header format must accept the shared pipe-continuation grammar,
apply their comment affixes to every continuation line, and leave canonical field rendering to the
base implementation. A processor that deliberately replaces the complete header renderer is outside
this compatibility guarantee.

______________________________________________________________________

## Validation requirements

The implementation and its tests must verify:

- blank TOML delimiter layout does not create leading or trailing rendered paragraphs;
- pre-wrapped, overlong, and single-line selected TOML prose render identically;
- paragraph boundaries are retained and each paragraph wraps independently;
- content containing a colon cannot be parsed as a new field;
- unselected multiline values retain their logical-line layout through pipe continuations;
- all built-in processors apply affixes and width measurement to continuation lines;
- a successful application converges on one canonical header block.
