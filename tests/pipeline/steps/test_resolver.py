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

from pathlib import Path
from typing import TYPE_CHECKING

from tests.conftest import EffectiveRegistries
from tests.conftest import make_file_type
from tests.pipeline.conftest import make_pipeline_context
from tests.pipeline.conftest import run_resolver
from topmark.config.io.deserializers import mutable_config_from_defaults
from topmark.filetypes.model import ContentGate
from topmark.filetypes.model import FileType
from topmark.pipeline.context.model import ProcessingContext
from topmark.pipeline.status import ResolveStatus
from topmark.processors.base import HeaderProcessor

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

    from topmark.config.model import Config
    from topmark.pipeline.context.model import ProcessingContext
    from topmark.registry.types import ProcessorDefinition


class _ContentHitMatcher:
    def __call__(self, path: Path) -> bool:
        try:
            return "MAGIC_SIGNATURE" in path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return False


class _HitsJsoncMatcher:
    def __call__(self, path: Path) -> bool:
        return path.read_text(encoding="utf-8").lstrip().startswith("//")


class _AlwaysTrueContentMatcher:
    def __call__(self, path: Path) -> bool:
        _: Path = path
        return True


class _AlwaysFalseContentMatcher:
    def __call__(self, path: Path) -> bool:
        _: Path = path
        return False


class _AlwaysRuntimeContentMatcher:
    def __call__(self, path: Path) -> bool:
        raise RuntimeError("boom")


# Helper to run resolver under deterministic registries using the fixture
def _resolve(
    file: Path,
    *,
    filetypes: Mapping[str, FileType],
    processors: Mapping[str, HeaderProcessor | ProcessorDefinition],
    effective_registries: EffectiveRegistries,
    cfg: Config | None = None,
) -> ProcessingContext:
    """Run the resolver step for a single file under deterministic registries."""
    with effective_registries(filetypes, processors):
        cfg_final: Config = cfg or mutable_config_from_defaults().freeze()
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
        local_key="python",
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
    assert ctx.file_type.local_key == "python"
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
        local_key="python",
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

    # Build a FileType with skip_processing=True
    ft_name = "docs"
    ft: FileType = make_file_type(
        local_key=ft_name,
        extensions=[".md"],
        skip_processing=True,
    )

    # Monkeypatch the file type and processor registries to use our custom type only.
    filetypes: dict[str, FileType] = {ft_name: ft}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.file_type is not None and ctx.file_type.local_key == ft_name
    assert ctx.header_processor is None
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_HEADERS_UNSUPPORTED


