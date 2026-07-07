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
from topmark.core.errors import ReservedNamespaceError
from topmark.registry import filetypes as filetype_registry_module
from topmark.registry.filetypes import FileTypeRegistry

if TYPE_CHECKING:
    from collections.abc import Mapping

    from topmark.filetypes.model import FileType


def test_filename_rule_normalization_preserves_registry_identity() -> None:
    """Filename-rule normalization does not affect registry identity fields."""
    file_type: FileType = make_file_type(
        local_key="settings_json",
        namespace="pytest",
        filenames=[r".vscode\settings.json"],
        description="VS Code settings file type",
    )

    with patched_effective_registries(
        filetypes={"settings_json": file_type},
        processors={},
    ):
        resolved: FileType | None = FileTypeRegistry.resolve_filetype_id(
            "pytest:settings_json",
        )

    assert file_type.local_key == "settings_json"
    assert file_type.namespace == "pytest"
    assert file_type.qualified_key == "pytest:settings_json"
    assert file_type.filenames == [".vscode/settings.json"]
    assert resolved is file_type


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


def test_registry_identity_helpers_preserve_canonical_key_contract() -> None:
    """Identity helpers should build and split canonical registry keys predictably."""
    from topmark.registry.identity import make_qualified_key
    from topmark.registry.identity import split_qualified_key

    qualified_key: str = make_qualified_key("pytest", "sample")

    assert qualified_key == "pytest:sample"
    assert split_qualified_key(qualified_key) == ("pytest", "sample")


@pytest.mark.parametrize(
    ("namespace", "local_key", "match"),
    [
        ("pytest", "sample", r"\('pytest', 'sample'\)"),
        ("", "sample", "namespace must be a non-empty str"),
        ("pytest", "", "local_key must be a non-empty str"),
        ("PyTest", "sample", "namespace must match"),
        ("pytest", "bad:key", "local_key must match"),
    ],
)
def test_require_and_validate_registry_identity_enforces_public_token_contract(
    namespace: object,
    local_key: object,
    match: str,
) -> None:
    """Registry identity validation should reject missing or malformed tokens."""
    from topmark.registry.identity import require_and_validate_registry_identity

    if namespace == "pytest" and local_key == "sample":
        assert require_and_validate_registry_identity(
            namespace=namespace,
            local_key=local_key,
            owner="tests.Owner",
        ) == ("pytest", "sample")
        return

    with pytest.raises(TypeError, match=match):
        require_and_validate_registry_identity(
            namespace=namespace,
            local_key=local_key,
            owner="tests.Owner",
        )


def test_reserved_topmark_namespace_is_restricted_to_topmark_owned_entities() -> None:
    """The reserved built-in namespace should not be usable by external plugins."""
    from topmark.registry.identity import validate_reserved_topmark_namespace

    validate_reserved_topmark_namespace(
        "topmark",
        owner="topmark.filetypes.PythonFileType",
        owner_module="topmark.filetypes.builtins.core_langs",
        entities="file types",
    )

    with pytest.raises(TypeError, match="reserved for built-in TopMark file types"):
        validate_reserved_topmark_namespace(
            "topmark",
            owner="tests.plugins.ExternalFileType",
            owner_module="tests.plugins",
            entities="file types",
        )


def test_owner_label_returns_fully_qualified_type_name() -> None:
    """Owner labels should use the stable fully-qualified Python type name."""
    from topmark.registry.identity import owner_label

    class SampleType:
        pass

    assert owner_label(SampleType) == (f"{SampleType.__module__}.{SampleType.__qualname__}")


def test_filetype_validation_rejects_non_filetype_candidate() -> None:
    """File type registry validation should reject non-FileType objects."""
    with pytest.raises(TypeError, match="Expected instance of FileType"):
        FileTypeRegistry._validate_ft(object())  # pyright: ignore[reportPrivateUsage]


