# tests/unit/test_classify_outcome.py

# topmark:header:start
#
#   file         : test_classify_outcome.py
#   file_relpath : tests/unit/test_classify_outcome.py
#   project      : TopMark
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for CLI summary bucketing in :func:`topmark.cli.utils.classify_outcome`.

These tests assert the **stable contract** (identifier → label family) documented
in the function’s Google-style docstring. They avoid full pipeline execution by
synthesizing minimal :class:`ProcessingContext` objects with relevant statuses.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from topmark.cli.utils import classify_outcome
from topmark.config import Config
from topmark.pipeline.context import (
    ComparisonStatus,
    FileStatus,
    GenerationStatus,
    HeaderProcessingStatus,
    HeaderStatus,
    ProcessingContext,
    StripStatus,
)


def _ctx_with_status(**kwargs: Any) -> ProcessingContext:
    """Return a minimal context with a custom `HeaderProcessingStatus`.

    Args:
      **kwargs: Fields to override on :class:`HeaderProcessingStatus`.

    Returns:
      ProcessingContext: Context with the requested status, dummy path/config.
    """
    status = HeaderProcessingStatus(**kwargs)
    return ProcessingContext(path=Path("/tmp/x"), config=Config.from_defaults(), status=status)


def _assert_key_label(ctx: ProcessingContext, expected_key: str, label_sub: str) -> None:
    key, label, _ = classify_outcome(ctx)
    assert key == expected_key, (key, label)
    assert label_sub in label.lower(), label


# --- Strip pipeline buckets ----------------------------------------------------


def test_strip_ready_bucket() -> None:
    """When `strip` prepared a removal, bucket is `strip:ready` (would change)."""
    ctx = _ctx_with_status(file=FileStatus.RESOLVED, strip=StripStatus.READY)
    _assert_key_label(ctx, "strip:ready", "strip header")


def test_strip_none_missing_header() -> None:
    """No header present → `strip:none` (no work to do)."""
    ctx = _ctx_with_status(
        file=FileStatus.RESOLVED,
        strip=StripStatus.NOT_NEEDED,
        header=HeaderStatus.MISSING,
    )
    _assert_key_label(ctx, "strip:none", "no header")


# --- Default pipeline buckets --------------------------------------------------


def test_insert_bucket_on_missing_header() -> None:
    """Default command: missing header and generation ready → `insert`."""
    ctx = _ctx_with_status(
        file=FileStatus.RESOLVED,
        header=HeaderStatus.MISSING,
        generation=GenerationStatus.GENERATED,
    )
    _assert_key_label(ctx, "insert", "insert header")


def test_update_bucket_on_changed_header() -> None:
    """Default command: detected header and comparison changed → `update`."""
    ctx = _ctx_with_status(
        file=FileStatus.RESOLVED,
        header=HeaderStatus.DETECTED,
        comparison=ComparisonStatus.CHANGED,
    )
    _assert_key_label(ctx, "update", "update header")


def test_ok_bucket_on_unchanged() -> None:
    """Default command: detected header and unchanged → `ok` (up-to-date)."""
    ctx = _ctx_with_status(
        file=FileStatus.RESOLVED,
        header=HeaderStatus.DETECTED,
        comparison=ComparisonStatus.UNCHANGED,
    )
    _assert_key_label(ctx, "ok", "up-to-date")


def test_no_fields_bucket() -> None:
    """Default command: generation has no fields → `no_fields`."""
    ctx = _ctx_with_status(
        file=FileStatus.RESOLVED,
        header=HeaderStatus.MISSING,
        generation=GenerationStatus.NO_FIELDS,
    )
    _assert_key_label(ctx, "no_fields", "no fields")


def test_malformed_and_empty_buckets() -> None:
    """Default command: header empty/malformed map to `header:*` buckets."""
    ctx_empty = _ctx_with_status(file=FileStatus.RESOLVED, header=HeaderStatus.EMPTY)
    key1, label1, _ = classify_outcome(ctx_empty)
    assert key1 == "header:empty" and "empty" in label1.lower()

    ctx_bad = _ctx_with_status(file=FileStatus.RESOLVED, header=HeaderStatus.MALFORMED)
    key2, label2, _ = classify_outcome(ctx_bad)
    assert key2 == "header:malformed" and "malformed" in label2.lower()


def test_file_axis_errors_are_passed_through() -> None:
    """Non-RESOLVED file states map to `file:*` buckets with labels from FileStatus."""
    ctx = _ctx_with_status(file=FileStatus.SKIPPED_UNSUPPORTED)
    key, label, _ = classify_outcome(ctx)
    assert key.startswith("file:"), (key, label)
    assert "unsupported" in label.lower()
