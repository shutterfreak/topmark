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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.filetypes.checks.json_like import json_like_can_insert
    from topmark.filetypes.checks.xml import xml_can_insert
    from topmark.filetypes.detectors.jsonc import looks_like_jsonc
    from topmark.filetypes.model import ContentMatcher
    from topmark.filetypes.model import InsertChecker
    from topmark.filetypes.model import PreInsertContextView
    from topmark.filetypes.model import PreInsertHeaderProcessorView
    from topmark.pipeline.adapters import PreInsertViewAdapter
    from topmark.processors.base import HeaderProcessor

    content_matcher: ContentMatcher = looks_like_jsonc
    json_like_insert_checker: InsertChecker = json_like_can_insert
    xml_insert_checker: InsertChecker = xml_can_insert

__all__ = [
    "verify_header_processor_view_protocol",
    "verify_pre_insert_adapter_protocol",
]


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
