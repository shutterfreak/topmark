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
from pathlib import PureWindowsPath
from typing import TYPE_CHECKING
from typing import cast

import pytest

import topmark.utils.path as path_utils
from tests.helpers.paths import symlink_or_skip
from topmark.config.resolution.synthetic import BUILTIN_DEFAULTS_TOML_SOURCE
from topmark.config.resolution.synthetic import BUNDLED_TEMPLATE_TOML_SOURCE
from topmark.config.resolution.synthetic import DEFAULT_CONFIG_SOURCE
from topmark.config.resolution.synthetic import SyntheticConfigSource
from topmark.utils.path import canonical_processing_path
from topmark.utils.path import canonicalize_existing_path
from topmark.utils.path import format_config_source_path
from topmark.utils.path import format_header_metadata_path
from topmark.utils.path import format_machine_path
from topmark.utils.path import format_posix_path

if TYPE_CHECKING:
    from collections.abc import Callable


# ---- path canonicalization tests ----


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


def test_canonicalize_existing_relative_directory_returns_absolute_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative directory inputs should resolve to their absolute identity."""
    directory: Path = tmp_path / "Project" / "Sources"
    directory.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    assert canonicalize_existing_path(Path("Project/Sources")) == directory.resolve()


def test_canonical_processing_path_uses_symlink_target_identity(tmp_path: Path) -> None:
    """Processing identity should collapse symlink spelling to the target path."""
    target: Path = tmp_path / "real" / "source.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hello')\n", encoding="utf-8")
    link: Path = symlink_or_skip(tmp_path / "links" / "source-link.py", target)

    assert canonical_processing_path(link) == target.resolve()


def test_canonical_processing_path_delegates_to_existing_path_canonicalization(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The named processing adapter should retain canonicalization semantics."""
    source: Path = tmp_path / "source.py"
    canonical: Path = tmp_path / "Canonical.py"
    calls: list[Path] = []

    def record(path: Path) -> Path:
        calls.append(path)
        return canonical

    monkeypatch.setattr(
        path_utils,
        "canonicalize_existing_path",
        record,
    )

    assert canonical_processing_path(source) == canonical
    assert calls == [source]


def test_canonicalize_existing_path_returns_resolved_path_when_inspection_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Directory inspection errors should preserve already-resolved identity."""
    path: Path = tmp_path / "Project" / "source.py"
    path.parent.mkdir()
    path.write_text("", encoding="utf-8")
    resolved: Path = path.resolve()

    def inspection_denied(self: Path) -> object:
        raise PermissionError("inspection denied")

    monkeypatch.setattr(
        Path,
        "iterdir",
        inspection_denied,
    )

    assert canonicalize_existing_path(path) == resolved


def test_canonicalize_existing_path_propagates_unexpected_inspection_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only filesystem inspection failures should trigger conservative fallback."""
    path: Path = tmp_path / "source.py"
    path.write_text("", encoding="utf-8")

    def unexpected_failure(self: Path) -> object:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(
        Path,
        "iterdir",
        unexpected_failure,
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        canonicalize_existing_path(path)


@pytest.mark.case_insensitive_fs
def test_canonicalize_existing_path_recovers_directory_entry_casing_when_observable(
    case_insensitive_fs: Path,
) -> None:
    """Case-insensitive filesystems should return spelling stored in directory entries."""
    stored: Path = case_insensitive_fs / "MixedCase" / "Source.PY"
    stored.parent.mkdir()
    stored.write_text("", encoding="utf-8")
    alternate: Path = case_insensitive_fs / "mixedcase" / "source.py"

    assert canonicalize_existing_path(alternate) == stored.resolve()


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
    ("path", "expected"),
    [
        pytest.param(
            PureWindowsPath(r"C:\Repo\src\topmark\pipeline\machine\payloads.py"),
            "C:/Repo/src/topmark/pipeline/machine/payloads.py",
            id="drive-absolute",
        ),
        pytest.param(
            PureWindowsPath(r"D:\Workspace\docs\usage\machine-output.md"),
            "D:/Workspace/docs/usage/machine-output.md",
            id="different-drive-absolute",
        ),
        pytest.param(
            PureWindowsPath(r"\\server\share\project\src\example.py"),
            "//server/share/project/src/example.py",
            id="unc-share",
        ),
    ],
)
def test_format_posix_path_handles_windows_path_spellings(
    path: PureWindowsPath,
    expected: str,
) -> None:
    """Generic POSIX formatting should handle Windows-native path spellings."""
    # `format_posix_path()` intentionally requires only the Path.as_posix()
    # behavior. Cast the pure Windows path so this contract is exercised on
    # every host platform without requiring a real Windows filesystem path.
    assert format_posix_path(cast("Path", path)) == expected


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


@pytest.mark.parametrize(
    ("formatter", "path", "expected"),
    [
        pytest.param(
            format_header_metadata_path,
            PureWindowsPath(r"C:\Repo\src\topmark\__main__.py"),
            "C:/Repo/src/topmark/__main__.py",
            id="header-metadata-drive-path",
        ),
        pytest.param(
            format_machine_path,
            PureWindowsPath(r"D:\Workspace\pkg\module.py"),
            "D:/Workspace/pkg/module.py",
            id="machine-different-drive-path",
        ),
        pytest.param(
            format_machine_path,
            PureWindowsPath(r"\\server\share\pkg\module.py"),
            "//server/share/pkg/module.py",
            id="machine-unc-path",
        ),
    ],
)
def test_semantic_path_formatters_handle_windows_path_spellings(
    formatter: Callable[[Path], str],
    path: PureWindowsPath,
    expected: str,
) -> None:
    """Semantic path formatters should normalize Windows spellings to POSIX."""
    # `format_machine_path()` and `format_header_metadata_path()` delegate to
    # `.as_posix()`. Cast the pure Windows path to cover cross-platform
    # serialization without requiring host-specific path objects.
    assert formatter(cast("Path", path)) == expected


def test_format_config_source_path_uses_posix_separators_for_real_paths() -> None:
    """Real config source paths should serialize using POSIX separators."""
    path: Path = Path("config") / "workspace" / "topmark.toml"

    assert format_config_source_path(path) == "config/workspace/topmark.toml"


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param(
            PureWindowsPath(r"C:\Repo\topmark.toml"),
            "C:/Repo/topmark.toml",
            id="drive-absolute",
        ),
        pytest.param(
            PureWindowsPath(r"\\server\share\topmark.toml"),
            "//server/share/topmark.toml",
            id="unc-share",
        ),
    ],
)
def test_format_config_source_path_handles_windows_path_spellings(
    path: PureWindowsPath,
    expected: str,
) -> None:
    """Real config source paths should normalize Windows spellings to POSIX."""
    # `format_config_source_path()` accepts real filesystem paths and synthetic
    # labels. Cast the pure Windows path so Windows serialization is covered on
    # every host platform.
    assert format_config_source_path(cast("Path", path)) == expected


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
