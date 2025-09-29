# topmark:header:start
#
#   project      : TopMark
#   file         : test_resolver.py
#   file_relpath : tests/pipeline/steps/test_resolver.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for the `resolver` pipeline step.

This suite focuses on resolver behavior only:
- selecting a FileType using extension, filename-tail, regex pattern, and content gating
- deterministic tie-breaking by score then name
- precedence of `skip_processing` and missing processor scenarios
- registry edge cases and exception safety

Each test monkeypatches the file-type and/or processor registries to remain
fully deterministic and independent of the built-in definitions.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Callable, cast

import topmark.pipeline.steps.resolver as resolver_mod
from topmark.config import Config, MutableConfig
from topmark.filetypes.base import (
    ContentGate,
    FileType,  # runtime import for typing/cast correctness
)
from topmark.pipeline.context import ProcessingContext, ResolveStatus
from topmark.pipeline.steps.resolver import resolve

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

    from topmark.pipeline.processors.base import HeaderProcessor


# Produce a duck-typed FileType object with proper static type for Pyright
def _ft(**kwargs: object) -> FileType:
    return cast("FileType", SimpleNamespace(**kwargs))


# Convenience to annotate content matcher callables
def _cm(fn: Callable[[Path], bool]) -> Callable[[Path], bool]:
    return fn


# --- For monkeypatching and custom FileType tests ---


# Typed helper to satisfy Pyright when monkeypatching the processor registry
def _empty_processor_registry() -> dict[str, "HeaderProcessor"]:
    return {}


def _empty_filetype_registry() -> dict[str, "FileType"]:
    return {}


# --- Helpers for typed processor registries ---
def _one_processor_registry(name: str) -> dict[str, "HeaderProcessor"]:
    return {name: cast("HeaderProcessor", object())}


# def _processors_registry(*names: str) -> dict[str, "HeaderProcessor"]:
#     return {n: cast("HeaderProcessor", object()) for n in names}


def test_resolve_python_file_resolves_with_processor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A simple Python file should resolve to a supported file type with a processor."""
    content: str = "print('Hi!')\n"
    f: Path = tmp_path / "x.py"
    # Use newline="" so Python preserves the exact line endings we provide.
    with f.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    # Deterministic registries: one Python FileType and a dummy processor for it
    py_ft: FileType = _ft(
        name="python",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"python": py_ft})
    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"python": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)

    # Resolve the file type
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED

    # The resolver must identify a processor; otherwise the reader step would be ill-defined.
    assert ctx.file_type is not None
    assert ctx.file_type.name == "python"
    assert ctx.header_processor is not None


# --- Additional targeted resolver tests ---


def test_resolve_unknown_extension_marked_unsupported(
    tmp_path: Path, monkeypatch: "pytest.MonkeyPatch"
) -> None:
    """Files with no matching FileType must be marked SKIPPED_UNSUPPORTED."""
    f: Path = tmp_path / "mystery.weirdext"
    f.write_text("just text\n", encoding="utf-8")

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", _empty_filetype_registry)
    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", _empty_processor_registry)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.UNSUPPORTED
    assert ctx.file_type is None
    assert ctx.header_processor is None


def test_resolve_sets_skip_when_no_processor_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When FileType matches without registered processor, resolver must skip with warning.

    This relates to known file types which are not (yet) supported by a header processor.
    """
    f: Path = tmp_path / "x.py"
    f.write_text("print('hi')\n", encoding="utf-8")

    # Monkeypatch the processor registry to be empty to force the no-processor path.
    py_ft: FileType = _ft(
        name="python",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"python": py_ft})
    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", _empty_processor_registry)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    # Should match a FileType (Python) but have no processor
    assert ctx.file_type is not None
    assert ctx.header_processor is None
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED


