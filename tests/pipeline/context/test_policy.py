# topmark:header:start
#
#   project      : TopMark
#   file         : test_policy.py
#   file_relpath : tests/pipeline/context/test_policy.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Contract tests for context-level policy decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.helpers.pipeline import make_pipeline_context
from topmark.config.policy import BomBeforeShebangMode
from topmark.config.policy import EmptyInsertMode
from topmark.config.policy import FrozenPolicy
from topmark.config.policy import HeaderMutationMode
from topmark.config.policy import PolicyRegistry
from topmark.pipeline.context.policy import allow_content_reflow
from topmark.pipeline.context.policy import allow_empty_header
from topmark.pipeline.context.policy import allow_insert_into_empty_like
from topmark.pipeline.context.policy import allow_mixed_line_endings
from topmark.pipeline.context.policy import bom_before_shebang_mode
from topmark.pipeline.context.policy import can_change
from topmark.pipeline.context.policy import check_permitted_by_policy
from topmark.pipeline.context.policy import effective_would_add_or_update
from topmark.pipeline.context.policy import effective_would_strip
from topmark.pipeline.context.policy import is_empty_for_insert
from topmark.pipeline.context.policy import is_empty_for_insert_unchanged_by_default
from topmark.pipeline.context.policy import should_remove_bom_before_shebang
from topmark.pipeline.context.policy import source_lines_with_remediated_bom
from topmark.pipeline.context.policy import would_add_or_update
from topmark.pipeline.context.policy import would_change
from topmark.pipeline.context.policy import would_strip
from topmark.pipeline.status import ComparisonStatus
from topmark.pipeline.status import FsStatus
from topmark.pipeline.status import HeaderStatus
from topmark.pipeline.status import ResolveStatus
from topmark.pipeline.status import StripStatus

if TYPE_CHECKING:
    from pathlib import Path

    from topmark.config.model import FrozenConfig
    from topmark.pipeline.context.model import ProcessingContext


def _set_global_policy(context: ProcessingContext, policy: FrozenPolicy) -> None:
    """Replace the effective global policy for a focused contract test."""
    context.policy_registry = PolicyRegistry(global_policy=policy, by_type={})


@pytest.mark.parametrize(
    ("mode", "fs_status", "is_logically_empty", "is_effectively_empty", "expected"),
    [
        (EmptyInsertMode.BYTES_EMPTY, FsStatus.OK, True, True, False),
        (EmptyInsertMode.LOGICAL_EMPTY, FsStatus.OK, True, True, True),
        (EmptyInsertMode.LOGICAL_EMPTY, FsStatus.OK, False, True, False),
        (EmptyInsertMode.WHITESPACE_EMPTY, FsStatus.OK, False, True, True),
        (EmptyInsertMode.BYTES_EMPTY, FsStatus.EMPTY, False, False, True),
    ],
)
def test_empty_insert_classification_obeys_effective_mode(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    mode: EmptyInsertMode,
    fs_status: FsStatus,
    is_logically_empty: bool,
    is_effectively_empty: bool,
    expected: bool,
) -> None:
    """Empty classification should distinguish byte, logical, and whitespace modes."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "empty-policy.py",
        default_frozen_config,
    )
    _set_global_policy(context, FrozenPolicy(empty_insert_mode=mode))
    context.status.fs = fs_status
    context.is_logically_empty = is_logically_empty
    context.is_effectively_empty = is_effectively_empty

    assert is_empty_for_insert(context) is expected


@pytest.mark.parametrize("allow_insert", [False, True])
def test_empty_insert_permission_and_default_bucketing_are_complements(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    allow_insert: bool,
) -> None:
    """Empty-like mutation permission should invert unchanged-by-default bucketing."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "empty-permission.py",
        default_frozen_config,
    )
    _set_global_policy(
        context,
        FrozenPolicy(
            allow_header_in_empty_files=allow_insert,
            empty_insert_mode=EmptyInsertMode.LOGICAL_EMPTY,
        ),
    )
    context.status.fs = FsStatus.OK
    context.is_logically_empty = True
    context.is_effectively_empty = True

    assert allow_insert_into_empty_like(context) is allow_insert
    assert is_empty_for_insert_unchanged_by_default(context) is (not allow_insert)


