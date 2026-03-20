# topmark:header:start
#
#   project      : TopMark
#   file         : test_processor_key_token.py
#   file_relpath : tests/unit/test_processor_key_token.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for processor key token validity and registry key semantics.

These tests cover:
- token validation for processor `namespace` and `key` (regex-based),
- `HeaderProcessor.__init_subclass__` validation behavior, and
- duplicate qualified-key detection during processor-registry composition.

See [`topmark.processors.base`][topmark.processors.base].
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from hypothesis import given
from hypothesis import strategies as st

from tests.conftest import make_file_type
from topmark.constants import TOPMARK_NAMESPACE
from topmark.constants import VALID_REGISTRY_TOKEN_RE
from topmark.core.errors import DuplicateProcessorKeyError
from topmark.processors.base import HeaderProcessor
from topmark.registry.filetypes import FileTypeRegistry
from topmark.registry.processors import HeaderProcessorRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType

TOKEN_RE: re.Pattern[str] = re.compile(f"^{VALID_REGISTRY_TOKEN_RE}$")


# ----------------------------
# Hypothesis property tests
# ----------------------------

# Generate valid tokens directly from the same regex used by production.
VALID_TOKEN: st.SearchStrategy[str] = st.from_regex(f"^{VALID_REGISTRY_TOKEN_RE}$", fullmatch=True)

# Generate *mostly* ASCII-ish strings, then filter out those that are valid.
# Keep the alphabet small to avoid performance issues.
INVALID_TOKEN: st.SearchStrategy[str] = st.text(
    alphabet=st.characters(
        # Avoid control characters that can make failures unreadable.
        blacklist_categories=("Cs", "Cc"),
        min_codepoint=0x20,
        max_codepoint=0x7E,
    ),
    min_size=0,
    max_size=32,
).filter(lambda s: TOKEN_RE.fullmatch(s) is None)


@given(VALID_TOKEN)
def test_token_regex_accepts_all_valid_tokens(token: str) -> None:
    """Property test: every generated valid token must match."""
    assert TOKEN_RE.fullmatch(token)


@given(INVALID_TOKEN)
def test_token_regex_rejects_invalid_tokens(token: str) -> None:
    """Property test: every generated invalid token must not match."""
    assert TOKEN_RE.fullmatch(token) is None


# ----------------------------
# Targeted example tests
# ----------------------------


@pytest.mark.parametrize(
    "token",
    [
        # minimal
        "a",
        "x",
        # alphanumeric
        "abc",
        "a1",
        "py3",
        # underscores
        "c_block",
        "a_b_c",
        # hyphens
        "c-block",
        "a-b-c",
        # dots
        "x.y",
        "x.y.z",
        # mixed separators
        "a1-b2.c3_d4",
        "xml.v1",
        "builtin_processor",
    ],
)
def test_valid_tokens_examples(token: str) -> None:
    """Allow valid tokens."""
    assert TOKEN_RE.fullmatch(token), f"Expected valid token: {token}"


@pytest.mark.parametrize(
    "token",
    [
        # empty
        "",
        # must start with letter
        "1abc",
        "_abc",
        "-abc",
        ".abc",
        # must not end with separator
        "abc_",
        "abc-",
        "abc.",
        # consecutive separators
        "a__b",
        "a--b",
        "a..b",
        "a.-b",
        "a_.b",
        # uppercase not allowed
        "Abc",
        "abcDef",
        # forbidden characters
        "a:b",  # colon reserved
        "a b",  # space
        "a/b",  # slash
        "a\\b",
        "a,b",
        "a@b",
        # separator-only
        ".",
        "-",
        "_",
    ],
)
def test_invalid_tokens_examples(token: str) -> None:
    """Disallow invalid tokens."""
    assert not TOKEN_RE.fullmatch(token), f"Expected invalid token: {token}"


def test_no_colon_allowed() -> None:
    """Disallow colon in token."""
    assert not TOKEN_RE.fullmatch("a:b")


