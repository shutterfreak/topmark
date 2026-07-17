# topmark:header:start
#
#   project      : TopMark
#   file         : test_xml.py
#   file_relpath : tests/processors/test_xml.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the XmlHeaderProcessor (HTML/XML-style ``<!-- ... -->`` comments).

Exercises placement rules for HTML, XML (with declaration and DOCTYPE), SVG,
and component templates (Vue, Svelte). Also validates idempotency and `strip_header_block` behavior
 including preservation of the XML declaration.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import expected_block_lines_for
from tests.helpers.pipeline import find_line
from tests.helpers.pipeline import make_pipeline_context
from tests.helpers.pipeline import materialize_updated_lines
from tests.helpers.pipeline import run_insert
from tests.helpers.registry import make_file_type
from tests.helpers.registry import resolve_processor_for_path
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.core.logging import get_logger
from topmark.filetypes.model import InsertCapability
from topmark.filetypes.policy import FileTypeHeaderPolicy
from topmark.pipeline import runner
from topmark.pipeline.pipelines import Pipeline
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import ContentStatus
from topmark.pipeline.status import GenerationStatus
from topmark.pipeline.status import ResolveStatus
from topmark.processors.builtins.xml import XmlHeaderProcessor
from topmark.processors.types import StripDiagKind

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from tests.helpers.pipeline import BlockSignatures
    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.core.logging import TopmarkLogger
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.pipeline.protocols import Step
    from topmark.processors.base import HeaderProcessor
    from topmark.processors.types import StripHeaderResult


logger: TopmarkLogger = get_logger(__name__)


def _xml_processor_with_policy(*, ensure_blank_after_header: bool) -> XmlHeaderProcessor:
    """Create an XML processor with a deterministic test header policy."""
    processor = XmlHeaderProcessor()
    processor.file_type = make_file_type(
        local_key="xml-test",
        namespace="test",
        header_policy=FileTypeHeaderPolicy(
            ensure_blank_after_header=ensure_blank_after_header,
        ),
    )
    return processor


def test_xml_processor_basics(tmp_path: Path) -> None:
    """Basic detection and scan.

    Creates an HTML file without a TopMark block; the scanner should report no
    existing header and resolve the file type to HTML.
    """
    # Create a sample file with html-prefixed comments
    file: Path = tmp_path / "sample.html"
    file.write_text("<html>\n<body><p>Hello.</p></body></html>")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = make_pipeline_context(file, cfg)

    pipeline: Sequence[Step[ProcessingContext]] = Pipeline.CHECK.steps
    ctx = runner.run(ctx, pipeline)

    assert ctx.path == file
    assert ctx.file_type and ctx.file_type.local_key == "html"
    assert ctx.views.image is not None
    assert ctx.views.header is None


def test_html_top_of_file_with_trailing_blank(tmp_path: Path) -> None:
    """Insert header at the very top of plain HTML and keep a trailing blank.

    Verifies that the block-open lands at index 0 and that a single blank line
    follows the closing marker for readability.
    """
    file: Path = tmp_path / "index.html"
    file.write_text("<!DOCTYPE html>\n<html></html>\n")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    logger.debug("ctx.updated_file_lines: %s", lines)
    sig: BlockSignatures = expected_block_lines_for(file)
    if "block_open" in sig:
        open_idx: int = find_line(lines, sig["block_open"])
        assert open_idx == 0
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 1
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


def test_xml_with_declaration_only(tmp_path: Path) -> None:
    """XML with only a declaration: insert after declaration (+1 blank).

    Ensures the XML declaration remains line 0 and the header follows after a
    single blank separator.
    """
    file: Path = tmp_path / "doc.xml"
    file.write_text('<?xml version="1.0"?>\n<root/>\n')

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)
    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        open_idx: int = find_line(lines, sig["block_open"])
        assert open_idx == 2
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 3
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


def test_xml_with_declaration_and_doctype(tmp_path: Path) -> None:
    """XML with declaration + DOCTYPE: insert after both (+1 blank).

    Asserts correct placement of the block-open/start after the prolog elements
    and a single blank line.
    """
    file: Path = tmp_path / "doc2.xml"
    file.write_text('<?xml version="1.0"?>\n<!DOCTYPE note SYSTEM "Note.dtd">\n<note/>\n')

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)
    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        open_idx: int = find_line(lines, sig["block_open"])
        assert open_idx == 3
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 4
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


