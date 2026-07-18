# topmark:header:start
#
#   project      : TopMark
#   file         : policy_protocols.py
#   file_relpath : tests/typecheck/config/policy_protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Static structural contracts for resolved policy configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from topmark.config.model import FrozenConfig
    from topmark.config.policy import HasPolicyConfig

__all__ = [
    "verify_frozen_config_policy_protocol",
]


def verify_frozen_config_policy_protocol(
    config: FrozenConfig,
) -> HasPolicyConfig:
    """Statically assert that FrozenConfig exposes resolved policy values."""
    return config
