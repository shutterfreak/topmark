# topmark:header:start
#
#   file         : test_xml.py
#   file_relpath : tests/pipeline/processors/test_xml.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the XmlHeaderProcessor (HTML/XML-style ``<!-- ... -->`` comments).

Exercises placement rules for HTML, XML (with declaration and DOCTYPE), SVG,
Markdown (HTML comments), and component templates (Vue, Svelte). Also validates
idempotency and `strip_header_block` behavior including preservation of the
XML declaration.
"""

from pathlib import Path

from tests.conftest import mark_pipeline
from tests.pipeline.processors.conftest import expected_block_lines_for, find_line, run_insert
from topmark.config import Config
from topmark.config.logging import get_logger
from topmark.pipeline import runner
from topmark.pipeline.context import ProcessingContext
from topmark.pipeline.pipelines import get_pipeline

logger = get_logger(__name__)


@mark_pipeline
def test_xml_processor_basics(tmp_path: Path) -> None:
    """Basic detection and scan.

    Creates an HTML file without a TopMark block; the scanner should report no
    existing header and resolve the file type to HTML.
    """
    # Create a sample file with html-prefixed comments
    file = tmp_path / "sample.html"
    file.write_text("<html>\n<body><p>Hello.</p></body></html>")

    config = Config.from_defaults()
    context = ProcessingContext.bootstrap(path=file, config=config)
    steps = get_pipeline("check")
    context = runner.run(context, steps)

    assert context.path == file
    assert context.file_type and context.file_type.name == "html"
    assert context.file_lines is not None
    assert context.existing_header_range is None


@mark_pipeline
def test_html_top_of_file_with_trailing_blank(tmp_path: Path) -> None:
    """Insert header at the very top of plain HTML and keep a trailing blank.

    Verifies that the block-open lands at index 0 and that a single blank line
    follows the closing marker for readability.
    """
    f = tmp_path / "index.html"
    f.write_text("<!DOCTYPE html>\n<html></html>\n")

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    logger.debug("ctx.updated_file_lines: %s", lines)
    sig = expected_block_lines_for(f)
    if "block_open" in sig:
        open_idx = find_line(lines, sig["block_open"])
        assert open_idx == 0
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 1
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


@mark_pipeline
def test_markdown_top_of_file_with_trailing_blank(tmp_path: Path) -> None:
    """Markdown supports HTML comments; insert at top with trailing blank.

    Confirms the HTML-comment-based header is added at the top (block-open at 0,
    start-line at 1) and that a blank line follows the block.
    """
    f = tmp_path / "README.md"
    f.write_text("# Title\n\nSome text.\n")

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


@mark_pipeline
def test_xml_with_declaration_only(tmp_path: Path) -> None:
    """XML with only a declaration: insert after declaration (+1 blank).

    Ensures the XML declaration remains line 0 and the header follows after a
    single blank separator.
    """
    f = tmp_path / "doc.xml"
    f.write_text('<?xml version="1.0"?>\n<root/>\n')

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        open_idx = find_line(lines, sig["block_open"])
        assert open_idx == 2
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 3
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


@mark_pipeline
def test_xml_with_declaration_and_doctype(tmp_path: Path) -> None:
    """XML with declaration + DOCTYPE: insert after both (+1 blank).

    Asserts correct placement of the block-open/start after the prolog elements
    and a single blank line.
    """
    f = tmp_path / "doc2.xml"
    f.write_text('<?xml version="1.0"?>\n<!DOCTYPE note SYSTEM "Note.dtd">\n<note/>\n')

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        open_idx = find_line(lines, sig["block_open"])
        assert open_idx == 3
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 4
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


@mark_pipeline
def test_svg_with_declaration(tmp_path: Path) -> None:
    """SVG (XML) with declaration: insert after declaration (+1 blank).

    Mirrors the XML behavior for SVG files.
    """
    f = tmp_path / "icon.svg"
    f.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16"></svg>\n'
    )

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        open_idx = find_line(lines, sig["block_open"])
        assert open_idx == 2
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 3


@mark_pipeline
def test_vue_top_of_file(tmp_path: Path) -> None:
    """Vue SFC behaves like HTML: header at top with trailing blank.

    Uses HTML-style comments for the header block.
    """
    f = tmp_path / "App.vue"
    f.write_text("<template>\n  <div/>\n</template>\n")

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


@mark_pipeline
def test_svelte_top_of_file(tmp_path: Path) -> None:
    """Svelte component behaves like HTML: header at top with trailing blank.

    Uses HTML-style comments for the header block.
    """
    f = tmp_path / "Widget.svelte"
    f.write_text("<script>\n  let x = 1;\n</script>\n")

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


@mark_pipeline
def test_xml_single_line_declaration(tmp_path: Path) -> None:
    """Declaration and root on one line: insert after decl (+1 blank).

    Verifies that char-offset insertion splits the line after the declaration,
    inserts a blank, then the header block.
    """
    f = tmp_path / "singleline_decl.xml"
    # No newline between declaration and root element
    f.write_text('<?xml version="1.0"?><root/>\n')

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    # The first line should end with the XML declaration (we inserted the first newline)
    assert lines[0].lstrip("\ufeff").startswith("<?xml")

    # Expect: line 0 = decl, line 1 = blank, line 2 = block open, line 3 = start
    if "block_open" in sig:
        open_idx = find_line(lines, sig["block_open"])
        assert open_idx == 2
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 3

    # Ensure a trailing blank after the header block
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


@mark_pipeline
def test_xml_single_line_decl_and_doctype(tmp_path: Path) -> None:
    """Declaration + DOCTYPE + root on one line: insert after prolog (+1 blank).

    Confirms correct splitting and placement when both declaration and DOCTYPE
    precede the root on the same physical line.
    """
    f = tmp_path / "singleline_decl_doctype.xml"
    # XML declaration, DOCTYPE, and root all on a single line
    f.write_text('<?xml version="1.0"?><!DOCTYPE note SYSTEM "Note.dtd"><note/>\n')

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    # First logical line contains decl+doctype (newline inserted by header placement)
    assert lines[0].lstrip("\ufeff").startswith("<?xml")

    # Expect: line 0 = decl+doctype, line 1 = blank, line 2 = block open, line 3 = start
    if "block_open" in sig:
        open_idx = find_line(lines, sig["block_open"])
        assert open_idx == 2
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 3

    # Ensure a trailing blank after the header block
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines) and lines[close_idx + 1].strip() == ""


@mark_pipeline
def test_html_with_existing_banner_comment(tmp_path: Path) -> None:
    """Header must precede any pre-existing banner comment in HTML.

    Ensures the TopMark block is inserted first and the previous banner follows
    after the block close.
    """
    f = tmp_path / "banner.html"
    f.write_text("<!-- existing:license banner -->\n<html></html>\n")

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    # Header must start at very top
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1

    # The pre-existing banner should appear after the TopMark header block
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        assert close_idx + 1 < len(lines)
        # First non-TopMark comment line should be the banner
        banner_idx = find_line(lines, "<!-- existing:license banner -->")
        assert banner_idx > close_idx


@mark_pipeline
def test_markdown_with_existing_banner_comment(tmp_path: Path) -> None:
    """Markdown: header precedes any existing banner comment.

    Confirms block placement and ordering of the prior banner comment after the
    TopMark header.
    """
    f = tmp_path / "BANNER.md"
    f.write_text("<!-- md:banner -->\n# Title\n\n")

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1

    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        banner_idx = find_line(lines, "<!-- md:banner -->")
        assert banner_idx > close_idx


@mark_pipeline
def test_xml_decl_then_existing_banner_comment(tmp_path: Path) -> None:
    """XML with declaration and a banner: header after decl, before banner.

    Validates that the header is anchored after the XML declaration and precedes
    the existing banner comment.
    """
    f = tmp_path / "doc_with_banner.xml"
    f.write_text('<?xml version="1.0"?>\n<!-- xml:banner -->\n<root/>\n')

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 2
    assert find_line(lines, sig["start_line"]) == 3

    # Ensure banner comes AFTER the TopMark header block
    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        banner_idx = find_line(lines, "<!-- xml:banner -->")
        assert banner_idx > close_idx


@mark_pipeline
def test_xml_decl_doctype_then_existing_banner_comment(tmp_path: Path) -> None:
    """XML with declaration + DOCTYPE and a banner: header after prolog.

    Ensures the header is placed after the declaration and DOCTYPE but before the
    banner comment.
    """
    f = tmp_path / "doc_with_prolog_banner.xml"
    f.write_text(
        '<?xml version="1.0"?>\n'
        '<!DOCTYPE note SYSTEM "Note.dtd">\n'
        "<!-- xml:prolog-banner -->\n"
        "<note/>\n"
    )

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 3
    assert find_line(lines, sig["start_line"]) == 4

    if "block_close" in sig:
        close_idx = find_line(lines, sig["block_close"])
        banner_idx = find_line(lines, "<!-- xml:prolog-banner -->")
        assert banner_idx > close_idx


@mark_pipeline
def test_xml_idempotent_reapply_no_diff(tmp_path: Path) -> None:
    """Idempotent re-application for HTML/XML-like files.

    The second run after writing the first output must produce identical content.
    """
    f = tmp_path / "idem.html"
    f.write_text("<html><body>hi</body></html>\n")

    cfg = Config.from_defaults()

    ctx1 = run_insert(f, cfg)
    lines1 = ctx1.updated_file_lines or []

    with f.open("w", encoding="utf-8", newline="") as fp:
        fp.write("".join(lines1))

    ctx2 = run_insert(f, cfg)
    lines2 = ctx2.updated_file_lines or []

    assert lines2 == lines1, "Second run must be a no-op (idempotent) for XML/HTML"


# --- strip_header_block: test XML declaration is preserved, header is removed ---
@mark_pipeline
def test_xml_strip_header_block_respects_declaration(tmp_path: Path) -> None:
    """`strip_header_block` removes the header and preserves the XML declaration.

    Exercises both explicit-span and auto-detect paths and asserts identical
    results with the declaration retained as the first logical line.
    """
    from topmark.pipeline.processors import get_processor_for_file

    f = tmp_path / "strip_doc.xml"
    f.write_text(
        '<?xml version="1.0"?>\n'
        "<!-- topmark:header:start -->\n"
        "<!-- h -->\n"
        "<!-- topmark:header:end -->\n"
        "<root/>\n",
        encoding="utf-8",
    )

    proc = get_processor_for_file(f)
    assert proc is not None

    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)

    # 1) With explicit span for the HTML-style comment block
    new1, span1 = proc.strip_header_block(lines=lines, span=(1, 3))
    assert new1[0].lstrip("\ufeff").startswith("<?xml"), "XML declaration must remain"
    assert "topmark:header:start" not in "".join(new1)
    assert span1 == (1, 3)

    # 2) Let the processor detect bounds itself
    new2, span2 = proc.strip_header_block(lines=lines)
    # Declaration must remain identical on the auto-detect path as well
    assert new2[0].lstrip("\ufeff").startswith("<?xml"), "XML declaration must remain (auto-detect)"
    assert new2 == new1
    assert span2 == (1, 3)


@mark_pipeline
def test_markdown_fenced_code_no_insertion_inside(tmp_path: Path) -> None:
    """Do not insert inside Markdown fenced code blocks.

    The header must be placed at the top of the document and the original fenced
    code block must remain intact.
    """
    f = tmp_path / "FENCE.md"
    f.write_text("```html\n<!-- topmark:header:start -->\n```\nReal content\n")
    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    # Header should be at top (before the fenced block) and not inside it
    sig = expected_block_lines_for(f)
    if "block_open" in sig:
        assert find_line(lines, sig["block_open"]) == 0
    assert find_line(lines, sig["start_line"]) == 1
    assert "<!-- topmark:header:start -->" in "".join(lines), (
        "Original fence content must remain untouched"
    )


@mark_pipeline
def test_xml_doctype_with_internal_subset(tmp_path: Path) -> None:
    """DOCTYPE with simple internal subset (multi-line) is respected.

    Confirms header insertion occurs after the declaration and the entirety of the
    multi-line DOCTYPE, followed by a single blank line.
    """
    f = tmp_path / "subset.xml"
    f.write_text('<?xml version="1.0"?>\n<!DOCTYPE root [\n  <!ELEMENT root EMPTY>\n]>\n<root/>\n')
    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)
    lines = ctx.updated_file_lines or []
    assert lines[0].lstrip("\ufeff").startswith("<?xml")
    # header begins after declaration + doctype + one blank
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 5  # decl(0) doctype(1..3) blank(4) start(5)


@mark_pipeline
def test_xml_bom_preserved_text_insert(tmp_path: Path) -> None:
    """Ensure XML processor preserves BOM on text-insert path.

    Writes an XML file that begins with a UTF-8 BOM and verifies that, after the
    header is inserted via the XML processor's text-based insertion path, the BOM
    remains at the start of the first output line.

    Args:
        tmp_path: Temporary directory provided by pytest.
    """
    f = tmp_path / "bom.xml"
    f.write_bytes(b"\xef\xbb\xbf<?xml version='1.0'?>\n<root/>\n")
    ctx = run_insert(f, Config.from_defaults())
    assert (ctx.updated_file_lines or [])[0].startswith("\ufeff")
