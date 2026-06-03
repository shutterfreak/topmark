# topmark:header:start
#
#   project      : TopMark
#   file         : test_path.py
#   file_relpath : tests/utils/test_path.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for path utility helpers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from topmark.config.resolution.synthetic import BUILTIN_DEFAULTS_TOML_SOURCE
from topmark.config.resolution.synthetic import BUNDLED_TEMPLATE_TOML_SOURCE
from topmark.config.resolution.synthetic import DEFAULT_CONFIG_SOURCE
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.utils.path import canonicalize_existing_path
from topmark.utils.path import format_config_source_path
from topmark.utils.path import format_header_metadata_path
from topmark.utils.path import format_machine_path
from topmark.utils.path import format_posix_path

if TYPE_CHECKING:
    from collections.abc import Callable


# ---- path canonalization tests ----


@pytest.mark.parametrize(
    "relative_path",
    [
        pytest.param(Path("TopMark.toml"), id="root-file"),
        pytest.param(Path("Project") / "Config" / "TopMark.toml", id="nested-file"),
    ],
)
def test_canonicalize_existing_path_returns_existing_path(
    tmp_path: Path,
    relative_path: Path,
) -> None:
    """Existing paths should resolve to the same filesystem object."""
    path: Path = tmp_path / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("", encoding="utf-8")

    assert canonicalize_existing_path(path) == path.resolve()


def test_canonicalize_existing_path_requires_existing_path(tmp_path: Path) -> None:
    """Missing paths should fail strict resolution."""
    path: Path = tmp_path / "missing.toml"

    with pytest.raises(FileNotFoundError):
        canonicalize_existing_path(path)


# ---- path POSIX rendering tests ----


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (
            Path("src") / "topmark" / "presentation" / "shared" / "paths.py",
            "src/topmark/presentation/shared/paths.py",
        ),
        (
            Path("docs") / "usage" / "commands" / "config" / "dump.md",
            "docs/usage/commands/config/dump.md",
        ),
    ],
)
def test_format_posix_path_uses_posix_separators(path: Path, expected: str) -> None:
    """Generic POSIX path formatting should use forward slashes."""
    assert format_posix_path(path) == expected


@pytest.mark.parametrize(
    ("formatter", "path", "expected"),
    [
        (
            format_header_metadata_path,
            Path("src") / "topmark" / "presentation" / "shared" / "paths.py",
            "src/topmark/presentation/shared/paths.py",
        ),
        (
            format_machine_path,
            Path("src") / "topmark" / "pipeline" / "machine" / "payloads.py",
            "src/topmark/pipeline/machine/payloads.py",
        ),
    ],
)
def test_semantic_path_formatters_use_posix_separators(
    formatter: Callable[[Path], str],
    path: Path,
    expected: str,
) -> None:
    """Semantic path formatters should preserve POSIX serialization semantics."""
    assert callable(formatter)
    assert formatter(path) == expected


def test_format_config_source_path_uses_posix_separators_for_real_paths() -> None:
    """Real config source paths should serialize using POSIX separators."""
    path: Path = Path("config") / "workspace" / "topmark.toml"

    assert format_config_source_path(path) == "config/workspace/topmark.toml"


@pytest.mark.parametrize(
    "source",
    [
        pytest.param(
            DEFAULT_CONFIG_SOURCE,
            id="defaults",
        ),
        pytest.param(
            BUILTIN_DEFAULTS_TOML_SOURCE,
            id="builtin-toml-default",
        ),
        pytest.param(
            BUNDLED_TEMPLATE_TOML_SOURCE,
            id="bundled-template",
        ),
        pytest.param(
            SyntheticConfigSource(label="<synthetic test config source>"),
            id="custom-synthetic",
        ),
    ],
)
def test_format_config_source_path_preserves_synthetic_labels(
    source: SyntheticConfigSource,
) -> None:
    """Synthetic config source identifiers should remain stable labels."""
    assert format_config_source_path(source) == source.label
