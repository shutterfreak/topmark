# topmark:header:start
#
#   project      : TopMark
#   file         : view_protocols.py
#   file_relpath : tests/typecheck/pipeline/view_protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static structural contracts for pipeline views."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.pipeline.views import FileImageView
    from topmark.pipeline.views import ListFileImageView
    from topmark.pipeline.views import Releasable
    from topmark.pipeline.views import SegmentUpdatedContent
    from topmark.pipeline.views import UpdatedContent

__all__ = [
    "verify_file_image_protocol",
    "verify_file_image_release_protocol",
    "verify_updated_content_protocol",
]


def verify_file_image_protocol(
    view: ListFileImageView,
) -> FileImageView:
    """Statically assert that the list-backed image exposes the complete view."""
    return view


def verify_file_image_release_protocol(
    view: ListFileImageView,
) -> Releasable:
    """Statically assert that the list-backed image participates in pruning."""
    return view


def verify_updated_content_protocol(
    content: SegmentUpdatedContent,
) -> UpdatedContent:
    """Statically assert that segment content is repeatably iterable."""
    return content
