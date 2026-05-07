# topmark:header:start
#
#   project      : TopMark
#   file         : test_filetype_identity.py
#   file_relpath : tests/registry/test_filetype_identity.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Pure normalization/ambiguity contract tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.registry import make_file_type
from tests.helpers.registry import patched_effective_registries
from topmark.core.errors import AmbiguousFileTypeIdentifierError
from topmark.core.errors import InvalidRegistryIdentityError
from topmark.registry.filetypes import FileTypeRegistry

if TYPE_CHECKING:
    from topmark.filetypes.model import FileType


def test_resolve_filetype_id_accepts_unambiguous_local_identifier() -> None:
    """Unqualified local identifiers resolve when they match exactly one file type."""
    file_type: FileType = make_file_type(
        local_key="sample",
        namespace="pytest",
        extensions=[".sample"],
        description="Sample file type",
    )

    with patched_effective_registries(filetypes={"sample": file_type}, processors={}):
        resolved: FileType | None = FileTypeRegistry.resolve_filetype_id("sample")

    assert resolved
    assert resolved is file_type
    assert resolved.qualified_key == "pytest:sample"


def test_resolve_filetype_id_accepts_qualified_identifier() -> None:
    """Qualified identifiers resolve directly to their canonical registry entry."""
    file_type: FileType = make_file_type(
        local_key="sample",
        namespace="pytest",
        extensions=[".sample"],
        description="Sample file type",
    )

    with patched_effective_registries(filetypes={"sample": file_type}, processors={}):
        resolved: FileType | None = FileTypeRegistry.resolve_filetype_id("pytest:sample")

    assert resolved
    assert resolved is file_type
    assert resolved.qualified_key == "pytest:sample"


def test_resolve_filetype_id_honors_default_namespace_for_local_identifier() -> None:
    """A default namespace constrains local identifier resolution."""
    file_type: FileType = make_file_type(
        local_key="sample",
        namespace="pytest",
        extensions=[".sample"],
        description="Sample file type",
    )

    with patched_effective_registries(filetypes={"sample": file_type}, processors={}):
        assert (
            FileTypeRegistry.resolve_filetype_id(
                "sample",
                default_namespace="pytest",
            )
            is file_type
        )
        assert (
            FileTypeRegistry.resolve_filetype_id(
                "sample",
                default_namespace="other",
            )
            is None
        )


def test_resolve_filetype_id_returns_none_for_unknown_identifier() -> None:
    """Unknown but well-formed identifiers are not treated as malformed."""
    file_type: FileType = make_file_type(
        local_key="sample",
        namespace="pytest",
        extensions=[".sample"],
        description="Sample file type",
    )

    with patched_effective_registries(filetypes={"sample": file_type}, processors={}):
        assert FileTypeRegistry.resolve_filetype_id("missing") is None
        assert FileTypeRegistry.resolve_filetype_id("pytest:missing") is None
        assert FileTypeRegistry.resolve_filetype_id("other:sample") is None


@pytest.mark.parametrize(
    "identifier",
    [
        ":sample",
        "pytest:",
        "pytest:sample:extra",
    ],
)
def test_resolve_filetype_id_rejects_malformed_qualified_identifier(
    identifier: str,
) -> None:
    """Malformed qualified identifiers fail explicitly instead of becoming unknown."""
    with pytest.raises(InvalidRegistryIdentityError):
        FileTypeRegistry.resolve_filetype_id(identifier)


def test_resolve_filetype_id_rejects_ambiguous_local_identifier() -> None:
    """Unqualified local identifiers fail when multiple namespaces match."""
    first: FileType = make_file_type(
        local_key="shared",
        namespace="first",
        extensions=[".first"],
        description="First shared file type",
    )
    second: FileType = make_file_type(
        local_key="shared",
        namespace="second",
        extensions=[".second"],
        description="Second shared file type",
    )

    with (
        patched_effective_registries(
            filetypes={"first-shared": first, "second-shared": second},
            processors={},
        ),
        pytest.raises(AmbiguousFileTypeIdentifierError) as exc_info,
    ):
        FileTypeRegistry.resolve_filetype_id("shared")

    assert exc_info.value.file_type == "shared"
    assert exc_info.value.candidates == ("first:shared", "second:shared")


def test_resolve_filetype_id_default_namespace_disambiguates_local_identifier() -> None:
    """A default namespace may disambiguate an otherwise ambiguous local key."""
    first: FileType = make_file_type(
        local_key="shared",
        namespace="first",
        extensions=[".first"],
        description="First shared file type",
    )
    second: FileType = make_file_type(
        local_key="shared",
        namespace="second",
        extensions=[".second"],
        description="Second shared file type",
    )

    with patched_effective_registries(
        filetypes={"first-shared": first, "second-shared": second},
        processors={},
    ):
        assert (
            FileTypeRegistry.resolve_filetype_id(
                "shared",
                default_namespace="first",
            )
            is first
        )
        assert (
            FileTypeRegistry.resolve_filetype_id(
                "shared",
                default_namespace="second",
            )
            is second
        )
        assert (
            FileTypeRegistry.resolve_filetype_id(
                "shared",
                default_namespace="missing",
            )
            is None
        )


def test_resolve_filetype_id_qualified_identifier_ignores_default_namespace() -> None:
    """Qualified identifiers should not be remapped by a default namespace."""
    first: FileType = make_file_type(
        local_key="shared",
        namespace="first",
        extensions=[".first"],
        description="First shared file type",
    )
    second: FileType = make_file_type(
        local_key="shared",
        namespace="second",
        extensions=[".second"],
        description="Second shared file type",
    )

    with patched_effective_registries(
        filetypes={"first-shared": first, "second-shared": second},
        processors={},
    ):
        assert (
            FileTypeRegistry.resolve_filetype_id(
                "first:shared",
                default_namespace="second",
            )
            is first
        )
        assert (
            FileTypeRegistry.resolve_filetype_id(
                "second:shared",
                default_namespace="first",
            )
            is second
        )


def test_resolve_filetype_id_allows_qualified_identifier_when_local_is_ambiguous() -> None:
    """Qualified identifiers remain deterministic even when local keys collide."""
    first: FileType = make_file_type(
        local_key="shared",
        namespace="first",
        extensions=[".first"],
        description="First shared file type",
    )
    second: FileType = make_file_type(
        local_key="shared",
        namespace="second",
        extensions=[".second"],
        description="Second shared file type",
    )

    with patched_effective_registries(
        filetypes={"first-shared": first, "second-shared": second},
        processors={},
    ):
        assert FileTypeRegistry.resolve_filetype_id("first:shared") is first
        assert FileTypeRegistry.resolve_filetype_id("second:shared") is second
