# topmark:header:start
#
#   project      : TopMark
#   file         : hints.py
#   file_relpath : src/topmark/pipeline/hints.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Hint taxonomy and normalization utilities for the TopMark pipeline.

This module defines the canonical vocabulary and structure for *diagnostic hints*
emitted by pipeline steps, as well as helpers for hint aggregation, ranking, and
selection. Hints are lightweight, non-binding messages that help explain
intermediate conditions or advisory diagnostics (e.g., "would insert header",
"file contains mixed line endings"). They are used for telemetry, CLI feedback,
and public API inspection but do not influence control flow directly.

Overview:
    • `Axis` — enumerates stable pipeline axes that can emit hints.
    • `KnownCode` — curated list of common, machine-friendly hint codes.
    • `Hint` — dataclass capturing a normalized hint payload.
    • `make_hint` — factory helper to create validated, consistent Hint objects.
    • `HintLog` — mutable container for per-context hints with convenience helpers.
    • `select_headline_hint` — ranking helper that selects the most relevant hint.

Design principles:
    * Hints are **diagnostic only**; they never alter processing behavior.
    * `Axis` values are stable and map 1:1 to pipeline status axes.
    * `KnownCode` covers frequent cases but is not exhaustive; ad-hoc
      string codes are allowed.
    * `ProcessingContext.add_hint` stores normalized hints to simplify
      aggregation, ranking (headline selection), and coarse bucketing.
    * `HintLog` and `select_headline_hint` centralize ranking and aggregation logic.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any

from yachalk import chalk

from topmark.config.logging import get_logger
from topmark.core.enum_mixins import EnumIntrospectionMixin
from topmark.core.presentation import ColoredStrEnum

if TYPE_CHECKING:
    from collections.abc import Iterable

    from topmark.config.logging import TopmarkLogger

logger: TopmarkLogger = get_logger(__name__)


class Axis(EnumIntrospectionMixin, str, Enum):
    """Canonical axes that can emit hints.

    Values are short, machine-friendly strings that align with pipeline status axes.
    These are intentionally *stable*; prefer adding new *codes* over adding new axes.

    Members:
        RESOLVE: File type resolution phase.
        FS: File system checks (existence, permissions, binary, newline mix).
        CONTENT: Text content/read phase (encoding, policy skips).
        HEADER: Header scan/parse phase (presence, bounds, malformed).
        GENERATION: Field generation/build phase.
        RENDER: Header rendering phase.
        COMPARISON: Content/format comparison phase.
        STRIP: Header removal phase.
        PLAN: Plan phase (update planning) (insert/replace/remove).
        PATCH: Patch generation phase (unified diff text).
        WRITE: Final write/emit phase (file/stdout/preview).

    Notes:
        Axis values should change only in major versions. When new situations
        arise, add or reuse *codes* under an existing axis before introducing a
        new axis.
    """

    # NOTE: preserve the exact order and keep in sync with ProcessingStatus

    RESOLVE = "resolve"
    FS = "fs"
    CONTENT = "content"
    HEADER = "header"
    GENERATION = "generation"
    RENDER = "render"
    STRIP = "strip"
    COMPARISON = "comparison"
    PLAN = "plan"
    PATCH = "patch"
    WRITE = "write"


class Cluster(EnumIntrospectionMixin, ColoredStrEnum):
    """Coarse, outcome-oriented groups for hints.

    Clusters provide a small set of semantically meaningful buckets used for CLI
    coloring and headline ranking (e.g., ERROR outranks UNCHANGED). Colors are
    chosen to be legible on common dark/light terminal themes and to avoid low
    contrast combinations.

    Accessibility:
        Do not rely solely on color to convey meaning. Always include a textual
        label (e.g., "changed", "skipped").
    """

    PENDING = "pending", chalk.gray
    UNCHANGED = "unchanged", chalk.green
    WOULD_CHANGE = "would_change", chalk.yellow
    CHANGED = "changed", chalk.yellow_bright.bold
    SKIPPED = "skipped", chalk.gray.bold
    UNSUPPORTED = "unsupported", chalk.magenta
    BLOCKED_POLICY = "blocked_policy", chalk.red.bold
    ERROR = "error", chalk.red_bright


