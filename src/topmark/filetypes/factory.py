# topmark:header:start
#
#   project      : TopMark
#   file         : factory.py
#   file_relpath : src/topmark/filetypes/factory.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Factories for creating `FileType` instances.

This module centralizes small helpers that build `FileType` objects with sensible
defaults and a clear identity model.

Rationale:
    * `FileType` identity is **(namespace, name)**.
    * TopMark reserves the namespace `TOPMARK_NAMESPACE` for built-in file types.
    * Call sites should not repeat boilerplate such as converting `None` to empty lists.

The helpers here are intentionally lightweight and side-effect free: they return
`FileType` instances but do not register them.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Final

from topmark.constants import TOPMARK_NAMESPACE
from topmark.filetypes.model import ContentGate
from topmark.filetypes.model import ContentMatcher
from topmark.filetypes.model import FileType
from topmark.filetypes.model import InsertChecker

if TYPE_CHECKING:
    from collections.abc import Callable

    from topmark.filetypes.policy import FileTypeHeaderPolicy


def make_filetype_factory(*, namespace: str) -> Callable[..., FileType]:
    """Return a `FileType` constructor that pre-binds a namespace.

    This is useful for plugin authors and internal topical modules that want to
    define multiple file types in the same namespace without repeating the
    `namespace=...` argument.

    Args:
        namespace: The namespace to assign to all constructed `FileType` objects.

    Returns:
        A callable with the same keyword-only parameters as `make_builtin_filetype`,
        except that `namespace` is fixed.

    Notes:
        This helper does **not** register the file type; it only constructs it.
        Registration happens when file types are loaded into a registry.
    """

    def _make(
        *,
        name: str,
        description: str,
        extensions: list[str] | None = None,
        filenames: list[str] | None = None,
        patterns: list[str] | None = None,
        skip_processing: bool = False,
        content_matcher: ContentMatcher | None = None,
        content_gate: ContentGate = ContentGate.NEVER,
        header_policy: FileTypeHeaderPolicy | None = None,
        pre_insert_checker: InsertChecker | None = None,
    ) -> FileType:
        return FileType(
            namespace=namespace,
            name=name,
            extensions=extensions if extensions is not None else [],
            filenames=filenames if filenames is not None else [],
            patterns=patterns if patterns is not None else [],
            description=description,
            header_policy=header_policy,
            skip_processing=skip_processing,
            content_matcher=content_matcher,
            content_gate=content_gate,
            pre_insert_checker=pre_insert_checker,
        )

    return _make


# Convenience: a factory with the built-in namespace pre-bound
BUILTIN_FILETYPE_FACTORY: Final = make_filetype_factory(
    namespace=TOPMARK_NAMESPACE,
)
