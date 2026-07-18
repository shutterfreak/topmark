# topmark:header:start
#
#   project      : TopMark
#   file         : test_file.py
#   file_relpath : tests/utils/test_file.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for filesystem utility helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import topmark.utils.file as file_utils
from tests.helpers.paths import symlink_or_skip
from topmark.utils.file import RebasedGlobPatterns
from topmark.utils.file import compute_relpath
from topmark.utils.file import rebase_glob_patterns
from topmark.utils.file import safe_unlink

if TYPE_CHECKING:
    from collections.abc import Generator


def test_compute_relpath_returns_direct_descendant_without_os_fallback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A descendant should use the direct pathlib relationship."""
    root: Path = tmp_path / "project"
    path: Path = root / "src" / "logical.py"

    def fail_relpath(*args: object, **kwargs: object) -> str:
        pytest.fail("os.path.relpath() should not be called for a descendant")

    monkeypatch.setattr(
        file_utils.os.path,
        "relpath",
        fail_relpath,
    )

    assert compute_relpath(path, root) == Path("src/logical.py")


def test_compute_relpath_returns_dot_for_root_itself(
    tmp_path: Path,
) -> None:
    """A root relative to itself should use pathlib's dot representation."""
    root: Path = tmp_path / "project"

    assert compute_relpath(root, root) == Path()


@pytest.mark.parametrize(
    ("path_parts", "expected"),
    [
        pytest.param(
            ("sibling", "file.py"),
            Path("../sibling/file.py"),
            id="sibling",
        ),
        pytest.param(
            (),
            Path(".."),
            id="ancestor",
        ),
    ],
)
def test_compute_relpath_represents_paths_outside_root(
    tmp_path: Path,
    path_parts: tuple[str, ...],
    expected: Path,
) -> None:
    """Outside paths should retain the normal dot-dot representation."""
    parent: Path = tmp_path / "workspace"
    root: Path = parent / "project"
    path: Path = parent.joinpath(*path_parts)

    assert compute_relpath(path, root) == expected


def test_compute_relpath_resolves_relative_logical_paths_from_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Relative logical paths need not exist and should be anchored to the CWD."""
    monkeypatch.chdir(tmp_path)

    first: Path = compute_relpath(Path("logical/stdin.py"), Path("metadata"))
    second: Path = compute_relpath(Path("logical/stdin.py"), Path("metadata"))

    assert first == Path("../logical/stdin.py")
    assert second == first


def test_compute_relpath_uses_resolved_symlink_target_identity(
    tmp_path: Path,
) -> None:
    """Relative metadata should follow the established resolved target identity."""
    target: Path = tmp_path / "target" / "source.py"
    target.parent.mkdir()
    target.write_text("", encoding="utf-8")
    link: Path = tmp_path / "root" / "source.py"
    link.parent.mkdir()
    symlink_or_skip(link, target)

    assert compute_relpath(link, tmp_path / "root") == Path("../target/source.py")


def test_compute_relpath_returns_resolved_path_for_incompatible_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A cross-drive relpath failure should conservatively retain the absolute path."""
    path: Path = tmp_path / "outside" / "logical.py"
    root: Path = tmp_path / "root"

    def incompatible_roots(*args: object, **kwargs: object) -> str:
        raise ValueError("path is on drive D:, start on drive C:")

    monkeypatch.setattr(
        file_utils.os.path,
        "relpath",
        incompatible_roots,
    )

    assert compute_relpath(path, root) == path.resolve()


