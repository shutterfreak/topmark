# topmark:header:start
#
#   project      : TopMark
#   file         : test_file_type_filters.py
#   file_relpath : tests/resolution/files/test_file_type_filters.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""File-type include/exclude tests for file-list resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.helpers.config import make_frozen_config
from tests.helpers.registry import make_file_type
from tests.resolution.files._helpers import file_resolver_mod
from tests.resolution.files._helpers import py_content_matcher
from tests.resolution.files._helpers import resolve_selected
from tests.resolution.files._helpers import text_content_matcher
from tests.resolution.files._helpers import write
from topmark.core.errors import AmbiguousFileTypeIdentifierError
from topmark.core.errors import InvalidRegistryIdentityError
from topmark.filetypes.model import ContentGate
from topmark.registry.filetypes import FileTypeRegistry

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from topmark.config.model import FrozenConfig
    from topmark.filetypes.model import FileType


def test_file_types_filtering(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Filter final results by configured include_file_types: tuple[str, ...] = () with registry."""
    write(tmp_path / "a.py", "x")
    write(tmp_path / "b.txt", "x")

    with monkeypatch.context() as m:
        m.chdir(tmp_path)

        ft_py: FileType = make_file_type(
            local_key="py",
            content_matcher=py_content_matcher,
            content_gate=ContentGate.ALWAYS,
        )
        FileTypeRegistry.register(ft_py)

        ft_text: FileType = make_file_type(
            local_key="text",
            content_matcher=text_content_matcher,
            content_gate=ContentGate.ALWAYS,
        )
        FileTypeRegistry.register(ft_text)

        try:
            cfg: FrozenConfig = make_frozen_config(
                files=["."],
                include_file_types={"py"},
            )
            files: list[Path] = resolve_selected(cfg)
            rel: list[str] = sorted(p.as_posix() for p in files)

            assert rel == ["a.py"]
        finally:
            FileTypeRegistry.unregister_by_local_key("py")
            FileTypeRegistry.unregister_by_local_key("text")


def test_file_type_unknown_is_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Warn and ignore unknown file types.

    Args:
        tmp_path: Pytest temporary directory fixture.
        monkeypatch: Pytest monkeypatch fixture.
        caplog: Pytest fixture to capture log records.
    """
    (tmp_path / "a.py").write_text("x")
    monkeypatch.chdir(tmp_path)

    ft_py: FileType = make_file_type(
        local_key="py",
        content_matcher=py_content_matcher,
        content_gate=ContentGate.ALWAYS,
    )
    FileTypeRegistry.register(ft_py)

    try:
        caplog.set_level("WARNING")
        include_file_types: set[str] = {"py", "unknown"}
        cfg: FrozenConfig = make_frozen_config(
            files=["."],
            include_file_types=include_file_types,
        )
        files: list[Path] = resolve_selected(cfg)
        assert [p.as_posix() for p in files] == ["a.py"]
        assert any(
            "Unknown included file types specified" in r.message
            # NOTE: see src/topmark/file_resolver.py
            for r in caplog.records
        )
    finally:
        FileTypeRegistry.unregister_by_local_key("py")


def test_multiple_unknown_file_types_warn_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """When multiple unknown file types are configured, warn once listing all."""
    (tmp_path / "a.py").write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    ft_py: FileType = make_file_type(
        local_key="py",
        content_matcher=py_content_matcher,
        content_gate=ContentGate.ALWAYS,
    )
    FileTypeRegistry.register(ft_py)

    try:
        caplog.set_level("WARNING")
        include_file_types: set[str] = {"unknown1", "py", "unknown2"}
        cfg: FrozenConfig = make_frozen_config(
            files=["."],
            include_file_types=include_file_types,
        )
        files: list[Path] = resolve_selected(cfg)
        assert [p.as_posix() for p in files] == ["a.py"]
        msgs: list[str] = [
            r.message
            for r in caplog.records
            if "Unknown included file types specified" in r.message
            # NOTE: see src/topmark/file_resolver.py
        ]
        assert len(msgs) == 1
        assert "unknown1" in msgs[0] and "unknown2" in msgs[0]
    finally:
        FileTypeRegistry.unregister_by_local_key("py")


def test_ambiguous_file_type_identifier_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Ambiguous file type identifiers should warn and resolve to no type."""

    def raise_ambiguous(_file_type_id: str) -> FileType | None:
        raise AmbiguousFileTypeIdentifierError(
            file_type="python",
            candidates=("alpha:python", "beta:python"),
        )

    monkeypatch.setattr(
        FileTypeRegistry,
        "resolve_filetype_id",
        raise_ambiguous,
    )
    caplog.set_level("WARNING")

    resolved: list[FileType] = file_resolver_mod._resolve_configured_file_types(  # pyright: ignore[reportPrivateUsage]
        frozenset({"python"}),
    )

    assert resolved == []
    assert any(
        "Ambiguous file type identifier ignored during file selection: python" in record.message
        for record in caplog.records
    )


def test_malformed_file_type_identifier_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Malformed file type identifiers should warn and resolve to no type."""

    def raise_malformed(_file_type_id: str) -> FileType | None:
        raise InvalidRegistryIdentityError(
            message="bad identifier",
        )

    monkeypatch.setattr(
        FileTypeRegistry,
        "resolve_filetype_id",
        raise_malformed,
    )
    caplog.set_level("WARNING")

    resolved: list[FileType] = file_resolver_mod._resolve_configured_file_types(  # pyright: ignore[reportPrivateUsage]
        frozenset({"bad identifier"}),
    )

    assert resolved == []
    assert any(
        "Malformed file type identifier ignored during file selection: bad identifier"
        in record.message
        for record in caplog.records
    )


def test_exclude_file_type_filter_keeps_non_matching_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Exclude file-type filters should only remove matching file types."""
    py_file: Path = tmp_path / "example.py"
    py_file.write_text("x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    cfg: FrozenConfig = make_frozen_config(
        files=["."],
        exclude_file_types={"markdown"},
    )

    rel: list[str] = [p.as_posix() for p in resolve_selected(cfg)]

    assert rel == ["example.py"]
