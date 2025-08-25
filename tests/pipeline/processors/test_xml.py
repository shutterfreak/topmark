# topmark:header:start
#
#   file         : test_xml.py
#   file_relpath : tests/pipeline/processors/test_xml.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the XmlHeaderProcessor (HTML/XML-style comments)."""

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
    """Test the basic functionality of the XmlHeaderProcessor."""
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
    """Plain HTML: header at top (index 0) and a trailing blank after the block."""
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
    """Markdown: header at top; Markdown supports HTML comments."""
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
    """XML with declaration only: header after declaration with exactly one blank."""
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
    """XML with declaration + DOCTYPE: header after both, with 1 blank before header."""
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
    """SVG (XML) with declaration: header after declaration with one blank."""
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
    """Vue SFC: treat as HTML-like, header at top with trailing blank."""
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
    """Svelte component: treat as HTML-like, header at top with trailing blank."""
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
    """XML with declaration and root on the same line: insert after decl.

    Expectation:
      * The header is inserted *after* the XML declaration, with exactly one
        blank line before the header block, even though the root element begins
        on the same physical line in the original file.
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
    """XML with declaration + DOCTYPE on the same line: insert after both.

    Expectation:
      * The header is inserted *after* the XML declaration and DOCTYPE, with
        exactly one blank line before the header block, even when both appear
        on the same physical line as the root element in the original file.
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
    """HTML: insert header at top even if a banner comment already exists."""
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
    """Markdown: supports HTML comments; header goes at the top before a banner."""
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
    """XML with declaration and a leading banner comment: header after decl, before banner."""
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
    """XML with declaration + DOCTYPE and a banner: header after prolog, before banner."""
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
    """Idempotency for XML-like processor: re-running insertion is a no-op.

    Uses an HTML file (handled by XmlHeaderProcessor) without a header, runs the
    insert once, writes the result, and runs again. The second run should not
    modify the file.
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
