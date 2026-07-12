# topmark:header:start
#
#   project      : TopMark
#   file         : test_adapters.py
#   file_relpath : tests/pipeline/test_adapters.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for lightweight pipeline adapters."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import make_pipeline_context
from topmark.filetypes.model import FileType
from topmark.pipeline.adapters import PreInsertViewAdapter
from topmark.pipeline.adapters import as_sequence
from topmark.pipeline.views import ListFileImageView

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext


def _file_type() -> FileType:
    return FileType(
        local_key="adapter-test",
        namespace="tests",
        extensions=[".txt"],
        filenames=[],
        patterns=[],
        description="Adapter test file type",
    )


def test_pre_insert_adapter_forwards_context_metadata_and_streams_image_lines(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """The adapter should expose the checker view without copying context metadata."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "sample.txt",
        default_frozen_config,
    )
    file_type: FileType = _file_type()
    source_lines: list[str] = ["first\r\n", "second"]
    context.file_type = file_type
    context.newline_style = "\r\n"
    context.views.image = ListFileImageView(source_lines)

    adapter = PreInsertViewAdapter(context)

    assert adapter.file_type is file_type
    assert adapter.header_processor is context.header_processor
    assert adapter.newline_style == "\r\n"
    assert list(adapter.lines) == source_lines


def test_pre_insert_adapter_exposes_safe_empty_lines_for_missing_image(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Synthetic or partially processed contexts should adapt to an empty line stream."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "unread.txt",
        default_frozen_config,
    )

    adapter = PreInsertViewAdapter(context)

    assert list(adapter.lines) == []
    assert adapter.file_type is None
    assert adapter.header_processor is None


def test_pre_insert_adapter_has_diagnostic_repr(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """The adapter representation should identify its stream, newline, and file type."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "sample.txt",
        default_frozen_config,
    )
    context.file_type = _file_type()
    context.newline_style = "\n"
    adapter = PreInsertViewAdapter(context)

    assert repr(adapter) == (
        "<PreInsertViewAdapter lines=tuple_iterator "
        "newline_style='\\n' file_type='tests:adapter-test'>"
    )


def test_as_sequence_preserves_existing_lists_without_copying() -> None:
    """Already materialized line lists should retain identity for downstream consumers."""
    lines: list[str] = ["first\n", "second"]

    assert as_sequence(lines) is lines


def test_as_sequence_materializes_other_iterables_and_handles_absent_state() -> None:
    """Non-list streams should be materialized once, while absent state becomes empty."""
    yielded: list[str] = []

    def _lines() -> Iterator[str]:
        for line in ("first\n", "second"):
            yielded.append(line)
            yield line

    assert as_sequence(None) == []
    assert as_sequence(("tuple\n", "line")) == ["tuple\n", "line"]
    assert as_sequence(_lines()) == ["first\n", "second"]
    assert yielded == ["first\n", "second"]


class _SentinelError(RuntimeError):
    """Sentinel exception used to verify propagation."""


def test_as_sequence_propagates_iteration_exceptions() -> None:
    """Producer failures should propagate unchanged during materialization."""

    def _broken_lines() -> Iterator[str]:
        yield "first\n"
        raise _SentinelError("boom")

    with pytest.raises(_SentinelError, match="boom"):
        as_sequence(_broken_lines())
