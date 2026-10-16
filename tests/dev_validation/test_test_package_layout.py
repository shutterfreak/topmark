# topmark:header:start
#
#   project      : TopMark
#   file         : test_test_package_layout.py
#   file_relpath : tests/dev_validation/test_test_package_layout.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Developer-validation checks for the test package layout."""

from __future__ import annotations

from pathlib import Path

import pytest
import tomlkit

from topmark.core.typing_guards import is_mapping
from topmark.core.typing_guards import is_str_list
from topmark.toml.typing_guards import is_toml_table

_TESTS_ROOT: Path = Path(__file__).resolve().parents[1]
_PYPROJECT_PATH: Path = _TESTS_ROOT.parent / "pyproject.toml"
_IGNORED_DIR_NAMES: frozenset[str] = frozenset({".pytest_cache", "__pycache__"})


def _contains_python_file(path: Path) -> bool:
    """Return whether the directory contains at least one Python source file."""
    return any(child.is_file() and child.suffix == ".py" for child in path.iterdir())


def _pytest_norecursedirs() -> frozenset[str]:
    """Return the directory names pytest must not recurse into."""
    document: tomlkit.TOMLDocument = tomlkit.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))

    toml_obj: object = document.unwrap()
    assert is_mapping(toml_obj), "pyproject.toml must contain a top-level TOML table"

    tool_tbl: object = toml_obj.get("tool")
    assert is_toml_table(tool_tbl), "[tool] must be a TOML table"

    pytest_config: object = tool_tbl.get("pytest")
    assert is_toml_table(pytest_config), "[tool.pytest] must be a TOML table"

    ini_options: object = pytest_config.get("ini_options")
    assert is_toml_table(ini_options), "[tool.pytest.ini_options] must be a TOML table"

    values: object = ini_options.get("norecursedirs")
    assert isinstance(values, list), "norecursedirs must be a TOML array"
    assert is_str_list(values), "norecursedirs must contain strings"

    return frozenset(values)


@pytest.mark.dev_validation
def test_python_test_directories_are_packages() -> None:
    """Every test directory containing Python modules has an ``__init__.py`` marker."""
    missing: list[str] = [
        path.relative_to(_TESTS_ROOT).as_posix() or "."
        for path in [_TESTS_ROOT, *sorted(_TESTS_ROOT.rglob("*"))]
        if path.is_dir()
        and path.name not in _IGNORED_DIR_NAMES
        and _contains_python_file(path)
        and not (path / "__init__.py").is_file()
    ]

    assert missing == [], f"Test directories without __init__.py: {missing!r}"


@pytest.mark.dev_validation
def test_pytest_recursion_keeps_repository_tooling_tests_collectible() -> None:
    """Generic recursion exclusions do not hide source-aligned tooling test packages."""
    norecursedirs: frozenset[str] = _pytest_norecursedirs()

    assert {
        "tools",
        "docs",
    }.isdisjoint(norecursedirs)
    assert ".zensical" in norecursedirs