def test_compute_relpath_propagates_unexpected_os_fallback_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the documented incompatible-root ValueError should be swallowed."""

    def unexpected_failure(
        *args: object,
        **kwargs: object,
    ) -> str:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(
        file_utils.os.path,
        "relpath",
        unexpected_failure,
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        compute_relpath(tmp_path / "outside", tmp_path / "root")


@pytest.mark.parametrize(
    ("from_parts", "to_parts", "expected_prefix"),
    [
        pytest.param(
            ("project",),
            ("project",),
            "",
            id="same-base",
        ),
        pytest.param(
            ("project", "config"),
            ("project",),
            "config/",
            id="child-base",
        ),
        pytest.param(
            ("project",),
            ("project", "config"),
            "../",
            id="parent-base",
        ),
        pytest.param(
            ("project", "other"),
            ("project", "config"),
            "../other/",
            id="sibling-base",
        ),
    ],
)
def test_rebase_glob_patterns_handles_base_relationships(
    tmp_path: Path,
    from_parts: tuple[str, ...],
    to_parts: tuple[str, ...],
    expected_prefix: str,
) -> None:
    """Successful rebasing should use an exact POSIX-style relative prefix."""
    result: RebasedGlobPatterns = rebase_glob_patterns(
        ["src/**/*.py"],
        from_base=tmp_path.joinpath(*from_parts),
        to_base=tmp_path.joinpath(*to_parts),
    )

    assert result.patterns == [f"{expected_prefix}src/**/*.py"]
    assert result.warnings == []


def test_rebase_glob_patterns_preserves_pattern_text_and_sequence(
    tmp_path: Path,
) -> None:
    """Rebasing should trim/skip edges but not parse or deduplicate glob text."""
    patterns: Generator[str, None, None] = (
        pattern
        for pattern in [
            "  *.py  ",
            "",
            "   ",
            "!generated/**",
            "/src/[a-z]?.py",
            "!/vendor/**",
            "*.py",
        ]
    )

    result: RebasedGlobPatterns = rebase_glob_patterns(
        patterns,
        from_base=tmp_path / "project" / "config",
        to_base=tmp_path / "project",
    )

    assert result.patterns == [
        "config/*.py",
        "!config/generated/**",
        "config/src/[a-z]?.py",
        "!config/vendor/**",
        "config/*.py",
    ]
    assert result.warnings == []


def test_rebase_glob_patterns_cross_root_returns_original_generator_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Incompatible roots should retain input spellings and produce one useful warning."""
    original: list[str] = ["  *.py  ", "!generated/**", "/src/**"]

    def incompatible_roots(
        *args: object,
        **kwargs: object,
    ) -> str:
        raise ValueError("different drives")

    monkeypatch.setattr(
        file_utils.os.path,
        "relpath",
        incompatible_roots,
    )
    from_base: Path = tmp_path / "from"
    to_base: Path = tmp_path / "to"

    result: RebasedGlobPatterns = rebase_glob_patterns(
        (pattern for pattern in original),
        from_base=from_base,
        to_base=to_base,
    )

    assert result.patterns == original
    assert len(result.warnings) == 1
    assert str(from_base) in result.warnings[0]
    assert str(to_base) in result.warnings[0]
    assert "different drives" in result.warnings[0]


def test_rebase_glob_patterns_propagates_unexpected_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unexpected prefix-computation failures should remain visible."""

    def unexpected_failure(
        *args: object,
        **kwargs: object,
    ) -> str:
        raise RuntimeError("unexpected")

    monkeypatch.setattr(
        file_utils.os.path,
        "relpath",
        unexpected_failure,
    )

    with pytest.raises(RuntimeError, match="unexpected"):
        rebase_glob_patterns([], from_base=tmp_path / "from", to_base=tmp_path / "to")


def test_safe_unlink_none_and_missing_path_are_quiet(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Optional or already-absent cleanup targets should be harmless."""
    caplog.set_level(logging.ERROR)

    safe_unlink(None)
    safe_unlink(tmp_path / "missing")

    assert caplog.records == []


def test_safe_unlink_removes_file_and_repeated_cleanup_is_quiet(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Successful cleanup should remove a file and remain idempotent."""
    path: Path = tmp_path / "temporary.txt"
    path.write_text("temporary", encoding="utf-8")
    caplog.set_level(logging.ERROR)

    safe_unlink(path)
    safe_unlink(path)

    assert not path.exists()
    assert caplog.records == []


def test_safe_unlink_logs_and_swallows_oserror(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Deletion failures should be observable without escaping cleanup."""
    path: Path = tmp_path / "temporary.txt"
    path.write_text("temporary", encoding="utf-8")

    def deny_unlink(
        self: Path,
        *,
        missing_ok: bool = False,
    ) -> None:
        raise PermissionError("cleanup denied")

    monkeypatch.setattr(
        Path,
        "unlink",
        deny_unlink,
    )
    caplog.set_level(logging.ERROR)

    safe_unlink(path)

    assert path.exists()
    assert str(path) in caplog.text
    assert "cleanup denied" in caplog.text
