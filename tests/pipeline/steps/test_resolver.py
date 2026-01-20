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

Each test overrides the effective registries to remain
fully deterministic and independent of the built-in definitions.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.conftest import EffectiveRegistries, make_file_type
from tests.pipeline.conftest import make_pipeline_context, run_resolver
from topmark.config import Config, MutableConfig
from topmark.filetypes.base import (
    ContentGate,
    FileType,  # runtime import for typing/cast correctness
)
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.processors.base import HeaderProcessor
from topmark.pipeline.status import ResolveStatus

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from topmark.pipeline.context.model import ProcessingContext


# Convenience to annotate content matcher callables
def _cm(fn: Callable[[Path], bool]) -> Callable[[Path], bool]:
    return fn


# Helper to run resolver under deterministic registries using the fixture
def _resolve(
    file: Path,
    *,
    filetypes: Mapping[str, FileType],
    processors: Mapping[str, HeaderProcessor],
    effective_registries: EffectiveRegistries,
    cfg: Config | None = None,
) -> ProcessingContext:
    """Run the resolver step for a single file under deterministic registries."""
    with effective_registries(filetypes, processors):
        cfg_final: Config = cfg or MutableConfig.from_defaults().freeze()
        ctx: ProcessingContext = make_pipeline_context(file, cfg_final)
        return run_resolver(ctx)


