# topmark:header:start
#
#   project      : TopMark
#   file         : filename_rules.py
#   file_relpath : src/topmark/filetypes/filename_rules.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Normalize and validate file type filename rules.

`FileType.filenames` entries are declarative registry matching rules, not
filesystem paths. Rules are stored as canonical POSIX-style strings so registry
output and resolver behavior stay stable across platforms.

A rule may be either an exact basename such as `Makefile` or a relative
tail-subpath such as `.vscode/settings.json`. Backslashes are accepted as
compatibility input and normalized to `/`; absolute paths, drive paths, UNC
paths, empty segments, and `.` / `..` segments are rejected.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING
from typing import Final

from topmark.core.errors import InvalidFileTypeDefinitionError

if TYPE_CHECKING:
    from collections.abc import Iterable


_WINDOWS_DRIVE_RULE_RE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z]:/")


def _normalize_filename_rule(rule: str, *, file_type: str) -> str:
    """Return the canonical POSIX-style representation for a filename rule.

    Args:
        rule: Exact basename or relative tail-subpath filename rule.
        file_type: Qualified file type identifier used in validation errors.

    Returns:
        The canonical filename rule using `/` as separator.

    Raises:
        InvalidFileTypeDefinitionError: If `rule` is not a valid relative
            registry matching rule.
    """
    normalized: str = rule.replace("\\", "/")
    if normalized == "":
        raise InvalidFileTypeDefinitionError(
            message="Invalid filename rule: filename rules must not be empty.",
            file_type=file_type,
            field_name="filenames",
            value=rule,
        )
    if normalized in {".", ".."}:
        raise InvalidFileTypeDefinitionError(
            message=(
                "Invalid filename rule: filename rules must be exact basenames "
                "or relative tail-subpath rules, not directory segments."
            ),
            file_type=file_type,
            field_name="filenames",
            value=rule,
        )
    if normalized.startswith("//"):
        raise InvalidFileTypeDefinitionError(
            message="Invalid filename rule: filename rules must not be UNC paths.",
            file_type=file_type,
            field_name="filenames",
            value=rule,
        )
    if normalized.startswith("/"):
        raise InvalidFileTypeDefinitionError(
            message="Invalid filename rule: filename rules must not be absolute paths.",
            file_type=file_type,
            field_name="filenames",
            value=rule,
        )
    if _WINDOWS_DRIVE_RULE_RE.match(normalized):
        raise InvalidFileTypeDefinitionError(
            message="Invalid filename rule: filename rules must not be Windows drive paths.",
            file_type=file_type,
            field_name="filenames",
            value=rule,
        )

    parts: list[str] = normalized.split("/")
    if any(part == "" for part in parts):
        raise InvalidFileTypeDefinitionError(
            message="Invalid filename rule: filename rules must not contain empty path segments.",
            file_type=file_type,
            field_name="filenames",
            value=rule,
        )
    if any(part in {".", ".."} for part in parts):
        raise InvalidFileTypeDefinitionError(
            message="Invalid filename rule: filename rules must not contain '.' or '..' segments.",
            file_type=file_type,
            field_name="filenames",
            value=rule,
        )
    return normalized


def normalize_filename_rules(rules: Iterable[str], *, file_type: str) -> list[str]:
    """Return canonical POSIX-style filename rules.

    Args:
        rules: Exact basename and relative tail-subpath filename rules to
            normalize.
        file_type: Qualified file type identifier used in validation errors.

    Returns:
        Canonical filename rules using `/` as separator.

    Invalid rules are rejected by the single-rule normalizer before any
    canonical value is returned.
    """
    return [_normalize_filename_rule(rule, file_type=file_type) for rule in rules]
