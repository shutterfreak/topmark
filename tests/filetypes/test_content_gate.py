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

from tests.conftest import make_file_type
from topmark.filetypes.model import ContentGate
from topmark.filetypes.model import FileType

if TYPE_CHECKING:
    from pathlib import Path


class Probe:
    """Callable probe that records invocation count and returns a fixed result."""

    def __init__(self, result: bool) -> None:
        self.result: bool = result
        self.calls = 0

    def __call__(self, path: Path) -> bool:  # content_matcher signature
        """Increment call counter and return the fixed result."""
        self.calls += 1
        return self.result


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
