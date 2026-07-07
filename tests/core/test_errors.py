# topmark:header:start
#
#   project      : TopMark
#   file         : test_errors.py
#   file_relpath : tests/core/test_errors.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for core TopMark exception context and formatting."""

from __future__ import annotations

from pathlib import Path

import pytest

from topmark.config.validation import MutableValidationLogs
from topmark.core.errors import AmbiguousFileTypeIdentifierError
from topmark.core.errors import ConfigValidationError
from topmark.core.errors import DuplicateProcessorKeyError
from topmark.core.errors import ErrorContext
from topmark.core.errors import InvalidFileTypeDefinitionError
from topmark.core.errors import InvalidRegistryIdentityError
from topmark.core.errors import ReservedNamespaceError
from topmark.core.errors import TomlDocumentError
from topmark.core.errors import TopmarkError
from topmark.core.errors import UnknownFileTypeError
from topmark.core.errors import UnsupportedFileTypeError


def test_topmark_error_string_and_args_preserve_context_message() -> None:
    """Base errors should expose the context message through standard exception APIs."""
    context = ErrorContext(message="plain failure", details=("detail=a",))
    error = TopmarkError(context)

    assert str(error) == "plain failure"
    assert error.args == ("plain failure",)
    assert error.context is context
    assert error.context.details == ("detail=a",)


@pytest.mark.parametrize(
    ("error", "message", "qualified_key", "details"),
    [
        pytest.param(
            ReservedNamespaceError(
                namespace="topmark",
                owner="external fixture",
                entities="file types",
                owner_module="tests.plugins",
            ),
            (
                "Reserved namespace violation: 'topmark' is reserved for built-in "
                "TopMark file types (owner: external fixture)"
            ),
            None,
            (
                "namespace=topmark",
                "owner=external fixture",
                "entities=file types",
                "owner_module=tests.plugins",
            ),
            id="reserved-namespace",
        ),
        pytest.param(
            InvalidFileTypeDefinitionError(
                message="invalid file type",
                file_type="plugin:demo",
                field_name="extensions",
                value="*.py",
            ),
            "invalid file type",
            "plugin:demo",
            ("field=extensions", "value=*.py"),
            id="invalid-file-type-definition",
        ),
        pytest.param(
            AmbiguousFileTypeIdentifierError(
                file_type="python",
                candidates=("topmark:python", "plugin:python"),
            ),
            "Ambiguous file type identifier: python (candidates: topmark:python, plugin:python)",
            "python",
            ("candidate=topmark:python", "candidate=plugin:python"),
            id="ambiguous-file-type-identifier",
        ),
        pytest.param(
            InvalidRegistryIdentityError(
                message="bad identity",
                identifier="bad:key:again",
                namespace="bad",
                local_key="key:again",
            ),
            "bad identity",
            "bad:key:again",
            (
                "identifier=bad:key:again",
                "namespace=bad",
                "local_key=key:again",
            ),
            id="invalid-registry-identity",
        ),
        pytest.param(
            DuplicateProcessorKeyError(
                qualified_key="plugin:processor",
                existing_class="ExistingProcessor",
                new_class="NewProcessor",
            ),
            (
                "Duplicate processor key detected: plugin:processor "
                "(classes: ExistingProcessor vs NewProcessor)"
            ),
            "plugin:processor",
            ("existing_class=ExistingProcessor", "new_class=NewProcessor"),
            id="duplicate-processor-key",
        ),
    ],
)
def test_structured_error_constructors_preserve_machine_context(
    error: TopmarkError,
    message: str,
    qualified_key: str | None,
    details: tuple[str, ...],
) -> None:
    """Structured constructors should keep display text separate from machine context."""
    assert str(error) == message
    assert error.context.message == message
    assert error.context.qualified_key == qualified_key
    assert error.context.details == details