def test_svg_with_declaration(tmp_path: Path) -> None:
    """SVG (XML) with declaration: insert after declaration (+1 blank).

    Mirrors the XML behavior for SVG files.
    """
    file: Path = tmp_path / "icon.svg"
    file.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"></svg>\n'
    )

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)
    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        open_idx: int = find_line(lines, sig["block_open"])
        assert open_idx == 2
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 3


def test_vue_top_of_file(tmp_path: Path) -> None:
    """Vue SFC behaves like HTML: header at top with trailing blank.

    Uses HTML-style comments for the header block.
    """
    file: Path = tmp_path / "App.vue"
    file.write_text("<template>\n  <div/>\n</template>\n")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


def test_svelte_top_of_file(tmp_path: Path) -> None:
    """Svelte component behaves like HTML: header at top with trailing blank.

    Uses HTML-style comments for the header block.
    """
    file: Path = tmp_path / "Widget.svelte"
    file.write_text("<script>\n  let x = 1;\n</script>\n")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


def test_xml_single_line_declaration(tmp_path: Path) -> None:
    """Declaration and root on one line: insert after decl (+1 blank).

    Verifies that char-offset insertion splits the line after the declaration,
    inserts a blank, then the header block. Don't write to file, compare the
    image lines and updated lines.
    """
    file: Path = tmp_path / "singleline_decl.xml"
    # No newline between declaration and root element
    file.write_text('<?xml version="1.0"?><root/>\n')

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    # Strict XML InsertChecker flags this as unsupported due to reflow:
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.pre_insert_capability == InsertCapability.SKIP_IDEMPOTENCE_RISK
    assert ctx.status.content == ContentStatus.SKIPPED_REFLOW
    assert ctx.is_halted is True


def test_xml_prolog_and_body_on_same_line_blocked_by_policy(tmp_path: Path) -> None:
    """XML prolog and body on same line would reflow, blocked by policy."""
    file: Path = tmp_path / "one.xml"
    original = '<?xml version="1.0"?><root/>'  # no trailing newline
    file.write_text(original, encoding="utf-8")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    # Strict XML InsertChecker flags this as unsupported due to reflow:
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.pre_insert_capability == InsertCapability.SKIP_IDEMPOTENCE_RISK
    assert ctx.status.content == ContentStatus.SKIPPED_REFLOW
    assert ctx.is_halted is True


@pytest.mark.parametrize(
    "separator, label",
    [
        ("\x85", "nel"),
        ("\u2028", "line_separator"),
        ("\u2029", "paragraph_separator"),
    ],
)
def test_xml_prolog_and_body_separated_by_exotic_separator_blocked_by_policy(
    tmp_path: Path, separator: str, label: str
) -> None:
    """XML NEL/LS/PS near the insertion boundary is an idempotence risk."""
    file: Path = tmp_path / f"xml_exotic_separator_{label}.xml"
    original: str = f'<?xml version="1.0"?>{separator}<root/>'
    file.write_text(original, encoding="utf-8", newline="")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.pre_insert_capability == InsertCapability.SKIP_IDEMPOTENCE_RISK
    assert ctx.status.content == ContentStatus.SKIPPED_REFLOW
    assert ctx.is_halted is True
    assert ctx.newline_style == "\n"
    assert ctx.newline_hist == {}


def test_xml_prolog_and_body_on_same_line_alllowed_by_policy(tmp_path: Path) -> None:
    """XML prolog and body on same line would reflow, allowed by policy."""
    file: Path = tmp_path / "one.xml"
    original = '<?xml version="1.0"?><root/>'  # no trailing newline
    file.write_text(original, encoding="utf-8")

    draft: MutableConfig = mutable_config_from_defaults()
    draft.policy.allow_reflow = True
    cfg: FrozenConfig = draft.freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    after_insert: str = "".join(lines)

    assert ctx.status.generation == GenerationStatus.GENERATED
    assert ctx.status.comparison == ComparisonStatus.CHANGED
    assert any(TOPMARK_START_MARKER in line for line in lines)

    proc: HeaderProcessor | None = resolve_processor_for_path(path=file)
    assert proc is not None

    lines = after_insert.splitlines(keepends=True)
    strip_result: StripHeaderResult = proc.strip_header_block(
        lines=lines,
        span=None,
        newline_style=ctx.newline_style,  # from ProcessingContext
        ends_with_newline=False,  # original was single-line without FNL
    )
    assert strip_result.diagnostic.kind == StripDiagKind.REMOVED

    roundtrip: str = "".join(strip_result.lines)

    # Assert that original and roundtrip only differ in white space
    # The re.sub(r'\s+', '', ...) function removes all whitespace characters
    # (space, tab, newline, etc.) from both strings before comparison.
    assert re.sub(r"\s+", "", original) == re.sub(r"\s+", "", roundtrip)


