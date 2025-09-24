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
from typing import TYPE_CHECKING, Callable

from topmark.filetypes.base import ContentGate, FileType
from topmark.filetypes.policy import FileTypeHeaderPolicy

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


def _ft(
    *,
    name: str = "probe",
    extensions: list[str] | None = None,
    filenames: list[str] | None = None,
    patterns: list[str] | None = None,
    matcher: Callable[[Path], bool] | None = None,
    gate: ContentGate = ContentGate.ALWAYS,
) -> FileType:
    return FileType(
        name=name,
        extensions=extensions or [],
        filenames=filenames or [],
        patterns=patterns or [],
        description="probe type",
        content_matcher=matcher,
        content_gate=gate,
        header_policy=FileTypeHeaderPolicy(
            supports_shebang=False,
            ensure_blank_after_header=True,
        ),
    )


def test_gate_never_does_not_call_matcher_but_keeps_name_match(tmp_path: Path) -> None:
    """NEVER gate skips matcher but still matches on name rules."""
    probe = Probe(result=False)
    ft: FileType = _ft(
        extensions=[".json"],
        matcher=probe,
        gate=ContentGate.NEVER,
    )
    p: Path = tmp_path / "a.json"
    p.write_text("{}")

    assert ft.matches(p) is True  # name rule matched; probe not allowed
    assert probe.calls == 0


def test_gate_if_extension_calls_matcher_only_on_extension_match(tmp_path: Path) -> None:
    """IF_EXTENSION gate calls matcher only when extension matched."""
    # Extension match ⇒ probe called
    probe_ext = Probe(result=True)
    ft_ext: FileType = _ft(
        extensions=[".json"],
        matcher=probe_ext,
        gate=ContentGate.IF_EXTENSION,
    )
    p1: Path = tmp_path / "x.json"
    p1.write_text("// jsonc\n{}")
    assert ft_ext.matches(p1) is True
    assert probe_ext.calls == 1

    # Filename (not extension) match ⇒ probe NOT called
    probe_name = Probe(result=True)
    ft_name: FileType = _ft(
        filenames=["special.conf"],
        matcher=probe_name,
        gate=ContentGate.IF_EXTENSION,
    )
    p2: Path = tmp_path / "special.conf"
    p2.write_text("key=value")
    assert ft_name.matches(p2) is True  # name rule matched, but no probe
    assert probe_name.calls == 0

    # No name rule match ⇒ probe NOT called, overall False
    probe_none = Probe(result=True)
    ft_none: FileType = _ft(
        extensions=[".json"],
        matcher=probe_none,
        gate=ContentGate.IF_EXTENSION,
    )
    p3: Path = tmp_path / "readme.txt"
    p3.write_text("text")
    assert ft_none.matches(p3) is False
    assert probe_none.calls == 0


def test_gate_if_filename_calls_matcher_only_on_filename_match(tmp_path: Path) -> None:
    """IF_FILENAME gate calls matcher only when filename matched."""
    probe = Probe(result=True)
    ft: FileType = _ft(
        filenames=[".vscode/settings.json"],
        matcher=probe,
        gate=ContentGate.IF_FILENAME,
    )

    # Tail subpath match ⇒ probe called
    p: Path = tmp_path / ".vscode" / "settings.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("// jsonc\n{}")
    assert ft.matches(p) is True
    assert probe.calls == 1

    # Extension-only match ⇒ probe NOT called; still True due to name match
    probe2 = Probe(result=True)
    ft2: FileType = _ft(
        extensions=[".json"],
        filenames=["config.yaml"],
        matcher=probe2,
        gate=ContentGate.IF_FILENAME,
    )
    p2: Path = tmp_path / "data.json"
    p2.write_text("{}")
    assert ft2.matches(p2) is True  # extension matched; gate blocks probe
    assert probe2.calls == 0


def test_gate_if_pattern_calls_matcher_only_on_pattern_match(tmp_path: Path) -> None:
    """IF_PATTERN gate calls matcher only when regex pattern matched."""
    probe = Probe(result=False)
    ft: FileType = _ft(
        patterns=[r"requirements\.(in|txt)"],
        matcher=probe,
        gate=ContentGate.IF_PATTERN,
    )

    p: Path = tmp_path / "requirements.txt"
    p.write_text("# pinned deps")
    assert ft.matches(p) is False  # pattern matched; probe called and returned False
    assert probe.calls == 1


def test_gate_if_any_name_rule_calls_matcher_for_any_name_hit(tmp_path: Path) -> None:
    """IF_ANY_NAME_RULE gate calls matcher for any matching rule (ext/file/pattern)."""
    probe = Probe(result=True)
    ft: FileType = _ft(
        extensions=[".json"],
        filenames=["Makefile"],
        matcher=probe,
        gate=ContentGate.IF_ANY_NAME_RULE,
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
    ft: FileType = _ft(
        extensions=[],
        filenames=[],
        patterns=[],
        matcher=probe,
        gate=ContentGate.IF_NONE,
    )

    p: Path = tmp_path / "anything.weird"
    p.write_text("content")
    assert ft.matches(p) is True
    assert probe.calls == 1

    # If any name rule exists, IF_NONE must NOT probe; result = name rule truthiness
    probe2 = Probe(result=True)
    ft2: FileType = _ft(
        extensions=[".weird"],
        matcher=probe2,
        gate=ContentGate.IF_NONE,
    )
    p2: Path = tmp_path / "x.weird"
    p2.write_text("content")
    assert ft2.matches(p2) is True  # extension matched; probe blocked
    assert probe2.calls == 0


def test_gate_always_always_calls_matcher_and_returns_its_result(tmp_path: Path) -> None:
    """ALWAYS gate always calls matcher and returns its boolean result."""
    probe_true = Probe(result=True)
    ft_true: FileType = _ft(
        extensions=[],
        matcher=probe_true,
        gate=ContentGate.ALWAYS,
    )
    p1: Path = tmp_path / "no-match.ext"
    p1.write_text("x")
    assert ft_true.matches(p1) is True
    assert probe_true.calls == 1

    probe_false = Probe(result=False)
    ft_false: FileType = _ft(
        extensions=[".json"],
        matcher=probe_false,
        gate=ContentGate.ALWAYS,
    )
    p2: Path = tmp_path / "x.json"
    p2.write_text("{}")
    assert ft_false.matches(p2) is False
    assert probe_false.calls == 1