def test_reserved_namespace_error_omits_optional_owner_module_detail() -> None:
    """Reserved namespace errors should not invent optional owner-module context."""
    error = ReservedNamespaceError(
        namespace="topmark",
        owner="external fixture",
        entities="processors",
    )

    assert str(error) == (
        "Reserved namespace violation: 'topmark' is reserved for built-in "
        "TopMark processors (owner: external fixture)"
    )
    assert error.context.details == (
        "namespace=topmark",
        "owner=external fixture",
        "entities=processors",
    )
    assert error.owner_module is None


@pytest.mark.parametrize(
    ("error", "qualified_key", "details"),
    [
        pytest.param(
            InvalidFileTypeDefinitionError(
                message="missing extensions",
                file_type="plugin:demo",
                field_name="extensions",
            ),
            "plugin:demo",
            ("field=extensions",),
            id="field-only",
        ),
        pytest.param(
            InvalidFileTypeDefinitionError(
                message="invalid scalar",
                value="*.py",
            ),
            None,
            ("value=*.py",),
            id="value-only",
        ),
        pytest.param(
            InvalidFileTypeDefinitionError(message="invalid anonymous file type"),
            None,
            (),
            id="no-optional-context",
        ),
    ],
)
def test_invalid_file_type_definition_error_preserves_partial_context(
    error: InvalidFileTypeDefinitionError,
    qualified_key: str | None,
    details: tuple[str, ...],
) -> None:
    """Invalid file-type definitions should preserve only caller-supplied details."""
    assert error.context.qualified_key == qualified_key
    assert error.context.details == details


def test_invalid_registry_identity_error_falls_back_to_local_key_context() -> None:
    """Registry identity errors should use local-key context when no raw identifier exists."""
    error = InvalidRegistryIdentityError(
        message="bad local key",
        namespace="plugin",
        local_key="bad/key",
    )

    assert str(error) == "bad local key"
    assert error.context.qualified_key == "bad/key"
    assert error.context.details == (
        "namespace=plugin",
        "local_key=bad/key",
    )
    assert error.identifier is None


def test_file_type_lookup_errors_include_optional_path_context() -> None:
    """File-type lookup errors should preserve both display and path context."""
    path = Path("src/example.py")

    unsupported = UnsupportedFileTypeError(file_type="topmark:python", path=path)
    unknown = UnknownFileTypeError(file_type="plugin:missing", path=path)

    assert str(unsupported) == "Unsupported file type for src/example.py: topmark:python"
    assert unsupported.context.path == path
    assert unsupported.context.qualified_key == "topmark:python"
    assert unsupported.file_type == "topmark:python"

    assert str(unknown) == "Unknown file type identifier for src/example.py: plugin:missing"
    assert unknown.context.path == path
    assert unknown.context.qualified_key == "plugin:missing"
    assert unknown.file_type == "plugin:missing"


def test_toml_document_errors_preserve_detail_context() -> None:
    """TOML document errors should carry caller-provided surgery/rendering details."""
    error = TomlDocumentError(message="cannot edit TOML", details=("table=tool.topmark",))

    assert str(error) == "cannot edit TOML"
    assert error.context.details == ("table=tool.topmark",)


def test_config_validation_error_summarizes_staged_diagnostics() -> None:
    """Config validation errors should preserve flattened diagnostics and staged counts."""
    validation_logs = MutableValidationLogs()
    validation_logs.toml_source.add_error("bad TOML")
    validation_logs.merged_config.add_warning("deprecated key")
    validation_logs.runtime_applicability.add_error("bad runtime override")

    error = ConfigValidationError(
        validation_logs=validation_logs,
        strict=True,
        details=("source=topmark.toml",),
    )

    assert "Config validation failed (strict = True)" in str(error)
    assert "TOML errors: 1, warnings: 0" in str(error)
    assert "Merged-config errors: 0, warnings: 1" in str(error)
    assert "Runtime errors: 1, warnings: 0" in str(error)
    assert error.context.details == ("source=topmark.toml",)
    assert error.context.diagnostics is not None
    assert [diagnostic.message for diagnostic in error.context.diagnostics] == [
        "bad TOML",
        "deprecated key",
        "bad runtime override",
    ]
