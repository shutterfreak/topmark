# topmark:header:start
#
#   project      : TopMark
#   file         : state.py
#   file_relpath : src/topmark/cli/state.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Strongly typed Click invocation state for TopMark CLI commands."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING

from topmark.cli.console.click_console import Console
from topmark.cli.console.color import ColorMode
from topmark.cli.console.protocols import ConsoleProtocol
from topmark.cli.console.protocols import is_console_protocol
from topmark.config.policy import MutablePolicy
from topmark.core.formats import OutputFormat
from topmark.core.typing_guards import is_mapping

if TYPE_CHECKING:
    import click


@dataclass(kw_only=True, slots=True)
class TopmarkCliState:
    """Shared invocation-scoped CLI state stored on Click contexts.

    This state object holds the strongly typed human-output/runtime fields that
    are shared across multiple CLI helpers during a single command invocation.

    The ``extras`` mapping is a temporary compatibility bucket for a small
    number of remaining unmigrated CLI options.
    """

    verbosity: int = 0
    quiet: bool = False
    output_format: OutputFormat = OutputFormat.TEXT
    color_mode: ColorMode = ColorMode.AUTO
    color_enabled: bool = False
    console: ConsoleProtocol = field(default_factory=lambda: Console(enable_color=False))
    log_level: int | None = None
    prune_pipeline_views: bool = True
    apply_changes: bool = False
    write_mode: str | None = None
    policy: MutablePolicy = field(default_factory=MutablePolicy)

    # Temporary compatibility bucket for the remaining unmigrated CLI options.
    extras: dict[str, object] = field(default_factory=lambda: {})

    def get(self, key: str, default: object | None = None) -> object | None:
        """Return a typed field or compatibility extra by key.

        Args:
            key: The stored state key.
            default: Fallback value when the key is absent.

        Returns:
            The stored value for ``key`` if present, otherwise ``default``.
        """
        if key == "verbosity":
            return self.verbosity
        if key == "quiet":
            return self.quiet
        if key == "output_format":
            return self.output_format
        if key == "color_mode":
            return self.color_mode
        if key == "color_enabled":
            return self.color_enabled
        if key == "console":
            return self.console
        if key == "log_level":
            return self.log_level
        if key == "prune_pipeline_views":
            return self.prune_pipeline_views
        if key == "apply_changes":
            return self.apply_changes
        if key == "write_mode":
            return self.write_mode
        if key == "policy":
            return self.policy
        return self.extras.get(key, default)

    def __getitem__(self, key: str) -> object:
        """Return a stored field or compatibility extra.

        Args:
            key: The stored state key.

        Returns:
            The stored value for ``key``.

        Raises:
            KeyError: If ``key`` is not present.
        """
        sentinel: object = object()
        value: object | None = self.get(key, sentinel)
        if value is sentinel:
            raise KeyError(key)
        return value

    def __setitem__(self, key: str, value: object) -> None:
        """Store a typed field or compatibility extra.

        Args:
            key: The stored state key.
            value: Value to store for ``key``.

        Raises:
            TypeError: If a typed field receives an incompatible value.
        """
        if key == "verbosity":
            if not isinstance(value, int):
                raise TypeError(f"{key} must be an int")
            self.verbosity = value
            return
        if key == "quiet":
            if not isinstance(value, bool):
                raise TypeError(f"{key} must be a bool")
            self.quiet = value
            return
        if key == "output_format":
            if not isinstance(value, OutputFormat):
                raise TypeError(f"{key} must be an OutputFormat")
            self.output_format = value
            return
        if key == "color_mode":
            if not isinstance(value, ColorMode):
                raise TypeError(f"{key} must be a ColorMode")
            self.color_mode = value
            return
        if key == "color_enabled":
            if not isinstance(value, bool):
                raise TypeError(f"{key} must be a bool")
            self.color_enabled = value
            return
        if key == "console":
            if not is_console_protocol(value):
                raise TypeError(f"{key} must be a ConsoleProtocol")
            self.console = value  # Protocol checked at call sites.
            return
        if key == "log_level":
            if value is not None and not isinstance(value, int):
                raise TypeError(f"{key} must be an int | None")
            self.log_level = value
            return
        if key == "prune_pipeline_views":
            if not isinstance(value, bool):
                raise TypeError(f"{key} must be a bool")
            self.prune_pipeline_views = value
            return
        if key == "apply_changes":
            if not isinstance(value, bool):
                raise TypeError(f"{key} must be a bool")
            self.apply_changes = value
            return
        if key == "write_mode":
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{key} must be a str | None")
            self.write_mode = value
            return
        if key == "policy":
            if not isinstance(value, MutablePolicy):
                raise TypeError(f"{key} must be a MutablePolicy")
            self.policy = value
            return
        self.extras[key] = value

    def setdefault(self, key: str, default: object) -> object:
        """Return the stored value for ``key`` or store ``default``.

        Args:
            key: The stored state key.
            default: Value to store if ``key`` is absent.

        Returns:
            The existing or newly stored value.
        """
        existing: object | None = self.get(key)
        if existing is not None:
            return existing
        self[key] = default
        return default


