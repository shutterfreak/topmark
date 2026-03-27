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
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import cast

import pytest

from tests.api.conftest import has_header
from tests.api.conftest import read_text
from topmark import api
from topmark.api.protocols import PublicPolicy
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
