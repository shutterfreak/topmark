# topmark:header:start
#
#   project      : TopMark
#   file         : registry.py
#   file_relpath : tests/helpers/registry.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared helpers for registry- and binding-related tests.

This module contains reusable utilities for tests that need to construct
minimal file types, patch effective registry views, or resolve processors via
TopMark's binding layer without depending on the full built-in registry state.

The helpers are intentionally explicit and importable so registry tests can
control file-type/processor state deterministically.
"""

from __future__ import annotations

import re
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar
from typing import cast

from topmark.filetypes.model import ContentGate
from topmark.filetypes.model import ContentMatcher
from topmark.filetypes.model import FileType
from topmark.filetypes.model import InsertChecker
from topmark.filetypes.policy import FileTypeHeaderPolicy
from topmark.processors.base import HeaderProcessor
from topmark.registry.types import ProcessorDefinition
from topmark.resolution.filetypes import resolve_binding_for_path

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Collection
    from collections.abc import Iterator
    from collections.abc import Mapping
    from pathlib import Path


def make_file_type(
    *,
    local_key: str,
    namespace: str = "pytest",
    description: str = "",
    extensions: list[str] | None = None,
    filenames: list[str] | None = None,
    patterns: list[str] | None = None,
    content_matcher: ContentMatcher | None = None,
    content_gate: ContentGate = ContentGate.NEVER,
    header_policy: FileTypeHeaderPolicy | None = None,
    pre_insert_checker: InsertChecker | None = None,
    matches: Callable[[Path], bool] | None = None,
    skip_processing: bool = False,
) -> FileType:
    """Create a minimal `FileType` instance for tests.

    This helper lets tests construct small explicit file-type definitions
    without relying on the built-in registry population or plugin discovery.
    It still returns a real [`FileType`][topmark.filetypes.model.FileType]
    object so resolution and registry code exercise normal runtime behavior.

    Notes:
        - `content_matcher` is used by resolver scoring and content-gating tests.
        - `matches` is used by file discovery/filtering (`resolve_file_list`). If not
          provided, it defaults to a small matcher that checks extensions, filename tails,
          regex patterns (fullmatch), and finally falls back to `content_matcher` when available.
        - The default matcher is path-based and doesn’t read file contents unless `content_matcher`
          is provided. Extension matching is suffix-based, so `.tar.gz` rules work.

    Args:
        local_key: File type local identifier within the namespace.
        namespace: File type namespace (MUST NOT be `topmark`).
        description: The file type description.
        extensions: Extension rules (including leading dots, e.g. `.py`).
        filenames: Filename-tail rules (relative path tails).
        patterns: Regex patterns (strings) evaluated via fullmatch in the resolver.
        content_matcher: Optional content matcher callable.
        content_gate: Content gating mode.
        header_policy: Policy describing how headers should be inserted/removed for a file type.
        pre_insert_checker: Optional Callable that inspects the current processing context before a
            header insertion is attempted.
        matches: Optional matcher used by file discovery and file-type filtering. If not provided,
            `matches` defaults to a small matcher that checks extensions, filename tails, regex
            patterns (fullmatch), then falls back to content_matcher.
        skip_processing: Whether this file type is known but has no headers.

    Returns:
        A duck-typed `FileType` instance.
    """
    # `resolve_file_list()` expects FileType.matches(Path) -> bool.
    # The real FileType implementation can match on extensions, filename tails,
    # regex patterns, and (optionally) content matchers.
    ext_rules: list[str] = list(extensions or ())
    filename_rules: list[str] = list(filenames or ())
    pattern_rules: list[str] = list(patterns or ())

    def _default_matches(p: Path) -> bool:
        # Normalize for deterministic comparisons across OS path styles.
        name_str: str = p.name
        posix_str: str = p.as_posix()

        # 1) Extension rules (replicates `FileType.matches()` implementation)
        suffix: str = p.suffix
        for ext in ext_rules:
            if ext.count(".") > 1:
                # Multiple-dot suffix (e.g., `.tar.gz`)
                if name_str.endswith(ext):
                    return True
            else:
                # Single-dot suffix
                if suffix == ext:
                    return True

        # 2) Filename-tail rules (relative tails)
        #    We support both exact filename matches and path tail matches.
        for tail in filename_rules:
            if not tail:
                continue
            tail_norm: str = tail.replace("\\", "/")
            if (
                name_str == tail_norm
                or posix_str.endswith("/" + tail_norm)
                or posix_str.endswith(tail_norm)
            ):
                return True

        # 3) Regex patterns (fullmatch contract)
        if pattern_rules:
            for pat in pattern_rules:
                if not pat:
                    continue
                try:
                    if re.fullmatch(pat, name_str) or re.fullmatch(pat, posix_str):
                        return True
                except re.error:
                    # Test helper: ignore invalid regexes; production code validates.
                    continue

        # 4) Optional content matcher fallback
        if content_matcher is not None:
            try:
                return bool(content_matcher(p))
            except (OSError, UnicodeError, ValueError, TypeError):
                return False

        return False

    # Handle overrides of default `matches()` implementation.
    matcher: Callable[[Path], bool]
    matcher = matches if matches is not None else _default_matches

    if matches:

        class CustomMatcherFileType(FileType):
            matches: Callable[..., bool] = matcher

        return CustomMatcherFileType(
            local_key=local_key,
            namespace=namespace,
            description=description,
            extensions=extensions if extensions is not None else [],
            filenames=filenames if filenames is not None else [],
            patterns=patterns if patterns is not None else [],
            skip_processing=skip_processing,
            content_matcher=content_matcher,
            content_gate=content_gate,
            header_policy=header_policy or FileTypeHeaderPolicy(),
            pre_insert_checker=pre_insert_checker,
        )
    return FileType(
        local_key=local_key,
        namespace=namespace,
        description=description,
        extensions=extensions if extensions is not None else [],
        filenames=filenames if filenames is not None else [],
        patterns=patterns if patterns is not None else [],
        skip_processing=skip_processing,
        content_matcher=content_matcher,
        content_gate=content_gate,
        header_policy=header_policy or FileTypeHeaderPolicy(),
        pre_insert_checker=pre_insert_checker,
    )


@contextmanager
def patched_effective_registries(
    *,
    filetypes: Mapping[str, FileType],
    processors: Mapping[str, HeaderProcessor | ProcessorDefinition],
) -> Iterator[None]:
    """Temporarily override the effective registries used by TopMark.

    This helper patches the composed file-type, processor, and binding views
    so tests can work with a small deterministic registry snapshot instead of
    the full built-in registry state.

    Use this in tests that need deterministic, minimal registries without
    depending on built-in file types/processors or plugin discovery.

    Notes:
        - This overrides the composition functions only; overlays remain reset
          by the autouse fixture (or are irrelevant while patched).
        - Cache is cleared before patch, after patch, and again on restore.
        - The `processors` input is still keyed by file type local key for test
          convenience, but processor definitions are normalized into the new
          canonical processor-key registry shape before patching.

    Args:
        filetypes: Effective file type registry to expose for the duration of
            the context, keyed by file type local key.
        processors: Effective processor registry input keyed by file type local
            key for test convenience. Values may be runtime `HeaderProcessor`
            instances or `ProcessorDefinition` objects and are normalized into
            the canonical processor-key registry shape.

    Yields:
        None: Control is yielded to the caller while the effective registries
        are patched.
    """
    from topmark.registry.bindings import BindingRegistry
    from topmark.registry.filetypes import FileTypeRegistry
    from topmark.registry.processors import HeaderProcessorRegistry

    # Silence Pyright regarding use of private members:
    ft_reg = cast("Any", FileTypeRegistry)
    hp_reg = cast("Any", HeaderProcessorRegistry)

    # Normalize processors into the canonical processor-key registry shape.
    processor_defs_by_filetype: dict[str, ProcessorDefinition] = {}
    processor_defs_by_qualified_key: dict[str, ProcessorDefinition] = {}
    for file_type_local_key, processor in processors.items():
        if isinstance(processor, ProcessorDefinition):
            proc_def: ProcessorDefinition = processor
        else:
            proc_cls = type(processor)
            proc_def = ProcessorDefinition(
                namespace=proc_cls.namespace,
                local_key=proc_cls.local_key,
                processor_class=proc_cls,
            )
        processor_defs_by_filetype[file_type_local_key] = proc_def
        processor_defs_by_qualified_key[proc_def.qualified_key] = proc_def

    # Some tests intentionally use mismatched processor keys; in those cases we
    # should not invent a binding for a file type that is not present.
    binding_map: dict[str, str] = {}
    for file_type_local_key, proc_def in processor_defs_by_filetype.items():
        file_type: FileType | None = filetypes.get(file_type_local_key)
        if file_type is None:
            continue
        binding_map[file_type.qualified_key] = proc_def.qualified_key

    ft_reg._clear_cache()
    hp_reg._clear_cache()

    # Save the original compose hooks.
    orig_ft_compose = ft_reg._compose
    orig_ft_compose_by_local_key = ft_reg._compose_by_local_key
    orig_hp_compose = hp_reg._compose
    orig_binding_compose: Callable[..., dict[str, str]] = BindingRegistry._compose  # pyright: ignore[reportPrivateUsage]

    try:
        ft_reg._compose = classmethod(
            lambda cls: {ft.qualified_key: ft for ft in filetypes.values()}
        )
        ft_reg._compose_by_local_key = classmethod(lambda cls: dict(filetypes))
        hp_reg._compose = classmethod(lambda cls: dict(processor_defs_by_qualified_key))
        BindingRegistry._compose = classmethod(lambda cls: dict(binding_map))  # pyright: ignore[reportAttributeAccessIssue, reportPrivateUsage]
        ft_reg._clear_cache()
        hp_reg._clear_cache()
        yield
    finally:
        ft_reg._compose = orig_ft_compose
        ft_reg._compose_by_local_key = orig_ft_compose_by_local_key
        hp_reg._compose = orig_hp_compose
        BindingRegistry._compose = orig_binding_compose  # pyright: ignore[reportPrivateUsage]
        ft_reg._clear_cache()
        hp_reg._clear_cache()


# ---- Concrete helper type for HeaderProcessor registry tests ----


class TestRegistryProcessor(HeaderProcessor):
    """Minimal concrete `HeaderProcessor` subclass for registry tests.

    This test helper is no longer duck-typed. It is a real `HeaderProcessor`
    subclass so it participates in the same identity validation as production
    processors.
    """

    local_key: ClassVar[str] = "stub_processor"
    namespace: ClassVar[str] = "test"
    description: ClassVar[str] = "Minimal concrete HeaderProcessor subclass used by registry tests."


def registry_processor_class() -> type[HeaderProcessor]:
    """Return the concrete processor class used in registry tests."""
    return TestRegistryProcessor


def resolve_processor_for_path(
    path: Path,
    *,
    include_file_types: Collection[str] | None = None,
    exclude_file_types: Collection[str] | None = None,
) -> HeaderProcessor | None:
    """Resolve the effective header processor for `path`.

    This is a small convenience wrapper around
    [`resolve_binding_for_path()`][topmark.resolution.filetypes.resolve_binding_for_path]
    used by tests that only care about the resolved processor object.

    Args:
        path: Filesystem path of the file being resolved.
        include_file_types: Optional whitelist of allowed unqualified file type
            names.
        exclude_file_types: Optional blacklist of disallowed unqualified file
            type names.

    Returns:
        The resolved header processor (or None).
    """
    return resolve_binding_for_path(
        path,
        include_file_types=include_file_types,
        exclude_file_types=exclude_file_types,
    ).processor
