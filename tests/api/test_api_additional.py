# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_additional.py
#   file_relpath : tests/api/test_api_additional.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Additional API tests for TopMark.

Covers edge cases for `api.check`, including mutually exclusive options and
explicit config restricting discovered file types.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import cfg
from topmark import api

if TYPE_CHECKING:
    from pathlib import Path


def test_check_mutually_exclusive_add_update_raises(repo_py_toml_xyz_no_header: Path) -> None:
    """`add_only` and `update_only` are mutually exclusive and should raise."""
    with pytest.raises(ValueError):
        _run_result: api.RunResult = api.check(
            [repo_py_toml_xyz_no_header / "src"],
            apply=False,
            add_only=True,
            update_only=True,
        )


def test_check_with_explicit_config_restricts_file_types(repo_py_toml_xyz_no_header: Path) -> None:
    """Explicit config should restrict discovery to the given file types.

    We pass a config mapping that limits `files.file_types` to ["python"]. The API
    should honor this mapping without merging project config and only return Python files.
    """
    r: api.RunResult = api.check(
        [repo_py_toml_xyz_no_header / "src"],
        apply=False,
        config=cfg(files={"file_types": ["python"]}),
        file_types=None,  # rely solely on config mapping here
    )

    paths: set[Path] = {fr.path for fr in r.files}
    assert repo_py_toml_xyz_no_header / "src" / "without_header.py" in paths
    # The unknown extension should not appear when restricted to python
    assert repo_py_toml_xyz_no_header / "src" / "readme.xyz" not in paths