def test_resolve_python_file_resolves_with_processor(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """A simple Python file should resolve to a supported file type with a processor."""
    content: str = "print('Hi!')\n"
    file: Path = tmp_path / "x.py"
    # Use newline="" so Python preserves the exact line endings we provide.
    with file.open("w", encoding="utf-8", newline="") as fh:
        fh.write(content)

    # Deterministic registries: one Python FileType and a dummy processor for it
    py_ft: FileType = make_file_type(
        name="python",
        extensions=[".py"],
    )

    filetypes: dict[str, FileType] = {"python": py_ft}
    processors: dict[str, HeaderProcessor] = {"python": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )

    assert ctx.status.resolve == ResolveStatus.RESOLVED

    # The resolver must identify a processor; otherwise the reader step would be ill-defined.
    assert ctx.file_type is not None
    assert ctx.file_type.name == "python"
    assert ctx.header_processor is not None


# --- Additional targeted resolver tests ---


def test_resolve_unknown_extension_marked_unsupported(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Files with no matching FileType must be marked SKIPPED_UNSUPPORTED."""
    file: Path = tmp_path / "mystery.weirdext"
    file.write_text("just text\n", encoding="utf-8")

    filetypes: dict[str, FileType] = {}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.UNSUPPORTED
    assert ctx.file_type is None
    assert ctx.header_processor is None


def test_resolve_sets_skip_when_no_processor_registered(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """When FileType matches without registered processor, resolver must skip with warning.

    This relates to known file types which are not (yet) supported by a header processor.
    """
    file: Path = tmp_path / "x.py"
    file.write_text("print('hi')\n", encoding="utf-8")

    # Monkeypatch the processor registry to be empty to force the no-processor path.
    py_ft: FileType = make_file_type(
        name="python",
        extensions=[".py"],
    )

    filetypes: dict[str, FileType] = {"python": py_ft}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    # Should match a FileType (Python) but have no processor
    assert ctx.file_type is not None
    assert ctx.header_processor is None
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED


def test_resolve_respects_skip_processing_filetype(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Resolver must set SKIPPED_KNOWN_NO_HEADERS when FileType.skip_processing is True."""
    # Create a contrived file that will match our custom FileType by extension.
    file: Path = tmp_path / "readme.md"
    file.write_text("# docs\n", encoding="utf-8")

    # Build a minimal duck-typed FileType with skip_processing=True
    ft: FileType = make_file_type(
        name="Docs",
        extensions=[".md"],
        skip_processing=True,
    )

    # Monkeypatch the file type and processor registries to use our custom type only.
    filetypes: dict[str, FileType] = {"Docs": ft}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.file_type is not None and ctx.file_type.name == "Docs"
    assert ctx.header_processor is None
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED


def test_resolve_can_use_content_gate_when_allowed(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Resolver may select a FileType via content_matcher when ContentGate.ALWAYS is set."""
    file: Path = tmp_path / "mystery.bin"
    file.write_text("MAGIC_SIGNATURE\n", encoding="utf-8")

    def _content_hit(p: Path) -> bool:
        try:
            return "MAGIC_SIGNATURE" in p.read_text(encoding="utf-8")
        except Exception:
            return False

    ft: FileType = make_file_type(
        name="Magic",
        content_gate=ContentGate.ALWAYS,
        content_matcher=_content_hit,
    )

    filetypes: dict[str, FileType] = {"Magic": ft}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.file_type is not None and ctx.file_type.name == "Magic"
    assert ctx.header_processor is None
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED


def test_resolve_deterministic_name_tiebreak(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Two equal-score candidates must resolve deterministically by name (ASC)."""
    file: Path = tmp_path / "x.foo"
    file.write_text("data\n", encoding="utf-8")

    ftA: FileType = make_file_type(
        name="AJson",
        extensions=[".foo"],
    )
    ftB: FileType = make_file_type(
        name="BJson",
        extensions=[".foo"],
    )

    filetypes: dict[str, FileType] = {"AJson": ftA, "BJson": ftB}

    processors: dict[str, HeaderProcessor] = {"AJson": HeaderProcessor()}

    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "AJson"  # name ASC
    assert ctx.header_processor is not None


def test_resolve_filename_tail_beats_extension(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Filename-tail match must outrank a pure extension match."""
    file: Path = tmp_path / "app.conf.example"
    file.write_text("cfg\n", encoding="utf-8")

    ft_ext: FileType = make_file_type(
        name="ByExt",
        extensions=[".conf"],
    )
    ft_tail: FileType = make_file_type(
        name="ByTail",
        filenames=["app.conf.example"],
    )

    filetypes: dict[str, FileType] = {"ByExt": ft_ext, "ByTail": ft_tail}
    processors: dict[str, HeaderProcessor] = {"ByTail": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ByTail"


def test_resolve_pattern_beats_extension(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Regex pattern must outrank a pure extension match."""
    file: Path = tmp_path / "service.special.log"
    file.write_text("lines\n", encoding="utf-8")

    ft_ext: FileType = make_file_type(
        name="ByExt",
        extensions=[".log"],
    )
    ft_pat: FileType = make_file_type(
        name="ByPat",
        patterns=[r".*\.special\.log"],
    )

    filetypes: dict[str, FileType] = {"ByExt": ft_ext, "ByPat": ft_pat}
    processors: dict[str, HeaderProcessor] = {"ByPat": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ByPat"


def test_resolve_content_upgrade_over_extension(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Content upgrade (e.g. JSONC) must outrank a plain extension match."""
    file: Path = tmp_path / "x.json"
    file.write_text('// comment\n{ "k": 1 }\n', encoding="utf-8")

    def hits_jsonc(p: Path) -> bool:
        return p.read_text(encoding="utf-8").lstrip().startswith("//")

    ft_json: FileType = make_file_type(
        name="JSON",
        extensions=[".json"],
    )
    ft_jsonc: FileType = make_file_type(
        name="JSONC",
        extensions=[".json"],
        content_gate=ContentGate.IF_EXTENSION,
        content_matcher=hits_jsonc,
    )

    filetypes: dict[str, FileType] = {"JSON": ft_json, "JSONC": ft_jsonc}
    processors: dict[str, HeaderProcessor] = {"JSONC": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "JSONC"


def test_resolve_gating_if_extension_excludes_when_miss(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_EXTENSION gate must exclude when content matcher misses."""
    file: Path = tmp_path / "x.json"
    file.write_text('{"k": 1}\n', encoding="utf-8")

    ft_json: FileType = make_file_type(
        name="JSON",
        extensions=[".json"],
    )

    def _no_jsonc(p: Path) -> bool:  # typed matcher
        return False

    ft_jsonc: FileType = make_file_type(
        name="JSONC",
        extensions=[".json"],
        content_gate=ContentGate.IF_EXTENSION,
        content_matcher=_cm(_no_jsonc),
    )

    filetypes: dict[str, FileType] = {"JSON": ft_json, "JSONC": ft_jsonc}
    processors: dict[str, HeaderProcessor] = {"JSON": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "JSON"


def test_resolve_gating_if_any_requires_content_hit(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_ANY_NAME_RULE must require a content hit to include the candidate."""
    file: Path = tmp_path / "x.foo"
    file.write_text("payload\n", encoding="utf-8")

    def _miss(p: Path) -> bool:
        return False

    ft_any: FileType = make_file_type(
        name="AnyName",
        extensions=[".foo"],
        content_gate=ContentGate.IF_ANY_NAME_RULE,
        content_matcher=_cm(_miss),
    )
    # Provide a fallback that wins when AnyName is excluded
    ft_ext: FileType = make_file_type(
        name="ByExt",
        extensions=[".foo"],
    )

    filetypes: dict[str, FileType] = {"AnyName": ft_any, "ByExt": ft_ext}
    processors: dict[str, HeaderProcessor] = {"ByExt": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ByExt"


def test_resolve_gating_if_none_allows_pure_content_match(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_NONE allows a pure content-based match with no name rules."""
    file: Path = tmp_path / "mystery"
    file.write_text("MAGIC\n", encoding="utf-8")

    def _hit(p: Path) -> bool:
        return True

    ft: FileType = make_file_type(
        name="Magic",
        content_gate=ContentGate.IF_NONE,
        content_matcher=_cm(_hit),
    )

    filetypes: dict[str, FileType] = {"Magic": ft}
    processors: dict[str, HeaderProcessor] = {"Magic": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "Magic"


def test_resolve_content_matcher_exception_is_safe(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Exceptions in content_matcher must be treated as misses, not failures."""
    file: Path = tmp_path / "x.foo"
    file.write_text("x\n", encoding="utf-8")

    def boom(_: Path) -> bool:
        raise RuntimeError("boom")

    ft_gate: FileType = make_file_type(
        name="Gate",
        extensions=[".foo"],
        content_gate=ContentGate.IF_EXTENSION,
        content_matcher=boom,
    )
    ft_fallback: FileType = make_file_type(
        name="Fallback",
        extensions=[".foo"],
    )

    filetypes: dict[str, FileType] = {"Gate": ft_gate, "Fallback": ft_fallback}
    processors: dict[str, HeaderProcessor] = {"Fallback": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "Fallback"


def test_resolve_filename_tail_backslash_normalization(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Backslash tails must normalize to POSIX for filename-tail matching."""
    # Filename-tail rules use backslash->slash normalization; this test exercises that path.
    folder: Path = tmp_path / ".vscode"
    folder.mkdir()
    file: Path = folder / "settings.json"
    file.write_text("{}\n", encoding="utf-8")

    ft: FileType = make_file_type(
        name="VSCode",
        filenames=[r".vscode\settings.json"],
    )

    filetypes: dict[str, FileType] = {"VSCode": ft}
    processors: dict[str, HeaderProcessor] = {"VSCode": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "VSCode"


def test_resolve_multi_dot_extension_specificity(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """More specific multi-dot extension must outrank a shorter suffix."""
    file: Path = tmp_path / "x.d.ts"
    file.write_text("declare const x: number;\n", encoding="utf-8")

    ft_ts: FileType = make_file_type(
        name="TS",
        extensions=[".ts"],
    )
    ft_dts: FileType = make_file_type(
        name="DTS",
        extensions=[".d.ts"],
    )

    filetypes: dict[str, FileType] = {"TS": ft_ts, "DTS": ft_dts}
    processors: dict[str, HeaderProcessor] = {"DTS": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "DTS"


def test_resolve_skip_processing_overrides_registered_processor(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """skip_processing=True must override even if a processor is registered."""
    file: Path = tmp_path / "doc.md"
    file.write_text("# md\n", encoding="utf-8")

    ft: FileType = make_file_type(
        name="Docs",
        extensions=[".md"],
        skip_processing=True,
    )

    filetypes: dict[str, FileType] = {"Docs": ft}
    processors: dict[str, HeaderProcessor] = {"Docs": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED
    assert ctx.header_processor is None


def test_resolve_empty_registry_means_unsupported(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Empty file-type registry must yield SKIPPED_UNSUPPORTED."""
    file: Path = tmp_path / "anything.ext"
    file.write_text("x\n", encoding="utf-8")

    filetypes: dict[str, FileType] = {}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve is ResolveStatus.UNSUPPORTED
    assert ctx.file_type is None
    assert ctx.header_processor is None


# --- Additional resolver tests (stubs) ---


def test_resolve_filename_tail_beats_pattern(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """When both filename-tail and pattern match, the filename-tail must win (higher score)."""
    file: Path = tmp_path / "config" / "app.json"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("{}\n", encoding="utf-8")

    ft_tail: FileType = make_file_type(
        name="ByTail",
        filenames=["config/app.json"],
    )
    ft_pat: FileType = make_file_type(
        name="ByPat",
        patterns=[r".*\.json"],
    )

    filetypes: dict[str, FileType] = {"ByTail": ft_tail, "ByPat": ft_pat}
    processors: dict[str, HeaderProcessor] = {"ByTail": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ByTail"


def test_resolve_extension_case_sensitivity_current_contract(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Extensions are currently case-sensitive: `.py` will not match `X.PY` (clarify contract)."""
    file: Path = tmp_path / "X.PY"
    file.write_text("print('hi')\n", encoding="utf-8")

    # Only a .py type is registered; uppercase filename should not match by extension.
    ft_py: FileType = make_file_type(
        name="python",
        extensions=[".py"],
    )

    filetypes: dict[str, FileType] = {"python": ft_py}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    # With only the lowercase extension registered, expect unsupported or no-processor
    # on a different fallback.
    assert ctx.status.resolve in {
        ResolveStatus.UNSUPPORTED,
        ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED,
    }


def test_resolve_pattern_fullmatch_not_search(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    r"""Resolver uses fullmatch for regex patterns.

    Example: `.*\.log` matches `file.log` but not `file.log.bak`.
    """
    file1: Path = tmp_path / "file.log"
    file1.write_text("log\n", encoding="utf-8")
    file2: Path = tmp_path / "file.log.bak"
    file2.write_text("bak\n", encoding="utf-8")

    ft_pat: FileType = make_file_type(
        name="ByPat",
        patterns=[r".*\.log"],
    )
    ft_bak: FileType = make_file_type(
        name="ByBak",
        extensions=[".bak"],
    )

    filetypes: dict[str, FileType] = {"ByPat": ft_pat, "ByBak": ft_bak}
    processors1: dict[str, HeaderProcessor] = {"ByPat": HeaderProcessor()}
    processors2: dict[str, HeaderProcessor] = {"ByBak": HeaderProcessor()}
    cfg: Config = MutableConfig.from_defaults().freeze()
    ctx1: ProcessingContext = _resolve(
        file1,
        filetypes=filetypes,
        processors=processors1,
        effective_registries=effective_registries,
        cfg=cfg,
    )
    assert ctx1.status.resolve == ResolveStatus.RESOLVED
    assert ctx1.file_type and ctx1.file_type.name == "ByPat"

    # For file.log.bak, fullmatch should fail and fallback to ByBak
    ctx2: ProcessingContext = _resolve(
        file2,
        filetypes=filetypes,
        processors=processors2,
        effective_registries=effective_registries,
        cfg=cfg,
    )
    assert ctx2.status.resolve == ResolveStatus.RESOLVED
    assert ctx2.file_type and ctx2.file_type.name == "ByBak"


def test_resolve_gating_if_pattern_requires_content_hit(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_PATTERN: when a regex pattern matches but content matcher misses, exclude candidate."""
    file: Path = tmp_path / "metrics.prom"
    file.write_text("# HELP\n# TYPE\n", encoding="utf-8")

    def _miss(_: Path) -> bool:
        return False

    ft_pat: FileType = make_file_type(
        name="ByPat",
        patterns=[r".*\.prom"],
        content_gate=ContentGate.IF_PATTERN,
        content_matcher=_cm(_miss),
    )
    ft_fallback: FileType = make_file_type(
        name="Text",
        extensions=[".prom"],
    )

    filetypes: dict[str, FileType] = {"ByPat": ft_pat, "Text": ft_fallback}
    processors: dict[str, HeaderProcessor] = {"Text": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "Text"


def test_resolve_gating_if_filename_requires_content_hit(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_FILENAME: when a filename-tail matches but content matcher misses, exclude candidate."""
    file: Path = tmp_path / "configs" / "service.yaml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("k: v\n", encoding="utf-8")

    def _miss(_: Path) -> bool:
        return False

    ft_fname: FileType = make_file_type(
        name="ByTail",
        filenames=["configs/service.yaml"],
        content_gate=ContentGate.IF_FILENAME,
        content_matcher=_cm(_miss),
    )
    ft_fallback: FileType = make_file_type(
        name="YAML",
        extensions=[".yaml"],
    )

    filetypes: dict[str, FileType] = {"ByTail": ft_fname, "YAML": ft_fallback}
    processors: dict[str, HeaderProcessor] = {"YAML": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "YAML"


def test_resolve_content_only_with_always_gate(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """ALWAYS gate: a type with no name rules can be selected solely by content matcher."""
    file: Path = tmp_path / "mystery.bin"
    file.write_text("MAGIC\n", encoding="utf-8")

    def _hit(_: Path) -> bool:
        return True

    ft_magic: FileType = make_file_type(
        name="Magic",
        content_gate=ContentGate.ALWAYS,
        content_matcher=_cm(_hit),
    )

    filetypes: dict[str, FileType] = {"Magic": ft_magic}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.file_type and ctx.file_type.name == "Magic"
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED


def test_resolve_tie_with_both_processors_uses_name_asc(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """With equal scores and processors for both, resolver picks lexicographically smaller name."""
    file: Path = tmp_path / "x.data"
    file.write_text("x\n", encoding="utf-8")

    ftA: FileType = make_file_type(
        name="Alpha",
        extensions=[".data"],
    )
    ftB: FileType = make_file_type(
        name="Beta",
        extensions=[".data"],
    )

    filetypes: dict[str, FileType] = {"Alpha": ftA, "Beta": ftB}
    processors: dict[str, HeaderProcessor] = {"Alpha": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "Alpha"


def test_resolve_processor_registry_name_mismatch_leads_to_skip(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """If processor registry key differs from FileType.name, resolver must skip (no processor)."""
    file: Path = tmp_path / "x.py"
    file.write_text("print(1)\n", encoding="utf-8")

    ft_py: FileType = make_file_type(
        name="Python",
        extensions=[".py"],
    )

    # Processor registered under a different key; should not be found.
    filetypes: dict[str, FileType] = {"Python": ft_py}
    processors: dict[str, HeaderProcessor] = {"python": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
    assert ctx.file_type and ctx.file_type.name == "Python"


def test_resolve_deep_filename_tail_normalization(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Filename-tail rules with nested paths must match after backslash->slash normalization."""
    folder: Path = tmp_path / "a" / "b" / ".config" / "tool"
    folder.mkdir(parents=True, exist_ok=True)
    file: Path = folder / "settings.json"
    file.write_text("{}\n", encoding="utf-8")

    ft: FileType = make_file_type(
        name="ToolCfg",
        filenames=[r".config\tool/settings.json"],  # backslash in declared tail
    )

    filetypes: dict[str, FileType] = {"ToolCfg": ft}
    processors: dict[str, HeaderProcessor] = {"ToolCfg": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.name == "ToolCfg"
