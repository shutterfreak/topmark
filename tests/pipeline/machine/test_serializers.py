# topmark:header:start
#
#   project      : TopMark
#   file         : test_serializers.py
#   file_relpath : tests/pipeline/machine/test_serializers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Defensive unit tests for pipeline machine-readable serializers.

These tests exercise serializer guards that are intentionally unreachable
through the public CLI. They verify that the serializer layer rejects
unsupported output formats with a consistent `ValueError`, ensuring the
defensive contract remains intact independently of CLI validation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import unsupported_output_format
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.core.formats import OutputFormat
from topmark.core.machine.payloads import build_meta_payload
from topmark.pipeline.machine.serializers import serialize_probe_results
from topmark.pipeline.machine.serializers import serialize_processing_results
from topmark.toml.resolution import ResolvedTopmarkTomlSources

if TYPE_CHECKING:
    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig
    from topmark.core.machine.schemas import MetaPayload


def _serializer_context() -> tuple[
    MetaPayload,
    FrozenConfig,
    ResolvedTopmarkTomlSources,
]:
    """Build shared serializer inputs for defensive format tests."""
    meta: MetaPayload = build_meta_payload()
    draft: MutableConfig = mutable_config_from_defaults()
    config: FrozenConfig = draft.freeze()
    resolved_toml_sources: ResolvedTopmarkTomlSources = ResolvedTopmarkTomlSources(
        sources=[],
        writer_options=None,
        strict=False,
    )
    return meta, config, resolved_toml_sources


@pytest.mark.parametrize(
    ("fmt", "is_supported"),
    [
        (OutputFormat.JSON, True),
        (OutputFormat.NDJSON, True),
        (OutputFormat.TEXT, False),
        (OutputFormat.MARKDOWN, False),
        ("bad_format", False),
    ],
)
def test_serialize_probe_results_accepts_only_machine_formats(
    fmt: OutputFormat | str,
    is_supported: bool,
) -> None:
    """`serialize_probe_results` raises ValueError on unsupported machine formats."""
    meta, config, resolved_toml_sources = _serializer_context()

    effective_fmt: OutputFormat = unsupported_output_format(fmt)

    if is_supported:
        serialize_probe_results(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            results=[],
            fmt=effective_fmt,
        )
        return

    with pytest.raises(
        ValueError,
        match=f"Unsupported machine-readable output format: {effective_fmt!r}",
    ):
        serialize_probe_results(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            results=[],
            fmt=effective_fmt,
        )


@pytest.mark.parametrize(
    ("fmt", "is_supported"),
    [
        (OutputFormat.JSON, True),
        (OutputFormat.NDJSON, True),
        (OutputFormat.TEXT, False),
        (OutputFormat.MARKDOWN, False),
        ("bad_format", False),
    ],
)
def test_serialize_processing_results_accepts_only_machine_formats(
    fmt: OutputFormat | str,
    is_supported: bool,
) -> None:
    """`serialize_processing_results` raises ValueError on unsupported machine formats."""
    meta, config, resolved_toml_sources = _serializer_context()

    effective_fmt: OutputFormat = unsupported_output_format(fmt)

    if is_supported:
        serialize_processing_results(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            results=[],
            fmt=effective_fmt,
            summary_mode=False,
        )
        return

    with pytest.raises(
        ValueError,
        match=f"Unsupported machine-readable output format: {effective_fmt!r}",
    ):
        serialize_processing_results(
            meta=meta,
            config=config,
            resolved_toml=resolved_toml_sources,
            results=[],
            fmt=effective_fmt,
            summary_mode=False,
        )
