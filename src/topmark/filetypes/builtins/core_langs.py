# topmark:header:start
#
#   project      : TopMark
#   file         : core_langs.py
#   file_relpath : src/topmark/filetypes/builtins/core_langs.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Core, curly-brace, and compiled languages.

Groups classic C-family and similar languages that typically use ``//`` and
``/* ... */`` comments and do not require shebang handling.

Exports:
    FILETYPES: Concrete definitions for C, C++, C#, Go, Java, Kotlin, Rust, Solidity, and Swift.

Notes:
    Header policies in this module generally disable shebang support and enforce a blank line after
    inserted headers to keep code visually separated.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.filetypes.factory import BUILTIN_FILETYPE_FACTORY
from topmark.filetypes.policy import FileTypeHeaderPolicy

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType

FILETYPES: list[FileType] = [
    BUILTIN_FILETYPE_FACTORY(
        name="c",
        extensions=[".c", ".h"],
        filenames=[],
        patterns=[],
        description="C sources and headers (*.c, *.h)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    BUILTIN_FILETYPE_FACTORY(
        name="cpp",
        extensions=[".cc", ".cxx", ".cpp", ".hh", ".hpp", ".hxx"],
        filenames=[],
        patterns=[],
        description="C++ sources and headers (*.cc, *.cxx, *.cpp, *.hh, *.hpp, *.hxx)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    BUILTIN_FILETYPE_FACTORY(
        name="cs",
        extensions=[".cs"],
        filenames=[],
        patterns=[],
        description="C# sources (*.cs)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    BUILTIN_FILETYPE_FACTORY(
        name="go",
        extensions=[".go"],
        filenames=[],
        patterns=[],
        description="Go sources (*.go)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    BUILTIN_FILETYPE_FACTORY(
        name="java",
        extensions=[".java"],
        filenames=[],
        patterns=[],
        description="Java sources (*.java)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    BUILTIN_FILETYPE_FACTORY(
        name="kotlin",
        extensions=[".kt", ".kts"],
        filenames=[],
        patterns=[],
        description="Kotlin sources (*.kt, *.kts)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    BUILTIN_FILETYPE_FACTORY(
        name="rust",
        extensions=[".rs"],
        filenames=[],
        patterns=[],
        description="Rust sources (*.rs)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    BUILTIN_FILETYPE_FACTORY(
        name="solidity",
        extensions=[".sol"],
        filenames=[],
        patterns=[],
        description="Solidity smart contracts (*.sol)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    ),
    BUILTIN_FILETYPE_FACTORY(
        name="swift",
        extensions=[".swift"],
        filenames=[],
        patterns=[],
        description="Swift sources (*.swift)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
]
