# topmark:header:start
#
#   project      : TopMark
#   file         : test_state.py
#   file_relpath : tests/cli/test_state.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for typed CLI state bootstrapping."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import click
import pytest

from topmark.cli.cli_types import CliWriteMode
from topmark.cli.console.click_console import Console
from topmark.cli.console.color import ColorMode
from topmark.cli.state import TopmarkCliState
from topmark.cli.state import bootstrap_cli_state
from topmark.cli.state import get_cli_state
from topmark.core.formats import OutputFormat

if TYPE_CHECKING:
    from collections.abc import Mapping


def _make_click_context(
    obj: object = None,
) -> click.Context:
    """Create a minimal Click context carrying an arbitrary object."""
    ctx = click.Context(
        click.Command("topmark-test"),
        info_name="topmark-test",
    )
    ctx.obj = obj
    return ctx


def test_bootstrap_cli_state_creates_default_state_when_context_obj_is_none() -> None:
    """Missing Click state should be replaced with a default typed state."""
    ctx: click.Context = _make_click_context()

    state: TopmarkCliState = bootstrap_cli_state(ctx)

    assert ctx.obj is state
    assert state.verbosity == 0
    assert state.quiet is False
    assert state.output_format is OutputFormat.TEXT
    assert state.color_mode is ColorMode.AUTO
    assert state.color_enabled is False
    assert isinstance(state.console, Console)
    assert state.log_level is None
    assert state.prune_pipeline_views is True
    assert state.apply_changes is False
    assert state.write_mode is None
    assert state.resolved_writer_options is None


def test_bootstrap_cli_state_returns_existing_typed_state() -> None:
    """Existing typed state should be returned unchanged."""
    existing = TopmarkCliState(
        verbosity=2,
        quiet=True,
        output_format=OutputFormat.JSON,
        color_mode=ColorMode.NEVER,
        color_enabled=False,
        console=Console(enable_color=False),
        log_level=logging.WARNING,
        prune_pipeline_views=False,
        apply_changes=True,
        write_mode=CliWriteMode.ATOMIC,
    )
    ctx: click.Context = _make_click_context(existing)

    state: TopmarkCliState = bootstrap_cli_state(ctx)

    assert state is existing
    assert ctx.obj is existing


def test_bootstrap_cli_state_lifts_legacy_mapping_with_known_fields() -> None:
    """Legacy dict-like Click state should be lifted into typed CLI state."""
    console = Console(enable_color=True)
    ctx: click.Context = _make_click_context(
        {
            "verbosity": 3,
            "quiet": True,
            "output_format": OutputFormat.MARKDOWN,
            "color_mode": ColorMode.ALWAYS,
            "color_enabled": True,
            "console": console,
            "log_level": logging.DEBUG,
            "prune_pipeline_views": False,
            "apply_changes": True,
            "write_mode": "inplace",
            "unknown": "preserved only during extraction",
            42: "ignored non-string key",
        }
    )

    state: TopmarkCliState = bootstrap_cli_state(ctx)

    assert ctx.obj is state
    assert state.verbosity == 3
    assert state.quiet is True
    assert state.output_format is OutputFormat.MARKDOWN
    assert state.color_mode is ColorMode.ALWAYS
    assert state.color_enabled is True
    assert state.console is console
    assert state.log_level == logging.DEBUG
    assert state.prune_pipeline_views is False
    assert state.apply_changes is True
    assert state.write_mode is CliWriteMode.INPLACE


def test_bootstrap_cli_state_lifts_legacy_mapping_with_optional_defaults() -> None:
    """Missing optional legacy fields should use the typed-state defaults."""
    ctx: click.Context = _make_click_context(
        {
            "output_format": OutputFormat.TEXT,
            "color_mode": ColorMode.AUTO,
            "color_enabled": False,
            "console": Console(enable_color=False),
            "verbosity": 1,
            "quiet": False,
        }
    )

    state: TopmarkCliState = bootstrap_cli_state(ctx)

    assert state.log_level is None
    assert state.prune_pipeline_views is True
    assert state.apply_changes is False
    assert state.write_mode is None


