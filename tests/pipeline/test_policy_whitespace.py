# topmark:header:start
#
#   project      : TopMark
#   file         : test_policy_whitespace.py
#   file_relpath : tests/pipeline/test_policy_whitespace.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for policy-aware whitespace classification helpers."""

from __future__ import annotations

import pytest

from topmark.filetypes.policy import BlankCollapseMode
from topmark.filetypes.policy import FileTypeHeaderPolicy
from topmark.pipeline.policy_whitespace import is_effectively_empty_body
from topmark.pipeline.policy_whitespace import is_pure_spacer


def test_pure_spacer_uses_strict_defaults_without_policy() -> None:
    """Default spacer classification preserves control characters."""
    assert is_pure_spacer("", None) is True
    assert is_pure_spacer(" \t", None) is True
    assert is_pure_spacer("\n", None) is True
    assert is_pure_spacer(" \t\r\n", None) is True
    assert is_pure_spacer("\ufeff \t\n", None) is True
    assert is_pure_spacer("\x0c\n", None) is False


def test_pure_spacer_unicode_policy_accepts_unicode_whitespace() -> None:
    """UNICODE mode treats non-ASCII whitespace as blank content."""
    policy = FileTypeHeaderPolicy(blank_collapse_mode=BlankCollapseMode.UNICODE)

    assert is_pure_spacer("\u2003\n", policy) is True
    assert is_pure_spacer("\x0c\n", policy) is True
    assert is_pure_spacer("x\n", policy) is False


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
def test_pure_spacer_recognizes_supported_physical_newlines(newline: str) -> None:
    """Exact supported EOLs remain spacers even when collapsing is disabled."""
    policy = FileTypeHeaderPolicy(blank_collapse_mode=BlankCollapseMode.NONE)

    assert is_pure_spacer(newline, policy) is True


def test_pure_spacer_none_policy_preserves_non_empty_lines() -> None:
    """NONE mode still accepts empty/EOL-only lines but preserves contentful whitespace."""
    policy = FileTypeHeaderPolicy(blank_collapse_mode=BlankCollapseMode.NONE)

    assert is_pure_spacer(" \n", policy) is False
    assert is_pure_spacer("\ufeff\n", policy) is False


@pytest.mark.parametrize(
    "mode",
    [BlankCollapseMode.STRICT, BlankCollapseMode.UNICODE],
)
def test_pure_spacer_respects_extra_collapsible_characters(mode: BlankCollapseMode) -> None:
    """Extra collapse characters extend both strict and unicode policies."""
    policy = FileTypeHeaderPolicy(blank_collapse_mode=mode, blank_collapse_extra="-")

    assert is_pure_spacer("---\n", policy) is True
    assert is_pure_spacer("--x\n", policy) is False


def test_effectively_empty_body_uses_strict_defaults_without_policy() -> None:
    """Default empty-body checks preserve control characters such as form-feed."""
    assert is_effectively_empty_body([], None) is True
    assert is_effectively_empty_body(["", "\ufeff", " \t\n"], None) is True
    assert is_effectively_empty_body([" \t\n", "\x0c\n"], None) is False


def test_effectively_empty_body_honors_unicode_policy() -> None:
    """UNICODE mode allows Unicode whitespace-only bodies to collapse."""
    policy = FileTypeHeaderPolicy(blank_collapse_mode=BlankCollapseMode.UNICODE)

    assert is_effectively_empty_body(["\u2003\n", "\x0c\n"], policy) is True
    assert is_effectively_empty_body(["\u2003x\n"], policy) is False


def test_effectively_empty_body_honors_none_policy() -> None:
    """NONE mode treats every non-empty body line as meaningful content."""
    policy = FileTypeHeaderPolicy(blank_collapse_mode=BlankCollapseMode.NONE)

    assert is_effectively_empty_body([""], policy) is True
    assert is_effectively_empty_body(["\n"], policy) is False
    assert is_effectively_empty_body([" \n"], policy) is False


@pytest.mark.parametrize(
    "mode",
    [BlankCollapseMode.STRICT, BlankCollapseMode.UNICODE],
)
def test_effectively_empty_body_respects_extra_collapsible_characters(
    mode: BlankCollapseMode,
) -> None:
    """Extra collapse characters can opt selected content into empty-body treatment."""
    policy = FileTypeHeaderPolicy(
        blank_collapse_mode=mode,
        blank_collapse_extra="-",
    )

    assert is_effectively_empty_body(["---\n", "\ufeff-\r\n"], policy) is True
    assert is_effectively_empty_body(["--x\n"], policy) is False