def test_simple_policy_permissions_reflect_effective_policy(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Boolean policy helpers should expose effective resolved flags directly."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "flags.py",
        default_frozen_config,
    )
    _set_global_policy(
        context,
        FrozenPolicy(
            render_empty_header_when_no_fields=True,
            allow_reflow=True,
        ),
    )

    assert allow_empty_header(context) is True
    assert allow_content_reflow(context) is True


@pytest.mark.parametrize("healthy_status", [FsStatus.OK, FsStatus.EMPTY])
def test_reader_policy_helpers_accept_healthy_filesystem_states(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    healthy_status: FsStatus,
) -> None:
    """Reader policy gates should not block healthy filesystem states."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "reader-policy.py",
        default_frozen_config,
    )
    context.status.fs = healthy_status

    assert allow_mixed_line_endings(context) is True
    assert bom_before_shebang_mode(context) is BomBeforeShebangMode.REJECT


@pytest.mark.parametrize(
    "fs_status",
    [
        FsStatus.MIXED_LINE_ENDINGS,
        FsStatus.BOM_BEFORE_SHEBANG,
        FsStatus.BINARY,
    ],
)
def test_reader_policy_helpers_strictly_deny_problem_states(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    fs_status: FsStatus,
) -> None:
    """Targeted and unrelated filesystem problems should be denied strictly."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "reader-deny.py",
        default_frozen_config,
    )
    context.status.fs = fs_status

    assert allow_mixed_line_endings(context) is False


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        (BomBeforeShebangMode.REJECT, False),
        (BomBeforeShebangMode.REMOVE_BOM, True),
    ],
)
def test_bom_before_shebang_remediation_uses_effective_mode(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    mode: BomBeforeShebangMode,
    expected: bool,
) -> None:
    """The remediation predicate should combine detection facts and resolved policy."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "bom-policy.py",
        default_frozen_config,
    )
    _set_global_policy(context, FrozenPolicy(bom_before_shebang=mode))
    context.status.fs = FsStatus.BOM_BEFORE_SHEBANG
    context.leading_bom = True
    context.has_shebang = True

    assert bom_before_shebang_mode(context) is mode
    assert should_remove_bom_before_shebang(context) is expected
    assert source_lines_with_remediated_bom(["#!python\n"], context) == (
        ["\ufeff#!python\n"] if expected else ["#!python\n"]
    )


@pytest.mark.parametrize(
    ("mode", "header_status", "expected"),
    [
        (HeaderMutationMode.ADD_ONLY, HeaderStatus.MISSING, True),
        (HeaderMutationMode.ADD_ONLY, HeaderStatus.DETECTED, False),
        (HeaderMutationMode.ADD_ONLY, HeaderStatus.EMPTY, False),
        (HeaderMutationMode.UPDATE_ONLY, HeaderStatus.MISSING, False),
        (HeaderMutationMode.UPDATE_ONLY, HeaderStatus.DETECTED, True),
        (HeaderMutationMode.ALL, HeaderStatus.MISSING, True),
        (HeaderMutationMode.ALL, HeaderStatus.DETECTED, True),
    ],
)
def test_check_permission_obeys_header_mutation_mode(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    mode: HeaderMutationMode,
    header_status: HeaderStatus,
    expected: bool,
) -> None:
    """Mutation policy should distinguish insert and update intent."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "mutation-mode.py",
        default_frozen_config,
    )
    _set_global_policy(context, FrozenPolicy(header_mutation_mode=mode))
    context.status.header = header_status

    assert check_permitted_by_policy(context) is expected


def test_policy_decisions_remain_indeterminate_before_relevant_steps_run(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Policy helpers should preserve uncertainty before mutation intent is known."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "pending.py",
        default_frozen_config,
    )

    assert check_permitted_by_policy(context) is None
    assert would_change(context) is None

    context.status.strip = StripStatus.NOT_NEEDED

    assert check_permitted_by_policy(context) is None
    assert would_change(context) is False


def test_change_feasibility_requires_resolution_and_safe_header_state(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Mutation feasibility should require resolution and reject malformed headers."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "feasibility.py",
        default_frozen_config,
    )
    context.status.fs = FsStatus.OK
    context.status.header = HeaderStatus.MISSING

    assert can_change(context) is False

    context.status.resolve = ResolveStatus.RESOLVED

    assert can_change(context) is True

    context.status.header = HeaderStatus.MALFORMED

    assert can_change(context) is False


