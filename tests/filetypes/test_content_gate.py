# topmark:header:start
#
#   project      : TopMark
#   file         : test_content_gate.py
#   file_relpath : tests/filetypes/test_content_gate.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Unit tests for ContentGate semantics in FileType.matches()."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from tests.helpers.registry import make_file_type
from topmark.core.constants import TOPMARK_END_MARKER
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.filetypes.checks.json_like import json_like_can_insert
from topmark.filetypes.detectors.jsonc import looks_like_jsonc
from topmark.filetypes.model import ContentGate
from topmark.filetypes.model import FileType
from topmark.filetypes.model import InsertCapability

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

    from topmark.filetypes.model import InsertCheckResult
    from topmark.filetypes.model import PreInsertHeaderProcessorView


class JsonLikePreInsertContext:
    """Minimal pre-insert context for JSON-like insert-check tests."""

    lines: Iterable[str]
    newline_style: str
    header_processor: PreInsertHeaderProcessorView | None
    file_type: FileType | None

    def __init__(
        self,
        *,
        lines: Iterable[str],
        newline_style: str = "\n",
        header_processor: PreInsertHeaderProcessorView | None = None,
        file_type: FileType | None,
    ) -> None:
        self.lines = tuple(lines)
        self.newline_style = newline_style
        self.header_processor = header_processor
        self.file_type = file_type


class Probe:
    """Callable probe that records invocation count and returns a fixed result."""

    def __init__(self, result: bool) -> None:
        self.result: bool = result
        self.calls = 0

    def __call__(self, path: Path) -> bool:  # content_matcher signature
        """Increment call counter and return the fixed result."""
        self.calls += 1
        return self.result


_USE_JSON_AS_JSONC_FILE_TYPE = object()


def _json_as_jsonc_file_type() -> FileType:
    """Return the JSON-as-JSONC file type used by the insert checker."""
    return make_file_type(local_key="json-as-jsonc")


def _json_like_context(
    lines: list[str],
    *,
    file_type: FileType | None | object = _USE_JSON_AS_JSONC_FILE_TYPE,
) -> JsonLikePreInsertContext:
    """Build a minimal context for `json_like_can_insert()`.

    By default this returns a context for the targeted `json-as-jsonc` file type.
    Pass `file_type=None` explicitly to exercise unresolved file-type behavior.
    """
    resolved_file_type: FileType | None
    if file_type is _USE_JSON_AS_JSONC_FILE_TYPE:
        resolved_file_type = _json_as_jsonc_file_type()
    elif isinstance(file_type, FileType) or file_type is None:
        resolved_file_type = file_type
    else:
        raise TypeError("file_type must be a FileType, None, or the internal sentinel")

    return JsonLikePreInsertContext(
        lines=lines,
        file_type=resolved_file_type,
    )


def test_gate_never_does_not_call_matcher_but_keeps_name_match(tmp_path: Path) -> None:
    """NEVER gate skips matcher but still matches on name rules."""
    probe = Probe(result=False)
    ft: FileType = make_file_type(
        local_key="json",
        extensions=[".json"],
        content_matcher=probe,
        content_gate=ContentGate.NEVER,
    )
    p: Path = tmp_path / "a.json"
    p.write_text("{}")

    assert ft.matches(p) is True  # name rule matched; probe not allowed
    assert probe.calls == 0


def test_gate_if_extension_calls_matcher_only_on_extension_match(tmp_path: Path) -> None:
    """IF_EXTENSION gate calls matcher only when extension matched."""
    # Extension match ⇒ probe called
    probe_ext = Probe(result=True)
    ft_ext: FileType = make_file_type(
        local_key="json",
        extensions=[".json"],
        content_matcher=probe_ext,
        content_gate=ContentGate.IF_EXTENSION,
    )
    p1: Path = tmp_path / "x.json"
    p1.write_text("// jsonc\n{}")
    assert ft_ext.matches(p1) is True
    assert probe_ext.calls == 1

    # Filename (not extension) match ⇒ probe NOT called
    probe_name = Probe(result=True)
    ft_name: FileType = make_file_type(
        local_key="special-conf",
        filenames=["special.conf"],
        content_matcher=probe_name,
        content_gate=ContentGate.IF_EXTENSION,
    )
    p2: Path = tmp_path / "special.conf"
    p2.write_text("key=value")
    assert ft_name.matches(p2) is True  # name rule matched, but no probe
    assert probe_name.calls == 0

    # No name rule match ⇒ probe NOT called, overall False
    probe_none = Probe(result=True)
    ft_none: FileType = make_file_type(
        local_key="json",
        extensions=[".json"],
        content_matcher=probe_none,
        content_gate=ContentGate.IF_EXTENSION,
    )
    p3: Path = tmp_path / "readme.txt"
    p3.write_text("text")
    assert ft_none.matches(p3) is False
    assert probe_none.calls == 0