def test_filetype_registry_translates_reserved_namespace_validation_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Registry validation should expose reserved namespace failures as core errors."""
    file_type: FileType = make_file_type(
        local_key="patched_reserved_filetype",
        namespace="pytest",
        extensions=[".patched-reserved"],
        description="patched reserved file type",
    )

    def _reject_reserved_namespace(
        namespace: str,
        *,
        owner: str,
        owner_module: str,
        entities: str,
    ) -> None:
        assert namespace == "pytest"
        assert owner.endswith("FileType")
        assert owner_module == type(file_type).__module__
        assert entities == "file types"
        raise TypeError("forced reserved namespace failure")

    monkeypatch.setattr(
        filetype_registry_module,
        "validate_reserved_topmark_namespace",
        _reject_reserved_namespace,
    )

    with pytest.raises(ReservedNamespaceError):
        FileTypeRegistry._validate_ft(file_type)  # pyright: ignore[reportPrivateUsage]


def test_filetype_local_key_mapping_is_readonly_and_reuses_cache() -> None:
    """The local-key compatibility mapping should be read-only and cached."""
    import types

    FileTypeRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]
    try:
        first: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()
        second: Mapping[str, FileType] = FileTypeRegistry.as_mapping_by_local_key()

        assert isinstance(first, types.MappingProxyType)
        assert first is second
        assert not hasattr(first, "__setitem__")
    finally:
        FileTypeRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]


def test_filetype_registry_sorted_views_include_registered_overlays() -> None:
    """File type names, qualified keys, and namespaces should be sorted views."""
    zed: FileType = make_file_type(
        local_key="zed_public_view_filetype",
        namespace="zpytest",
        extensions=[".zed-public-view"],
        description="zed public view file type",
    )
    alpha: FileType = make_file_type(
        local_key="alpha_public_view_filetype",
        namespace="apytest",
        extensions=[".alpha-public-view"],
        description="alpha public view file type",
    )

    try:
        FileTypeRegistry.register(zed)
        FileTypeRegistry.register(alpha)

        names: tuple[str, ...] = FileTypeRegistry.names()
        qualified_keys: tuple[str, ...] = FileTypeRegistry.qualified_keys()
        namespaces: tuple[str, ...] = FileTypeRegistry.namespaces()

        assert names == tuple(sorted(names))
        assert qualified_keys == tuple(sorted(qualified_keys))
        assert namespaces == tuple(sorted(set(namespaces)))
        assert zed.local_key in names
        assert alpha.local_key in names
        assert zed.qualified_key in qualified_keys
        assert alpha.qualified_key in qualified_keys
        assert "zpytest" in namespaces
        assert "apytest" in namespaces
    finally:
        FileTypeRegistry.unregister_by_local_key(zed.local_key)
        FileTypeRegistry.unregister_by_local_key(alpha.local_key)


def test_resolve_filetype_id_returns_none_for_blank_identifier() -> None:
    """Blank file type identifiers should resolve to a stable null value."""
    assert FileTypeRegistry.resolve_filetype_id("   ") is None


def test_filetype_register_rejects_duplicate_local_key() -> None:
    """Overlay registration should reject duplicate local-key identities."""
    original: FileType = make_file_type(
        local_key="duplicate_public_filetype",
        namespace="pytest",
        extensions=[".duplicate-public"],
        description="duplicate public file type",
    )
    duplicate: FileType = make_file_type(
        local_key="duplicate_public_filetype",
        namespace="otherpytest",
        extensions=[".duplicate-public-other"],
        description="duplicate public file type in another namespace",
    )

    try:
        FileTypeRegistry.register(original)

        with pytest.raises(ValueError, match="Duplicate FileType local_key"):
            FileTypeRegistry.register(duplicate)
    finally:
        FileTypeRegistry.unregister_by_local_key(original.local_key)
        FileTypeRegistry.unregister_by_local_key(duplicate.local_key)


def test_filetype_unregister_by_qualified_key_removes_overlay_and_reports_unknown() -> None:
    """Qualified-key unregister should remove overlays and report missing entries."""
    file_type: FileType = make_file_type(
        local_key="qualified_unregister_filetype",
        namespace="pytest",
        extensions=[".qualified-unregister"],
        description="qualified unregister file type",
    )

    FileTypeRegistry.register(file_type)
    try:
        assert FileTypeRegistry.unregister(file_type.qualified_key) is True
        assert FileTypeRegistry.get(file_type.qualified_key) is None
        assert FileTypeRegistry.unregister(file_type.qualified_key) is False
    finally:
        FileTypeRegistry.unregister_by_local_key(file_type.local_key)


def test_filetype_unregister_overlay_only_entry_without_local_cache_hit() -> None:
    """Qualified-key unregister should handle overlay-only entries without base fallback."""
    file_type: FileType = make_file_type(
        local_key="overlay_only_uncached_unregister_filetype",
        namespace="pytest",
        extensions=[".overlay-only-uncached-unregister"],
        description="overlay-only uncached unregister file type",
    )

    FileTypeRegistry.register(file_type)
    try:
        assert FileTypeRegistry.as_mapping()[file_type.qualified_key] is file_type
        FileTypeRegistry._cache = None  # pyright: ignore[reportPrivateUsage]

        assert FileTypeRegistry.unregister(file_type.qualified_key) is True
        assert file_type.local_key not in FileTypeRegistry._removals  # pyright: ignore[reportPrivateUsage]
        assert FileTypeRegistry.get(file_type.qualified_key) is None
    finally:
        FileTypeRegistry.unregister_by_local_key(file_type.local_key)
        FileTypeRegistry._removals.discard(  # pyright: ignore[reportPrivateUsage]
            file_type.local_key,
        )
        FileTypeRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]


# Additional tests for FileTypeRegistry edge cases


def test_filetype_compose_rejects_base_key_that_disagrees_with_filetype_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Base registry composition should reject mismatched local-key entries."""
    file_type: FileType = make_file_type(
        local_key="actual_base_filetype_key",
        namespace="pytest",
        extensions=[".actual-base-key"],
        description="actual base file type key",
    )

    def _base_registry() -> dict[str, FileType]:
        return {"wrong_base_filetype_key": file_type}

    monkeypatch.setattr(
        "topmark.filetypes.instances.get_base_file_type_registry",
        _base_registry,
    )
    FileTypeRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]
    try:
        with pytest.raises(ValueError, match="does not match FileType.local_key"):
            FileTypeRegistry.names()
    finally:
        FileTypeRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]