def test_resolve_respects_skip_processing_filetype(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolver must set SKIPPED_KNOWN_NO_HEADERS when FileType.skip_processing is True."""
    # Create a contrived file that will match our custom FileType by extension.
    f: Path = tmp_path / "readme.md"
    f.write_text("# docs\n", encoding="utf-8")

    # Build a minimal duck-typed FileType with skip_processing=True
    ft: FileType = _ft(
        name="Docs",
        extensions=[".md"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=True,
    )

    # Monkeypatch the file type and processor registries to use our custom type only.
    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"Docs": ft})
    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", _empty_processor_registry)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.file_type is not None and ctx.file_type.name == "Docs"
    assert ctx.header_processor is None
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED


def test_resolve_can_use_content_gate_when_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Resolver may select a FileType via content_matcher when ContentGate.ALWAYS is set."""
    f: Path = tmp_path / "mystery.bin"
    f.write_text("MAGIC_SIGNATURE\n", encoding="utf-8")

    def _content_hit(p: Path) -> bool:
        try:
            return "MAGIC_SIGNATURE" in p.read_text(encoding="utf-8")
        except Exception:
            return False

    ft: FileType = _ft(
        name="Magic",
        extensions=[],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.ALWAYS,
        content_matcher=_content_hit,
        skip_processing=False,
    )

    # Only our custom type is present; no processors registered to keep the test simple.
    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"Magic": ft})
    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", _empty_processor_registry)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.file_type is not None and ctx.file_type.name == "Magic"
    assert ctx.header_processor is None
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED


