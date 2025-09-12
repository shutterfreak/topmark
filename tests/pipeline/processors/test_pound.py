# topmark:header:start
#
#   project      : TopMark
#   file         : test_pound.py
#   file_relpath : tests/pipeline/processors/test_pound.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the PoundHeaderProcessor (``#`` line comments).

Covers shebang/encoding handling, placement before banners, CRLF preservation,
idempotent re-application, and `strip_header_block` behavior. Docstrings follow
Google style and end with punctuation.
"""

from pathlib import Path

from tests.conftest import mark_pipeline
from tests.pipeline.conftest import expected_block_lines_for, find_line, run_insert
from topmark.config import MutableConfig
from topmark.config.logging import get_logger
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline import runner
from topmark.pipeline.context import HeaderStatus, ProcessingContext
from topmark.pipeline.pipelines import get_pipeline
from topmark.pipeline.processors.pound import PoundHeaderProcessor

logger = get_logger(__name__)


@mark_pipeline
def test_pound_processor_basics(tmp_path: Path) -> None:
    """Basic detection and scan.

    Creates a Python file without a TopMark block; the scanner should report no
    existing header and resolve the file type to Python.
    """
    # Create a sample file with pound-prefixed comments
    file = tmp_path / "sample.py"
    file.write_text("#!/usr/bin/env python3\n\nprint('hello')\n")

    config = MutableConfig.from_defaults().freeze()
    context = ProcessingContext.bootstrap(path=file, config=config)
    steps = get_pipeline("check")
    context = runner.run(context, steps)

    assert context.path == file
    assert context.file_type and context.file_type.name == "python"
    assert context.file_lines is not None
    assert context.existing_header_range is None


@mark_pipeline
def test_pound_processor_detects_existing_header(tmp_path: Path) -> None:
    """Test that PoundHeaderProcessor correctly detects an existing TopMark header.

    This test creates a file with a pre-inserted TopMark header block and verifies that:
    - The file type is detected as Python
    - The header block is correctly located by line range
    - The parsed header fields include the expected key-value pairs

    Args:
        tmp_path (Path): pytest-provided temporary directory for test file creation.
    """
    file = tmp_path / "example.py"
    file.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "#\n"
        "#   file: example.py\n"
        "#   license: MIT\n"
        "#\n"
        f"# {TOPMARK_END_MARKER}\n"
        "\n"
        "print('hello')\n"
    )

    config = MutableConfig.from_defaults().freeze()
    context = ProcessingContext.bootstrap(path=file, config=config)
    steps = get_pipeline("check")
    context = runner.run(context, steps)

    assert context.file_type and context.file_type.name == "python"
    assert context.existing_header_range == (0, 5)
    assert context.existing_header_dict is not None
    assert "file" in context.existing_header_dict
    assert context.existing_header_dict["file"] == "example.py"


@mark_pipeline
def test_pound_processor_missing_header(tmp_path: Path) -> None:
    """Test that PoundHeaderProcessor handles files with no TopMark header.

    This test verifies that when a file does not contain a TopMark header,
    the processor correctly identifies the header status as missing and does not
    set header range or fields.

    Args:
        tmp_path (Path): Temporary path provided by pytest for test file creation.
    """
    file = tmp_path / "no_header.py"
    file.write_text("#!/usr/bin/env python3\n\nprint('no header here')\n")

    config = MutableConfig.from_defaults().freeze()
    context = ProcessingContext.bootstrap(path=file, config=config)
    steps = get_pipeline("check")
    context = runner.run(context, steps)

    assert context.file_type and context.file_type.name == "python"
    assert context.existing_header_range is None
    assert context.existing_header_dict == {} or context.existing_header_dict is None
    assert context.status.header.name == "MISSING"


@mark_pipeline
def test_pound_processor_malformed_header(tmp_path: Path) -> None:
    """Test that PoundHeaderProcessor handles malformed TopMark headers.

    This test verifies that if the header block is incomplete or malformed,
    it is not parsed and header status reflects the malformed state.

    Args:
        tmp_path (Path): Temporary path provided by pytest for test file creation.
    """
    file = tmp_path / "malformed.py"
    file.write_text(
        f"# {TOPMARK_START_MARKER}\n"
        "#   file example.py\n"  # Missing colon
        f"# {TOPMARK_END_MARKER}\n"
        "\n"
        "print('oops')\n"
    )

    config = MutableConfig.from_defaults().freeze()
    context = ProcessingContext.bootstrap(path=file, config=config)
    steps = get_pipeline("check")
    context = runner.run(context, steps)

    assert context.file_type and context.file_type.name == "python"
    assert context.existing_header_range == (0, 2)
    assert context.existing_header_dict == {} or context.existing_header_dict is None
    assert context.status.header in {HeaderStatus.MALFORMED, HeaderStatus.EMPTY}


@mark_pipeline
def test_insert_with_shebang_adds_single_blank_line(tmp_path: Path) -> None:
    """Insert after shebang with exactly one blank line.

    Setup:
      * line 0: shebang (e.g., env python)
      * no blank line initially

    Expectations:
      * header begins at index 2 (shebang, inserted blank, header)
      * there is at least one blank line after the end marker
    """
    f = tmp_path / "shebang.py"
    # No blank line after shebang initially
    f.write_text("#!/usr/bin/env python3\nprint('hello')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    logger.debug(
        "expected_header_block:\n=== BEGIN ===\n$%s\n=== END ===", ctx.expected_header_block
    )
    logger.debug("lines:\n=== BEGIN ===\n$%s\n=== END ===", "\n".join(lines))
    # shebang should remain first
    assert lines[0].startswith("#!")

    sig = expected_block_lines_for(f)
    # Expect exactly one blank line after shebang before header start
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 2, f"header should start at line 3 (index 2), got {start_idx}"

    # There should be at least one blank line after end marker
    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines)
    assert lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_insert_with_shebang_existing_blank_not_duplicated(tmp_path: Path) -> None:
    """Do not duplicate an existing blank line after the shebang.

    Setup:
      * line 0: shebang
      * line 1: existing blank

    Expectation:
      * header begins at index 2
    """
    f = tmp_path / "shebang_blank.py"
    # Already has a blank line after shebang
    f.write_text("#!/usr/bin/env python3\n\nprint('hello')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    # header should start at index 2 as well: shebang (0), existing blank (1), header (2)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 2, f"expected header at index 2, got {start_idx}"


@mark_pipeline
def test_insert_with_shebang_and_encoding(tmp_path: Path) -> None:
    """Insert after shebang + encoding with one blank.

    Setup:
      * line 0: shebang
      * line 1: PEP 263 encoding

    Expectation:
      * header begins at index 3 (shebang, encoding, inserted blank, header)
    """
    f = tmp_path / "shebang_encoding.py"
    # Shebang followed by PEP 263 encoding line, no blank line yet
    f.write_text("#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nprint('x')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    # header should start after: shebang (0), encoding (1), inserted blank (2) => header (3)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 3, f"expected header at index 3 after shebang+encoding, got {start_idx}"


@mark_pipeline
def test_insert_without_shebang_starts_at_top_and_blank_after(tmp_path: Path) -> None:
    """Insert at top of file when there is no shebang, with a trailing blank.

    Expectations:
      * header begins at index 0
      * at least one blank line follows the header block
    """
    f = tmp_path / "no_shebang.py"
    f.write_text("print('hello')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    # header must start at beginning of file
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0, f"expected header at top of file, got index {start_idx}"

    # ensure at least one blank line after header
    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines)
    assert lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_insert_trailing_blank_not_added_if_next_line_is_blank(tmp_path: Path) -> None:
    """Avoid adding an extra trailing blank when the next line is already blank.

    Setup:
      * first line of the file is blank

    Expectations:
      * header begins at index 0
      * exactly one blank line follows the header block
      * original non-blank content remains immediately after
    """
    f = tmp_path / "trailing_blank.py"
    # First line of content is intentionally blank
    f.write_text("\nprint('after blank')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    # header at top
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0

    # The next line after the end marker should already be blank (from original file),
    # prepare_header_for_insertion should not add another blank => still exactly one.
    end_idx = find_line(lines, sig["end_line"])
    assert lines[end_idx + 1].strip() == ""
    # And the following line should be the original print
    assert (end_idx + 2) < len(lines)
    assert lines[end_idx + 2].startswith("print(")


# Additional tests for more file types and scenarios
@mark_pipeline
def test_shell_with_shebang_spacing(tmp_path: Path) -> None:
    """Shell: exactly one blank between shebang and header; trailing blank ensured."""
    f = tmp_path / "script.sh"
    f.write_text("#!/usr/bin/env bash\necho hi\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    assert lines[0].startswith("#!")
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 2
    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_r_with_shebang_spacing(tmp_path: Path) -> None:
    """R: shebang honored with exactly one blank before header."""
    f = tmp_path / "analysis.R"
    f.write_text("#!/usr/bin/env Rscript\nprint('x')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    assert lines[0].startswith("#!")
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 2


@mark_pipeline
def test_julia_with_shebang_spacing(tmp_path: Path) -> None:
    """Julia: shebang honored with exactly one blank before header."""
    f = tmp_path / "compute.jl"
    f.write_text("#!/usr/bin/env julia\nprintln(1+1)\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    assert lines[0].startswith("#!")
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 2


@mark_pipeline
def test_ruby_with_shebang_and_encoding(tmp_path: Path) -> None:
    """Ruby: shebang + encoding; header after inserted blank at index 3."""
    f = tmp_path / "tool.rb"
    f.write_text("#!/usr/bin/env ruby\n# encoding: utf-8\nputs 'ok'\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    assert lines[0].startswith("#!")
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 3


@mark_pipeline
def test_perl_with_shebang_spacing(tmp_path: Path) -> None:
    """Perl: exactly one blank between shebang and header."""
    f = tmp_path / "script.pl"
    f.write_text('#!/usr/bin/env perl\nprint "ok\\n";\n')

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    assert lines[0].startswith("#!")
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 2


@mark_pipeline
def test_dockerfile_top_and_trailing_blank(tmp_path: Path) -> None:
    """Dockerfile: header at top; trailing blank ensured."""
    f = tmp_path / "Dockerfile"
    f.write_text("FROM alpine:3.19\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0
    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_yaml_top_and_trailing_blank(tmp_path: Path) -> None:
    """YAML: header at top; trailing blank ensured."""
    f = tmp_path / "config.yaml"
    f.write_text("key: value\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0
    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_toml_top_and_trailing_blank(tmp_path: Path) -> None:
    """TOML: header at top; trailing blank ensured."""
    f = tmp_path / "pyproject.toml"
    f.write_text("[tool.example]\nname='x'\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0
    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_env_without_shebang_top_and_trailing_blank(tmp_path: Path) -> None:
    """.env: header at top; trailing blank ensured."""
    f = tmp_path / ".env"
    f.write_text("FOO=bar\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0
    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_pound_crlf_preserves_newlines(tmp_path: Path) -> None:
    r"""CRLF fixtures: Pound header preserves CRLF newline style.

    The inserted header block and surrounding spacing should use ``\r\n``
    when the original file uses CRLF line endings.
    """
    f = tmp_path / "crlf.py"
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("#!/usr/bin/env python3\nprint('hello')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    # joined = "".join(lines)

    # All lines should end with CRLF (no bare LF)
    for i, ln in enumerate(lines):
        assert ln.endswith("\r\n"), f"line {i} does not end with CRLF: {ln!r}"

    # Sanity: header start exists with CRLF signature
    sig = expected_block_lines_for(f, newline="\r\n")
    assert find_line(lines, sig["start_line"]) >= 0


# --- Additional tests for banner comments and placement ---


@mark_pipeline
def test_pound_banner_at_top_header_precedes_banner(tmp_path: Path) -> None:
    """Pound: header at top even if a banner of `#` lines exists.

    Expectation:
      * Without a shebang, the TopMark header is inserted at index 0.
      * The existing `#` banner comment lines follow after the TopMark header block.
    """
    f = tmp_path / "banner_top.py"
    f.write_text("# existing:license banner\n# another line\n\nprint('hello')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    # Header must start at the very top
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0

    # The pre-existing banner should appear after the TopMark header block
    end_idx = find_line(lines, sig["end_line"])
    banner_idx = find_line(lines, "# existing:license banner")
    assert banner_idx > end_idx


@mark_pipeline
def test_pound_shebang_then_banner_header_between(tmp_path: Path) -> None:
    """Pound: header sits between shebang and an existing `#` banner.

    Expectation:
      * With a shebang, header is inserted after shebang with exactly one blank line.
      * Any pre-existing banner follows after the TopMark header block.
    """
    f = tmp_path / "shebang_banner.py"
    f.write_text(
        "#!/usr/bin/env python3\n# existing:license banner\n# another line\n\nprint('hello')\n"
    )

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    # Shebang should remain first
    assert lines[0].startswith("#!")

    # Header should start at index 2 (shebang, inserted blank, header)
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 2

    # Pre-existing banner must follow after the TopMark header block
    end_idx = find_line(lines, sig["end_line"])
    banner_idx = find_line(lines, "# existing:license banner")
    assert banner_idx > end_idx


@mark_pipeline
def test_pound_shebang_encoding_then_banner_header_between(tmp_path: Path) -> None:
    """Pound: shebang + encoding, header between prolog and banner.

    Expectation:
      * With shebang + PEP 263 encoding, header begins at index 3.
      * Pre-existing banner appears after the TopMark header block.
    """
    f = tmp_path / "shebang_encoding_banner.py"
    f.write_text(
        "#!/usr/bin/env python3\n"
        "# -*- coding: utf-8 -*-\n"
        "# existing:license banner\n"
        "\n"
        "print('ok')\n"
    )

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    assert lines[0].startswith("#!")
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 3

    end_idx = find_line(lines, sig["end_line"])
    banner_idx = find_line(lines, "# existing:license banner")
    assert banner_idx > end_idx


@mark_pipeline
def test_pound_crlf_with_banner_preserves_newlines_and_order(tmp_path: Path) -> None:
    r"""CRLF: header preserves CRLF and precedes existing banner.

    Expectation:
      * File uses CRLF; all output lines end with ``\r\n``.
      * Header is inserted at top (no shebang), banner follows.
    """
    f = tmp_path / "banner_crlf.py"
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("# existing:license banner\n# another line\n\nprint('x')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    for i, ln in enumerate(lines):
        assert ln.endswith("\r\n"), f"line {i} does not end with CRLF: {ln!r}"

    sig = expected_block_lines_for(f, newline="\r\n")
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0

    end_idx = find_line(lines, sig["end_line"])
    banner_idx = find_line(lines, "# existing:license banner")
    assert banner_idx > end_idx


# --- New tests for banner variants with leading blanks and long hash rule separators ---


@mark_pipeline
def test_pound_banner_with_leading_blanks(tmp_path: Path) -> None:
    """Pound: header at top, preserves leading blanks before an existing banner.

    Setup:
      * Two leading blank lines, then a `#` banner.

    Expectations:
      * Header begins at index 0.
      * The original two leading blanks are preserved immediately after the
        header block.
      * The banner begins right after those preserved blanks.
    """
    f = tmp_path / "banner_leading_blanks.py"
    f.write_text("\n\n# banner one\n# banner two\nprint('x')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0

    end_idx = find_line(lines, sig["end_line"])
    # The next two lines after the header must be the original leading blanks
    assert end_idx + 2 < len(lines)
    assert lines[end_idx + 1].strip() == ""
    assert lines[end_idx + 2].strip() == ""

    # The banner should start right after those preserved blanks
    banner_idx = find_line(lines, "# banner one")
    assert banner_idx == end_idx + 3


@mark_pipeline
def test_pound_long_hash_rule_banner(tmp_path: Path) -> None:
    """Pound: header at top when file starts with long hash rule lines.

    Expectations:
      * Header at index 0.
      * Exactly one blank line after header block.
      * Then the first hash rule line.
    """
    f = tmp_path / "hash_rule.py"
    f.write_text("##########\n##########\n\nprint('x')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0

    end_idx = find_line(lines, sig["end_line"])
    # Policy ensures a trailing blank when the next line isn't blank
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""
    # First rule line should appear immediately after that blank
    assert lines[end_idx + 2].startswith("#")


@mark_pipeline
def test_pound_shebang_then_long_hash_rule_banner(tmp_path: Path) -> None:
    """Pound: shebang first, then hash rule banner; header inserted between.

    Expectations:
      * Shebang remains line 0.
      * Header begins at index 2 (shebang, inserted blank, header).
      * A single blank follows the header, then the first hash rule line.
    """
    f = tmp_path / "shebang_hash_rule.sh"
    f.write_text("#!/usr/bin/env bash\n##########\n\necho hi\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    sig = expected_block_lines_for(f)

    assert lines[0].startswith("#!")
    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 2

    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""
    assert lines[end_idx + 2].startswith("#")


@mark_pipeline
def test_pound_crlf_leading_blank_and_banner(tmp_path: Path) -> None:
    r"""CRLF: header at top; preserves leading blank and banner order.

    Setup:
      * File uses CRLF endings.
      * One leading blank, then a banner line.

    Expectations:
      * All output lines end with CRLF.
      * Header begins at index 0.
      * The original blank is preserved as the single blank after the header.
      * The banner follows immediately after that blank.
    """
    f = tmp_path / "banner_leading_blanks_crlf.py"
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("\n# banner\nprint('x')\n")

    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)

    lines = ctx.updated_file_lines or []
    for i, ln in enumerate(lines):
        assert ln.endswith("\r\n"), f"line {i} does not end with CRLF: {ln!r}"

    sig = expected_block_lines_for(f, newline="\r\n")

    start_idx = find_line(lines, sig["start_line"])
    assert start_idx == 0

    end_idx = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""
    banner_idx = find_line(lines, "# banner")
    assert banner_idx == end_idx + 2


@mark_pipeline
def test_pound_idempotent_reapply_no_diff(tmp_path: Path) -> None:
    """Idempotency: running insertion twice should not change the file the second time.

    We first insert a header into a file that has none, then write the updated
    lines back to disk and run insertion again. The second run should produce
    exactly the same content (no additional changes).
    """
    f = tmp_path / "idem.py"
    f.write_text("print('hello')\n")

    cfg = MutableConfig.from_defaults().freeze()

    # First insertion
    ctx1 = run_insert(f, cfg)
    lines1 = ctx1.updated_file_lines or []

    # Persist result to disk, preserving exact line endings
    with f.open("w", encoding="utf-8", newline="") as fp:
        fp.write("".join(lines1))

    # Second insertion
    ctx2 = run_insert(f, cfg)
    lines2 = ctx2.updated_file_lines or []

    assert lines2 == lines1, "Second run must be a no-op (idempotent)"


# --- strip_header_block: test both with and without span, preserving shebang ---
@mark_pipeline
def test_strip_header_block_with_and_without_span_preserves_shebang(tmp_path: Path) -> None:
    """`strip_header_block` removes the header and preserves the shebang.

    This test exercises both code paths in the processor:
      * With an explicit span (as provided by the scanner), and
      * Without a span (processor computes bounds itself).

    Expectations:
      * The shebang line remains at index 0.
      * The entire TopMark header block is removed.
      * The returned span matches the actual header location.
    """
    from topmark.pipeline.processors import get_processor_for_file

    f = tmp_path / "strip_shebang.py"
    f.write_text(
        "#!/usr/bin/env python3\n"
        f"# {TOPMARK_START_MARKER}\n"
        "# field\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('ok')\n",
        encoding="utf-8",
    )

    proc = get_processor_for_file(f)
    assert proc is not None

    lines = f.read_text(encoding="utf-8").splitlines(keepends=True)

    # 1) With explicit span
    new1, span1 = proc.strip_header_block(lines=lines, span=(1, 3))
    assert new1[0].startswith("#!"), "shebang must be preserved"
    joined1 = "".join(new1)
    assert TOPMARK_START_MARKER not in joined1
    assert span1 == (1, 3)

    # 2) Without span (processor must detect bounds)
    new2, span2 = proc.strip_header_block(lines=lines, span=None)
    assert new2 == new1
    assert span2 == (1, 3)


@mark_pipeline
def test_pound_encoding_only_at_top(tmp_path: Path) -> None:
    """Encoding line without shebang (PEP 263 at top).

    Ensures the header still starts at the very top (index 0) when only an
    encoding line is present without a shebang line.
    """
    f = tmp_path / "enc_only.py"
    f.write_text("# -*- coding: utf-8 -*-\nprint('x')\n")
    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)
    sig = expected_block_lines_for(f)
    # header should still start at top, not after encoding-only line
    assert find_line(ctx.updated_file_lines or [], sig["start_line"]) == 0


@mark_pipeline
def test_pound_bom_preserved(tmp_path: Path) -> None:
    """Preserve a leading UTF-8 BOM at the start of the output.

    When a file begins with a BOM, the reader strips it in-memory and the updater
    re-attaches it before the first header line. The resulting first output line
    must begin with ``\ufeff``.
    """
    f = tmp_path / "bom.py"
    f.write_bytes(b"\xef\xbb\xbfprint('x')\n")  # UTF-8 BOM
    cfg = MutableConfig.from_defaults().freeze()
    ctx = run_insert(f, cfg)
    # BOM should still be present at the beginning of the first line
    assert (ctx.updated_file_lines or [])[0].startswith("\ufeff")


def test_pound_processor_only_removes_first_header_block() -> None:
    """Only the first header occurrence should be removed during strip."""
    p = PoundHeaderProcessor()
    lines = [
        f"# {TOPMARK_START_MARKER}\n",
        "# A\n",
        f"# {TOPMARK_END_MARKER}\n",
        "code\n",
        f"# {TOPMARK_START_MARKER}\n",  # Example block later in the file
        "# B\n",
        f"# {TOPMARK_END_MARKER}\n",
        "more\n",
    ]

    new, span = p.strip_header_block(lines=lines, span=(0, 2))

    # First header removed; later example block must remain.
    s = "".join(new)

    assert "code\n" in s and "more\n" in s

    assert f"# {TOPMARK_START_MARKER}" in s  # second block still present

    assert span == (0, 2)
