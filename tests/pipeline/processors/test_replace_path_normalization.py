# topmark:header:start
#
#   file         : test_replace_path_normalization.py
#   file_relpath : tests/pipeline/processors/test_replace_path_normalization.py
#   project      : TopMark
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

from tests.pipeline.conftest import run_insert
from topmark.config import Config


def _is_crlf_lines(lines: list[str]) -> bool:
    """Return True if all lines (except possibly the last) end with CRLF."""
    if not lines:
        return True
    for ln in lines[:-1]:
        if not ln.endswith("\r\n"):
            return False
    # Last line may or may not end with newline depending on source.
    return True


def _ends_with_newline(text: str) -> bool:
    return text.endswith("\n") or text.endswith("\r")


def test_replace_preserves_crlf(tmp_path: Path) -> None:
    """Replace on a CRLF-seeded header preserves CRLF endings."""
    f = tmp_path / "a.c"

    # Write with platform newline enforcement: open(newline="\r\n") ensures CRLF.
    with f.open("w", encoding="utf-8", newline="\r\n") as fp:
        fp.write("// topmark:header:start\n// x\n// topmark:header:end\nint main(){return 0;}\n")

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)  # should replace header
    lines = ctx.updated_file_lines or []
    assert _is_crlf_lines(lines), "All lines (but maybe the last) must use CRLF"


def test_replace_preserves_no_final_newline_lf(tmp_path: Path) -> None:
    """Replace on LF-seeded header without final newline preserves that policy."""
    f = tmp_path / "a.py"
    f.write_text(
        "# topmark:header:start\n# x\n# topmark:header:end\nprint('x')",  # no final newline
        encoding="utf-8",
    )

    cfg = Config.from_defaults()
    ctx = run_insert(f, cfg)  # should replace header
    out = "".join(ctx.updated_file_lines or [])
    assert not _ends_with_newline(out), "Must preserve absence of final newline"