def test_gate_if_filename_calls_matcher_only_on_filename_match(tmp_path: Path) -> None:
    """IF_FILENAME gate calls matcher only when filename matched."""
    probe = Probe(result=True)
    ft: FileType = make_file_type(
        local_key="vscode",
        filenames=[".vscode/settings.json"],
        content_matcher=probe,
        content_gate=ContentGate.IF_FILENAME,
    )

    # Tail subpath match ⇒ probe called
    p: Path = tmp_path / ".vscode" / "settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("// jsonc\n{}")
    assert ft.matches(p) is True
    assert probe.calls == 1

    # Extension-only match ⇒ probe NOT called; still True due to name match
    probe2 = Probe(result=True)
    ft2: FileType = make_file_type(
        local_key="json",
        extensions=[".json"],
        filenames=["config.yaml"],
        content_matcher=probe2,
        content_gate=ContentGate.IF_FILENAME,
    )
    p2: Path = tmp_path / "data.json"
    p2.write_text("{}")
    assert ft2.matches(p2) is True  # extension matched; gate blocks probe
    assert probe2.calls == 0


def test_gate_if_pattern_calls_matcher_only_on_pattern_match(tmp_path: Path) -> None:
    """IF_PATTERN gate calls matcher only when regex pattern matched."""
    probe = Probe(result=False)
    ft: FileType = make_file_type(
        local_key="python-requirements",
        patterns=[r"requirements\.(in|txt)"],
        content_matcher=probe,
        content_gate=ContentGate.IF_PATTERN,
    )

    p: Path = tmp_path / "requirements.txt"
    p.write_text("# pinned deps")
    assert ft.matches(p) is False  # pattern matched; probe called and returned False
    assert probe.calls == 1


def test_gate_if_any_name_rule_calls_matcher_for_any_name_hit(tmp_path: Path) -> None:
    """IF_ANY_NAME_RULE gate calls matcher for any matching rule (ext/file/pattern)."""
    probe = Probe(result=True)
    ft: FileType = make_file_type(
        local_key="json",
        extensions=[".json"],
        filenames=["Makefile"],
        content_matcher=probe,
        content_gate=ContentGate.IF_ANY_NAME_RULE,
    )

    # Extension match ⇒ probe called
    p1: Path = tmp_path / "x.json"
    p1.write_text("// ok\n{}")
    assert ft.matches(p1) is True
    # Filename match ⇒ probe called
    p2: Path = tmp_path / "Makefile"
    p2.write_text("# rules")
    assert ft.matches(p2) is True

    assert probe.calls == 2


def test_gate_if_none_probes_when_no_name_rules_defined(tmp_path: Path) -> None:
    """IF_NONE gate probes only if no name rules are defined."""
    # No extensions/filenames/patterns ⇒ probe allowed
    probe = Probe(result=True)
    ft: FileType = make_file_type(
        local_key="test",
        extensions=[],
        filenames=[],
        patterns=[],
        content_matcher=probe,
        content_gate=ContentGate.IF_NONE,
    )

    p: Path = tmp_path / "anything.weird"
    p.write_text("content")
    assert ft.matches(p) is True
    assert probe.calls == 1

    # If any name rule exists, IF_NONE must NOT probe; result = name rule truthiness
    probe2 = Probe(result=True)
    ft2: FileType = make_file_type(
        local_key="weird",
        extensions=[".weird"],
        content_matcher=probe2,
        content_gate=ContentGate.IF_NONE,
    )
    p2: Path = tmp_path / "x.weird"
    p2.write_text("content")
    assert ft2.matches(p2) is True  # extension matched; probe blocked
    assert probe2.calls == 0


