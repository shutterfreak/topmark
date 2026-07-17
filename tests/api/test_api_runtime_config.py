# topmark:header:start
#
#   project      : TopMark
#   file         : test_api_runtime_config.py
#   file_relpath : tests/api/test_api_runtime_config.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for API configuration-input normalization."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.api.runtime import ensure_mutable_config
from topmark.config.io.deserializers import mutable_config_from_defaults

if TYPE_CHECKING:
    from topmark.config.model import FrozenConfig
    from topmark.config.model import MutableConfig


def test_ensure_mutable_config_none_returns_fresh_defaults() -> None:
    """None creates a fresh mutable default draft for every normalization."""
    first: MutableConfig = ensure_mutable_config(None)
    second: MutableConfig = ensure_mutable_config(None)

    assert first is not second
    assert first.freeze() == second.freeze()


def test_ensure_mutable_config_preserves_mutable_identity() -> None:
    """Mutable drafts pass through by identity for internal callers and tests."""
    draft: MutableConfig = mutable_config_from_defaults()

    assert ensure_mutable_config(draft) is draft


def test_ensure_mutable_config_thaws_independent_frozen_draft(
    default_frozen_config: FrozenConfig,
) -> None:
    """Frozen input is copied with staged validation state preserved."""
    frozen: MutableConfig = default_frozen_config.thaw()
    frozen.validation_logs.merged_config.add_warning("preserved warning")
    source: FrozenConfig = frozen.freeze()

    draft: MutableConfig = ensure_mutable_config(source)
    draft.header_fields.append("custom")
    draft.validation_logs.merged_config.add_error("draft-only error")

    assert draft is not source
    assert [item.message for item in draft.validation_logs.merged_config.items] == [
        "preserved warning",
        "draft-only error",
    ]
    assert [item.message for item in source.validation_logs.merged_config.items] == [
        "preserved warning"
    ]
    assert "custom" not in source.header_fields


def test_ensure_mutable_config_deserializes_plain_mapping() -> None:
    """Plain mappings are normalized through the TOML-like deserializer."""
    draft: MutableConfig = ensure_mutable_config(
        {
            "fields": {"project": "TopMark"},
            "header": {"fields": ["project"]},
        }
    )

    assert draft.field_values == {"project": "TopMark"}
    assert draft.header_fields == ["project"]
