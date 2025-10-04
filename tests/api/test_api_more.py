# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_more.py
#   file_relpath : tests/api/test_api_more.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Additional API tests: skip_unsupported and parameter precedence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.api.conftest import cfg
from topmark import api

if TYPE_CHECKING:
    from pathlib import Path


def test_skip_unsupported_hides_unsupported_files(repo_py_toml_xyz_no_header: Path) -> None:
    """When skip_unsupported=True, view filtering should hide unsupported files.

    We pass explicit paths so the resolver considers both files; the unsupported one
    should be filtered out in the returned file list when skip_unsupported=True.
    """
    src: Path = repo_py_toml_xyz_no_header / "src"
    paths: list[Path] = [src / "without_header.py", src / "note.xyz"]

    r_no_skip: api.RunResult = api.check(
        paths, apply=False, file_types=None, skip_unsupported=False
    )
    paths_no_skip: set[Path] = {fr.path for fr in r_no_skip.files}
    assert src / "without_header.py" in paths_no_skip
    # unsupported may still appear in view when skip_unsupported=False
    assert (src / "note.xyz") in paths_no_skip

    r_skip: api.RunResult = api.check(paths, apply=False, file_types=None, skip_unsupported=True)
    paths_skip: set[Path] = {fr.path for fr in r_skip.files}
    assert src / "without_header.py" in paths_skip
    # now it should be filtered out
    assert (src / "note.xyz") not in paths_skip


def test_file_types_param_overrides_config(repo_py_toml_xyz_no_header: Path) -> None:
    """Test 'file_types' override in config and API.

    When both config.files.file_types and file_types param are provided,
    the explicit API parameter should take precedence (narrowing).
    """
    src: Path = repo_py_toml_xyz_no_header / "src"

    # Config would allow python and toml; explicit param narrows to python only.
    r: api.RunResult = api.check(
        [src],
        apply=False,
        config=cfg(files={"file_types": ["python", "toml"]}),
        file_types=["python"],
    )
    seen: set[Path] = {fr.path for fr in r.files}
    assert src / "without_header.py" in seen
    assert (src / "data.toml") not in seen
