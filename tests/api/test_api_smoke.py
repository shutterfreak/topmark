# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_smoke.py
#   file_relpath : tests/api/test_api_smoke.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Basic smoke tests for the public TopMark API surface."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark import api

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.version.types import VersionInfo


def test_version_is_nonempty_string() -> None:
    """api.commands.version.version() returns nonempty string."""
    v_info: VersionInfo = api.get_version_info()
    v: str = v_info.version_text
    assert isinstance(v, str) and v.strip(), "version() must return a non-empty string"


def test_list_filetypes_includes_python() -> None:
    """api.list_filetypes() contains metadata for the built-in Python file type."""
    items: list[api.FileTypeInfo] = api.list_filetypes()
    assert any(ft.get("local_key") == "python" for ft in items), (
        "python file type must be registered"
    )


def test_list_processors_is_nonempty() -> None:
    """api.list_processors() returns structurally valid processor metadata entries."""
    procs: list[api.ProcessorInfo] = api.list_processors()
    assert procs and all("qualified_key" in p for p in procs), "processors list should not be empty"


def test_strip_dry_run_reports_would_strip(repo_py_with_header: Path) -> None:
    """api.commands.pipeline.strip() reports 'WOULD_STRIP' on supported file without header."""
    r: api.RunResult = api.strip(
        [repo_py_with_header / "src"],
        apply=False,
        include_file_types=["python"],
    )
    # At least one file (with_header.py) should be reported as would_change
    assert api.Outcome.WOULD_STRIP in r.summary
    assert r.written == 0 and r.failed == 0


def test_strip_apply_then_check_is_unchanged(repo_py_with_header: Path) -> None:
    """api.commands.pipeline.check() after api.strip(apply=True) reports 'WOULD_INSERT'."""
    src_dir: Path = repo_py_with_header / "src"

    # Apply strip: remove headers
    r_strip: api.RunResult = api.strip(
        [src_dir],
        apply=True,
        include_file_types=["python"],
    )
    assert r_strip.had_errors is False
    assert r_strip.written >= 1  # header removed

    # Now a dry-run check should say the file would change (header missing),
    # unless the configured policy for missing headers marks it unchanged.
    r_check: api.RunResult = api.check(
        [src_dir],
        apply=False,
        include_file_types=["python"],
    )

    # Accept either: would_change (header would be re-inserted) or unchanged
    # depending on project defaults. Assert at least one bucket is present.
    assert api.Outcome.WOULD_INSERT in r_check.summary
