# topmark:header:start
#
#   project      : TopMark
#   file         : policy_whitespace.py
#   file_relpath : src/topmark/pipeline/policy_whitespace.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Policy-aware whitespace utilities for the pipeline.

This module provides shared helpers used by processors and steps to reason about
blank lines and effectively empty bodies in a file-type aware way. The behavior is
controlled by [`topmark.filetypes.policy.FileTypeHeaderPolicy`][], in particular
its ``blank_collapse_mode`` and ``blank_collapse_extra`` fields.

Helpers
-------
* ``is_pure_spacer(line, policy)`` — classify a single line as a *pure spacer*
  per policy (STRICT/UNICODE/NONE, with optional extra chars).
* ``is_effectively_empty_body(lines, policy)`` — determine whether a sequence of
  lines should be treated as *effectively empty* (only spaces/tabs/EOLs and BOMs),
  without consuming control characters such as form-feed unless the policy opts in.
"""

from topmark.filetypes.policy import (
    BlankCollapseMode,
    FileTypeHeaderPolicy,
)


def is_pure_spacer(line: str, policy: FileTypeHeaderPolicy | None) -> bool:
    r"""Return True if `line` should be treated as a pure spacer per policy.

    STRICT: spaces/tabs/EOL only; preserve control chars (e.g., \x0c).
    UNICODE: all Unicode whitespace (like str.strip()).
    NONE: never collapse non-empty lines.

    `blank_collapse_extra` may list extra chars to treat as blank in addition.

    Args:
        line (str): The line to check.
        policy (FileTypeHeaderPolicy | None): The policy to use, or None for defaults

    Returns:
        bool: True if the line is blank per policy, else False.
    """
    if line == "" or line in ("\n", "\r\n", "\r"):
        return True

    if policy is None:
        mode: BlankCollapseMode = BlankCollapseMode.STRICT
        extra: str = ""
    else:
        mode = policy.blank_collapse_mode
        extra = policy.blank_collapse_extra

    s: str = line.replace("\ufeff", "")  # ignore BOM for spacer purposes

    if mode is BlankCollapseMode.NONE:
        return False

    if mode is BlankCollapseMode.UNICODE:
        t: str = s.strip()  # all unicode whitespace
        t = t.replace("\n", "").replace("\r", "")
        return t == "" or all(ch in extra for ch in t)

    # STRICT
    t = s.strip(" \t")
    t = t.replace("\n", "").replace("\r", "")
    return t == "" or all(ch in extra for ch in t)


# Collapse to BOM-only, no-FNL when the body is effectively empty.
# We deliberately define "empty" narrowly to avoid eating control characters like
# form-feed (\x0c) that Python's str.strip() would treat as whitespace. Here, only
# spaces, tabs, and end-of-line markers are considered ignorable; any other codepoint
# (after removing a BOM) makes the body non-empty.
# NOTE: call this **before** BOM reattachment.
# NOTE: this assumes that whitespace-only lines are not significant in the body.
# TODO: consider making this configurable via a policy option.
def is_effectively_empty_body(
    lines: list[str],
    policy: FileTypeHeaderPolicy | None,
) -> bool:
    r"""Return True if the given ``lines`` are *effectively empty* per policy.

    The body is considered empty when, after removing BOMs and line terminators,
    all remaining characters are ignorable under the policy:

      - STRICT (default): only spaces and tabs are ignorable; control characters
        such as form-feed (\\x0c) are preserved.
      - UNICODE: any Unicode whitespace is ignorable (akin to ``str.strip()``).
      - NONE: never treat non-empty content as empty.

    ``blank_collapse_extra`` extends the ignorable set with project-specific
    characters.
    """
    mode: BlankCollapseMode = (
        policy.blank_collapse_mode if policy is not None else BlankCollapseMode.STRICT
    )
    extra: str = (policy.blank_collapse_extra if policy is not None else "") or ""

    for ln in lines:
        if ln == "":
            continue
        s: str = ln.replace("\ufeff", "")  # ignore BOM
        # Remove EOLs for content check
        s_noeol: str = s.replace("\r", "").replace("\n", "")
        if mode is BlankCollapseMode.UNICODE:
            t: str = s_noeol.strip()
            if t == "":
                continue
            if not all(ch in extra for ch in t):
                return False
        elif mode is BlankCollapseMode.NONE:
            # anything non-empty makes the body non-empty
            return False
        else:
            # STRICT: spaces/tabs only (plus extra)
            t = s_noeol.strip(" \t")
            if t == "":
                continue
            if not all(ch in extra for ch in t):
                return False
    return True