def test_resolve_deterministic_name_tiebreak(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Two equal-score candidates must resolve deterministically by name (ASC)."""
    f: Path = tmp_path / "x.foo"
    f.write_text("data\n", encoding="utf-8")

    ftA: FileType = _ft(
        name="AJson",
        extensions=[".foo"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )
    ftB: FileType = _ft(
        name="BJson",
        extensions=[".foo"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"AJson": ftA, "BJson": ftB}
    )

    # Register only AJson processor to prove selected type drives processor
    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"AJson": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "AJson"  # name ASC
    assert ctx.header_processor is not None


def test_resolve_filename_tail_beats_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filename-tail match must outrank a pure extension match."""
    f: Path = tmp_path / "app.conf.example"
    f.write_text("cfg\n", encoding="utf-8")

    ft_ext: FileType = _ft(
        name="ByExt",
        extensions=[".conf"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )
    ft_tail: FileType = _ft(
        name="ByTail",
        extensions=[],
        filenames=["app.conf.example"],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"ByExt": ft_ext, "ByTail": ft_tail}
    )

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"ByTail": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ByTail"


def test_resolve_pattern_beats_extension(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regex pattern must outrank a pure extension match."""
    f: Path = tmp_path / "service.special.log"
    f.write_text("lines\n", encoding="utf-8")

    ft_ext: FileType = _ft(
        name="ByExt",
        extensions=[".log"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )
    ft_pat: FileType = _ft(
        name="ByPat",
        extensions=[],
        filenames=[],
        patterns=[r".*\.special\.log"],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"ByExt": ft_ext, "ByPat": ft_pat}
    )

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"ByPat": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ByPat"


def test_resolve_content_upgrade_over_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Content upgrade (e.g. JSONC) must outrank a plain extension match."""
    f: Path = tmp_path / "x.json"
    f.write_text('// comment\n{ "k": 1 }\n', encoding="utf-8")

    def hits_jsonc(p: Path) -> bool:
        return p.read_text(encoding="utf-8").lstrip().startswith("//")

    ft_json: FileType = _ft(
        name="JSON",
        extensions=[".json"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )
    ft_jsonc: FileType = _ft(
        name="JSONC",
        extensions=[".json"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.IF_EXTENSION,
        content_matcher=hits_jsonc,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"JSON": ft_json, "JSONC": ft_jsonc}
    )

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"JSONC": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "JSONC"


def test_resolve_gating_if_extension_excludes_when_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IF_EXTENSION gate must exclude when content matcher misses."""
    f: Path = tmp_path / "x.json"
    f.write_text('{"k": 1}\n', encoding="utf-8")

    ft_json: FileType = _ft(
        name="JSON",
        extensions=[".json"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    def _no_jsonc(p: Path) -> bool:  # typed matcher
        return False

    ft_jsonc: FileType = _ft(
        name="JSONC",
        extensions=[".json"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.IF_EXTENSION,
        content_matcher=_cm(_no_jsonc),
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"JSON": ft_json, "JSONC": ft_jsonc}
    )

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"JSON": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "JSON"


def test_resolve_gating_if_any_requires_content_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IF_ANY_NAME_RULE must require a content hit to include the candidate."""
    f: Path = tmp_path / "x.foo"
    f.write_text("payload\n", encoding="utf-8")

    def _miss(p: Path) -> bool:
        return False

    ft_any: FileType = _ft(
        name="AnyName",
        extensions=[".foo"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.IF_ANY_NAME_RULE,
        content_matcher=_cm(_miss),
        skip_processing=False,
    )
    # Provide a fallback that wins when AnyName is excluded
    ft_ext: FileType = _ft(
        name="ByExt",
        extensions=[".foo"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"AnyName": ft_any, "ByExt": ft_ext}
    )

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"ByExt": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ByExt"


def test_resolve_gating_if_none_allows_pure_content_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IF_NONE allows a pure content-based match with no name rules."""
    f: Path = tmp_path / "mystery"
    f.write_text("MAGIC\n", encoding="utf-8")

    def _hit(p: Path) -> bool:
        return True

    ft: FileType = _ft(
        name="Magic",
        extensions=[],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.IF_NONE,
        content_matcher=_cm(_hit),
        skip_processing=False,
    )

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"Magic": ft})

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"Magic": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "Magic"


def test_resolve_content_matcher_exception_is_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exceptions in content_matcher must be treated as misses, not failures."""
    f: Path = tmp_path / "x.foo"
    f.write_text("x\n", encoding="utf-8")

    def boom(_: Path) -> bool:
        raise RuntimeError("boom")

    ft_gate: FileType = _ft(
        name="Gate",
        extensions=[".foo"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.IF_EXTENSION,
        content_matcher=boom,
        skip_processing=False,
    )
    ft_fallback: FileType = _ft(
        name="Fallback",
        extensions=[".foo"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"Gate": ft_gate, "Fallback": ft_fallback}
    )

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"Fallback": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "Fallback"


def test_resolve_filename_tail_backslash_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Backslash tails must normalize to POSIX for filename-tail matching."""
    # Filename-tail rules use backslash->slash normalization; this test exercises that path.
    d: Path = tmp_path / ".vscode"
    d.mkdir()
    f: Path = d / "settings.json"
    f.write_text("{}\n", encoding="utf-8")

    ft: FileType = _ft(
        name="VSCode",
        extensions=[],
        filenames=[r".vscode\settings.json"],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"VSCode": ft})

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"VSCode": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "VSCode"


def test_resolve_multi_dot_extension_specificity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """More specific multi-dot extension must outrank a shorter suffix."""
    f: Path = tmp_path / "x.d.ts"
    f.write_text("declare const x: number;\n", encoding="utf-8")

    ft_ts: FileType = _ft(
        name="TS",
        extensions=[".ts"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )
    ft_dts: FileType = _ft(
        name="DTS",
        extensions=[".d.ts"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"TS": ft_ts, "DTS": ft_dts}
    )

    class _P:
        pass

    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", lambda: {"DTS": _P()})

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "DTS"


def test_resolve_skip_processing_overrides_registered_processor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """skip_processing=True must override even if a processor is registered."""
    f: Path = tmp_path / "doc.md"
    f.write_text("# md\n", encoding="utf-8")

    ft: FileType = _ft(
        name="Docs",
        extensions=[".md"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=True,
    )

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"Docs": ft})
    monkeypatch.setattr(
        resolver_mod, "get_header_processor_registry", lambda: _one_processor_registry("Docs")
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED
    assert ctx.header_processor is None


def test_resolve_empty_registry_means_unsupported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Empty file-type registry must yield SKIPPED_UNSUPPORTED."""
    f: Path = tmp_path / "anything.ext"
    f.write_text("x\n", encoding="utf-8")

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", _empty_filetype_registry)
    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", _empty_processor_registry)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)

    assert ctx.status.resolve is ResolveStatus.UNSUPPORTED
    assert ctx.file_type is None
    assert ctx.header_processor is None


# --- Additional resolver tests (stubs) ---


def test_resolve_filename_tail_beats_pattern(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When both filename-tail and pattern match, the filename-tail must win (higher score)."""
    f: Path = tmp_path / "config" / "app.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("{}\n", encoding="utf-8")

    ft_tail: FileType = _ft(
        name="ByTail",
        extensions=[],
        filenames=["config/app.json"],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )
    ft_pat: FileType = _ft(
        name="ByPat",
        extensions=[],
        filenames=[],
        patterns=[r".*\.json"],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"ByTail": ft_tail, "ByPat": ft_pat}
    )
    monkeypatch.setattr(
        resolver_mod, "get_header_processor_registry", lambda: _one_processor_registry("ByTail")
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ByTail"


def test_resolve_extension_case_sensitivity_current_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Extensions are currently case-sensitive: `.py` will not match `X.PY` (clarify contract)."""
    f: Path = tmp_path / "X.PY"
    f.write_text("print('hi')\n", encoding="utf-8")

    # Only a .py type is registered; uppercase filename should not match by extension.
    ft_py: FileType = _ft(
        name="python",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"python": ft_py})
    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", _empty_processor_registry)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    # With only the lowercase extension registered, expect unsupported or no-processor
    # on a different fallback.
    assert ctx.status.resolve in {
        ResolveStatus.UNSUPPORTED,
        ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED,
    }


def test_resolve_pattern_fullmatch_not_search(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r"""Resolver uses fullmatch for regex patterns.

    Example: `.*\.log` matches `file.log` but not `file.log.bak`.
    """
    f1: Path = tmp_path / "file.log"
    f1.write_text("log\n", encoding="utf-8")
    f2: Path = tmp_path / "file.log.bak"
    f2.write_text("bak\n", encoding="utf-8")

    ft_pat: FileType = _ft(
        name="ByPat",
        extensions=[],
        filenames=[],
        patterns=[r".*\.log"],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )
    ft_bak: FileType = _ft(
        name="ByBak",
        extensions=[".bak"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"ByPat": ft_pat, "ByBak": ft_bak}
    )
    monkeypatch.setattr(
        resolver_mod, "get_header_processor_registry", lambda: _one_processor_registry("ByPat")
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx1: ProcessingContext = ProcessingContext.bootstrap(path=f1, config=cfg)
    ctx1 = resolve(ctx1)
    assert ctx1.status.resolve == ResolveStatus.RESOLVED
    assert ctx1.file_type and ctx1.file_type.name == "ByPat"

    # For file.log.bak, fullmatch should fail and fallback to ByBak
    monkeypatch.setattr(
        resolver_mod, "get_header_processor_registry", lambda: _one_processor_registry("ByBak")
    )
    ctx2: ProcessingContext = ProcessingContext.bootstrap(path=f2, config=cfg)
    ctx2 = resolve(ctx2)
    assert ctx2.status.resolve == ResolveStatus.RESOLVED
    assert ctx2.file_type and ctx2.file_type.name == "ByBak"


def test_resolve_gating_if_pattern_requires_content_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IF_PATTERN: when a regex pattern matches but content matcher misses, exclude candidate."""
    f: Path = tmp_path / "metrics.prom"
    f.write_text("# HELP\n# TYPE\n", encoding="utf-8")

    def _miss(_: Path) -> bool:
        return False

    ft_pat: FileType = _ft(
        name="ByPat",
        extensions=[],
        filenames=[],
        patterns=[r".*\.prom"],
        content_gate=ContentGate.IF_PATTERN,
        content_matcher=_cm(_miss),
        skip_processing=False,
    )
    ft_fallback: FileType = _ft(
        name="Text",
        extensions=[".prom"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"ByPat": ft_pat, "Text": ft_fallback}
    )
    monkeypatch.setattr(
        resolver_mod, "get_header_processor_registry", lambda: _one_processor_registry("Text")
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "Text"


def test_resolve_gating_if_filename_requires_content_hit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """IF_FILENAME: when a filename-tail matches but content matcher misses, exclude candidate."""
    f: Path = tmp_path / "configs" / "service.yaml"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("k: v\n", encoding="utf-8")

    def _miss(_: Path) -> bool:
        return False

    ft_fname: FileType = _ft(
        name="ByTail",
        extensions=[],
        filenames=["configs/service.yaml"],
        patterns=[],
        content_gate=ContentGate.IF_FILENAME,
        content_matcher=_cm(_miss),
        skip_processing=False,
    )
    ft_fallback: FileType = _ft(
        name="YAML",
        extensions=[".yaml"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(
        resolver_mod, "get_file_type_registry", lambda: {"ByTail": ft_fname, "YAML": ft_fallback}
    )
    monkeypatch.setattr(
        resolver_mod, "get_header_processor_registry", lambda: _one_processor_registry("YAML")
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "YAML"


def test_resolve_content_only_with_always_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ALWAYS gate: a type with no name rules can be selected solely by content matcher."""
    f: Path = tmp_path / "mystery.bin"
    f.write_text("MAGIC\n", encoding="utf-8")

    def _hit(_: Path) -> bool:
        return True

    ft_magic: FileType = _ft(
        name="Magic",
        extensions=[],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.ALWAYS,
        content_matcher=_cm(_hit),
        skip_processing=False,
    )

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"Magic": ft_magic})
    monkeypatch.setattr(resolver_mod, "get_header_processor_registry", _empty_processor_registry)

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.file_type and ctx.file_type.name == "Magic"
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED


def test_resolve_tie_with_both_processors_uses_name_asc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With equal scores and processors for both, resolver picks lexicographically smaller name."""
    f: Path = tmp_path / "x.data"
    f.write_text("x\n", encoding="utf-8")

    ftA: FileType = _ft(
        name="Alpha",
        extensions=[".data"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )
    ftB: FileType = _ft(
        name="Beta",
        extensions=[".data"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"Alpha": ftA, "Beta": ftB})
    monkeypatch.setattr(
        resolver_mod, "get_header_processor_registry", lambda: _one_processor_registry("Alpha")
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "Alpha"


def test_resolve_processor_registry_name_mismatch_leads_to_skip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If processor registry key differs from FileType.name, resolver must skip (no processor)."""
    f: Path = tmp_path / "x.py"
    f.write_text("print(1)\n", encoding="utf-8")

    ft_py: FileType = _ft(
        name="Python",
        extensions=[".py"],
        filenames=[],
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    # Processor registered under a different key; should not be found.
    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"Python": ft_py})
    monkeypatch.setattr(
        resolver_mod, "get_header_processor_registry", lambda: _one_processor_registry("python")
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
    assert ctx.file_type and ctx.file_type.name == "Python"


def test_resolve_deep_filename_tail_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Filename-tail rules with nested paths must match after backslash->slash normalization."""
    d: resolver_mod.Path = tmp_path / "a" / "b" / ".config" / "tool"
    d.mkdir(parents=True, exist_ok=True)
    f: Path = d / "settings.json"
    f.write_text("{}\n", encoding="utf-8")

    ft: FileType = _ft(
        name="ToolCfg",
        extensions=[],
        filenames=[r".config\tool/settings.json"],  # backslash in declared tail
        patterns=[],
        content_gate=ContentGate.NEVER,
        content_matcher=None,
        skip_processing=False,
    )

    monkeypatch.setattr(resolver_mod, "get_file_type_registry", lambda: {"ToolCfg": ft})
    monkeypatch.setattr(
        resolver_mod, "get_header_processor_registry", lambda: _one_processor_registry("ToolCfg")
    )

    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx: ProcessingContext = ProcessingContext.bootstrap(path=f, config=cfg)
    ctx = resolve(ctx)
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ToolCfg"
