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
from topmark.core.outcomes import Outcome

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.api.types import FileTypeInfo
    from topmark.api.types import ProcessorInfo
    from topmark.version.types import VersionInfo


def test_version_is_nonempty_string() -> None:
    """api.commands.version.version() returns nonempty string."""
    v_info: VersionInfo = api.get_version_info()
    v: str = v_info.version_text
    assert isinstance(v, str) and v.strip(), "version() must return a non-empty string"


def test_get_version_text_is_convenience_string_form() -> None:
    """get_version_text() mirrors the non-SemVer structured version view."""
    version_text: str = api.get_version_text()

    assert isinstance(version_text, str)
    assert version_text.strip()
    assert version_text == api.get_version_info(semver=False).version_text


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


def test_registry_helpers_return_detached_primitive_metadata() -> None:
    """Registry helpers project identities, tuples, policies, and delimiters."""
    filetypes_before: list[FileTypeInfo] = api.list_filetypes()
    processors_before: list[ProcessorInfo] = api.list_processors()

    python: FileTypeInfo = next(item for item in filetypes_before if item["local_key"] == "python")
    assert python["qualified_key"] == f"{python['namespace']}:{python['local_key']}"
    assert isinstance(python["extensions"], tuple)
    assert isinstance(python["filenames"], tuple)
    assert isinstance(python["patterns"], tuple)
    assert python["bound"] is True
    assert set(python["policy"]) == {
        "blank_collapse_extra",
        "blank_collapse_mode",
        "encoding_line_regex",
        "ensure_blank_after_header",
        "pre_header_blank_after_block",
        "supports_shebang",
    }

    processor: ProcessorInfo = processors_before[0]
    assert processor["qualified_key"] == (f"{processor['namespace']}:{processor['local_key']}")
    for delimiter in (
        "line_indent",
        "line_prefix",
        "line_suffix",
        "block_prefix",
        "block_suffix",
    ):
        assert isinstance(processor[delimiter], str)

    filetypes_before[0]["description"] = "detached test value"
    processors_before[0]["description"] = "detached test value"
    assert api.list_filetypes()[0]["description"] != "detached test value"
    assert api.list_processors()[0]["description"] != "detached test value"


def test_strip_dry_run_reports_would_strip(repo_py_with_header: Path) -> None:
    """api.commands.pipeline.strip() reports 'WOULD_STRIP' on supported file without header."""
    r: api.RunResult = api.strip(
        [repo_py_with_header / "src"],
        apply=False,
        include_file_types=["python"],
    )
    # At least one file (with_header.py) should be reported as would_change
    assert Outcome.WOULD_STRIP in r.summary
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
    assert Outcome.WOULD_INSERT in r_check.summary