class KnownCode(EnumIntrospectionMixin, str, Enum):
    """Illustrative, non-exhaustive set of codes.

    Codes are short, namespaced, and machine-friendly. Treat this enum as a
    convenient source of *well-known* codes used across TopMark. Do **not**
    require all codes to live here—`Hint` accepts arbitrary strings so
    extensions and experiments remain frictionless.

    Examples (selected):
        discovery/resolve: 'discovery:unsupported', 'discovery:no_processor'

        fs:               'fs:mixed_newlines', 'fs:bom_before_shebang'

        content:          'content:skipped_bom_shebang', 'content:skipped_mixed'

        header:           'header:missing', 'header:empty', 'header:malformed'

        generation:       'generation:no_fields', 'generation:generated'

        render:           'render:rendered'

        comparison:       'compare:changed', 'compare:unchanged'

        strip:            'strip:ready', 'strip:none', 'strip:failed'

        plan:             'plan:insert', 'plan:update', 'plan:remove', 'plan:skip'

        patch:            'patch:generated', 'patch:skipped', 'patch:failed'

        write:            'write:written', 'write:previewed', 'write:skipped', 'write:failed'

    Notes:
        Additions here are source-compatible. Removals or renames are breaking
        and should only occur in major releases.
    """

    # Resolve/discovery
    DISCOVERY_UNSUPPORTED = "discovery:unsupported"
    DISCOVERY_NO_PROCESSOR = "discovery:no_processor"
    # FS
    FS_BOM_BEFORE_SHEBANG = "fs:bom_before_shebang"
    FS_EMPTY = "fs:empty_file"
    FS_MIXED_NEWLINES = "fs:mixed_newlines"
    FS_NOT_FOUND = "fs:not_found"
    FS_UNREADABLE = "fs:unreadable"
    FS_UNWRITABLE = "fs:unwritable"
    # Content
    CONTENT_EMPTY_FILE = "content:empty_file"
    CONTENT_NOT_SUPPORTED = "content:not_supported"
    CONTENT_ENCODING_ERROR = "content:encoding_error"
    CONTENT_SKIPPED_BOM_SHEBANG = "content:skipped_bom_shebang"
    CONTENT_SKIPPED_MIXED = "content:skipped_mixed"
    CONTENT_SKIPPED_REFLOW = "content:skipped_reflow"
    CONTENT_UNREADABLE = "content:unreadable"
    # Header
    HEADER_MISSING = "header:missing"
    HEADER_EMPTY = "header:empty"
    HEADER_MALFORMED = "header:malformed"
    # Generation
    GENERATION_NO_FIELDS = "generation:no_fields"
    GENERATION_GENERATED = "generation:generated"
    # Render
    RENDER_RENDERED = "render:rendered"
    # Comparison
    COMPARE_CHANGED = "compare:changed"
    COMPARE_UNCHANGED = "compare:unchanged"
    COMPARE_SKIPPED = "compare:skipped"
    # Strip
    STRIP_READY = "strip:ready"
    STRIP_NONE = "strip:none"
    STRIP_FAILED = "strip:failed"
    # Update/Plan
    PLAN_INSERT = "plan:insert"
    PLAN_UPDATE = "plan:update"
    PLAN_REMOVE = "plan:remove"
    PLAN_SKIP = "plan:skip"
    PLAN_BLOCKED_POLICY = "plan:blocked_policy"
    PLAN_FAILED = "plan:failed"
    # Write
    WRITE_WRITTEN = "write:written"
    WRITE_PREVIEWED = "write:previewed"
    WRITE_SKIPPED = "write:skipped"
    WRITE_FAILED = "write:failed"
    # Patch
    PATCH_APPLIED = "patch:applied"
    PATCH_GENERATED = "patch:generated"
    PATCH_SKIPPED = "patch:skipped"
    PATCH_FAILED = "patch:failed"


# Higher is more severe/important
_CLUSTER_SCORE: dict[str, int] = {
    Cluster.ERROR.value: 100,
    Cluster.BLOCKED_POLICY.value: 90,
    Cluster.SKIPPED.value: 80,
    Cluster.UNSUPPORTED.value: 80,
    Cluster.CHANGED.value: 70,
    Cluster.WOULD_CHANGE.value: 60,
    Cluster.UNCHANGED.value: 50,
    Cluster.PENDING.value: 10,
}