def test_resolve_can_use_content_gate_when_allowed(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Resolver may select a FileType via content_matcher when ContentGate.ALWAYS is set."""
    file: Path = tmp_path / "mystery.bin"
    file.write_text("MAGIC_SIGNATURE\n", encoding="utf-8")

    ft_magic_name = "magic"
    ft_magic: FileType = make_file_type(
        local_key=ft_magic_name,
        content_gate=ContentGate.ALWAYS,
        content_matcher=_ContentHitMatcher(),
    )

    filetypes: dict[str, FileType] = {ft_magic_name: ft_magic}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.file_type is not None and ctx.file_type.local_key == ft_magic_name
    assert ctx.header_processor is None
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED


def test_resolve_deterministic_name_tiebreak(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Two equal-score candidates must resolve deterministically by name (ASC)."""
    file: Path = tmp_path / "x.foo"
    file.write_text("data\n", encoding="utf-8")

    ft_ajson_name = "ajson"
    ftA: FileType = make_file_type(
        local_key=ft_ajson_name,
        extensions=[".foo"],
    )
    ft_bjson_name = "ajson"
    ftB: FileType = make_file_type(
        local_key=ft_bjson_name,
        extensions=[".foo"],
    )

    filetypes: dict[str, FileType] = {ft_ajson_name: ftA, ft_bjson_name: ftB}

    processors: dict[str, HeaderProcessor] = {ft_ajson_name: HeaderProcessor()}

    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_ajson_name  # name ASC
    assert ctx.header_processor is not None


def test_resolve_filename_tail_beats_extension(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Filename-tail match must outrank a pure extension match."""
    file: Path = tmp_path / "app.conf.example"
    file.write_text("cfg\n", encoding="utf-8")

    ft_ext_name = "by-ext"
    ft_ext: FileType = make_file_type(
        local_key=ft_ext_name,
        extensions=[".conf"],
    )

    ft_tail_name = "by-tail"
    ft_tail: FileType = make_file_type(
        local_key=ft_tail_name,
        filenames=["app.conf.example"],
    )

    filetypes: dict[str, FileType] = {ft_ext_name: ft_ext, ft_tail_name: ft_tail}
    processors: dict[str, HeaderProcessor] = {ft_tail_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_tail_name


def test_resolve_pattern_beats_extension(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Regex pattern must outrank a pure extension match."""
    file: Path = tmp_path / "service.special.log"
    file.write_text("lines\n", encoding="utf-8")

    ft_ext_name = "by-ext"
    ft_ext: FileType = make_file_type(
        local_key=ft_ext_name,
        extensions=[".log"],
    )

    ft_pat_name = "by-pat"
    ft_pat: FileType = make_file_type(
        local_key=ft_pat_name,
        patterns=[r".*\.special\.log"],
    )

    filetypes: dict[str, FileType] = {ft_ext_name: ft_ext, ft_pat_name: ft_pat}
    processors: dict[str, HeaderProcessor] = {ft_pat_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_pat_name


def test_resolve_content_upgrade_over_extension(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Content upgrade (e.g. JSONC) must outrank a plain extension match."""
    file: Path = tmp_path / "x.json"
    file.write_text('// comment\n{ "k": 1 }\n', encoding="utf-8")

    ft_json_name = "json"
    ft_json: FileType = make_file_type(
        local_key=ft_json_name,
        extensions=[".json"],
    )

    ft_jsonc_name = "jsonc"
    ft_jsonc: FileType = make_file_type(
        local_key=ft_jsonc_name,
        extensions=[".json"],
        content_gate=ContentGate.IF_EXTENSION,
        content_matcher=_HitsJsoncMatcher(),
    )

    filetypes: dict[str, FileType] = {ft_json_name: ft_json, ft_jsonc_name: ft_jsonc}
    processors: dict[str, HeaderProcessor] = {ft_jsonc_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_jsonc_name


def test_resolve_gating_if_extension_excludes_when_miss(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_EXTENSION gate must exclude when content matcher misses."""
    file: Path = tmp_path / "x.json"
    file.write_text('{"k": 1}\n', encoding="utf-8")

    ft_json_name = "json"
    ft_json: FileType = make_file_type(
        local_key=ft_json_name,
        extensions=[".json"],
    )

    ft_jsonc_name = "jsonc"
    ft_jsonc: FileType = make_file_type(
        local_key=ft_jsonc_name,
        extensions=[".json"],
        content_gate=ContentGate.IF_EXTENSION,
        content_matcher=_AlwaysFalseContentMatcher(),
    )

    filetypes: dict[str, FileType] = {ft_json_name: ft_json, ft_jsonc_name: ft_jsonc}
    processors: dict[str, HeaderProcessor] = {ft_json_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_json_name


def test_resolve_gating_if_any_requires_content_hit(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_ANY_NAME_RULE must require a content hit to include the candidate."""
    file: Path = tmp_path / "x.foo"
    file.write_text("payload\n", encoding="utf-8")

    ft_any_name = "any_name"
    ft_any: FileType = make_file_type(
        local_key=ft_any_name,
        extensions=[".foo"],
        content_gate=ContentGate.IF_ANY_NAME_RULE,
        content_matcher=_AlwaysFalseContentMatcher(),
    )
    # Provide a fallback that wins when AnyName is excluded
    ft_ext_name = "by-ext"
    ft_ext: FileType = make_file_type(
        local_key=ft_ext_name,
        extensions=[".foo"],
    )

    filetypes: dict[str, FileType] = {ft_any_name: ft_any, ft_ext_name: ft_ext}
    processors: dict[str, HeaderProcessor] = {ft_ext_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_ext_name


def test_resolve_gating_if_none_allows_pure_content_match(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_NONE allows a pure content-based match with no name rules."""
    file: Path = tmp_path / "mystery"
    file.write_text("MAGIC\n", encoding="utf-8")

    ft_magic_name = "magic"
    ft_magic: FileType = make_file_type(
        local_key=ft_magic_name,
        content_gate=ContentGate.IF_NONE,
        content_matcher=_AlwaysTrueContentMatcher(),
    )

    filetypes: dict[str, FileType] = {ft_magic_name: ft_magic}
    processors: dict[str, HeaderProcessor] = {ft_magic_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_magic_name


def test_resolve_content_matcher_exception_is_safe(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Exceptions in content_matcher must be treated as misses, not failures."""
    file: Path = tmp_path / "x.foo"
    file.write_text("x\n", encoding="utf-8")

    ft_gate_name = "gate"
    ft_gate: FileType = make_file_type(
        local_key=ft_gate_name,
        extensions=[".foo"],
        content_gate=ContentGate.IF_EXTENSION,
        content_matcher=_AlwaysRuntimeContentMatcher(),
    )

    ft_fallback_name = "fallback"
    ft_fallback: FileType = make_file_type(
        local_key=ft_fallback_name,
        extensions=[".foo"],
    )

    filetypes: dict[str, FileType] = {ft_gate_name: ft_gate, ft_fallback_name: ft_fallback}
    processors: dict[str, HeaderProcessor] = {ft_fallback_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_fallback_name


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

    ft_vscode_name = "vscode"
    ft: FileType = make_file_type(
        local_key=ft_vscode_name,
        filenames=[r".vscode\settings.json"],
    )

    filetypes: dict[str, FileType] = {ft_vscode_name: ft}
    processors: dict[str, HeaderProcessor] = {ft_vscode_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_vscode_name


def test_resolve_multi_dot_extension_specificity(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """More specific multi-dot extension must outrank a shorter suffix."""
    file: Path = tmp_path / "x.d.ts"
    file.write_text("declare const x: number;\n", encoding="utf-8")

    ft_ts_name = "ts"
    ft_ts: FileType = make_file_type(
        local_key=ft_ts_name,
        extensions=[".ts"],
    )
    ft_dts_name = "dts"
    ft_dts: FileType = make_file_type(
        local_key=ft_dts_name,
        extensions=[".d.ts"],
    )

    filetypes: dict[str, FileType] = {ft_ts_name: ft_ts, ft_dts_name: ft_dts}
    processors: dict[str, HeaderProcessor] = {ft_dts_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_dts_name


def test_resolve_skip_processing_overrides_registered_processor(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """skip_processing=True must override even if a processor is registered."""
    file: Path = tmp_path / "doc.md"
    file.write_text("# md\n", encoding="utf-8")

    # Build a FileType with skip_processing=True
    ft_name = "docs"
    ft: FileType = make_file_type(
        local_key=ft_name,
        extensions=[".md"],
        skip_processing=True,
    )

    filetypes: dict[str, FileType] = {ft_name: ft}
    processors: dict[str, HeaderProcessor] = {ft_name: HeaderProcessor()}
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

    ft_tail_name = "by-tail"
    ft_tail: FileType = make_file_type(
        local_key=ft_tail_name,
        filenames=["config/app.json"],
    )

    ft_pat_name = "by-pat"
    ft_pat: FileType = make_file_type(
        local_key=ft_pat_name,
        patterns=[r".*\.json"],
    )

    filetypes: dict[str, FileType] = {ft_tail_name: ft_tail, ft_pat_name: ft_pat}
    processors: dict[str, HeaderProcessor] = {ft_tail_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_tail_name


def test_resolve_extension_case_sensitivity_current_contract(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Extensions are currently case-sensitive: `.py` will not match `X.PY` (clarify contract)."""
    file: Path = tmp_path / "X.PY"
    file.write_text("print('hi')\n", encoding="utf-8")

    # Only a .py type is registered; uppercase filename should not match by extension.
    ft_py: FileType = make_file_type(
        local_key="python",
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

    ft_pat_name = "by-pat"
    ft_pat: FileType = make_file_type(
        local_key=ft_pat_name,
        patterns=[r".*\.log"],
    )

    ft_bak_name = "by-bak"
    ft_bak: FileType = make_file_type(
        local_key=ft_bak_name,
        extensions=[".bak"],
    )

    filetypes: dict[str, FileType] = {ft_pat_name: ft_pat, ft_bak_name: ft_bak}
    processors1: dict[str, HeaderProcessor] = {ft_pat_name: HeaderProcessor()}
    processors2: dict[str, HeaderProcessor] = {ft_bak_name: HeaderProcessor()}
    cfg: Config = mutable_config_from_defaults().freeze()
    ctx1: ProcessingContext = _resolve(
        file1,
        filetypes=filetypes,
        processors=processors1,
        effective_registries=effective_registries,
        cfg=cfg,
    )
    assert ctx1.status.resolve == ResolveStatus.RESOLVED
    assert ctx1.file_type and ctx1.file_type.local_key == ft_pat_name

    # For file.log.bak, fullmatch should fail and fallback to ByBak
    ctx2: ProcessingContext = _resolve(
        file2,
        filetypes=filetypes,
        processors=processors2,
        effective_registries=effective_registries,
        cfg=cfg,
    )
    assert ctx2.status.resolve == ResolveStatus.RESOLVED
    assert ctx2.file_type and ctx2.file_type.local_key == ft_bak_name


def test_resolve_gating_if_pattern_requires_content_hit(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_PATTERN: when a regex pattern matches but content matcher misses, exclude candidate."""
    file: Path = tmp_path / "metrics.prom"
    file.write_text("# HELP\n# TYPE\n", encoding="utf-8")

    ft_pat_name = "by-pat"
    ft_pat: FileType = make_file_type(
        local_key=ft_pat_name,
        patterns=[r".*\.prom"],
        content_gate=ContentGate.IF_PATTERN,
        content_matcher=_AlwaysFalseContentMatcher(),
    )

    ft_text_name = "text"
    ft_fallback: FileType = make_file_type(
        local_key=ft_text_name,
        extensions=[".prom"],
    )

    filetypes: dict[str, FileType] = {ft_pat_name: ft_pat, ft_text_name: ft_fallback}
    processors: dict[str, HeaderProcessor] = {ft_text_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_text_name


def test_resolve_gating_if_filename_requires_content_hit(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """IF_FILENAME: when a filename-tail matches but content matcher misses, exclude candidate."""
    file: Path = tmp_path / "configs" / "service.yaml"
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("k: v\n", encoding="utf-8")

    ft_tail_name = "by-tail"
    ft_fname: FileType = make_file_type(
        local_key=ft_tail_name,
        filenames=["configs/service.yaml"],
        content_gate=ContentGate.IF_FILENAME,
        content_matcher=_AlwaysFalseContentMatcher(),
    )

    ft_yaml_name = "yaml"
    ft_fallback: FileType = make_file_type(
        local_key=ft_yaml_name,
        extensions=[".yaml"],
    )

    filetypes: dict[str, FileType] = {ft_tail_name: ft_fname, ft_yaml_name: ft_fallback}
    processors: dict[str, HeaderProcessor] = {ft_yaml_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_yaml_name


def test_resolve_content_only_with_always_gate(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """ALWAYS gate: a type with no name rules can be selected solely by content matcher."""
    file: Path = tmp_path / "mystery.bin"
    file.write_text("MAGIC\n", encoding="utf-8")

    ft_magic_name = "magic"
    ft_magic: FileType = make_file_type(
        local_key=ft_magic_name,
        content_gate=ContentGate.ALWAYS,
        content_matcher=_AlwaysTrueContentMatcher(),
    )

    filetypes: dict[str, FileType] = {ft_magic_name: ft_magic}
    processors: dict[str, HeaderProcessor] = {}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.file_type and ctx.file_type.local_key == ft_magic_name
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED


def test_resolve_tie_with_both_processors_uses_name_asc(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """With equal scores and processors for both, resolver picks lexicographically smaller name."""
    file: Path = tmp_path / "x.data"
    file.write_text("x\n", encoding="utf-8")

    ft_alpha_name = "alpha"
    ft_alpha: FileType = make_file_type(
        local_key=ft_alpha_name,
        extensions=[".data"],
    )

    ft_beta_name = "beta"
    ft_beta: FileType = make_file_type(
        local_key=ft_beta_name,
        extensions=[".data"],
    )

    filetypes: dict[str, FileType] = {ft_alpha_name: ft_alpha, ft_beta_name: ft_beta}
    processors: dict[str, HeaderProcessor] = {ft_alpha_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_alpha_name


def test_resolve_processor_registry_name_mismatch_leads_to_skip(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """If processor registry key differs from FileType.name, resolver must skip (no processor)."""
    file: Path = tmp_path / "x.py"
    file.write_text("print(1)\n", encoding="utf-8")

    ft_py_name = "python"
    ft_py: FileType = make_file_type(
        local_key=ft_py_name,
        extensions=[".py"],
    )

    # Processor registered under a different key; should not be found.
    filetypes: dict[str, FileType] = {ft_py_name: ft_py}
    processors: dict[str, HeaderProcessor] = {"python-variant": HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.TYPE_RESOLVED_NO_PROCESSOR_REGISTERED
    assert ctx.file_type and ctx.file_type.local_key == ft_py_name


def test_resolve_deep_filename_tail_normalization(
    tmp_path: Path,
    effective_registries: EffectiveRegistries,
) -> None:
    """Filename-tail rules with nested paths must match after backslash->slash normalization."""
    folder: Path = tmp_path / "a" / "b" / ".config" / "tool"
    folder.mkdir(parents=True, exist_ok=True)
    file: Path = folder / "settings.json"
    file.write_text("{}\n", encoding="utf-8")

    ft_toolcfg_name = "toolcfg"
    ft_toolcfg: FileType = make_file_type(
        local_key=ft_toolcfg_name,
        filenames=[r".config\tool/settings.json"],  # backslash in declared tail
    )

    filetypes: dict[str, FileType] = {ft_toolcfg_name: ft_toolcfg}
    processors: dict[str, HeaderProcessor] = {ft_toolcfg_name: HeaderProcessor()}
    ctx: ProcessingContext = _resolve(
        file,
        filetypes=filetypes,
        processors=processors,
        effective_registries=effective_registries,
    )
    assert ctx.status.resolve == ResolveStatus.RESOLVED
    assert ctx.file_type and ctx.file_type.local_key == ft_toolcfg_name
