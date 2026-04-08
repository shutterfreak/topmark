# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_policy_overlays.py
#   file_relpath : tests/api/test_api_policy_overlays.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""API tests for public policy overlays.

These tests focus on the public API policy surface rather than the lower-level
config/policy resolution helpers. They verify that public overlays are:

* validated (`InvalidPolicyError` on invalid tokens)
* applied globally
* applied per file type
* able to override policy coming from an explicit config mapping
* accepted by `strip()` for shared policy fields
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

import pytest

from tests.api.conftest import has_header
from tests.helpers.io import read_text
from topmark import api
from topmark.api.types import PublicPolicy
from topmark.core.errors import InvalidPolicyError

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.processors.base import HeaderProcessor


def unsafe_public_policy(data: dict[str, object]) -> PublicPolicy:
    """Return a deliberately unchecked policy payload for negative API tests.

    Note that we use a narrow cast in this helper:
    - the public API is correctly typed
    - the test intentionally supplies an invalid runtime value
    - Pyright would otherwise prevent reaching the runtime validation path you want to test
    """
    return cast("PublicPolicy", data)


def test_api_invalid_header_mutation_mode_raises_invalid_policy_error(
    repo_py_with_and_without_header: Path,
) -> None:
    """Invalid public `header_mutation_mode` values must be rejected."""
    with pytest.raises(InvalidPolicyError):
        _ = api.check(
            [repo_py_with_and_without_header / "src"],
            apply=False,
            include_file_types=["python"],
            policy=unsafe_public_policy({"header_mutation_mode": "bogus"}),
        )


def test_api_invalid_empty_insert_mode_raises_invalid_policy_error(
    repo_py_with_and_without_header: Path,
) -> None:
    """Invalid public `empty_insert_mode` values must be rejected."""
    with pytest.raises(InvalidPolicyError):
        _ = api.check(
            [repo_py_with_and_without_header / "src"],
            apply=False,
            include_file_types=["python"],
            policy=unsafe_public_policy({"empty_insert_mode": "bogus"}),
        )


def test_api_policy_by_type_overrides_global_policy_for_matching_file_type(
    repo_py_with_and_without_header: Path,
    proc_py: HeaderProcessor,
) -> None:
    """Per-type policy overlays must override the global policy for that type."""
    target: Path = repo_py_with_and_without_header / "src" / "without_header.py"
    assert not has_header(read_text(target), proc_py, "\n")

    r: api.RunResult = api.check(
        [target],
        apply=True,
        include_file_types=["python"],
        policy=PublicPolicy(
            header_mutation_mode="add_only",
        ),
        policy_by_type={
            "python": PublicPolicy(
                header_mutation_mode="update_only",
            ),
        },
    )

    assert r.had_errors is False
    assert r.written == 0
    assert not has_header(read_text(target), proc_py, "\n")


def test_api_public_policy_overlay_overrides_explicit_config_policy(
    repo_py_with_and_without_header: Path,
    proc_py: HeaderProcessor,
) -> None:
    """Public policy overlays must take precedence over explicit config mappings."""
    target: Path = repo_py_with_and_without_header / "src" / "without_header.py"
    assert not has_header(read_text(target), proc_py, "\n")

    config_mapping: dict[str, dict[str, str]] = {
        "policy": {
            "header_mutation_mode": "update_only",
        },
    }

    r: api.RunResult = api.check(
        [target],
        apply=True,
        include_file_types=["python"],
        config=config_mapping,
        policy=PublicPolicy(
            header_mutation_mode="add_only",
        ),
    )

    assert r.had_errors is False
    assert r.written >= 1
    assert has_header(read_text(target), proc_py, "\n")


def test_api_allow_header_in_empty_files_enables_empty_file_insertion(
    tmp_path: Path,
    proc_py: HeaderProcessor,
) -> None:
    """Global API policy overlays should allow insertion into an empty file."""
    target: Path = tmp_path / "empty.py"
    target.write_text("", encoding="utf-8")

    # Default policy should leave the truly empty file untouched.
    r_default: api.RunResult = api.check(
        [target],
        apply=True,
        include_file_types=["python"],
    )
    assert r_default.had_errors is False
    assert r_default.written == 0
    assert read_text(target) == ""

    # Public policy overlay should allow insertion into the empty file.
    target.write_text("", encoding="utf-8")
    r_allowed: api.RunResult = api.check(
        [target],
        apply=True,
        include_file_types=["python"],
        policy=PublicPolicy(
            allow_header_in_empty_files=True,
        ),
    )
    assert r_allowed.had_errors is False
    assert r_allowed.written >= 1
    assert has_header(read_text(target), proc_py, "\n")


def test_api_empty_insert_mode_whitespace_empty_affects_whitespace_only_input(
    tmp_path: Path,
    proc_py: HeaderProcessor,
) -> None:
    """Global API empty-insert policy should affect whitespace-only input."""
    target: Path = tmp_path / "whitespace_only.py"
    whitespace_only: str = " \n \n"

    # Under the default empty-insert mode, this input is not treated as empty,
    # so normal insertion may proceed.
    target.write_text(whitespace_only, encoding="utf-8")
    r_default: api.RunResult = api.check(
        [target],
        apply=True,
        include_file_types=["python"],
    )
    assert r_default.had_errors is False
    assert has_header(read_text(target), proc_py, "\n")

    # Under whitespace-empty mode, the same input is classified as empty and the
    # default policy still forbids insertion into empty files.
    target.write_text(whitespace_only, encoding="utf-8")
    r_whitespace_empty: api.RunResult = api.check(
        [target],
        apply=True,
        include_file_types=["python"],
        policy=PublicPolicy(
            empty_insert_mode="whitespace_empty",
        ),
    )
    assert r_whitespace_empty.had_errors is False
    assert r_whitespace_empty.written == 0
    assert read_text(target) == whitespace_only
    assert not has_header(read_text(target), proc_py, "\n")


def test_api_strip_accepts_shared_policy_overlay(
    repo_py_with_header: Path,
    proc_py: HeaderProcessor,
) -> None:
    """`strip()` should accept shared policy overlays without changing strip semantics."""
    target: Path = repo_py_with_header / "src" / "with_header.py"
    assert has_header(read_text(target), proc_py, "\n")

    r: api.RunResult = api.strip(
        [target],
        apply=True,
        include_file_types=["python"],
        policy=PublicPolicy(
            allow_content_probe=False,
        ),
    )

    assert r.had_errors is False
    assert r.written >= 1
    assert not has_header(read_text(target), proc_py, "\n")


def test_api_invalid_policy_by_type_header_mutation_mode_raises_invalid_policy_error(
    repo_py_with_and_without_header: Path,
) -> None:
    """Invalid per-type public `header_mutation_mode` values must be rejected."""
    with pytest.raises(InvalidPolicyError):
        _ = api.check(
            [repo_py_with_and_without_header / "src"],
            apply=False,
            include_file_types=["python"],
            policy_by_type={
                "python": unsafe_public_policy({"header_mutation_mode": "bogus"}),
            },
        )
