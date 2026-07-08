# topmark:header:start
#
#   project      : TopMark
#   file         : test_discovery_diagnostics.py
#   file_relpath : tests/resolution/files/test_discovery_diagnostics.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Discovery diagnostic tests for file-list resolution."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tests.helpers.config import make_frozen_config
from tests.helpers.paths import symlink_or_skip
from tests.resolution.files._helpers import file_resolver_mod
from tests.resolution.files._helpers import resolve_selected
from tests.resolution.files._helpers import write

if TYPE_CHECKING:
    import pytest

    from topmark.config.model import FrozenConfig


def test_broken_symlink_literal_is_reported_as_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken symlink literal should be reported as a missing input path."""
    link: Path = symlink_or_skip(tmp_path / "links" / "missing.py", tmp_path / "missing.py")

    monkeypatch.chdir(tmp_path)
    cfg: FrozenConfig = make_frozen_config(files=["links/missing.py"])

    result: file_resolver_mod.FileListResolution = (
        file_resolver_mod.resolve_file_list_with_diagnostics(cfg)
    )

    assert result.selected == ()
    assert result.unmatched_patterns == ()
    assert result.missing_literals == (Path("links/missing.py"),)
    assert link.is_symlink()


def test_missing_pattern_files_fail_gracefully(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Missing pattern source files should log an error and fail open."""
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    caplog.set_level("ERROR")

    include_cfg: FrozenConfig = make_frozen_config(
        files=["."],
        include_from=[str(tmp_path / "missing-include.txt")],  # non-existent
    )
    include_files: list[Path] = resolve_selected(include_cfg)
    # Missing include_from files log an error but do not remove candidates.
    assert [p.as_posix() for p in include_files] == ["a.py"]
    assert any("Cannot read patterns from" in r.message for r in caplog.records)

    caplog.clear()
    exclude_cfg: FrozenConfig = make_frozen_config(
        files=["."],
        exclude_from=[str(tmp_path / "missing-exclude.txt")],
    )
    exclude_files: list[Path] = resolve_selected(exclude_cfg)

    assert [p.as_posix() for p in exclude_files] == ["a.py"]
    assert any("Cannot read patterns from" in r.message for r in caplog.records)


def test_missing_exclude_from_file_fails_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Missing exclude_from files should log an error without removing candidates."""
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    caplog.set_level("ERROR")

    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        exclude_from=[str(tmp_path / "missing-exclude.txt")],
    )
    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]

    assert rel == ["a.py"]
    assert any("Cannot read patterns from" in record.message for record in caplog.records)


def test_missing_files_from_file_fails_open_with_no_selected_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Missing files_from sources should log an error and contribute no inputs."""
    write(tmp_path / "src" / "a.py", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        caplog.set_level("ERROR")
        cfg: FrozenConfig = make_frozen_config(
            files_from=[str(tmp_path / "missing-files.txt")],
        )
        resolution: file_resolver_mod.FileListResolution = (
            file_resolver_mod.resolve_file_list_with_diagnostics(cfg)
        )

    assert resolution.selected == ()
    assert resolution.missing_literals == ()
    assert resolution.unmatched_patterns == ()
    assert any("Cannot read file list from" in record.message for record in caplog.records)


def test_nonexistent_literal_paths_are_reported_as_missing_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Missing literal paths should be omitted from selected files but reported."""
    # One real file and one missing literal
    write(tmp_path / "a.py", "x")
    missing: Path = tmp_path / "missing.py"

    with monkeypatch.context() as m:
        m.chdir(tmp_path)
        caplog.set_level("WARNING")

        cfg: FrozenConfig = make_frozen_config(files=["a.py", str(missing)])
        resolution: file_resolver_mod.FileListResolution = (
            file_resolver_mod.resolve_file_list_with_diagnostics(cfg)
        )
        rel: list[str] = [p.as_posix() for p in resolution.selected]

        # Only the existing file should remain selected for processing.
        assert rel == ["a.py"]
        assert resolution.missing_literals == (missing,)
        assert resolution.unmatched_patterns == ()

        # Missing literal paths are still logged as discovery diagnostics.
        msgs: list[str] = [
            r.message for r in caplog.records if "No such file or directory" in r.message
        ]
        assert msgs, "Expected a warning about the missing literal path"


def test_unmatched_glob_patterns_are_reported_as_diagnostics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unmatched glob patterns should be omitted from selected files but reported."""
    monkeypatch.chdir(tmp_path)
    caplog.set_level("WARNING")

    cfg: FrozenConfig = make_frozen_config(files=["missing/**/*.py"])
    resolution: file_resolver_mod.FileListResolution = (
        file_resolver_mod.resolve_file_list_with_diagnostics(cfg)
    )

    assert resolution.selected == ()
    assert resolution.missing_literals == ()
    assert resolution.unmatched_patterns == ("missing/**/*.py",)
    assert any("No matches for glob pattern" in r.message for r in caplog.records)
