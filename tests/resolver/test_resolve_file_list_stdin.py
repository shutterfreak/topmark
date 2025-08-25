# topmark:header:start
#
#   file         : test_resolve_file_list_stdin.py
#   file_relpath : tests/resolver/test_resolve_file_list_stdin.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for `resolve_file_list` stdin ingestion.

These tests verify that the file resolver:

- Accepts a custom `stdin_stream` and reads paths when `stdin=True`.
- Treats failures while iterating over stdin as *no input*, returning an empty list.

The tests use real temporary files via pytest's `tmp_path` fixture and avoid invoking
Click or the CLI. They focus strictly on the resolver's behavior and typing contract.
"""

from io import StringIO
from pathlib import Path
from typing import Iterator

from topmark.config import Config
from topmark.file_resolver import resolve_file_list


def _cfg(stdin: bool = False) -> Config:
    """Build a minimal `Config` instance for resolver unit tests.

    Starts from defaults and resets fields that influence file selection so tests are
    deterministic and independent of project state.

    Args:
        stdin: Whether the resolver should read candidate paths from stdin.

    Returns:
        Config: A configuration object suitable for `resolve_file_list`.
    """
    # Start from defaults to satisfy all required fields
    cfg = Config.from_defaults()
    # Ensure a clean slate for file resolution
    cfg.stdin = stdin
    cfg.files = []
    cfg.include_patterns = []
    cfg.include_from = []
    cfg.exclude_patterns = []
    cfg.exclude_from = []
    cfg.file_types = set()
    cfg.relative_to = None
    cfg.relative_to_raw = None
    return cfg


def test_reads_paths_from_stdin_when_flag_set(tmp_path: Path) -> None:
    """It should read paths from the provided `stdin_stream` when `stdin=True`.

    The resolver must return the concrete `Path` objects corresponding to lines
    received on the stream.

    Args:
        tmp_path: pytest-provided temporary directory for creating test files.
    """
    # Arrange: create a real file to pass via stdin
    f = tmp_path / "x.py"
    f.write_text("print('ok')\n", encoding="utf-8")

    cfg = _cfg(stdin=True)

    # Act: pass a custom stdin stream (StringIO), not sys.stdin
    out = resolve_file_list(cfg, stdin_stream=StringIO(str(f) + "\n"))

    # Assert: resolver returns a list of Path objects with our file
    assert out == [f]


def test_bad_stdin_is_treated_as_no_input(tmp_path: Path) -> None:
    """It should treat stdin iteration errors as no input and return an empty list.

    The resolver guards the stdin ingestion with a try/except and therefore should
    not raise; higher layers can then handle the "no files" case gracefully.

    Args:
        tmp_path: pytest-provided temporary directory for creating test files.
    """

    class ExplodingIO(StringIO):
        """StringIO subclass that raises during iteration to simulate a broken stdin."""

        def __iter__(self) -> Iterator[str]:  # type: ignore
            """Iterate over the stream and raise to emulate a stdin failure."""
            raise RuntimeError("boom")

    cfg = _cfg(stdin=True)

    # Act: stream iteration raises; resolver should swallow and return []
    out = resolve_file_list(cfg, stdin_stream=ExplodingIO())

    # Assert: treated as no input; higher layers print 'No files...' and exit 0
    assert out == []
