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

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.conftest import mark_pipeline
from tests.pipeline.conftest import (
    BlockSignatures,
    expected_block_lines_for,
    find_line,
    materialize_updated_lines,
    run_insert,
)
from topmark.config import Config, MutableConfig
from topmark.config.logging import TopmarkLogger, get_logger
from topmark.config.policy import PolicyRegistry, make_policy_registry
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER
from topmark.pipeline import runner
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.pipelines import Pipeline
from topmark.pipeline.processors.pound import PoundHeaderProcessor
from topmark.pipeline.processors.types import StripDiagKind, StripDiagnostic
from topmark.pipeline.status import HeaderStatus

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.pipeline.processors.base import HeaderProcessor
    from topmark.pipeline.protocols import Step

logger: TopmarkLogger = get_logger(__name__)


@mark_pipeline
def test_pound_processor_basics(tmp_path: Path) -> None:
    """Basic detection and scan.

    Creates a Python file without a TopMark block; the scanner should report no
    existing header and resolve the file type to Python.
    """
    # Create a sample file with pound-prefixed comments
    file: Path = tmp_path / "sample.py"
    file.write_text("#!/usr/bin/env python3\n\nprint('hello')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    policy_registry: PolicyRegistry = make_policy_registry(cfg)
    ctx: ProcessingContext = ProcessingContext.bootstrap(
        path=file,
        config=cfg,
        policy_registry=policy_registry,
    )
    pipeline: Sequence[Step] = Pipeline.CHECK.steps
    ctx = runner.run(ctx, pipeline)

    assert ctx.path == file
    assert ctx.file_type and ctx.file_type.name == "python"
    assert ctx.views.image is not None  # or: assert context.file_line_count() > 0
    assert ctx.views.header is None


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
    file: Path = tmp_path / "example.py"
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

    cfg: Config = MutableConfig.from_defaults().freeze()
    policy_registry: PolicyRegistry = make_policy_registry(cfg)
    ctx: ProcessingContext = ProcessingContext.bootstrap(
        path=file,
        config=cfg,
        policy_registry=policy_registry,
    )

    pipeline: Sequence[Step] = Pipeline.CHECK.steps
    ctx = runner.run(
        ctx,
        pipeline,
        prune=False,  # We must inspect ctx_check.views.header
    )

    assert ctx.file_type and ctx.file_type.name == "python"
    assert ctx.views.header is not None
    assert ctx.views.header.range == (0, 5)
    assert ctx.views.header.mapping is not None
    assert "file" in ctx.views.header.mapping
    assert ctx.views.header.mapping["file"] == "example.py"
    ctx.views.release_all()  # Release the views


@mark_pipeline
def test_pound_processor_missing_header(tmp_path: Path) -> None:
    """Test that PoundHeaderProcessor handles files with no TopMark header.

    This test verifies that when a file does not contain a TopMark header,
    the processor correctly identifies the header status as missing and does not
    set header range or fields.

    Args:
        tmp_path (Path): Temporary path provided by pytest for test file creation.
    """
    path: Path = tmp_path / "no_header.py"
    path.write_text("#!/usr/bin/env python3\n\nprint('no header here')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    policy_registry: PolicyRegistry = make_policy_registry(cfg)
    ctx: ProcessingContext = ProcessingContext.bootstrap(
        path=path,
        config=cfg,
        policy_registry=policy_registry,
    )

    pipeline: Sequence[Step] = Pipeline.CHECK.steps
    ctx = runner.run(ctx, pipeline)

    assert ctx.file_type and ctx.file_type.name == "python"
    assert ctx.views.header is None
    assert ctx.status.header.name == "MISSING"


@mark_pipeline
@pytest.mark.parametrize(
    "header_fields, expected_status",
    [
        (
            "# bad header\n",  # Missing colon
            HeaderStatus.MALFORMED_ALL_FIELDS,
        ),
        (
            "# valid: header\n# bad header\n",  # One header OK, one with missing colon
            HeaderStatus.MALFORMED_SOME_FIELDS,
        ),
        (
            "# valid: header\n",  # Header OK
            HeaderStatus.DETECTED,
        ),
    ],
)
def test_pound_malformed_header_fields(
    tmp_path: Path,
    header_fields: str,
    expected_status: HeaderStatus,
) -> None:
    """Test that PoundHeaderProcessor handles malformed TopMark headers.

    This test verifies that if the header block is incomplete or malformed,
    it is not parsed and header status reflects the malformed state.

    Args:
        tmp_path (Path): Temporary path provided by pytest for test file creation.
        header_fields (str): Header fields for the test
        expected_status (HeaderStatus): expected HeaderStatus value for the test
    """
    path: Path = tmp_path / "malformed.py"
    path.write_text(
        f"# {TOPMARK_START_MARKER}\n{header_fields}# {TOPMARK_END_MARKER}\n\nprint('oops')\n"
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    policy_registry: PolicyRegistry = make_policy_registry(cfg)
    ctx: ProcessingContext = ProcessingContext.bootstrap(
        path=path,
        config=cfg,
        policy_registry=policy_registry,
    )

    pipeline: Sequence[Step] = Pipeline.CHECK.steps
    ctx = runner.run(ctx, pipeline)

    assert ctx.file_type and ctx.file_type.name == "python"
    assert ctx.views.header is not None
    assert ctx.status.header == expected_status


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
    path: Path = tmp_path / "shebang.py"
    # No blank line after shebang initially
    path.write_text("#!/usr/bin/env python3\nprint('hello')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(path, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    logger.debug(
        "expected_header_block:\n=== BEGIN ===\n$%s\n=== END ===",
        ctx.views.render.block if ctx.views.render else "",
    )
    logger.debug("lines:\n=== BEGIN ===\n$%s\n=== END ===", "\n".join(lines))
    # shebang should remain first
    assert lines[0].startswith("#!")

    sig: BlockSignatures = expected_block_lines_for(path)
    # Expect exactly one blank line after shebang before header start
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 2, f"header should start at line 3 (index 2), got {start_idx}"

    # There should be at least one blank line after end marker
    end_idx: int = find_line(lines, sig["end_line"])
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
    path: Path = tmp_path / "shebang_blank.py"
    # Already has a blank line after shebang
    path.write_text("#!/usr/bin/env python3\n\nprint('hello')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(path, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(path)
    # header should start at index 2 as well: shebang (0), existing blank (1), header (2)
    start_idx: int = find_line(lines, sig["start_line"])
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
    path: Path = tmp_path / "shebang_encoding.py"
    # Shebang followed by PEP 263 encoding line, no blank line yet
    path.write_text("#!/usr/bin/env python3\n# -*- coding: utf-8 -*-\nprint('x')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(path, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(path)
    # header should start after: shebang (0), encoding (1), inserted blank (2) => header (3)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 3, f"expected header at index 3 after shebang+encoding, got {start_idx}"


@mark_pipeline
def test_insert_without_shebang_starts_at_top_and_blank_after(tmp_path: Path) -> None:
    """Insert at top of file when there is no shebang, with a trailing blank.

    Expectations:
      * header begins at index 0
      * at least one blank line follows the header block
    """
    path: Path = tmp_path / "no_shebang.py"
    path.write_text("print('hello')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(path, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(path)
    # header must start at beginning of file
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0, f"expected header at top of file, got index {start_idx}"

    # ensure at least one blank line after header
    end_idx: int = find_line(lines, sig["end_line"])
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
    path: Path = tmp_path / "trailing_blank.py"
    # First line of content is intentionally blank
    path.write_text("\nprint('after blank')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(path, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(path)
    # header at top
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0

    # The next line after the end marker should already be blank (from original file),
    # prepare_header_for_insertion should not add another blank => still exactly one.
    end_idx: int = find_line(lines, sig["end_line"])
    assert lines[end_idx + 1].strip() == ""
    # And the following line should be the original print
    assert (end_idx + 2) < len(lines)
    assert lines[end_idx + 2].startswith("print(")


# Additional tests for more file types and scenarios
@mark_pipeline
def test_shell_with_shebang_spacing(tmp_path: Path) -> None:
    """Shell: exactly one blank between shebang and header; trailing blank ensured."""
    file: Path = tmp_path / "script.sh"
    file.write_text("#!/usr/bin/env bash\necho hi\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    assert lines[0].startswith("#!")
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 2
    end_idx: int = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_r_with_shebang_spacing(tmp_path: Path) -> None:
    """R: shebang honored with exactly one blank before header."""
    file: Path = tmp_path / "analysis.R"
    file.write_text("#!/usr/bin/env Rscript\nprint('x')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    assert lines[0].startswith("#!")
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 2


@mark_pipeline
def test_julia_with_shebang_spacing(tmp_path: Path) -> None:
    """Julia: shebang honored with exactly one blank before header."""
    file: Path = tmp_path / "compute.jl"
    file.write_text("#!/usr/bin/env julia\nprintln(1+1)\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    assert lines[0].startswith("#!")
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 2


@mark_pipeline
def test_ruby_with_shebang_and_encoding(tmp_path: Path) -> None:
    """Ruby: shebang + encoding; header after inserted blank at index 3."""
    file: Path = tmp_path / "tool.rb"
    file.write_text("#!/usr/bin/env ruby\n# encoding: utf-8\nputs 'ok'\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    assert lines[0].startswith("#!")
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 3


@mark_pipeline
def test_perl_with_shebang_spacing(tmp_path: Path) -> None:
    """Perl: exactly one blank between shebang and header."""
    file: Path = tmp_path / "script.pl"
    file.write_text('#!/usr/bin/env perl\nprint "ok\\n";\n')

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    assert lines[0].startswith("#!")
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 2


@mark_pipeline
def test_dockerfile_top_and_trailing_blank(tmp_path: Path) -> None:
    """Dockerfile: header at top; trailing blank ensured."""
    file: Path = tmp_path / "Dockerfile"
    file.write_text("FROM alpine:3.19\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0
    end_idx: int = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_yaml_top_and_trailing_blank(tmp_path: Path) -> None:
    """YAML: header at top; trailing blank ensured."""
    file: Path = tmp_path / "config.yaml"
    file.write_text("key: value\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0
    end_idx: int = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_toml_top_and_trailing_blank(tmp_path: Path) -> None:
    """TOML: header at top; trailing blank ensured."""
    file: Path = tmp_path / "pyproject.toml"
    file.write_text("[tool.example]\nname='x'\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0
    end_idx: int = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_env_without_shebang_top_and_trailing_blank(tmp_path: Path) -> None:
    """.env: header at top; trailing blank ensured."""
    file: Path = tmp_path / ".env"
    file.write_text("FOO=bar\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0
    end_idx: int = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""


@mark_pipeline
def test_pound_crlf_preserves_newlines(tmp_path: Path) -> None:
    r"""CRLF fixtures: Pound header preserves CRLF newline style.

    The inserted header block and surrounding spacing should use ``\r\n``
    when the original file uses CRLF line endings.
    """
    file: Path = tmp_path / "crlf.py"
    with file.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("#!/usr/bin/env python3\nprint('hello')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)

    # All lines should end with CRLF (no bare LF)
    for i, ln in enumerate(lines):
        assert ln.endswith("\r\n"), f"line {i} does not end with CRLF: {ln!r}"

    # Sanity: header start exists with CRLF signature
    sig: BlockSignatures = expected_block_lines_for(file, newline="\r\n")
    assert find_line(lines, sig["start_line"]) >= 0


# --- Additional tests for banner comments and placement ---


@mark_pipeline
def test_pound_banner_at_top_header_precedes_banner(tmp_path: Path) -> None:
    """Pound: header at top even if a banner of `#` lines exists.

    Expectation:
      * Without a shebang, the TopMark header is inserted at index 0.
      * The existing `#` banner comment lines follow after the TopMark header block.
    """
    file: Path = tmp_path / "banner_top.py"
    file.write_text("# existing:license banner\n# another line\n\nprint('hello')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)

    # Header must start at the very top
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0

    # The pre-existing banner should appear after the TopMark header block
    end_idx: int = find_line(lines, sig["end_line"])
    banner_idx: int = find_line(lines, "# existing:license banner")
    assert banner_idx > end_idx


@mark_pipeline
def test_pound_shebang_then_banner_header_between(tmp_path: Path) -> None:
    """Pound: header sits between shebang and an existing `#` banner.

    Expectation:
      * With a shebang, header is inserted after shebang with exactly one blank line.
      * Any pre-existing banner follows after the TopMark header block.
    """
    file: Path = tmp_path / "shebang_banner.py"
    file.write_text(
        "#!/usr/bin/env python3\n# existing:license banner\n# another line\n\nprint('hello')\n"
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)

    # Shebang should remain first
    assert lines[0].startswith("#!")

    # Header should start at index 2 (shebang, inserted blank, header)
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 2

    # Pre-existing banner must follow after the TopMark header block
    end_idx: int = find_line(lines, sig["end_line"])
    banner_idx: int = find_line(lines, "# existing:license banner")
    assert banner_idx > end_idx


@mark_pipeline
def test_pound_shebang_encoding_then_banner_header_between(tmp_path: Path) -> None:
    """Pound: shebang + encoding, header between prolog and banner.

    Expectation:
      * With shebang + PEP 263 encoding, header begins at index 3.
      * Pre-existing banner appears after the TopMark header block.
    """
    file: Path = tmp_path / "shebang_encoding_banner.py"
    file.write_text(
        "#!/usr/bin/env python3\n"
        "# -*- coding: utf-8 -*-\n"
        "# existing:license banner\n"
        "\n"
        "print('ok')\n"
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)

    assert lines[0].startswith("#!")
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 3

    end_idx: int = find_line(lines, sig["end_line"])
    banner_idx: int = find_line(lines, "# existing:license banner")
    assert banner_idx > end_idx


@mark_pipeline
def test_pound_crlf_with_banner_preserves_newlines_and_order(tmp_path: Path) -> None:
    r"""CRLF: header preserves CRLF and precedes existing banner.

    Expectation:
      * File uses CRLF; all output lines end with ``\r\n``.
      * Header is inserted at top (no shebang), banner follows.
    """
    file: Path = tmp_path / "banner_crlf.py"
    with file.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("# existing:license banner\n# another line\n\nprint('x')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    for i, ln in enumerate(lines):
        assert ln.endswith("\r\n"), f"line {i} does not end with CRLF: {ln!r}"

    sig: BlockSignatures = expected_block_lines_for(file, newline="\r\n")
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0

    end_idx: int = find_line(lines, sig["end_line"])
    banner_idx: int = find_line(lines, "# existing:license banner")
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
    file: Path = tmp_path / "banner_leading_blanks.py"
    file.write_text("\n\n# banner one\n# banner two\nprint('x')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)

    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0

    end_idx: int = find_line(lines, sig["end_line"])
    # The next two lines after the header must be the original leading blanks
    assert end_idx + 2 < len(lines)
    assert lines[end_idx + 1].strip() == ""
    assert lines[end_idx + 2].strip() == ""

    # The banner should start right after those preserved blanks
    banner_idx: int = find_line(lines, "# banner one")
    assert banner_idx == end_idx + 3


@mark_pipeline
def test_pound_long_hash_rule_banner(tmp_path: Path) -> None:
    """Pound: header at top when file starts with long hash rule lines.

    Expectations:
      * Header at index 0.
      * Exactly one blank line after header block.
      * Then the first hash rule line.
    """
    file: Path = tmp_path / "hash_rule.py"
    file.write_text("##########\n##########\n\nprint('x')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)

    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0

    end_idx: int = find_line(lines, sig["end_line"])
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
    file: Path = tmp_path / "shebang_hash_rule.sh"
    file.write_text("#!/usr/bin/env bash\n##########\n\necho hi\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    sig: BlockSignatures = expected_block_lines_for(file)

    assert lines[0].startswith("#!")
    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 2

    end_idx: int = find_line(lines, sig["end_line"])
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
    file: Path = tmp_path / "banner_leading_blanks_crlf.py"
    with file.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("\n# banner\nprint('x')\n")

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)

    lines: list[str] = materialize_updated_lines(ctx)
    for i, ln in enumerate(lines):
        assert ln.endswith("\r\n"), f"line {i} does not end with CRLF: {ln!r}"

    sig: BlockSignatures = expected_block_lines_for(file, newline="\r\n")

    start_idx: int = find_line(lines, sig["start_line"])
    assert start_idx == 0

    end_idx: int = find_line(lines, sig["end_line"])
    assert end_idx + 1 < len(lines) and lines[end_idx + 1].strip() == ""
    banner_idx: int = find_line(lines, "# banner")
    assert banner_idx == end_idx + 2


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

    file: Path = tmp_path / "strip_shebang.py"
    file.write_text(
        "#!/usr/bin/env python3\n"
        f"# {TOPMARK_START_MARKER}\n"
        "# field\n"
        f"# {TOPMARK_END_MARKER}\n"
        "print('ok')\n",
        encoding="utf-8",
    )

    proc: HeaderProcessor | None = get_processor_for_file(file)
    assert proc is not None

    lines: list[str] = file.read_text(encoding="utf-8").splitlines(keepends=True)

    # 1) With explicit span
    new1: list[str] = []
    span1: tuple[int, int] | None = None
    diag1: StripDiagnostic
    new1, span1, diag1 = proc.strip_header_block(lines=lines, span=(1, 3))
    assert diag1.kind == StripDiagKind.REMOVED
    assert new1[0].startswith("#!"), "shebang must be preserved"
    joined1: str = "".join(new1)
    assert TOPMARK_START_MARKER not in joined1
    assert span1 == (1, 3)

    # 2) Without span (processor must detect bounds)
    new2: list[str] = []
    span2: tuple[int, int] | None = None
    diag2: StripDiagnostic

    new2, span2, diag2 = proc.strip_header_block(lines=lines, span=None)
    assert diag2.kind == StripDiagKind.REMOVED
    assert new2 == new1
    assert span2 == (1, 3)


@mark_pipeline
def test_pound_encoding_only_at_top(tmp_path: Path) -> None:
    """Encoding line without shebang (PEP 263 at top).

    Ensures the header still starts at the very top (index 0) when only an
    encoding line is present without a shebang line.
    """
    file: Path = tmp_path / "enc_only.py"
    file.write_text("# -*- coding: utf-8 -*-\nprint('x')\n")
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)
    sig: BlockSignatures = expected_block_lines_for(file)

    lines: list[str] = materialize_updated_lines(ctx)

    # header should still start at top, not after encoding-only line
    assert find_line(lines, sig["start_line"]) == 0


@mark_pipeline
def test_pound_bom_preserved(tmp_path: Path) -> None:
    """Preserve a leading UTF-8 BOM at the start of the output.

    When a file begins with a BOM, the reader strips it in-memory and the updater
    re-attaches it before the first header line. The resulting first output line
    must begin with ``\ufeff``.
    """
    file: Path = tmp_path / "bom.py"
    file.write_bytes(b"\xef\xbb\xbfprint('x')\n")  # UTF-8 BOM
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(file, cfg)
    lines: list[str] = materialize_updated_lines(ctx)

    # BOM should still be present at the beginning of the first line
    assert (lines or [])[0].startswith("\ufeff")


def test_pound_processor_only_removes_first_header_block() -> None:
    """Only the first header occurrence should be removed during strip."""
    p = PoundHeaderProcessor()
    lines: list[str] = [
        f"# {TOPMARK_START_MARKER}\n",
        "# A\n",
        f"# {TOPMARK_END_MARKER}\n",
        "code\n",
        f"# {TOPMARK_START_MARKER}\n",  # Example block later in the file
        "# B\n",
        f"# {TOPMARK_END_MARKER}\n",
        "more\n",
    ]

    new: list[str] = []
    span: tuple[int, int] | None = None
    diag: StripDiagnostic

    new, span, diag = p.strip_header_block(lines=lines, span=(0, 2))

    # First header removed; later example block must remain.
    assert diag.kind == StripDiagKind.REMOVED

    s: str = "".join(new)

    assert "code\n" in s and "more\n" in s
    assert f"# {TOPMARK_START_MARKER}" in s  # second block still present
    assert span == (0, 2)