def test_filetype_unregister_by_qualified_key_hides_base_only_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qualified-key unregister should hide base entries without mutating the base."""
    file_type: FileType = make_file_type(
        local_key="base_only_unregister_filetype",
        namespace="pytest",
        extensions=[".base-only-unregister"],
        description="base-only unregister file type",
    )

    def _base_registry() -> dict[str, FileType]:
        return {file_type.local_key: file_type}

    monkeypatch.setattr(
        "topmark.filetypes.instances.get_base_file_type_registry",
        _base_registry,
    )
    FileTypeRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]
    try:
        assert FileTypeRegistry.get(file_type.qualified_key) is file_type

        assert FileTypeRegistry.unregister(file_type.qualified_key) is True
        assert FileTypeRegistry.get(file_type.qualified_key) is None
        assert file_type.local_key not in FileTypeRegistry.names()
    finally:
        FileTypeRegistry._removals.discard(  # pyright: ignore[reportPrivateUsage]
            file_type.local_key,
        )
        FileTypeRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]


def test_filetype_unregister_by_qualified_key_marks_base_entry_removed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Qualified-key unregister should record removals for base-only entries."""
    file_type: FileType = make_file_type(
        local_key="base_only_removal_marker_filetype",
        namespace="pytest",
        extensions=[".base-only-removal-marker"],
        description="base-only removal marker file type",
    )

    def _base_registry() -> dict[str, FileType]:
        return {file_type.local_key: file_type}

    monkeypatch.setattr(
        "topmark.filetypes.instances.get_base_file_type_registry",
        _base_registry,
    )
    FileTypeRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]
    try:
        assert file_type.local_key not in FileTypeRegistry._overrides  # pyright: ignore[reportPrivateUsage]
        assert file_type.local_key not in FileTypeRegistry._removals  # pyright: ignore[reportPrivateUsage]

        assert FileTypeRegistry.unregister(file_type.qualified_key) is True

        assert file_type.local_key in FileTypeRegistry._removals  # pyright: ignore[reportPrivateUsage]
        assert file_type.local_key not in FileTypeRegistry.as_mapping_by_local_key()
    finally:
        FileTypeRegistry._removals.discard(  # pyright: ignore[reportPrivateUsage]
            file_type.local_key,
        )
        FileTypeRegistry._clear_cache()  # pyright: ignore[reportPrivateUsage]
