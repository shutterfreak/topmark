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

_TESTS_ROOT: Path = Path(__file__).resolve().parents[1]
_IGNORED_DIR_NAMES: frozenset[str] = frozenset({".pytest_cache", "__pycache__"})


def _contains_python_file(path: Path) -> bool:
    """Return whether the directory contains at least one Python source file."""
    return any(child.is_file() and child.suffix == ".py" for child in path.iterdir())


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
