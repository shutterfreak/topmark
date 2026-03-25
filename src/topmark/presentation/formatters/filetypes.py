# topmark:header:start
#
#   project      : TopMark
#   file         : filetypes.py
#   file_relpath : src/topmark/presentation/formatters/filetypes.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Shared presentation helpers for `topmark.filetypes`."""

from __future__ import annotations

from typing import TYPE_CHECKING

from topmark.presentation.formatters.utils import bool_to_str

if TYPE_CHECKING:
    from collections.abc import Sequence

    from topmark.presentation.shared.registry import FileTypePolicyHumanItem


def filetype_policy_to_display_pairs(
    policy: FileTypePolicyHumanItem,
) -> Sequence[tuple[str, str]]:
    """Return ordered display pairs for a file type header policy.

    This helper generates a list of `(key: str, value: str)` pairs representing the
    ``FileTypePolicyHumanItem`` instance in a deterministic order, as declared in
    [`topmark.filetypes.policy.FileTypeHeaderPolicy`][topmark.filetypes.policy.FileTypeHeaderPolicy].

    The returned keys intentionally preserve the public API / TOML-facing field
    names so rendered output remains useful when drafting `[policy]` config tables.

    Args:
        policy: Human-facing file type policy metadata.

    Returns:
        Ordered `(key, value)` pairs for TEXT and MARKDOWN rendering.
    """
    items: list[tuple[str, str]] = []
    items.append(
        (
            "supports_shebang",
            bool_to_str(policy.supports_shebang),
        )
    )

    if policy.encoding_line_regex:
        # Ony report if defined an non-blank
        items.append(
            (
                "encoding_line_regex",
                repr(policy.encoding_line_regex),
            )
        )

    items.append(
        (
            "pre_header_blank_after_block",
            str(
                policy.pre_header_blank_after_block,
            ),
        )
    )

    items.append(
        (
            "ensure_blank_after_header",
            bool_to_str(policy.ensure_blank_after_header),
        )
    )

    items.append(
        (
            "blank_collapse_mode",
            policy.blank_collapse_mode,
        )
    )
    items.append(
        (
            "blank_collapse_extra",
            repr(policy.blank_collapse_extra),
        )
    )

    return tuple(items)