@dataclass(frozen=True)
class Hint:
    """Normalized hint payload attached to a `ProcessingContext`.

    Attributes:
        axis: Pipeline axis emitting the hint (e.g., `Axis.FS`).
        code: Stable machine key (e.g., 'fs:mixed_newlines', 'plan:insert').
            Accepts any string; prefer `KnownCode` members when available.
        message: Short, summary line suitable for single-line CLI output.
        detail: Optional extended diagnostic text (possibly multi-line)
            that callers may render only at higher verbosity levels.
        cluster: Optional broader grouping key for bucketing/analytics.
            Defaults to ``code`` when omitted.
        terminal: Whether the condition represents a terminal/stop state.
        reason: Optional additional detail (status value, policy id).
        meta: Optional extensibility bag (free-form).

    Example:
        ```python
        from topmark.pipeline.hints import Axis, KnownCode, make_hint

        hint = make_hint(
            axis=Axis.FS,
            code=KnownCode.FS_MIXED_NEWLINES,
            message="File contains mixed line endings; policy may allow proceeding",
            terminal=False,
        )
        ctx.add_hint(hint)
        ```
    """

    axis: Axis
    code: str
    message: str
    detail: str | None = None
    cluster: str | None = None
    terminal: bool = False
    reason: str | None = None
    meta: dict[str, Any] | None = None


def make_hint(
    *,
    axis: Axis,
    code: KnownCode | str,
    message: str,
    detail: str | None = None,
    cluster: Cluster | str | None = None,
    terminal: bool = False,
    reason: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Hint:
    """Create a normalized `Hint` with light validation and defaults.

    Accepts either a `KnownCode` or an arbitrary string for ``code``. If
    ``cluster`` is not provided, it defaults to the string form of ``code``. When
    a `Cluster` is supplied for ``cluster``, its string value is used.

    Args:
        axis: Axis emitting the hint.
        code: Stable machine key for the condition.
        message: Human-readable short summary line.
        detail: Optional extended diagnostic text rendered at higher
            verbosity (e.g., multi-line config snippets or rationale).
        cluster: Optional grouping key; defaults to ``code``.
        terminal: Whether this condition is terminal.
        reason: Optional detail string.
        meta: Optional extensibility bag.

    Returns:
        Frozen, normalized hint object.

    Example:
        ```python
        make_hint(axis=Axis.PLAN, code=KnownCode.PLAN_INSERT, message="would insert header")
        ```
    """
    code_str: str = code.value if isinstance(code, KnownCode) else str(code)
    cluster_str: str = (
        (cluster.value if isinstance(cluster, Cluster) else cluster)
        if cluster is not None
        else code_str
    )

    return Hint(
        axis=axis,
        code=code_str,
        message=message,
        detail=detail,
        cluster=cluster_str,
        terminal=terminal,
        reason=reason,
        meta=meta,
    )


@dataclass
class HintLog:
    """Mutable, per-context collection of diagnostic hints.

    This wrapper keeps hint aggregation and logging concerns local and
    provides a small façade (`add`, `headline`) so that callers do not
    depend on the concrete list representation.
    """

    items: list[Hint] = field(default_factory=lambda: [])

    def add(self, hint: Hint) -> None:
        """Attach a structured hint to the hint log.

        Hints are non-binding diagnostics used to refine human-readable
        summaries without affecting the core outcome classification.

        The hint collection is updated in place.

        Args:
            hint: The hint instance to attach.
        """
        self.items.append(hint)
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "added hint axis=%s code=%s message=%s", hint.axis, hint.code, hint.message
            )

    def headline(self) -> Hint | None:
        """Return the single most relevant hint from a hint log, order-agnostically.

        Ranking: ERROR > BLOCKED_POLICY > SKIPPED/UNSUPPORTED > CHANGED
        > WOULD_CHANGE > UNCHANGED > PENDING. Ties prefer ``terminal=True``.

        Returns:
            The top-ranked hint, or ``None`` if the log is empty.

        Notes:
            You can extend the tie-breaker with axis priority without changing callers.
        """

        def _score_cluster(cluster: str | None) -> int:
            if not cluster:
                return 0
            return _CLUSTER_SCORE.get(cluster, 0)

        best: Hint | None = None
        best_key: tuple[int, bool] = (-1, False)
        for h in self.items:
            key: tuple[int, bool] = (_score_cluster(h.cluster), bool(h.terminal))
            if key > best_key:
                best = h
                best_key = key
        return best

    def __iter__(self) -> Iterable[Hint]:
        """Iterate over all hints stored in this log.

        Returns:
            An iterator yielding the collected hints in insertion order.
        """
        return iter(self.items)

    def __len__(self) -> int:
        """Return the number of hints stored in this log.

        Returns:
            The number of hint entries.
        """
        return len(self.items)
