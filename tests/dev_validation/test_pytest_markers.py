# topmark:header:start
#
#   project      : TopMark
#   file         : test_pytest_markers.py
#   file_relpath : tests/dev_validation/test_pytest_markers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Developer-validation checks for pytest marker hygiene."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import cast

import pytest
import tomlkit

_REPO_ROOT: Path = Path(__file__).resolve().parents[2]
_TESTS_ROOT: Path = _REPO_ROOT / "tests"
_PYPROJECT_PATH: Path = _REPO_ROOT / "pyproject.toml"
_NOXFILE_PATH: Path = _REPO_ROOT / "noxfile.py"
_MAKEFILE_PATH: Path = _REPO_ROOT / "Makefile"
_MARKER_TOKEN_RE: re.Pattern[str] = re.compile(r"\b[A-Za-z_]\w*\b")
_MARK_EXPRESSION_KEYWORDS: frozenset[str] = frozenset({"and", "not", "or"})
_BUILTIN_MARKERS: frozenset[str] = frozenset(
    {
        "filterwarnings",
        "parametrize",
        "skip",
        "skipif",
        "usefixtures",
        "xfail",
    }
)


def _string_key_mapping(value: object, label: str) -> dict[str, object]:
    """Return ``value`` as a string-keyed mapping for TOML table traversal."""
    assert isinstance(value, dict), f"{label} must be a TOML table"

    # Validate the parsed TOML table shape before traversing it.
    raw_mapping: dict[object, object] = cast("dict[object, object]", value)
    mapping: dict[str, object] = {}
    for key, item in raw_mapping.items():
        assert isinstance(key, str), f"{label} contains a non-string key: {key!r}"
        mapping[key] = item
    return mapping


def _string_list(value: object, label: str) -> list[str]:
    """Return ``value`` as a list of strings."""
    assert isinstance(value, list), f"{label} must be a list"
    # Validate the parsed TOML array shape before traversing it.
    raw_items: list[object] = cast("list[object]", value)
    strings: list[str] = []
    for item in raw_items:
        assert isinstance(item, str), f"{label} contains a non-string item: {item!r}"
        strings.append(item)
    return strings


def _declared_pytest_markers() -> frozenset[str]:
    """Return custom pytest markers declared in ``pyproject.toml``."""
    document: tomlkit.TOMLDocument = tomlkit.loads(
        _PYPROJECT_PATH.read_text(
            encoding="utf-8",
        )
    )

    data: dict[str, object] = _string_key_mapping(
        document.unwrap(),
        "pyproject.toml",
    )
    tool: dict[str, object] = _string_key_mapping(data.get("tool"), "[tool]")
    pytest_config: dict[str, object] = _string_key_mapping(
        tool.get("pytest"),
        "[tool.pytest]",
    )
    ini_options: dict[str, object] = _string_key_mapping(
        pytest_config.get("ini_options"),
        "[tool.pytest.ini_options]",
    )
    marker_entries: list[str] = _string_list(
        ini_options.get("markers"),
        "[tool.pytest.ini_options].markers",
    )

    return frozenset(entry.split(":", maxsplit=1)[0].strip() for entry in marker_entries)


def _python_test_files() -> list[Path]:
    """Return Python test files, excluding interpreter and pytest cache directories."""
    return [
        path
        for path in sorted(_TESTS_ROOT.rglob("*.py"))
        if not path.name.startswith("._")
        and "__pycache__" not in path.parts
        and ".pytest_cache" not in path.parts
    ]


def _pytest_mark_names_from_file(path: Path) -> set[str]:
    """Return names used through ``pytest.mark.<name>`` in a Python file."""
    tree: ast.Module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        if not isinstance(node.value, ast.Attribute) or node.value.attr != "mark":
            continue
        if not isinstance(node.value.value, ast.Name) or node.value.value.id != "pytest":
            continue
        names.add(node.attr)
    return names


def _marker_tokens(expression: str) -> set[str]:
    """Extract marker names from a pytest ``-m`` expression string."""
    return {
        token
        for token in _MARKER_TOKEN_RE.findall(expression)
        if token not in _MARK_EXPRESSION_KEYWORDS
    }


