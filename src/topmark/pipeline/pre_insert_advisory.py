# topmark:header:start
#
#   project      : TopMark
#   file         : pre_insert_advisory.py
#   file_relpath : src/topmark/pipeline/pre_insert_advisory.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Durable pre-insert advisory values for reduced pipeline results.

Pre-insert capability is execution-time advisory state produced by reader and
planner steps. It is not part of policy evaluation itself, but it is useful
durable result metadata because it explains why some files are not safe
pre-insert candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from topmark.filetypes.model import InsertCapability


class SupportsPreInsertAdvisory(Protocol):
    """Minimum context-like surface required to snapshot pre-insert advice."""

    @property
    def pre_insert_capability(self) -> InsertCapability:
        """Current pre-insert capability advisory."""
        ...

    @property
    def pre_insert_reason(self) -> str | None:
        """Optional human-readable reason for the current advisory."""
        ...

    @property
    def pre_insert_origin(self) -> str | None:
        """Optional producer of the current advisory."""
        ...


@dataclass(frozen=True, kw_only=True, slots=True)
class PreInsertAdvisorySnapshot:
    """Durable snapshot of pre-insert capability advisory state.

    Attributes:
        capability: Current pre-insert capability advisory.
        reason: Optional human-readable reason for the advisory.
        origin: Optional producer of the advisory.
    """

    capability: InsertCapability
    reason: str | None
    origin: str | None

    @classmethod
    def from_context(
        cls,
        ctx: SupportsPreInsertAdvisory,
    ) -> PreInsertAdvisorySnapshot:
        """Create a pre-insert advisory snapshot from a context-like object.

        Args:
            ctx: Source object exposing pre-insert advisory state.

        Returns:
            Durable pre-insert advisory snapshot.
        """
        return cls(
            capability=ctx.pre_insert_capability,
            reason=ctx.pre_insert_reason,
            origin=ctx.pre_insert_origin,
        )

    def to_dict(self) -> dict[str, str | None]:
        """Return a JSON-friendly pre-insert advisory payload.

        Returns:
            Mapping matching the existing serialized advisory payload shape.
        """
        return {
            "capability": self.capability.name,
            "reason": self.reason,
            "origin": self.origin,
        }