def test_bootstrap_cli_state_rejects_unsupported_context_object_type() -> None:
    """Non-mapping non-state Click objects should be rejected."""
    ctx: click.Context = _make_click_context(object())

    with pytest.raises(TypeError, match="Unsupported ctx.obj type for TopmarkCliState"):
        bootstrap_cli_state(ctx)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("output_format", "text", "ctx.obj\\['output_format'\\] must be an OutputFormat"),
        ("color_mode", "auto", "ctx.obj\\['color_mode'\\] must be a ColorMode"),
        ("color_enabled", "false", "ctx.obj\\['color_enabled'\\] must be a bool"),
        ("console", object(), "ctx.obj\\['console'\\] must be a ConsoleProtocol"),
        ("verbosity", "1", "ctx.obj\\['verbosity'\\] must be an int"),
        ("quiet", "false", "ctx.obj\\['quiet'\\] must be a bool"),
        ("log_level", "20", "ctx.obj\\['log_level'\\] must be an int \\| None"),
        (
            "prune_pipeline_views",
            "true",
            "ctx.obj\\['prune_pipeline_views'\\] must be a bool",
        ),
        ("apply_changes", "true", "ctx.obj\\['apply_changes'\\] must be a bool"),
        (
            "write_mode",
            123,
            "ctx.obj\\['write_mode'\\] must be a CliWriteMode-compatible str \\| None",
        ),
    ],
)
def test_bootstrap_cli_state_rejects_invalid_legacy_field_types(
    field: str,
    value: object,
    message: str,
) -> None:
    """Legacy mapping bootstrap should validate all known typed fields."""
    data: dict[object, object] = {
        "output_format": OutputFormat.TEXT,
        "color_mode": ColorMode.AUTO,
        "color_enabled": False,
        "console": Console(enable_color=False),
        "verbosity": 0,
        "quiet": False,
        "log_level": None,
        "prune_pipeline_views": True,
        "apply_changes": False,
        "write_mode": None,
    }
    data[field] = value
    ctx: click.Context = _make_click_context(data)

    with pytest.raises(TypeError, match=message):
        bootstrap_cli_state(ctx)


def test_bootstrap_cli_state_rejects_unknown_legacy_write_mode() -> None:
    """Legacy context mappings should accept only canonical write-mode strings."""
    ctx: click.Context = _make_click_context({"write_mode": "sideways"})

    with pytest.raises(TypeError, match="must be one of: atomic, inplace, stdout"):
        bootstrap_cli_state(ctx)


def test_get_cli_state_returns_typed_state() -> None:
    """Typed CLI state should be retrievable from the Click context."""
    state = TopmarkCliState()
    ctx: click.Context = _make_click_context(state)

    assert get_cli_state(ctx) is state


def test_get_cli_state_rejects_uninitialized_context_object() -> None:
    """Accessing state before bootstrap should fail loudly."""
    ctx: click.Context = _make_click_context({})

    with pytest.raises(TypeError, match="ctx.obj is not initialized as TopmarkCliState"):
        get_cli_state(ctx)


def test_bootstrap_cli_state_accepts_read_only_mapping() -> None:
    """Bootstrap should accept arbitrary mapping objects, not only dict instances."""
    mapping: Mapping[str, object] = {
        "output_format": OutputFormat.TEXT,
        "color_mode": ColorMode.AUTO,
        "color_enabled": False,
        "console": Console(enable_color=False),
        "verbosity": 0,
        "quiet": False,
    }
    ctx: click.Context = _make_click_context(mapping)

    state: TopmarkCliState = bootstrap_cli_state(ctx)

    assert isinstance(state, TopmarkCliState)
    assert ctx.obj is state