def _nox_marker_expressions() -> list[str]:
    """Return pytest marker expressions passed through nox ``session.run`` calls."""
    tree: ast.Module = ast.parse(
        _NOXFILE_PATH.read_text(encoding="utf-8"), filename=str(_NOXFILE_PATH)
    )
    expressions: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        arguments: list[ast.expr] = list(node.args)
        command_parts: list[str] = [
            argument.value
            for argument in arguments
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str)
        ]
        if "pytest" not in command_parts:
            continue

        for index, argument in enumerate(arguments[:-1]):
            next_argument: ast.expr = arguments[index + 1]
            if not isinstance(argument, ast.Constant) or argument.value != "-m":
                continue
            if not isinstance(next_argument, ast.Constant) or not isinstance(
                next_argument.value, str
            ):
                continue
            expressions.append(next_argument.value)
    return expressions


def _makefile_marker_expressions() -> list[str]:
    """Return pytest marker expressions passed through Makefile recipes."""
    expressions: list[str] = []
    lines: list[str] = _MAKEFILE_PATH.read_text(encoding="utf-8").splitlines()
    for line in lines:
        if "pytest" not in line or " -m " not in line:
            continue
        match: re.Match[str] | None = re.search(
            r"\s-m\s+(?P<quote>[\"'])(?P<expression>.+?)(?P=quote)",
            line,
        )
        if match is None:
            continue
        expressions.append(match.group("expression"))
    return expressions


def _tool_marker_expressions() -> dict[str, list[str]]:
    """Return pytest marker expressions grouped by project tooling source."""
    return {
        "Makefile": _makefile_marker_expressions(),
        "noxfile.py": _nox_marker_expressions(),
    }


@pytest.mark.dev_validation
def test_used_custom_pytest_markers_are_declared() -> None:
    """Every custom marker used in tests is declared in pytest configuration."""
    declared_markers: frozenset[str] = _declared_pytest_markers()
    used_markers: set[str] = set()
    for path in _python_test_files():
        used_markers.update(_pytest_mark_names_from_file(path))

    custom_markers: set[str] = used_markers - _BUILTIN_MARKERS
    undeclared_markers: list[str] = sorted(custom_markers - declared_markers)

    assert undeclared_markers == [], f"Undeclared custom pytest markers: {undeclared_markers!r}"


@pytest.mark.dev_validation
def test_declared_pytest_markers_are_used_or_referenced_by_tooling() -> None:
    """Declared custom markers should be used or referenced by project tooling."""
    declared_markers: frozenset[str] = _declared_pytest_markers()

    used_markers: set[str] = set()
    for path in _python_test_files():
        used_markers.update(_pytest_mark_names_from_file(path))

    custom_markers: set[str] = used_markers - _BUILTIN_MARKERS

    referenced_markers: set[str] = set()
    for expressions in _tool_marker_expressions().values():
        for expression in expressions:
            referenced_markers.update(_marker_tokens(expression))

    unused: list[str] = sorted(
        marker
        for marker in declared_markers
        if marker not in custom_markers and marker not in referenced_markers
    )

    assert unused == [], f"Declared pytest markers are unused: {unused!r}"


@pytest.mark.dev_validation
def test_tool_pytest_marker_expressions_reference_declared_markers() -> None:
    """Project tooling pytest marker selections reference declared custom markers."""
    declared_markers: frozenset[str] = _declared_pytest_markers()
    unknown_by_source: dict[str, dict[str, list[str]]] = {}
    for source, expressions in _tool_marker_expressions().items():
        unknown_by_expression: dict[str, list[str]] = {
            expression: sorted(_marker_tokens(expression) - declared_markers)
            for expression in expressions
            if _marker_tokens(expression) - declared_markers
        }
        if unknown_by_expression:
            unknown_by_source[source] = unknown_by_expression

    assert unknown_by_source == {}, (
        "Project tooling pytest marker expressions reference undeclared markers: "
        f"{unknown_by_source!r}"
    )
