# topmark:header:start
#
#   project      : TopMark
#   file         : test_pyproject.py
#   file_relpath : tests/toml/test_pyproject.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for exact `[tool.topmark]` extraction."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import pytest
import tomlkit

from topmark.toml.pyproject import extract_pyproject_topmark_table

if TYPE_CHECKING:
    from topmark.toml.types import TomlTable


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"tool": "topmark"},
        {"tool": ["topmark"]},
        {"tool": {"other": {"enabled": True}}},
        {"tool": {"topmark": "enabled"}},
        {"tool": {"topmark": ["enabled"]}},
    ],
)
def test_missing_or_malformed_ownership_tables_return_none(data: TomlTable) -> None:
    """Missing and structurally invalid ownership shapes are not sources."""
    before: TomlTable = copy.deepcopy(data)

    assert extract_pyproject_topmark_table(data) is None
    assert data == before


@pytest.mark.parametrize(
    ("toml_text", "expected"),
    [
        ("[tool.topmark]\n", {}),
        (
            "[tool.topmark.config]\nstrict = false\n",
            {"config": {"strict": False}},
        ),
        (
            'tool.topmark.writer.strategy = "atomic"\n',
            {"writer": {"strategy": "atomic"}},
        ),
    ],
)
def test_ordinary_and_dotted_tables_extract_exact_topmark_mapping(
    toml_text: str,
    expected: TomlTable,
) -> None:
    """Normal TOML syntaxes preserve empty and populated TopMark tables."""
    parsed: TomlTable = tomlkit.parse(toml_text).unwrap()

    assert extract_pyproject_topmark_table(parsed) == expected


def test_extraction_ignores_unrelated_pyproject_content_and_tool_siblings() -> None:
    """Only the exact nested TopMark mapping is returned without input mutation."""
    topmark: TomlTable = {"config": {"strict": True}}
    data: TomlTable = {
        "build-system": {"requires": ["setuptools"]},
        "project": {"name": "demo"},
        "tool": {
            "ruff": {"line-length": 100},
            "topmark": topmark,
        },
    }
    before: TomlTable = copy.deepcopy(data)

    extracted: TomlTable | None = extract_pyproject_topmark_table(data)

    assert extracted == topmark
    assert extracted != data["tool"]
    assert extracted != data
    assert data == before
