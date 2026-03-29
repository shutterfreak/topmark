# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_more.py
#   file_relpath : tests/api/test_api_more.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Additional API tests: report filtering and parameter precedence."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark import api
from topmark.config.keys import Toml

if TYPE_CHECKING:
    from pathlib import Path


def test_report_scope_distinguishes_actionable_from_noncompliant(
    repo_py_toml_xyz_no_header: Path,
) -> None:
    """API report scopes should distinguish actionable and unsupported results.

    We pass explicit paths so the resolver considers both files. The Python file
    is actionable (missing header) and the `.xyz` file is unsupported.
    """
    src: Path = repo_py_toml_xyz_no_header / "src"
    paths: list[Path] = [src / "without_header.py", src / "note.xyz"]

    r_all: api.RunResult = api.check(
        paths,
        apply=False,
        include_file_types=None,
        report="all",
    )
    paths_all: set[Path] = {fr.path for fr in r_all.files}
    assert src / "without_header.py" in paths_all
    assert src / "note.xyz" in paths_all

    r_actionable: api.RunResult = api.check(
        paths,
        apply=False,
        include_file_types=None,
        report="actionable",
    )
    paths_actionable: set[Path] = {fr.path for fr in r_actionable.files}
    assert src / "without_header.py" in paths_actionable
    assert src / "note.xyz" not in paths_actionable

    r_noncompliant: api.RunResult = api.check(
        paths,
        apply=False,
        include_file_types=None,
        report="noncompliant",
    )
    paths_noncompliant: set[Path] = {fr.path for fr in r_noncompliant.files}
    assert src / "without_header.py" in paths_noncompliant
    assert src / "note.xyz" in paths_noncompliant


def test_include_file_types_param_overrides_config(
    repo_py_toml_xyz_no_header: Path,
) -> None:
    """Explicit API include-file-types should override the config mapping.

    When both `config.files.include_file_types` and the explicit
    `include_file_types=` parameter are provided, the explicit API argument
    should take precedence (replacing the config restriction rather than
    intersecting with it).
    """
    root: Path = repo_py_toml_xyz_no_header
    src: Path = root / "src"
    config_mapping: dict[str, object] = {
        Toml.SECTION_FILES: {
            Toml.KEY_INCLUDE_FILE_TYPES: ["toml"],
        },
    }

    # With config only, the run is restricted to TOML files.
    result_cfg: api.RunResult = api.check(
        [src],
        apply=False,
        config=config_mapping,
        include_file_types=None,
        report="all",
    )
    # The explicit API param should replace the config restriction and select
    # Python files instead.
    result_api: api.RunResult = api.check(
        [src],
        apply=False,
        config=config_mapping,
        include_file_types=["python"],
        report="all",
    )

    view_cfg: set[Path] = {fr.path for fr in result_cfg.files}
    view_api: set[Path] = {fr.path for fr in result_api.files}

    assert src / "data.toml" in view_cfg
    assert src / "without_header.py" not in view_cfg

    assert src / "without_header.py" in view_api
    assert src / "data.toml" not in view_api
