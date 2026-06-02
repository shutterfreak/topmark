# topmark:header:start
#
#   project      : TopMark
#   file         : test_path.py
#   file_relpath : tests/utils/test_path.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for path utility helpers."""

from __future__ import annotations

from pathlib import Path

from topmark.utils.path import format_header_metadata_path
from topmark.utils.path import format_machine_path


def test_format_header_metadata_path_uses_posix_separators() -> None:
    """Header metadata paths should serialize using POSIX separators."""
    path: Path = Path("src") / "topmark" / "presentation" / "shared" / "paths.py"

    assert format_header_metadata_path(path) == "src/topmark/presentation/shared/paths.py"


def test_format_machine_path_uses_posix_separators() -> None:
    """Machine-output paths should serialize using POSIX separators."""
    path: Path = Path("src") / "topmark" / "pipeline" / "machine" / "payloads.py"

    assert format_machine_path(path) == "src/topmark/pipeline/machine/payloads.py"