def test_namespace_and_key_valid_examples() -> None:
    """Accept valid namespace and key."""
    assert TOKEN_RE.fullmatch(TOPMARK_NAMESPACE)
    assert TOKEN_RE.fullmatch("xml")


# ----------------------------
# HeaderProcessor.__init_subclass__ validation
# ----------------------------


def test_init_subclass_rejects_invalid_namespace_token() -> None:
    """Creating a subclass with an invalid namespace must fail."""
    with pytest.raises((TypeError, ValueError)):

        class _BadNamespace(HeaderProcessor):  # pyright: ignore[reportUnusedClass]
            namespace = "Bad"  # uppercase should be rejected
            local_key = "xml"


def test_init_subclass_rejects_invalid_key_token() -> None:
    """Creating a subclass with an invalid local key must fail."""
    with pytest.raises((TypeError, ValueError)):

        class _BadKey(HeaderProcessor):  # pyright: ignore[reportUnusedClass]
            namespace = "builtin"
            local_key = "xml:"  # colon / trailing separator should be rejected


# ----------------------------
# Registry composition duplicate qualified-key detection
# ----------------------------


def test_registry_compose_rejects_duplicate_qualified_key_for_different_classes() -> None:
    """Reject two different processor classes sharing the same qualified key.

    The composed registry is keyed by file type name, so multiple instances of the *same*
    processor class may appear (one per file type). That is allowed.

    But two different classes claiming the same qualified key is a conflict.
    """

    class _ProcA(HeaderProcessor):
        namespace = "testns"
        local_key = "dup"

        def process(self, text: str) -> str:
            return text

    class _ProcB(HeaderProcessor):
        namespace = "testns"
        local_key = "dup"

        def process(self, text: str) -> str:
            return text

    ft1: FileType = make_file_type(
        name="ft_dup_1",
    )
    FileTypeRegistry.register(ft1)
    ft2: FileType = make_file_type(
        name="ft_dup_2",
    )
    FileTypeRegistry.register(ft2)

    try:
        HeaderProcessorRegistry.register(
            file_type=ft1,
            processor_class=_ProcA,
        )
        HeaderProcessorRegistry.register(
            file_type=ft2,
            processor_class=_ProcB,
        )

        # composition must fail because qk is the same but classes differ
        with pytest.raises(DuplicateProcessorKeyError):
            _ = HeaderProcessorRegistry.as_mapping()
    finally:
        HeaderProcessorRegistry.unregister(ft1.local_key)
        HeaderProcessorRegistry.unregister(ft2.local_key)
        FileTypeRegistry.unregister(ft1.local_key)
        FileTypeRegistry.unregister(ft2.local_key)


def test_registry_compose_allows_duplicate_qualified_key_for_same_class() -> None:
    """Allow the same processor class (same qualified key) to be bound to multiple file types."""

    class _ProcSame(HeaderProcessor):
        namespace = "testns"
        local_key = "same"

        def process(self, text: str) -> str:
            return text

    ft1: FileType = make_file_type(
        name="ft_same_1",
    )
    ft2: FileType = make_file_type(
        name="ft_same_2",
    )

    FileTypeRegistry.register(ft1)
    FileTypeRegistry.register(ft2)

    try:
        HeaderProcessorRegistry.register(
            file_type=ft1,
            processor_class=_ProcSame,
        )
        HeaderProcessorRegistry.register(
            file_type=ft2,
            processor_class=_ProcSame,
        )

        m: Mapping[str, HeaderProcessor] = HeaderProcessorRegistry.as_mapping()
        assert ft1.local_key in m and ft2.local_key in m
        assert type(m[ft1.local_key]) is _ProcSame
        assert type(m[ft2.local_key]) is _ProcSame
        assert m[ft1.local_key].qualified_key == m[ft2.local_key].qualified_key == "testns:same"
    finally:
        HeaderProcessorRegistry.unregister(ft1.local_key)
        HeaderProcessorRegistry.unregister(ft2.local_key)
        FileTypeRegistry.unregister(ft1.local_key)
        FileTypeRegistry.unregister(ft2.local_key)
