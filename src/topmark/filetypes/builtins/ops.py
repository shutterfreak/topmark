# topmark:header:start
#
#   project      : TopMark
#   file         : ops.py
#   file_relpath : src/topmark/filetypes/builtins/ops.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Operations and infrastructure files.

Covers operational artifacts such as Dockerfiles, environment files, Git
metadata, and SQL scripts.

Exports:
    FILETYPES (list[FileType]): Concrete definitions for Dockerfile, ``.env``
        files (and variants), Git metadata (``.gitignore``, ``.gitattributes``),
        and SQL scripts.

Notes:
    - ``.env`` files are treated like shell-style key/value lists. Shebang is
      allowed for portability, but typically absent.
    - Dockerfiles are matched by filename and pattern (e.g., ``Dockerfile.dev``).
"""

from __future__ import annotations

from topmark.filetypes.policy import FileTypeHeaderPolicy

from ..base import FileType

FILETYPES: list[FileType] = [
    FileType(
        name="dockerfile",
        extensions=[],
        filenames=["Dockerfile"],
        patterns=[r"Dockerfile(\..+)?"],
        description="Dockerfiles",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="env",
        extensions=[],
        filenames=[".env"],
        patterns=[r"\.env\..*"],
        description="Environment variable definition files (.env, .env.*)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=True,
            encoding_line_regex=None,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="git-meta",
        extensions=[],
        filenames=[".gitignore", ".gitattributes"],
        patterns=[],
        description="Git metadata files (.gitignore, .gitattributes)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="sql",
        extensions=[".sql"],
        filenames=[],
        patterns=[],
        description="SQL scripts (*.sql)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    ),
]