def bootstrap_cli_state(ctx: click.Context) -> TopmarkCliState:
    """Create or normalize the typed CLI state stored on ``ctx.obj``.

    This is the entrypoint bootstrap helper for the CLI layer. It should be
    called by the root Click group and by command entrypoints instead of
    ``ctx.ensure_object(dict)``.

    Behavior:
        - If ``ctx.obj`` already contains ``TopmarkCliState``, return it.
        - If ``ctx.obj`` is ``None``, create a fresh default state.
        - If ``ctx.obj`` is a mapping, lift known typed fields into
          ``TopmarkCliState`` and preserve any remaining string-keyed values in
          ``extras``.
        - Otherwise, raise ``TypeError``.

    Args:
        ctx: Active Click context.

    Returns:
        The bootstrapped typed CLI state.

    Raises:
        TypeError: If ``ctx.obj`` is neither ``None``, a mapping, nor
            ``TopmarkCliState``, or if lifted legacy values have incompatible types.
    """
    obj: object = ctx.obj

    if isinstance(obj, TopmarkCliState):
        return obj

    if obj is None:
        state = TopmarkCliState(
            verbosity=0,
            quiet=False,
            output_format=OutputFormat.TEXT,
            color_mode=ColorMode.AUTO,
            color_enabled=False,
            console=Console(enable_color=False),
            log_level=None,
            prune_pipeline_views=True,
            apply_changes=False,
            write_mode=None,
            policy=MutablePolicy(),
            extras={},
        )
        ctx.obj = state
        return state

    if not is_mapping(obj):
        raise TypeError(f"Unsupported ctx.obj type for TopmarkCliState: {type(obj)!r}")

    extras: dict[str, object] = {}
    for key, value in obj.items():
        if isinstance(key, str):
            extras[key] = value

    output_format_obj: object = extras.pop("output_format", OutputFormat.TEXT)
    color_mode_obj: object = extras.pop("color_mode", ColorMode.AUTO)
    color_enabled_obj: object = extras.pop("color_enabled", False)
    console_obj: object = extras.pop("console", Console(enable_color=False))
    verbosity_obj: object = extras.pop("verbosity", 0)
    quiet_obj: object = extras.pop("quiet", False)
    log_level_obj: object = extras.pop("log_level", None)
    prune_pipeline_views_obj: object = extras.pop("prune_pipeline_views", None)
    apply_changes_obj: object = extras.pop("apply_changes", False)
    write_mode_obj: object = extras.pop("write_mode", None)

    if not isinstance(output_format_obj, OutputFormat):
        raise TypeError("ctx.obj['output_format'] must be an OutputFormat")
    if not isinstance(color_mode_obj, ColorMode):
        raise TypeError("ctx.obj['color_mode'] must be a ColorMode")
    if not isinstance(color_enabled_obj, bool):
        raise TypeError("ctx.obj['color_enabled'] must be a bool")
    if not is_console_protocol(console_obj):
        raise TypeError("ctx.obj['console'] must be a ConsoleProtocol")
    if not isinstance(verbosity_obj, int):
        raise TypeError("ctx.obj['verbosity'] must be an int")
    if not isinstance(quiet_obj, bool):
        raise TypeError("ctx.obj['quiet'] must be a bool")
    if log_level_obj is not None and not isinstance(log_level_obj, int):
        raise TypeError("ctx.obj['log_level'] must be an int | None")
    if prune_pipeline_views_obj is not None and not isinstance(prune_pipeline_views_obj, bool):
        raise TypeError("ctx.obj['prune_pipeline_views'] must be a bool")
    if not isinstance(apply_changes_obj, bool):
        raise TypeError("ctx.obj['apply_changes'] must be a bool")
    if write_mode_obj is not None and not isinstance(write_mode_obj, str):
        raise TypeError("ctx.obj['write_mode'] must be a str | None")

    state = TopmarkCliState(
        verbosity=verbosity_obj,
        quiet=quiet_obj,
        output_format=output_format_obj,
        color_mode=color_mode_obj,
        color_enabled=color_enabled_obj,
        console=console_obj,
        log_level=log_level_obj,
        prune_pipeline_views=True if prune_pipeline_views_obj is None else prune_pipeline_views_obj,
        apply_changes=apply_changes_obj,
        write_mode=write_mode_obj,
        policy=MutablePolicy(),
        extras=extras,
    )
    ctx.obj = state
    return state


def get_cli_state(ctx: click.Context) -> TopmarkCliState:
    """Return the typed CLI state stored on ``ctx.obj``.

    Args:
        ctx: Active Click context.

    Returns:
        The typed CLI state.

    Raises:
        TypeError: If ``ctx.obj`` is not a ``TopmarkCliState`` instance.
    """
    obj: object = ctx.obj
    if not isinstance(obj, TopmarkCliState):
        raise TypeError("ctx.obj is not initialized as TopmarkCliState")
    return obj
