# topmark:header:start
#
#   project      : TopMark
#   file         : protocols.py
#   file_relpath : src/topmark/pipeline/context/protocols.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Structural protocols for context-like pipeline objects.

This module defines narrow contracts for code that needs to evaluate policy or
policy-derived outcome flags without depending on the concrete mutable
[`ProcessingContext`][topmark.pipeline.context.model.ProcessingContext] class.
Keeping these contracts in a context-owned module avoids import cycles between
context models, durable result snapshots, and policy helpers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from topmark.config.policy import FrozenPolicy
    from topmark.pipeline.context.status import ProcessingStatus


class SupportsPolicyEvaluation(Protocol):
    """Minimum context-like surface required by policy evaluation helpers.

    The protocol is intentionally status- and policy-focused. It should contain
    only fields used by `context.policy` helpers and by durable outcome snapshot
    creation. Step-specific advisory state should stay out of this protocol
    unless policy helpers start using it directly.
    """

    @property
    def status(self) -> ProcessingStatus:
        """Current per-axis processing status."""
        ...

    @property
    def is_empty_like(self) -> bool:
        """Whether the file is empty-like for policy purposes."""
        ...

    @property
    def is_effectively_empty(self) -> bool:
        """Whether the file image is effectively empty.

        Returns whether the decoded, BOM-stripped text image contains **no
        non-whitespace characters**. Newlines and other whitespace are allowed.
        This is the broad notion of "empty" used for most policy decisions.
        """
        ...

    @property
    def is_logically_empty(self) -> bool:
        """Whether the file is "logically empty".

        Returns whether the file is "logically empty": after BOM stripping,
        it contains optional horizontal whitespace and **at most one** trailing
        newline sequence (LF/CRLF/CR), and nothing else. This is a stricter subset
        of `is_effectively_empty` and is useful to preserve stable round-trips for
        files that are effectively placeholders.
        """
        ...

    @property
    def leading_bom(self) -> bool:
        """Whether the source began with a UTF-8 BOM."""
        ...

    @property
    def has_shebang(self) -> bool:
        """Whether the source begins with a shebang after BOM normalization."""
        ...

    def get_effective_policy(self) -> FrozenPolicy:
        """Return the effective policy for the current file and file type."""
        ...
