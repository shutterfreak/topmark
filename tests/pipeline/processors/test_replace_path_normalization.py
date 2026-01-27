# topmark:header:start
#
#   project      : TopMark
#   file         : test_replace_path_normalization.py
#   file_relpath : tests/pipeline/processors/test_replace_path_normalization.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Replace path newline/BOM normalization guarantees.

Covers:
- Existing CRLF header replaced → resulting file lines remain CRLF (no stray CR).
- Existing LF header *without* final newline replaced → still no final newline.

Relies on the fact that the default command will choose REPLACED when the
existing header differs from the expected header produced by the default config.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.pipeline.conftest import materialize_updated_lines, run_insert
from topmark.config import Config, MutableConfig
from topmark.constants import TOPMARK_END_MARKER, TOPMARK_START_MARKER

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.context.model import ProcessingContext


def _is_crlf_lines(lines: list[str]) -> bool:
    """Return True if all lines (except possibly the last) end with CRLF."""
    if not lines:
        return True

    # Last line may or may not end with newline depending on source.
    return all(ln.endswith("\r\n") for ln in lines[:-1])


def _ends_with_newline(text: str) -> bool:
    return text.endswith("\n") or text.endswith("\r")


def test_replace_preserves_crlf(tmp_path: Path) -> None:
    """Replace on a CRLF-seeded header preserves CRLF endings."""
    f: Path = tmp_path / "a.c"

    # Write with platform newline enforcement: open(newline="\r\n") ensures CRLF.
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write(
            f"// {TOPMARK_START_MARKER}\n// x\n// {TOPMARK_END_MARKER}\nint main(){{return 0;}}\n"
        )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)  # should replace header
    lines: list[str] = materialize_updated_lines(ctx)

    assert _is_crlf_lines(lines), "All lines (but maybe the last) must use CRLF"


def test_replace_preserves_no_final_newline_lf(tmp_path: Path) -> None:
    """Replace on LF-seeded header without final newline preserves that policy."""
    f: Path = tmp_path / "a.py"
    f.write_text(
        f"# {TOPMARK_START_MARKER}\n# x\n# {TOPMARK_END_MARKER}\nprint('x')",  # no final newline
        encoding="utf-8",
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = run_insert(f, cfg)  # should replace header
    lines: list[str] = materialize_updated_lines(ctx)
    out: str = "".join(lines)

    assert not _ends_with_newline(out), "Must preserve absence of final newline"
