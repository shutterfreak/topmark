# topmark:header:start
#
#   project      : TopMark
#   file         : protocols.py
#   file_relpath : tests/typecheck/filetypes/protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static structural contracts for file-type callables and adapters."""

from __future__ import annotations

__all__ = [
    "verify_header_processor_view_protocol",
    "verify_pre_insert_adapter_protocol",
    "verify_public_file_type_protocol",
]


from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence
    from pathlib import Path

    from topmark.api.protocols import PublicFileType
    from topmark.filetypes.checks.json_like import json_like_can_insert
    from topmark.filetypes.checks.xml import xml_can_insert
    from topmark.filetypes.detectors.jsonc import looks_like_jsonc
    from topmark.filetypes.model import ContentMatcher
    from topmark.filetypes.model import FileTypeActivation
    from topmark.filetypes.model import InsertChecker
    from topmark.filetypes.model import PreInsertContextView
    from topmark.filetypes.model import PreInsertHeaderProcessorView
    from topmark.pipeline.adapters import PreInsertViewAdapter
    from topmark.processors.base import HeaderProcessor

    content_matcher: ContentMatcher = looks_like_jsonc
    json_like_insert_checker: InsertChecker = json_like_can_insert
    xml_insert_checker: InsertChecker = xml_can_insert

    class _PublicFileTypeExample:
        """Representative plugin-facing file type for structural type checks."""

        name: str
        description: str
        extensions: Sequence[str]
        filenames: Sequence[str]
        patterns: Sequence[str]
        activation: FileTypeActivation = FileTypeActivation.DEFAULT
        content_matcher: Callable[[Path], bool] | None = None
        header_policy_name: str


def verify_pre_insert_adapter_protocol(
    adapter: PreInsertViewAdapter,
) -> PreInsertContextView:
    """Statically assert that the context adapter exposes the narrow checker view."""
    return adapter


def verify_header_processor_view_protocol(
    processor: HeaderProcessor,
) -> PreInsertHeaderProcessorView:
    """Statically assert that header processors expose the checker-facing method."""
    return processor


def verify_public_file_type_protocol(
    file_type: _PublicFileTypeExample,
) -> PublicFileType:
    """Statically assert that plugin-facing types expose activation authorization."""
    return file_type
