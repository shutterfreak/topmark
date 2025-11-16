# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_core.py
#   file_relpath : tests/api/test_api_core.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Core end-to-end tests for `topmark.api`.

These tests exercise discovery, view filtering, conflict validation, and write
behavior (`apply=True`) for `check()` and `strip()`. Registry-specific tests
live in dedicated modules under `tests/api/` to keep concerns separate.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.api.conftest import has_header
from topmark import api
from topmark.api.public_types import PublicPolicy
from topmark.api.types import Outcome

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.pipeline.processors.base import HeaderProcessor


def test_api_check_empty_dir(tmp_path: Path) -> None:
    """Empty directory yields no results and no errors."""
    r: api.RunResult = api.check([tmp_path], apply=False)
    assert r.files == ()
    assert r.summary == {}
    assert r.had_errors is False


def test_skip_compliant_and_unsupported(repo_py_with_header_and_xyz: Path) -> None:
    """View filters reduce results: compliant and unsupported are hideable."""
    root: Path = repo_py_with_header_and_xyz
    r0: api.RunResult = api.check([root / "src"], apply=False, file_types=["python"])
    r1: api.RunResult = api.check(
        [root / "src"], apply=False, file_types=["python"], skip_compliant=True
    )
    r2: api.RunResult = api.check(
        [root / "src"],
        apply=False,
        file_types=["python"],
        skip_compliant=True,
        skip_unsupported=True,
    )
    assert len(r2.files) <= len(r1.files) <= len(r0.files)


def test_add_only_and_update_only_conflict(tmp_path: Path) -> None:
    """Mutually exclusive flags (add_only & update_only) raise ValueError."""
    with pytest.raises(ValueError):
        api.check([tmp_path], apply=False, policy=PublicPolicy(add_only=True, update_only=True))


def test_apply_check_writes_when_needed(
    repo_py_with_and_without_header: Path, proc_py: HeaderProcessor
) -> None:
    """Dry-run reports change; apply writes header for missing file."""
    root: Path = repo_py_with_and_without_header
    target: Path = root / "src" / "without_header.py"
    r0: api.RunResult = api.check(
        [target],
        apply=False,
        file_types=["python"],
        policy=PublicPolicy(add_only=True),
    )
    assert any(fr.outcome in {Outcome.WOULD_INSERT, Outcome.WOULD_UPDATE} for fr in r0.files)
    r1: api.RunResult = api.check(
        [target],
        apply=True,
        file_types=["python"],
        policy=PublicPolicy(add_only=True),
    )
    assert r1.written >= 1
    assert has_header(target.read_text(encoding="utf-8"), proc_py, "\n")


def test_strip_removes_header(repo_py_with_header: Path, proc_py: HeaderProcessor) -> None:
    """Dry-run reports change; apply strips existing header."""
    root: Path = repo_py_with_header
    target: Path = root / "src" / "with_header.py"
    assert has_header(target.read_text(encoding="utf-8"), proc_py, "\n")
    r0: api.RunResult = api.strip([target], apply=False, file_types=["python"])
    # assert any(fr.outcome.value in {"would_change", "changed"} for fr in r0.files)
    assert any(fr.outcome == Outcome.WOULD_STRIP for fr in r0.files)

    r1: api.RunResult = api.strip([target], apply=True, file_types=["python"])
    assert r1.written >= 1
    assert not has_header(target.read_text(encoding="utf-8"), proc_py, "\n")


def test_config_mapping_limits_discovery(tmp_path: Path) -> None:
    """Explicit config mapping narrows discovery to requested file types."""
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("hello\n", encoding="utf-8")
    cfg: dict[str, dict[str, list[str]]] = {"files": {"file_types": ["python"]}}
    r: api.RunResult = api.check([tmp_path / "a.py", tmp_path / "b.txt"], apply=False, config=cfg)
    paths: set[str] = {str(fr.path) for fr in r.files}
    assert str(tmp_path / "a.py") in paths


def test_file_types_argument_filters(tmp_path: Path) -> None:
    """`file_types` argument narrows discovery to specific types."""
    (tmp_path / "a.py").write_text("print('a')\n", encoding="utf-8")
    (tmp_path / "b.toml").write_text("[x]\n", encoding="utf-8")
    r: api.RunResult = api.check([tmp_path], apply=False, file_types=["python"])
    suffixes: set[str] = {fr.path.suffix for fr in r.files}
    assert ".toml" not in suffixes


def test_diagnostics_shape(tmp_path: Path) -> None:
    """Diagnostics field is present and has expected shape (dict or None)."""
    r: api.RunResult = api.check([tmp_path], apply=False)
    assert isinstance(r.diagnostics, (dict, type(None)))