def test_xml_single_line_decl_and_doctype(tmp_path: Path) -> None:
    """Declaration + DOCTYPE + root on one line: insert after prolog (+1 blank).

    Confirms correct splitting and placement when both declaration and DOCTYPE
    precede the root on the same physical line. Don't write to file, compare the
    image lines and updated lines.
    """
    file: Path = tmp_path / "singleline_decl_doctype.xml"
    # XML declaration, DOCTYPE, and root all on a single line
    file.write_text('<?xml version="1.0"?><!DOCTYPE note SYSTEM "Note.dtd"><note/>\n')

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    # Strict XML InsertChecker flags this as unsupported due to reflow:
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.pre_insert_capability == InsertCapability.SKIP_IDEMPOTENCE_RISK
    assert ctx.status.content == ContentStatus.SKIPPED_REFLOW
    assert ctx.is_halted is True


def test_html_with_existing_banner_comment(tmp_path: Path) -> None:
    """Header must precede any pre-existing banner comment in HTML.

    Ensures the TopMark block is inserted first and the previous banner follows
    after the block close.
    """
    file: Path = tmp_path / "banner.html"
    file.write_text("<!-- existing:license banner -->\n<html></html>\n")

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)

    # Header must start at very top
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1

    # The pre-existing banner should appear after the TopMark header block
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines)
        # First non-TopMark comment line should be the banner
        banner_idx: int = find_line(lines, "<!-- existing:license banner -->")
        assert banner_idx > close_idx


def test_xml_decl_then_existing_banner_comment(tmp_path: Path) -> None:
    """XML with declaration and a banner: header after decl, before banner.

    Validates that the header is anchored after the XML declaration and precedes
    the existing banner comment.
    """
    file: Path = tmp_path / "doc_with_banner.xml"
    file.write_text('<?xml version="1.0"?>\n<!-- xml:banner -->\n<root/>\n')

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)

    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 2
    assert find_line(lines, sig["start_line"]) == 3

    # Ensure banner comes AFTER the TopMark header block
    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        banner_idx: int = find_line(lines, "<!-- xml:banner -->")
        assert banner_idx > close_idx


def test_xml_decl_doctype_then_existing_banner_comment(tmp_path: Path) -> None:
    """XML with declaration + DOCTYPE and a banner: header after prolog.

    Ensures the header is placed after the declaration and DOCTYPE but before the
    banner comment.
    """
    file: Path = tmp_path / "doc_with_prolog_banner.xml"
    file.write_text(
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE note SYSTEM "Note.dtd">\n'
        "<!-- xml:prolog-banner -->\n"
        "<note/>\n"
    )

    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)

    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 3
    assert find_line(lines, sig["start_line"]) == 4

    if "block_close" in sig:
        close_idx: int = find_line(lines, sig["block_close"])
        banner_idx: int = find_line(lines, "<!-- xml:prolog-banner -->")
        assert banner_idx > close_idx


# --- strip_header_block: test XML declaration is preserved, header is removed ---


