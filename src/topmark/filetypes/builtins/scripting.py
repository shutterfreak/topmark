# topmark:header:start
#
#   project      : TopMark
#   file         : scripting.py
#   file_relpath : src/topmark/filetypes/builtins/scripting.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Scripting and interpreter-driven languages.

Groups languages that commonly use shebangs and may include encoding pragmas.

Exports:
    FILETYPES: Concrete definitions for Julia, Makefile, Perl, Python (and stubs), R, Ruby,
        and POSIX/Bash/Zsh shell scripts.

Notes:
    - Python recognizes ``# coding: ...`` pragmas and preserves shebangs.
    - Makefiles are identified by filename only and do not support shebangs.
"""

from __future__ import annotations

from topmark.filetypes.base import FileType
from topmark.filetypes.policy import FileTypeHeaderPolicy

FILETYPES: list[FileType] = [
    FileType(
        name="julia",
        extensions=[".jl"],
        filenames=[],
        patterns=[],
        description="Julia source files (*.jl)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="makefile",
        extensions=[],
        filenames=["Makefile", "makefile"],
        patterns=[],
        description="Make build scripts (Makefile)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="perl",
        extensions=[".pl", ".pm"],
        filenames=[],
        patterns=[],
        description="Perl scripts/modules (*.pl, *.pm)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="python",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        description="Python source files (*.py)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=r"coding[:=]\s*([-\w.]+)",
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="python-stub",
        extensions=[".pyi"],
        filenames=[],
        patterns=[],
        description="Python type stub files (*.pyi)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="r",
        extensions=[".R", ".r"],
        filenames=[],
        patterns=[],
        description="R scripts (*.R, *.r)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="ruby",
        extensions=[".rb"],
        filenames=[],
        patterns=[],
        description="Ruby source files (*.rb)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=r"(coding|encoding)[:=]\s*([-\w.]+)",
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="shell",
        extensions=[".sh", ".bash", ".zsh"],
        filenames=[],
        patterns=[],
        description="POSIX/Bash/Zsh shell scripts",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
]
