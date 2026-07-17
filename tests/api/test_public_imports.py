# topmark:header:start
#
#   project      : TopMark
#   file         : test_public_imports.py
#   file_relpath : tests/api/test_public_imports.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Smoke tests for public imports and __all__ (Google-style)."""

from __future__ import annotations

import inspect
import subprocess
import sys
import types


def test_api_all_is_the_exact_supported_facade() -> None:
    """__all__ exposes exactly the reviewed stable façade."""
    from topmark import api

    expected: set[str] = {
        "ApiPipelineRun",
        "ContentStreamEvent",
        "DiagnosticEntry",
        "FileResult",
        "FileResultEvent",
        "FileTypeInfo",
        "Outcome",
        "ProbeCandidateInfo",
        "ProbeFileResult",
        "ProbeFileResultEvent",
        "ProbeRunResult",
        "ProbeStreamEvent",
        "ProcessorInfo",
        "PublicStreamEvent",
        "RunCompletedEvent",
        "RunResult",
        "RunStartedEvent",
        "VersionInfo",
        "check",
        "get_version_info",
        "get_version_text",
        "list_filetypes",
        "list_processors",
        "probe",
        "stream_check",
        "stream_probe",
        "stream_strip",
        "strip",
    }
    exported: set[str] = set(api.__all__)
    assert exported == expected
    assert (
        not {
            "ensure_mutable_config",
            "ContentRunCollector",
            "to_probe_file_result",
        }
        & exported
    )


def test_api_symbols_are_callable_types_or_type_aliases() -> None:
    """Every exported symbol is callable, a type/class, or a runtime type alias value."""
    from topmark import api

    # Ensure __all__ exists and is an iterable of strings
    assert hasattr(api, "__all__")
    assert all(isinstance(n, str) for n in api.__all__)

    for name in api.__all__:
        obj = getattr(api, name)
        # Functions are callable, DTOs are classes, and exported PEP 604 union
        # aliases are runtime types.UnionType values.
        assert callable(obj) or inspect.isclass(obj) or isinstance(obj, types.UnionType)


def test_importing_public_api_does_not_import_click() -> None:
    """The programmatic façade remains independent from Click."""
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import topmark.api; assert 'click' not in sys.modules",
        ],
        check=True,
    )