def test_xml_strip_header_block_respects_declaration(tmp_path: Path) -> None:
    """`strip_header_block` removes the header and preserves the XML declaration.

    Exercises both explicit-span and auto-detect paths and asserts identical
    results with the declaration retained as the first logical line.
    """
    file: Path = tmp_path / "strip_doc.xml"
    file.write_text(
        '<?xml version="1.0"?>\n'
        f"<!-- {TOPMARK_START_MARKER} -->\n"
        "<!-- h -->\n"
        f"<!-- {TOPMARK_END_MARKER} -->\n"
        "<root/>\n",
        encoding="utf-8",
    )

    proc: HeaderProcessor | None = resolve_processor_for_path(path=file)
    assert proc is not None

    lines: list[str] = file.read_text(encoding="utf-8").splitlines(keepends=True)

    # 1) With explicit span for the HTML-style comment block
    strip_result_1: StripHeaderResult = proc.strip_header_block(lines=lines, span=(1, 3))
    assert strip_result_1.diagnostic.kind == StripDiagKind.REMOVED
    assert strip_result_1.lines[0].lstrip("\ufeff").startswith("<?xml"), (
        "XML declaration must remain"
    )
    assert TOPMARK_START_MARKER not in "".join(strip_result_1.lines)
    assert strip_result_1.removed_span == (1, 3)

    # 2) Let the processor detect bounds itself
    strip_result_2: StripHeaderResult = proc.strip_header_block(lines=lines)
    # Declaration must remain identical on the auto-detect path as well
    assert strip_result_2.diagnostic.kind == StripDiagKind.REMOVED
    assert strip_result_2.lines[0].lstrip("\ufeff").startswith("<?xml"), (
        "XML declaration must remain (auto-detect)"
    )
    assert strip_result_2.lines == strip_result_1.lines
    assert strip_result_2.removed_span == (1, 3)


def test_xml_doctype_with_long_internal_subset(tmp_path: Path) -> None:
    """DOCTYPE with a long internal subset is respected.

    Confirms header insertion occurs after the declaration and the entirety of the
    multi-line DOCTYPE without relying on a bounded line look-back.
    """
    file: Path = tmp_path / "subset.xml"
    doctype_lines: list[str] = [
        "<!DOCTYPE root [\n",
        "  <!ELEMENT root EMPTY>\n",
        "  <!ENTITY one '1'>\n",
        "  <!ENTITY two '2'>\n",
        "  <!ENTITY three '3'>\n",
        "  <!ENTITY four '4'>\n",
        "]>\n",
    ]
    file.write_text('<?xml version="1.0"?>\n' + "".join(doctype_lines) + "<root/>\n")
    cfg: FrozenConfig = mutable_config_from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)
    lines: list[str] = materialize_updated_lines(ctx)

    assert lines[0].lstrip("\ufeff").startswith("<?xml")

    # Header begins after declaration + complete doctype + one owned blank.
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])

    assert lines[1:8] == doctype_lines
    assert lines[8] == "\n"
    assert "block_open" in sig
    assert lines[9].rstrip("\r\n") == sig["block_open"]
    assert start_idx == 10


def test_xml_legacy_header_inside_internal_subset_is_removed_then_reinserted(
    tmp_path: Path,
) -> None:
    """A legacy misplaced header is recoverable without damaging the DOCTYPE."""
    file: Path = tmp_path / "legacy-subset.xml"
    lines: list[str] = [
        '<?xml version="1.0"?>\n',
        "<!DOCTYPE root [\n",
        "  <!ELEMENT root EMPTY>\n",
        "<!--\n",
        f"{TOPMARK_START_MARKER}\n",
        "\n",
        "  file: legacy-subset.xml\n",
        "\n",
        f"{TOPMARK_END_MARKER}\n",
        "-->\n",
        "\n",
        "  <!ENTITY example 'value'>\n",
        "]>\n",
        "<root/>\n",
    ]
    original: list[str] = list(lines)
    file.write_text("".join(lines))
    processor: HeaderProcessor | None = resolve_processor_for_path(path=file)
    assert processor is not None

    stripped: StripHeaderResult = processor.strip_header_block(lines=lines)

    assert lines == original
    assert stripped.diagnostic.kind is StripDiagKind.REMOVED
    assert stripped.removed_span == (3, 9)
    assert stripped.lines == [*original[:3], *original[11:]]

    file.write_text("".join(stripped.lines))
    updated: list[str] = materialize_updated_lines(
        run_insert(file, mutable_config_from_defaults().freeze())
    )
    doctype_end: int = updated.index("]>\n")
    start_idx: int = find_line(updated, expected_block_lines_for(file)["start_line"])
    root_idx: int = updated.index("<root/>\n")

    assert updated[1:5] == [
        "<!DOCTYPE root [\n",
        "  <!ELEMENT root EMPTY>\n",
        "  <!ENTITY example 'value'>\n",
        "]>\n",
    ]
    assert doctype_end < start_idx < root_idx


