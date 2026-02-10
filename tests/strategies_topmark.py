# topmark:header:start
#
#   project      : TopMark
#   file         : strategies_topmark.py
#   file_relpath : tests/strategies_topmark.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# pyright: strict

"""Hypothesis strategies for generating TopMark-like files and header shapes.

These utilities intentionally *approximate* TopMark’s real renderers so property
tests can explore a wide but bounded input space without exploding combinations.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from hypothesis import strategies as st

Draw = Callable[[st.SearchStrategy[Any]], Any]

# --- ADAPT ME: import your public types/APIs here ---
# from topmark.header.processing import HeaderProcessor  # example
# from topmark.resolver import resolve_processor_for_path
# from topmark.builder import build_header_dict, build_header_text
# from topmark.scanner import scan_header_bounds
# from topmark.updater import update_or_insert_header
# from topmark.comparer import compare_rendered_or_dict
# from topmark.config import TopmarkConfig

# Common file type “families” you support
CommentFamily = Literal["pound", "slash", "xml", "cblock", "plain"]

SHEBANGS: tuple[str, ...] = (
    "#!/usr/bin/env bash",
    "#!/usr/bin/env sh",
    "#!/usr/bin/env python3",
)
BOMS: tuple[str, ...] = ("\ufeff", "")  # UTF-8 BOM or none

LINE_ENDINGS: tuple[str, ...] = ("\n", "\r\n")

BLACKLIST_CATEGORIES: tuple[Literal["Cs"], ...] = ("Cs",)


# Typical comment styles your processors handle
@dataclass(frozen=True)
class CommentStyle:
    """Minimal comment style descriptor used by the synthetic renderer."""

    family: CommentFamily
    line_prefix: str
    block_prefix: str | None = None
    block_suffix: str | None = None


POUND = CommentStyle("pound", "# ")
SLASH = CommentStyle("slash", "// ")
XML = CommentStyle("xml", "", "<!--", "-->")
CBLOCK = CommentStyle("cblock", " * ", "/*", " */")
PLAIN = CommentStyle("plain", "")  # e.g. Markdown where headers are raw blocks

COMMENT_STYLES: tuple[CommentStyle, ...] = (
    POUND,
    SLASH,
    XML,
    CBLOCK,
    PLAIN,
)


def _normalize_eol(s: str, le: str) -> str:
    """Normalize all end-of-line markers in ``s`` to ``le``."""
    # First collapse CRLF and lone CR to LF, then map LF to target `le`
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    if le != "\n":
        s = s.replace("\n", le)
    return s


def _merge_fields(core: dict[str, str], extra: dict[str, str]) -> dict[str, str]:
    merged: dict[str, str] = {**core, **extra}
    return merged


# Strategy: plausible TopMark header dicts
def s_header_fields() -> st.SearchStrategy[dict[str, str]]:
    """Header dicts roughly matching TopMark fields, plus rare extras."""
    # Match your config fields: project, file, license, copyright
    # Include optional fields, random ordering, whitespace jitter.
    base: st.SearchStrategy[dict[str, str]] = st.fixed_dictionaries(
        {
            "project": st.text(min_size=1, max_size=24),
            "file": st.from_regex(r"[A-Za-z0-9_\-./]+", fullmatch=True),
            "license": st.sampled_from(["MIT", "Apache-2.0", "BSD-3-Clause"]),
            "copyright": st.text(min_size=4, max_size=64),
        }
    )
    # Optionally sprinkle 1-2 unknown fields to test robustness
    extras: st.SearchStrategy[dict[str, str]] = st.dictionaries(
        keys=st.from_regex(r"[a-z]{3,10}", fullmatch=True),
        values=st.text(min_size=1, max_size=32),
        max_size=2,
    )
    return st.builds(_merge_fields, base, extras)


# Strategy: source file envelope with shebang/BOM, pre/post text, and comment style
@st.composite
def s_source_envelope(draw: Draw) -> tuple[str, CommentStyle, str]:
    """Generate a simple file envelope: BOM, optional shebang, junk, body."""
    bom: str = draw(st.sampled_from(BOMS))
    shebang: str = draw(st.sampled_from(SHEBANGS + ("",)))
    style: CommentStyle = draw(st.sampled_from(COMMENT_STYLES))
    le: str = draw(st.sampled_from(LINE_ENDINGS))
    pre_junk: str = draw(
        st.text(
            alphabet=st.characters(blacklist_categories=BLACKLIST_CATEGORIES, max_codepoint=0x00FF),
            min_size=0,
            max_size=30,
        )
    )
    body: str = draw(
        st.text(
            alphabet=st.characters(blacklist_categories=BLACKLIST_CATEGORIES, max_codepoint=0x00FF),
            min_size=0,
            max_size=120,
        )
    )
    # Compose a plausible file:
    # [BOM][shebang?]\n[pre_junk]\n[<maybe some comments>]\n<body]\n
    lead: str = ""
    if bom:
        lead += bom
    if shebang:
        lead += shebang + le
    if pre_junk:
        lead += pre_junk.rstrip("\n\r") + le
    if body and not body.endswith(("\n", "\r", "\r\n")):
        body = body + le
    content: str = lead + body
    return content, style, le


# --- Extension-aware source generator ---------------------------------------
@st.composite
def s_source_envelope_for_ext(
    draw: Draw, exts: Sequence[str] | None = None
) -> tuple[str, CommentStyle, str, str]:
    """Generate content consistent with the chosen file extension.

    Args:
        draw: Hypothesis draw function.
        exts: Optional list of file extensions to choose from.

    Returns:
        Generated content, comment style, line ending, and file extension.

    Note: content may be empty or contain no header block.
    """
    if exts is None:
        exts = (".py", ".sh", ".js", ".ts", ".cpp", ".h", ".xml", ".html")
    ext: str = draw(st.sampled_from(tuple(exts)))

    # Shared knobs
    le: str = draw(st.sampled_from(LINE_ENDINGS))
    bom: str = draw(st.sampled_from(BOMS))

    if ext in (".xml", ".html", ".svg", ".xhtml", ".xsl", ".xslt"):
        # XML/HTML-like: no shebang; optional XML decl; ensure tag-first if non-empty
        maybe_decl: bool = draw(st.booleans())
        decl: str = '<?xml version="1.0"?>' + le if maybe_decl else ""

        pre_junk: str = draw(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=BLACKLIST_CATEGORIES, max_codepoint=0x00FF
                ),
                min_size=0,
                max_size=30,
            )
        ).rstrip("\r\n")

        body: str = draw(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=BLACKLIST_CATEGORIES, max_codepoint=0x00FF
                ),
                min_size=0,
                max_size=120,
            )
        )
        if body and not body.endswith(("\n", "\r", "\r\n")):
            body = body + le

        lead: str = (bom or "") + decl
        if pre_junk:
            lead += pre_junk + le

        content: str = lead + body
        head_len: int = len(content) - len(content.lstrip("\ufeff\r\n\t "))
        tail: str = content[head_len:]
        if tail and not tail.lstrip().startswith("<"):
            # Wrap arbitrary text to keep XML processor assumptions valid
            content = content[:head_len] + f"<root>{tail}</root>\n"
        content = _normalize_eol(content, le)
        style: CommentStyle = XML

    elif ext in (".py", ".sh"):
        # Shell/Python: shebang optional
        shebang: str = draw(st.sampled_from(SHEBANGS + ("",)))
        pre_junk = draw(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=BLACKLIST_CATEGORIES, max_codepoint=0x00FF
                ),
                min_size=0,
                max_size=30,
            )
        ).rstrip("\r\n")
        body = draw(
            st.text(
                alphabet=st.characters(
                    blacklist_categories=BLACKLIST_CATEGORIES, max_codepoint=0x00FF
                ),
                min_size=0,
                max_size=120,
            )
        )
        if body and not body.endswith(("\n", "\r", "\r\n")):
            body = body + le

        # Shebang must be the first bytes in the file. If a shebang is present,
        # suppress BOM to avoid generating invalid envelopes that our pipeline
        # (correctly) refuses to modify under strict policy.
        safe_bom: str = "" if shebang else (bom or "")
        lead = safe_bom + (shebang + le if shebang else "")
        if pre_junk:
            lead += pre_junk + le
        content = lead + body
        content = _normalize_eol(content, le)
        style = POUND

    else:
        # C/JS-like: no shebang by default
        pre_junk = draw(
            st.text(
                alphabet=st.characters(blacklist_categories=BLACKLIST_CATEGORIES),
                min_size=0,
                max_size=60,
            )
        ).rstrip("\r\n")
        body = draw(
            st.text(
                alphabet=st.characters(blacklist_categories=BLACKLIST_CATEGORIES),
                min_size=0,
                max_size=200,
            )
        )
        if body and not body.endswith(("\n", "\r", "\r\n")):
            body = body + le

        lead = bom or ""
        if pre_junk:
            lead += pre_junk + le
        content = lead + body
        content = _normalize_eol(content, le)
        style = SLASH

    return content, style, le, ext


# Text rendering helper for a TopMark-like header block
def render_header_block(style: CommentStyle, le: str, fields: dict[str, str]) -> str:
    """Render a neutral, simplified header block for property tests.

    Property tests should still prefer the *real* renderer in snapshot tests.
    """

    def line(k: str, v: str) -> str:
        core: str = f"{k:<12} : {v}"
        if style.family == "xml":
            assert style.block_prefix is not None and style.block_suffix is not None
            return f"{style.block_prefix} {core} {style.block_suffix}{le}"
        if style.family == "pound":
            return f"{style.line_prefix}{core}{le}"
        if style.family == "slash":
            return f"{style.line_prefix}{core}{le}"
        # plain block
        return f"{core}{le}"

    lines: list[str] = [line(k, v) for k, v in fields.items()]
    if style.family == "xml":
        return "".join(lines)
    return "".join(lines)


# Strategy: files that already contain “near headers”
# (extra/missing fields, odd spacing)
@st.composite
def s_file_with_near_header(draw: Draw) -> tuple[str, CommentStyle, str, dict[str, str]]:
    """Generate files with a header-like block that can be malformed/partial."""
    content: str
    style: CommentStyle
    le: str
    content, style, le = draw(s_source_envelope())
    fields: dict[str, str] = draw(s_header_fields())
    # Reorder or drop a key to create a malformed or partial header
    keys: list[str] = list(fields.keys())
    if len(keys) > 2 and draw(st.booleans()):
        keys.pop(0)
    if keys:
        shuffled: Sequence[str] = draw(st.permutations(keys))
    else:
        shuffled = ()
    near_fields: dict[str, str] = {k: fields[k] for k in shuffled} if shuffled else fields
    hdr: str = render_header_block(style, le, near_fields)
    # Insert somewhere near top (after shebang/BOM)
    lines: list[str] = content.splitlines(keepends=True)
    insert_at: int = 0
    if lines and lines[0].startswith("#!"):
        insert_at = 1
    new_content: str = "".join(lines[:insert_at] + [hdr] + lines[insert_at:])
    return new_content, style, le, fields
