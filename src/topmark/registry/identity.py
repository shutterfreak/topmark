# topmark:header:start
#
#   project      : TopMark
#   file         : identity.py
#   file_relpath : src/topmark/registry/identity.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Identity helpers for the TopMark registry.

This module centralizes small, dependency-light helpers related to registry
identity construction and validation. It is intentionally shared by both
file-type and processor models so namespace/local-key rules remain consistent.
"""

from __future__ import annotations

import re

from topmark.constants import PACKAGE_NAME
from topmark.constants import TOPMARK_NAMESPACE
from topmark.constants import VALID_REGISTRY_TOKEN_RE


def owner_label(obj_type: type[object]) -> str:
    """Return a stable fully-qualified owner label for a Python type.

    This helper is used in registry identity validation and error reporting to
    identify the defining class in a consistent diagnostic form.

    Args:
        obj_type: The class/type to label.

    Returns:
        Fully-qualified owner label for diagnostics and validation messages.
    """
    return f"{obj_type.__module__}.{obj_type.__qualname__}"


def make_qualified_key(namespace: str, local_key: str) -> str:
    """Build a canonical qualified key from a namespace and local key.

    Format: "<namespace>:<local_key>"

    This helper centralizes identity construction for registry entities
    such as FileType and HeaderProcessor.

    Args:
        namespace: Namespace identifier (must already be validated).
        local_key: Namespace-local identifier.

    Returns:
        Fully-qualified key string.

    Note:
        This function does not perform validation. Callers are expected
        to provide already validated tokens.
    """
    return f"{namespace}:{local_key}"


def split_qualified_key(qualified_key: str) -> tuple[str, str]:
    """Split ``"<namespace>:<local_key>"`` into its components.

    Args:
        qualified_key: Fully-qualified registry identifier.

    Returns:
        ``(namespace, local_key)``.

    Notes:
        This helper performs a lightweight split only. It does not validate the
        resulting tokens or reject malformed inputs with multiple separators.
    """
    namespace, _, local_key = qualified_key.partition(":")
    return namespace, local_key


def is_valid_registry_token(value: str) -> bool:
    """Return whether a registry token is valid.

    Valid tokens are lowercase, must not contain ``":"``, and must match
    [`VALID_REGISTRY_TOKEN_RE`][topmark.constants.VALID_REGISTRY_TOKEN_RE].
    """
    if value != value.lower():
        return False
    if ":" in value:
        return False
    return bool(re.fullmatch(VALID_REGISTRY_TOKEN_RE, value))


def validate_registry_token(value: str, *, field_name: str, owner: str) -> None:
    """Validate a single registry token.

    Args:
        value: Token value to validate.
        field_name: Name of the corresponding field (for error reporting).
        owner: Fully-qualified owner label (for error reporting).

    Raises:
        TypeError: If validation fails.
    """
    if not is_valid_registry_token(value):
        raise TypeError(
            f"{owner}.{field_name} must match {VALID_REGISTRY_TOKEN_RE}, "
            "be lowercase, and not contain ':' "
            f"(found {value!r})"
        )


def require_nonempty_str(value: object, *, field_name: str, owner: str) -> str:
    """Return `value` as `str` after enforcing type and non-empty presence.

    Args:
        value: Candidate value to validate.
        field_name: Name of the corresponding field (for error reporting).
        owner: Fully-qualified owner label (for error reporting).

    Returns:
        The validated string value.

    Raises:
        TypeError: If `value` is not a non-empty string.
    """
    if not isinstance(value, str) or not value:
        raise TypeError(f"{owner}.{field_name} must be a non-empty str")
    return value


def require_and_validate_registry_identity(
    *,
    namespace: object,
    local_key: object,
    owner: str,
) -> tuple[str, str]:
    """Validate and normalize a registry identity pair.

    This helper first enforces that both values are non-empty strings and then
    validates them as registry tokens.

    Args:
        namespace: Candidate namespace value.
        local_key: Candidate namespace-local identifier.
        owner: Fully-qualified owner label (for error reporting).

    Returns:
        Normalized `(namespace, local_key)` strings.

    Raises:
        TypeError: If either value is missing, not a string, or fails token
            validation.
    """
    ns: str = require_nonempty_str(namespace, field_name="namespace", owner=owner)
    lk: str = require_nonempty_str(local_key, field_name="local_key", owner=owner)
    try:
        validate_registry_identity(namespace=ns, local_key=lk, owner=owner)
    except TypeError:  # noqa: TRY203
        raise

    return ns, lk


def validate_registry_identity(
    *,
    namespace: str,
    local_key: str,
    owner: str,
) -> None:
    """Validate a registry identity pair (`namespace`, `local_key`).

    Args:
        namespace: Namespace value to validate.
        local_key: Namespace-local identifier to validate.
        owner: Fully-qualified owner label (for error reporting).

    Raises:
        TypeError: If either token fails validation.
    """
    try:
        validate_registry_token(
            local_key,
            field_name="local_key",
            owner=owner,
        )

        validate_registry_token(
            namespace,
            field_name="namespace",
            owner=owner,
        )
    except TypeError:  # noqa: TRY203
        raise


def validate_reserved_topmark_namespace(
    namespace: str,
    *,
    owner: str,
    owner_module: str,
    entities: str,
) -> None:
    """Validate reserved use of the built-in `topmark` namespace.

    Args:
        namespace: Namespace value to validate.
        owner: Fully-qualified owner label (for error reporting).
        owner_module: Defining module of the corresponding entity.
        entities: Human label for the validated entity type (for example,
            ``"file types"`` or ``"processors"``).

    Raises:
        TypeError: If the reserved TopMark namespace is used outside the TopMark package.
    """
    if namespace == TOPMARK_NAMESPACE and not owner_module.startswith(f"{PACKAGE_NAME}."):
        raise TypeError(
            f"{owner}: namespace '{TOPMARK_NAMESPACE}' is reserved for built-in TopMark {entities}."
        )