def test_xml_strip_without_header_is_an_identity_noop() -> None:
    """XML-specific cleanup does not copy or annotate an absent-header result."""
    processor = XmlHeaderProcessor()
    lines: list[str] = ["<root/>\n"]

    result: StripHeaderResult = processor.strip_header_block(lines=lines)

    assert result.lines is lines
    assert result.removed_span is None
    assert result.diagnostic.kind is StripDiagKind.NOT_FOUND
    assert result.diagnostic.notes == []


def test_xml_bom_preserved_text_insert(tmp_path: Path) -> None:
    """Ensure XML processor preserves BOM on text-insert path.

    Writes an XML file that begins with a UTF-8 BOM and verifies that, after the
    header is inserted via the XML processor's text-based insertion path, the BOM
    remains at the start of the first output line.

    Args:
        tmp_path: Temporary directory provided by pytest.
    """
    file: Path = tmp_path / "bom.xml"
    file.write_bytes(b"\xef\xbb\xbf<?xml version='1.0'?>\n<root/>\n")
    ctx: ProcessingContext = run_insert(file, mutable_config_from_defaults().freeze())

    updated_lines: list[str] = materialize_updated_lines(ctx)

    assert updated_lines[0].startswith("\ufeff")


def test_xml_processor_respects_prolog_and_removes_block() -> None:
    """Header block removal while preserving `<?xml ...?>` prolog line."""
    xp = XmlHeaderProcessor()
    # TODO use the pipeline instead!
    lines: list[str] = [
        '<?xml version="1.0"?>\n',
        f"<!-- {TOPMARK_START_MARKER} -->\n",
        "<!-- h -->\n",
        f"<!-- {TOPMARK_END_MARKER} -->\n",
        "<root/>\n",
    ]

    strip_result: StripHeaderResult = xp.strip_header_block(lines=lines, span=(1, 3))

    assert strip_result.diagnostic.kind == StripDiagKind.REMOVED
    body: str = "".join(strip_result.lines)

    assert body.startswith("<?xml")
    assert "<root/>" in body
    assert f"<!-- {TOPMARK_START_MARKER} -->" not in body
    assert strip_result.removed_span == (1, 3)


def test_xml_strip_removes_exactly_one_policy_spacer_after_header() -> None:
    """XML strip should remove adjacent policy spacers after a removed header."""
    processor: XmlHeaderProcessor = _xml_processor_with_policy(
        ensure_blank_after_header=True,
    )
    lines: list[str] = [
        '<?xml version="1.0"?>\n',
        f"<!-- {TOPMARK_START_MARKER} -->\n",
        "<!-- h -->\n",
        f"<!-- {TOPMARK_END_MARKER} -->\n",
        "\n",
        "\n",
        "<root/>\n",
    ]

    strip_result: StripHeaderResult = processor.strip_header_block(
        lines=lines,
        span=(1, 3),
        newline_style="\n",
        ends_with_newline=True,
    )

    assert strip_result.diagnostic.kind == StripDiagKind.REMOVED
    assert strip_result.removed_span == (1, 3)
    assert strip_result.lines == [
        '<?xml version="1.0"?>\n',
        "<root/>\n",
    ]
    assert strip_result.diagnostic.notes == ["xml: removed one trailing spacer per policy"]


def test_xml_strip_preserves_pre_header_blank_while_trimming_policy_spacer() -> None:
    """XML strip should preserve pre-existing blank lines before the header."""
    processor: XmlHeaderProcessor = _xml_processor_with_policy(
        ensure_blank_after_header=True,
    )
    lines: list[str] = [
        '<?xml version="1.0"?>\n',
        "\n",
        f"<!-- {TOPMARK_START_MARKER} -->\n",
        "<!-- h -->\n",
        f"<!-- {TOPMARK_END_MARKER} -->\n",
        "\n",
        "<root/>\n",
    ]

    strip_result = processor.strip_header_block(
        lines=lines,
        span=(2, 4),
        newline_style="\n",
        ends_with_newline=True,
    )

    assert strip_result.diagnostic.kind == StripDiagKind.REMOVED
    assert strip_result.removed_span == (2, 4)
    assert strip_result.lines == [
        '<?xml version="1.0"?>\n',
        "\n",
        "<root/>\n",
    ]