def test_gate_always_always_calls_matcher_and_returns_its_result(tmp_path: Path) -> None:
    """ALWAYS gate always calls matcher and returns its boolean result."""
    probe_true = Probe(result=True)
    ft_true: FileType = make_file_type(
        local_key="test",
        extensions=[],
        content_matcher=probe_true,
        content_gate=ContentGate.ALWAYS,
    )
    p1: Path = tmp_path / "no-match.ext"
    p1.write_text("x")
    assert ft_true.matches(p1) is True
    assert probe_true.calls == 1

    probe_false = Probe(result=False)
    ft_false: FileType = make_file_type(
        local_key="json",
        extensions=[".json"],
        content_matcher=probe_false,
        content_gate=ContentGate.ALWAYS,
    )
    p2: Path = tmp_path / "x.json"
    p2.write_text("{}")
    assert ft_false.matches(p2) is False
    assert probe_false.calls == 1


# --- JSONC Detector Tests ---


@pytest.mark.parametrize(
    "content",
    [
        '{\n  // comment\n  "key": true\n}\n',
        "[\n  1,\n  // comment\n  2\n]\n",
        '{\n  /* block comment */\n  "key": true\n}\n',
        '{\n  /* unterminated block comment\n  "key": true\n}\n',
    ],
)
def test_jsonc_detector_accepts_comments_outside_strings(
    tmp_path: Path,
    content: str,
) -> None:
    """JSONC detector should accept line and block comments outside strings."""
    path: Path = tmp_path / "settings.json"
    path.write_text(content, encoding="utf-8")

    assert looks_like_jsonc(path) is True


@pytest.mark.parametrize(
    "content",
    [
        '{"url": "https://example.test/path"}\n',
        '{"glob": "src/*/tests"}\n',
        '{"escaped": "quote: \\" // not comment"}\n',
        '{"escaped": "slashes: \\\\// not comment"}\n',
        '{"block": "/* not comment */"}\n',
    ],
)
def test_jsonc_detector_ignores_comment_markers_inside_strings(
    tmp_path: Path,
    content: str,
) -> None:
    """JSONC detector should avoid false positives for comment tokens in strings."""
    path: Path = tmp_path / "plain.json"
    path.write_text(content, encoding="utf-8")

    assert looks_like_jsonc(path) is False


def test_jsonc_detector_line_comment_state_resets_after_newline(tmp_path: Path) -> None:
    """Line comment handling should resume normal scanning after newline."""
    path: Path = tmp_path / "line-reset.json"
    path.write_text('{\n  // first comment\n  "key": "value"\n}\n', encoding="utf-8")

    assert looks_like_jsonc(path) is True


def test_jsonc_detector_block_comment_state_resets_after_close(tmp_path: Path) -> None:
    """Block comment handling should resume scanning after closing delimiter."""
    path: Path = tmp_path / "block-reset.json"
    path.write_text('{\n  /* first comment */\n  "key": "value"\n}\n', encoding="utf-8")

    assert looks_like_jsonc(path) is True


@pytest.mark.parametrize(
    "content",
    [
        "",
        "   \n\t",
        "// comment without JSON structure\n",
        "plain text // comment\n",
    ],
)
def test_jsonc_detector_rejects_content_without_json_structure(
    tmp_path: Path,
    content: str,
) -> None:
    """JSONC detector should require at least a brace or bracket sanity marker."""
    path: Path = tmp_path / "not-json.txt"
    path.write_text(content, encoding="utf-8")

    assert looks_like_jsonc(path) is False


def test_jsonc_detector_rejects_plain_json_without_comments(tmp_path: Path) -> None:
    """Plain JSON without comments should not be classified as JSONC."""
    path = tmp_path / "plain.json"
    path.write_text('{"key": [1, 2, 3]}\n', encoding="utf-8")

    assert looks_like_jsonc(path) is False


def test_jsonc_detector_returns_false_for_unreadable_path(tmp_path: Path) -> None:
    """Unreadable paths should fail closed instead of raising."""
    path: Path = tmp_path / "directory.json"
    path.mkdir()

    assert looks_like_jsonc(path) is False


