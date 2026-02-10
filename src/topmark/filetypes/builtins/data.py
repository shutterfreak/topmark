# topmark:header:start
#
#   project      : TopMark
#   file         : data.py
#   file_relpath : src/topmark/filetypes/builtins/data.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Data and configuration formats.

Defines structured data formats and common config files. Some formats are
headerable (e.g., JSONC, INI, TOML, YAML); others are intentionally skipped
(e.g., plain JSON, PEP 561 marker).

Exports:
    FILETYPES: Concrete definitions for INI, JSON, JSONC,
        Python requirements/constraints, PEP 561 marker (``py.typed``), TOML,
        VS Code JSONC files, and YAML.

Notes:
    - JSONC detection is content-based via
      [`topmark.filetypes.detectors.jsonc.looks_like_jsonc`][] and gated to
      run only for ``.json`` files.
    - Plain JSON is recognized but marked ``skip_processing=True`` to avoid
      inserting headers into a format that does not permit comments.
"""

from __future__ import annotations

from topmark.filetypes.base import ContentGate, FileType
from topmark.filetypes.checks.json_like import json_like_can_insert
from topmark.filetypes.detectors.jsonc import looks_like_jsonc
from topmark.filetypes.policy import FileTypeHeaderPolicy

FILETYPES: list[FileType] = [
    FileType(
        name="ini",
        extensions=[".ini", ".cfg"],
        filenames=[".editorconfig", ".pypirc", ".pypirc.example", "pip.conf"],
        patterns=[],
        description=(
            "INI-style configuration files (*.ini, *.cfg, .editorconfig, .pypirc, pip.conf)"
        ),
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="json",
        extensions=[".json"],
        filenames=[],
        patterns=[],
        description="JSON (no comments; unheaderable)",
        skip_processing=True,
    ),
    FileType(
        name="jsonc",
        extensions=[".json"],
        filenames=[],
        patterns=[],
        description="JSON with comments (JSONC/CJSON)",
        skip_processing=False,
        content_matcher=looks_like_jsonc,
        content_gate=ContentGate.IF_EXTENSION,
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
        pre_insert_checker=json_like_can_insert,
    ),
    FileType(
        name="python-requirements",
        extensions=[],
        filenames=[],
        patterns=[r"requirements.*\.(in|txt)$", r"constraints.*\.txt$"],
        description="Python dependency/constraints files (requirements*.in|txt, constraints*.txt)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="python-typed-marker",
        extensions=[],
        filenames=["py.typed"],
        patterns=[],
        description="PEP 561 marker (single-token file)",
        skip_processing=True,
    ),
    FileType(
        name="toml",
        extensions=[".toml"],
        filenames=[],
        patterns=[],
        description="Tom's Obvious Minimal Language (*.toml)",
    ),
    FileType(
        name="vscode-jsonc",
        extensions=[],
        filenames=[".vscode/settings.json", ".vscode/extensions.json"],
        patterns=[],
        description="VS Code JSON with comments (JSONC)",
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            pre_header_blank_after_block=1,
            ensure_blank_after_header=True,
        ),
    ),
    FileType(
        name="yaml",
        extensions=[".yaml", ".yml"],
        filenames=[],
        patterns=[],
        description="YAML files (*.yaml, *.yml)",
    ),
]
