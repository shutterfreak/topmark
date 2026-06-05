# topmark:header:start
#
#   project      : TopMark
#   file         : paths.py
#   file_relpath : tests/helpers/paths.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared path assertions for machine-readable output tests.

The helpers in this module keep path-contract tests focused on behavior while
still validating nested JSON/NDJSON payloads recursively. They intentionally
assert only the stable machine-output contract: path-like string fields must be
serialized with POSIX separators and must therefore not contain backslashes.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING
from typing import Final

from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    from pathlib import Path


REQUIRE_SYMLINKS_ENV: Final[str] = "TOPMARK_REQUIRE_SYMLINKS"

MACHINE_PATH_FIELD_NAMES: Final[frozenset[str]] = frozenset(
    {
        "path",
        "config_files",
        "origin",
        "scope_root",
    }
)


def assert_machine_path(value: object, *, expected: str | None = None) -> str:
    """Assert that a machine path string uses POSIX separators.

    Args:
        value: Candidate machine-path value.
        expected: Optional exact string expected for the path.

    Returns:
        The validated path string.

    Raises:
        AssertionError: If `value` is not a string, contains a backslash, or
            does not equal `expected` when an expected value is supplied.
    """
    assert isinstance(value, str), f"machine path must be a string, got {value!r}"
    assert "\\" not in value, f"machine path must use POSIX separators: {value!r}"

    if expected is not None:
        assert value == expected

    return value


def assert_machine_path_value(value: object) -> list[str]:
    """Assert one path-like machine value and return all path strings found.

    Path-like fields may either be a single string or a list of strings, for
    example `path` versus `config_files`.

    Args:
        value: Candidate path-like value.

    Returns:
        Validated path strings found in `value`.

    Raises:
        AssertionError: If the value is neither a string nor a list of path
            strings, or if any path string uses non-POSIX separators.
    """
    if isinstance(value, str):
        return [assert_machine_path(value)]

    assert is_any_list(value), f"machine path field must be a string or list: {value!r}"

    paths: list[str] = []
    for item in value:
        paths.append(assert_machine_path(item))
    return paths


def _collect_machine_path_fields(
    value: object,
    path_field_names: frozenset[str],
    paths: list[str],
) -> None:
    """Collect and validate path-like fields from a parsed machine payload."""
    if is_mapping(value):
        mapping: dict[str, object] = as_object_dict(value)
        for key, item in mapping.items():
            if key in path_field_names and item is not None:
                paths.extend(assert_machine_path_value(item))
            _collect_machine_path_fields(item, path_field_names, paths)
        return

    if is_any_list(value):
        for item in value:
            _collect_machine_path_fields(item, path_field_names, paths)


def assert_machine_path_fields_are_posix(
    payload: object,
    *,
    path_field_names: frozenset[str] = MACHINE_PATH_FIELD_NAMES,
) -> list[str]:
    """Assert POSIX serialization for path-like fields in a machine payload.

    The traversal is recursive and intentionally schema-light so that it can be
    reused across processing, probe, config, and registry machine-output tests.

    Args:
        payload: Parsed JSON/NDJSON payload object to inspect.
        path_field_names: Field names whose values should be treated as
            machine-path strings or lists of machine-path strings.

    Returns:
        All validated path strings found under matching path-like field names.

    Raises:
        AssertionError: If a matching path-like field contains an invalid value
            or a string with non-POSIX separators.
    """
    paths: list[str] = []
    _collect_machine_path_fields(payload, path_field_names, paths)
    return paths


def symlink_or_skip(
    link: Path,
    target: Path,
    *,
    target_is_directory: bool = False,
) -> Path:
    """Create a symlink or skip when the platform disallows symlinks.

    Set `TOPMARK_REQUIRE_SYMLINKS=1` in CI jobs where symlink-dependent
    regressions must execute. In that mode, an unavailable symlink capability is
    reported as a test failure instead of a skip.

    Args:
        link: Symlink path to create.
        target: Symlink target.
        target_is_directory: Whether `target` is a directory.

    Returns:
        The created symlink path.
    """
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as exc:
        import pytest

        message: str = f"symlink creation is not available in this test environment: {exc}"
        if os.environ.get(REQUIRE_SYMLINKS_ENV) == "1":
            pytest.fail(message)
        pytest.skip(message)
    return link