def test_jsonc_detector_scans_only_prefix_limit(tmp_path: Path) -> None:
    """Comments beyond the detector prefix limit should not affect classification."""
    path: Path = tmp_path / "large.json"
    path.write_text("{" + (" " * 131072) + "// too late\n}", encoding="utf-8")

    assert looks_like_jsonc(path) is False


# --- JSON-like Insert Check Tests ---


def test_json_like_can_insert_allows_non_json_as_jsonc_file_types() -> None:
    """JSON-like insert check should only gate the JSON-as-JSONC file type."""
    ctx: JsonLikePreInsertContext = _json_like_context(
        ['{"key": true}\n'],
        file_type=make_file_type(local_key="python"),
    )

    result: InsertCheckResult = json_like_can_insert(ctx)

    assert result == {
        "capability": InsertCapability.OK,
        "origin": "topmark.filetypes.checks.json_like.json_like_can_insert",
    }


def test_json_like_can_insert_allows_unresolved_file_type() -> None:
    """Missing file-type information should fail open for this targeted checker."""
    ctx: JsonLikePreInsertContext = _json_like_context(['{"key": true}\n'], file_type=None)

    result: InsertCheckResult = json_like_can_insert(ctx)

    assert result == {
        "capability": InsertCapability.OK,
        "origin": "topmark.filetypes.checks.json_like.json_like_can_insert",
    }


def test_json_like_can_insert_skips_plain_json_when_promotion_disabled() -> None:
    """Plain JSON should not be promoted to JSONC by default."""
    ctx: JsonLikePreInsertContext = _json_like_context(['{"key": true}\n'])

    result: InsertCheckResult = json_like_can_insert(ctx)

    assert result == {
        "capability": InsertCapability.SKIP_POLICY,
        "reason": "JSON lacks comments; promotion to JSONC is disabled",
        "origin": "topmark.filetypes.checks.json_like.json_like_can_insert",
    }


def test_json_like_can_insert_allows_plain_json_when_promotion_enabled() -> None:
    """Explicit promotion should allow inserting a JSONC-style header."""
    ctx: JsonLikePreInsertContext = _json_like_context(['{"key": true}\n'])

    result: InsertCheckResult = json_like_can_insert(ctx, allow_promote=True)

    assert result == {
        "capability": InsertCapability.OK,
        "origin": "topmark.filetypes.checks.json_like.json_like_can_insert",
    }


@pytest.mark.parametrize(
    "lines",
    [
        ["{\n", "  // existing user comment\n", '  "key": true\n', "}\n"],
        ["{\n", "  /* existing user comment */\n", '  "key": true\n', "}\n"],
    ],
)
def test_json_like_can_insert_allows_existing_non_topmark_comments(lines: list[str]) -> None:
    """Existing non-TopMark comments indicate JSONC-compatible content."""
    ctx: JsonLikePreInsertContext = _json_like_context(lines)

    result: InsertCheckResult = json_like_can_insert(ctx)

    assert result == {
        "capability": InsertCapability.OK,
        "origin": "topmark.filetypes.checks.json_like.json_like_can_insert",
    }


@pytest.mark.parametrize(
    "lines",
    [
        [
            "{\n",
            f"  // {TOPMARK_START_MARKER}\n",
            f"  // {TOPMARK_END_MARKER}\n",
            '  "key": true\n',
            "}\n",
        ],
        [
            "{\n",
            f"  /* {TOPMARK_START_MARKER} */\n",
            f"  /* {TOPMARK_END_MARKER} */\n",
            '  "key": true\n',
            "}\n",
        ],
    ],
)
def test_json_like_can_insert_does_not_treat_topmark_markers_as_user_comments(
    lines: list[str],
) -> None:
    """TopMark marker comments alone should not make plain JSON safe to promote."""
    ctx: JsonLikePreInsertContext = _json_like_context(lines)

    result: InsertCheckResult = json_like_can_insert(ctx)

    assert result.get("capability") is InsertCapability.SKIP_POLICY
    assert result.get("reason") == "JSON lacks comments; promotion to JSONC is disabled"
