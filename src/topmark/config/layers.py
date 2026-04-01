# topmark:header:start
#
#   project      : TopMark
#   file         : layers.py
#   file_relpath : src/topmark/config/layers.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Config provenance layer models.

This module defines the immutable provenance objects used to track where layered
configuration fragments came from during resolution.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import MutableConfig


class ConfigLayerKind(str, Enum):
    """Kinds of config provenance layers."""

    DEFAULT = "default"
    USER = "user"
    DISCOVERED = "discovered"
    EXPLICIT = "explicit"
    CLI = "cli"
    API = "api"


@dataclass(frozen=True, slots=True)
class ConfigLayer:
    """Config provenance layer model.

    Attributes:
        origin: Actual file path, or a marker such as "<CLI overrides>".
        scope_root: Defaults, user, CLI, and API layers are usually `None`;
            file-backed layers use the containing config directory.
        precedence: Stable merge order.
        kind: Provenance kind for this layer (default, user, discovered,
            explicit, CLI, or API).
        config: Parsed layered config fragment for this layer only.
    """

    origin: Path | str
    scope_root: Path | None
    precedence: int
    kind: ConfigLayerKind
    config: MutableConfig