def test_effective_add_update_combines_intent_feasibility_and_policy(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Effective add/update should require intent, feasibility, and permission."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "effective-check.py",
        default_frozen_config,
    )
    context.status.resolve = ResolveStatus.RESOLVED
    context.status.fs = FsStatus.OK
    context.status.header = HeaderStatus.MISSING

    assert would_add_or_update(context) is True
    assert effective_would_add_or_update(context) is True

    _set_global_policy(
        context,
        FrozenPolicy(header_mutation_mode=HeaderMutationMode.UPDATE_ONLY),
    )

    assert effective_would_add_or_update(context) is False

    context.status.header = HeaderStatus.DETECTED
    context.status.comparison = ComparisonStatus.CHANGED

    assert effective_would_add_or_update(context) is True


def test_effective_strip_combines_ready_intent_and_feasibility(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Effective strip should require both prepared removal and safe mutation."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "effective-strip.py",
        default_frozen_config,
    )
    context.status.resolve = ResolveStatus.RESOLVED
    context.status.fs = FsStatus.OK
    context.status.header = HeaderStatus.DETECTED
    context.status.strip = StripStatus.READY

    assert would_strip(context) is True
    assert would_change(context) is True
    assert effective_would_strip(context) is True

    context.status.strip = StripStatus.FAILED

    assert would_strip(context) is False
    assert would_change(context) is True
    assert effective_would_strip(context) is False


@pytest.mark.parametrize(
    (
        "mode",
        "allow_insert",
        "is_logically_empty",
        "is_effectively_empty",
        "expected",
    ),
    [
        (EmptyInsertMode.LOGICAL_EMPTY, False, True, True, False),
        (EmptyInsertMode.LOGICAL_EMPTY, True, True, True, True),
        (EmptyInsertMode.LOGICAL_EMPTY, False, False, True, True),
        (EmptyInsertMode.WHITESPACE_EMPTY, False, False, True, False),
        (EmptyInsertMode.WHITESPACE_EMPTY, True, False, True, True),
    ],
)
def test_can_change_applies_empty_like_policy_and_mode(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    mode: EmptyInsertMode,
    allow_insert: bool,
    is_logically_empty: bool,
    is_effectively_empty: bool,
    expected: bool,
) -> None:
    """Mutation feasibility should combine empty classification and permission."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "empty-feasibility.py",
        default_frozen_config,
    )
    _set_global_policy(
        context,
        FrozenPolicy(
            empty_insert_mode=mode,
            allow_header_in_empty_files=allow_insert,
        ),
    )
    context.status.resolve = ResolveStatus.RESOLVED
    context.status.fs = FsStatus.OK
    context.status.header = HeaderStatus.MISSING
    context.is_logically_empty = is_logically_empty
    context.is_effectively_empty = is_effectively_empty

    assert can_change(context) is expected


@pytest.mark.parametrize(
    "header_status",
    [
        HeaderStatus.MALFORMED,
        HeaderStatus.MALFORMED_ALL_FIELDS,
        HeaderStatus.MALFORMED_SOME_FIELDS,
    ],
)
def test_can_change_rejects_all_malformed_header_states(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
    header_status: HeaderStatus,
) -> None:
    """Every malformed header state should block mutation."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "malformed-header.py",
        default_frozen_config,
    )
    context.status.resolve = ResolveStatus.RESOLVED
    context.status.fs = FsStatus.OK
    context.status.header = header_status

    assert can_change(context) is False


def test_can_change_rejects_failed_strip_preparation(
    tmp_path: Path,
    default_frozen_config: FrozenConfig,
) -> None:
    """Failed strip preparation should block mutation."""
    context: ProcessingContext = make_pipeline_context(
        tmp_path / "failed-strip.py",
        default_frozen_config,
    )
    context.status.resolve = ResolveStatus.RESOLVED
    context.status.fs = FsStatus.OK
    context.status.header = HeaderStatus.DETECTED
    context.status.strip = StripStatus.FAILED

    assert can_change(context) is False