def test_xml_strip_disabled_blank_policy_preserves_trailing_spacer() -> None:
    """XML strip should preserve base strip behavior when blank policy is disabled."""
    processor: XmlHeaderProcessor = _xml_processor_with_policy(
        ensure_blank_after_header=False,
    )
    lines: list[str] = [
        '<?xml version="1.0"?>\n',
        f"<!-- {TOPMARK_START_MARKER} -->\n",
        "<!-- h -->\n",
        f"<!-- {TOPMARK_END_MARKER} -->\n",
        "\n",
        "<root/>\n",
    ]

    strip_result: StripHeaderResult = processor.strip_header_block(
        lines=lines,
        span=(1, 3),
        newline_style="\n",
        ends_with_newline=True,
    )

    assert strip_result.diagnostic.kind == StripDiagKind.REMOVED
    assert strip_result.removed_span == (1, 3)
    assert strip_result.lines == [
        '<?xml version="1.0"?>\n',
        "<root/>\n",
    ]
    assert strip_result.diagnostic.notes == []


def test_xml_strip_at_eof_does_not_report_spacer_cleanup() -> None:
    """XML strip at EOF should not report policy-spacer cleanup."""
    processor: XmlHeaderProcessor = _xml_processor_with_policy(ensure_blank_after_header=True)
    lines: list[str] = [
        "<root>\n",
        f"<!-- {TOPMARK_START_MARKER} -->\n",
        "<!-- h -->\n",
        f"<!-- {TOPMARK_END_MARKER} -->\n",
    ]

    strip_result: StripHeaderResult = processor.strip_header_block(
        lines=lines,
        span=(1, 3),
        newline_style="\n",
        ends_with_newline=True,
    )

    assert strip_result.diagnostic.kind == StripDiagKind.REMOVED
    assert strip_result.removed_span == (1, 3)
    assert strip_result.lines == ["<root>\n"]
    assert strip_result.diagnostic.notes == []


def test_xml_strip_auto_detect_path_keeps_base_spacer_cleanup_notes() -> None:
    """XML auto-detect strip should not claim extra XML spacer cleanup."""
    processor: XmlHeaderProcessor = _xml_processor_with_policy(ensure_blank_after_header=True)
    lines: list[str] = [
        '<?xml version="1.0"?>\n',
        f"<!-- {TOPMARK_START_MARKER} -->\n",
        "<!-- h -->\n",
        f"<!-- {TOPMARK_END_MARKER} -->\n",
        "\n",
        "<root/>\n",
    ]

    strip_result: StripHeaderResult = processor.strip_header_block(
        lines=lines,
        span=None,
        newline_style="\n",
        ends_with_newline=True,
    )

    assert strip_result.diagnostic.kind == StripDiagKind.REMOVED
    assert strip_result.removed_span == (1, 3)
    assert strip_result.lines == [
        '<?xml version="1.0"?>\n',
        "<root/>\n",
    ]
    assert strip_result.diagnostic.notes == []


def test_xml_strip_preserves_bom_and_declaration_while_trimming_policy_spacer() -> None:
    """XML strip should preserve a BOM-bearing declaration line exactly."""
    processor: XmlHeaderProcessor = _xml_processor_with_policy(
        ensure_blank_after_header=True,
    )
    lines: list[str] = [
        '\ufeff<?xml version="1.0"?>\n',
        f"<!-- {TOPMARK_START_MARKER} -->\n",
        "<!-- h -->\n",
        f"<!-- {TOPMARK_END_MARKER} -->\n",
        "\n",
        "<root/>\n",
    ]

    strip_result = processor.strip_header_block(
        lines=lines,
        span=(1, 3),
        newline_style="\n",
        ends_with_newline=True,
    )

    assert strip_result.diagnostic.kind == StripDiagKind.REMOVED
    assert strip_result.removed_span == (1, 3)
    assert strip_result.lines == [
        '\ufeff<?xml version="1.0"?>\n',
        "<root/>\n",
    ]
