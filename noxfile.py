# topmark:header:start
#
#   project      : TopMark
#   file         : noxfile.py
#   file_relpath : noxfile.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""TopMark project automation via Nox (using uv-backed virtualenvs).

This file defines the developer and CI automation sessions used in this repository.

Sessions:
  - `lint`: Ruff + pydoclint + Makefile validation (mbake) on tracked files.
  - `lint_fixall`: Ruff lint autofix.
  - `format_check`: Verify formatting (ruff, mdformat, taplo, mbake).
  - `format`: Apply formatting (ruff, mdformat, taplo, mbake).
  - `docs`: Build MkDocs documentation in strict mode.
  - `docs_serve`: Serve docs locally.
  - `links`: Lychee link checks for docs/ + tracked Markdown.
  - `links_src`: Lychee link checks for Python sources (docstring URLs).
  - `links_all`: Combined link checks.
  - `links_site`: Lychee link checks for the built MkDocs site (includes generated pages).
  - `docstring_links`: Enforce docstring link style (custom tool).
  - `docs_hygiene`: Enforce lightweight Markdown snippet/include hygiene (custom tool).
  - `code_hygiene`: Enforce lightweight Python prose hygiene (custom tool).
  - `qa`: Per-Python session that runs pytest and pyright.
  - `qa_api`: Per-Python session that runs pytest + API snapshot + pyright in one env.
  - `api_snapshot`: Public API snapshot test (per Python).
  - `property_test`: Long-running property tests (opt-in).
  - `perf_baseline`: Local pipeline memory/allocation baseline benchmarks (opt-in).
  - `package_check`: Build sdist/wheel and validate metadata (twine).
  - `release_check`: Deterministic pre-release gate (single Python, offline-friendly).
  - `release_full`: Full release gate (serial QA + links + packaging + matrix).

Notes:
  - The default venv backend is `uv` (via `nox-uv`) for faster environment sync.
  - Session dependencies are installed from `pyproject.toml` extras instead of exported requirements
    files.
  - File lists are resolved from git via `git ls-files` to avoid scanning ignored files.

Common invocations:
  - `nox -s lint`
  - `nox -s format_check`
  - `nox -s docs`
  - `nox -s qa` (runs for all configured Python versions)
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any
from typing import Final

import nox

# Resolve supported Python versions once at startup from project metadata.
PYPROJECT: Final[dict[str, Any]] = nox.project.load_toml("pyproject.toml")
PYTHONS: Final[list[str]] = nox.project.python_versions(PYPROJECT)

# Canonical single-version checks use the second most recent supported Python version.
CANONICAL_PYTHON: Final[str] = PYTHONS[-2] if len(PYTHONS) > 1 else PYTHONS[0]

CURRENT_PYTHON_VERSION: Final[str] = f"{sys.version_info[0]}.{sys.version_info[1]}"

DEPS_DEV: Final[str] = ".[dev,typing,test]"
DEPS_DOCS: Final[str] = ".[docs]"
DEPS_QA: Final[str] = ".[dev,typing,test,docs]"


# Global options
# Keep defaults fast; run QA (multi-Python) explicitly or in CI.
nox.options.sessions = [
    "lint",
    "format_check",
    "docs",
    "test_entrypoints",
]
nox.options.default_venv_backend = "uv"

MAKEFILE_PATTERNS = (
    "Makefile",
    "**/Makefile",
    "makefile",
    "**/makefile",
)

MARKDOWN_PATTERNS = (
    ":(glob)*.md",
    ":(glob)docs/**/*.md",
)

SOURCE_PATTERNS = (":(glob)src/topmark/**/*.py",)


# Tools and scripts
CHECK_DOCS_HYGIENE_SCRIPT = "tools/docs/check_docs_hygiene.py"
CHECK_CODE_HYGIENE_SCRIPT = "tools/docs/check_code_hygiene.py"

TEST_PUBLIC_API_SNAPSHOT_SCRIPT = "tests/api/test_public_api_snapshot.py"


# Session installs are resolved from project metadata and extras.
# With nox-uv, `session.install(...)` is executed via uv under the hood.


def get_git_files(session: nox.Session, *specs: str) -> list[str]:
    """Return tracked files matching the given git pathspecs.

    Args:
        session: Current nox session.
        *specs: One or more git pathspecs (e.g. `:(glob)docs/**/*.md`).

    Returns:
        Tracked file paths, one per line.
    """
    out = session.run(
        "git",
        "ls-files",
        "--",
        *specs,
        silent=True,
        external=True,
    )
    out_s: str = str(out).strip()
    return out_s.splitlines() if out_s else []


@nox.session(python=False)
def print_python_matrix(session: nox.Session) -> None:
    """Print supported and canonical Python versions as JSON."""
    payload = {
        "supported": PYTHONS,
        "canonical": CANONICAL_PYTHON,
    }
    print(json.dumps(payload, sort_keys=True))  # noqa: T201


@nox.session(python=CANONICAL_PYTHON)
def package_check(session: nox.Session) -> None:
    """Build sdist/wheel and validate distribution metadata (twine).

    This is a lightweight packaging sanity check used by release gates.
    """
    session.install(DEPS_DEV)

    # Ensure a clean dist/ to avoid stale artifacts influencing checks.
    session.run(
        "python",
        "-c",
        "import shutil; [shutil.rmtree(p, ignore_errors=True) "
        "for p in ['build', 'dist', 'src/topmark.egg-info']]",
    )

    session.run(
        "uv",
        "build",
        "--sdist",
        "--wheel",
    )
    session.run(
        "twine",
        "check",
        "dist/*",
    )


def run_lychee(
    session: nox.Session,
    targets: list[str],
    *,
    verbose: bool = True,
    root_dir: str | None = None,
    chunk_size: int = 50,
) -> None:
    """Run lychee against a set of targets.

    Lychee can be invoked with many file paths. For large repositories, passing
    everything in one go may exceed OS argument-length limits. We therefore run
    lychee in chunks.

    Args:
        session: Current nox session.
        targets: Target paths to scan.
        verbose: Control `lychee` verbosity (default: `True`).
        root_dir: If set, pass `--root-dir` to lychee (useful for checking
            built sites with root-relative links).
        chunk_size: Maximum number of paths per lychee invocation.

    Raises:
        ValueError: If `chunk_size` is <= 0.
    """
    if not targets:
        return

    if chunk_size <= 0:
        raise ValueError(f"chunk_size must be > 0 (got {chunk_size})")

    session.log("lychee: scanning %d target(s)", len(targets))

    for i in range(0, len(targets), chunk_size):
        chunk: list[str] = targets[i : i + chunk_size]
        session.log("lychee: chunk %d–%d", i + 1, min(i + chunk_size, len(targets)))
        args: list[str] = [
            "lychee",
            "--config",
            "lychee.toml",
            "--no-progress",
            "--verbose" if verbose else "--quiet",
        ]
        if root_dir is not None:
            args.extend(["--root-dir", root_dir])

        session.run(
            *args,
            *chunk,
            external=True,
        )


@nox.session(python=PYTHONS)
def qa(session: nox.Session) -> None:
    """Run tests + pyright (per Python version)."""
    session.log("Supported Python versions: " + ", ".join(PYTHONS))

    session.install(DEPS_QA)

    # We add *session.posargs to the end of the command
    session.run(
        "pytest",
        "-q",
        "tests",
        "-m",
        "not slow and not hypothesis_slow",
        *session.posargs,
    )

    # `nox.Session.python` is typed broadly in nox' stubs (it can reflect decorator inputs),
    # but within a running session it should be a concrete interpreter version string.
    py_ver = session.python
    if not isinstance(py_ver, str) or not py_ver:
        raise RuntimeError(f"Unexpected session.python value: {py_ver!r}")

    session.run(
        "pyright",
        "--pythonversion",
        py_ver,
    )


@nox.session(python=PYTHONS)
def qa_api(session: nox.Session) -> None:
    """Run tests + API snapshot + pyright (per Python version) in one env.

    This is useful for release/CI gates where we want to reuse the same virtual
    environment for pytest + pyright + the API snapshot test.

    Any arguments passed after `--` are forwarded to the main pytest run.
    """
    session.log("Supported Python versions: " + ", ".join(PYTHONS))

    session.install(DEPS_QA)

    # Main test suite (posargs forwarded, e.g. "-n auto")
    session.run(
        "pytest",
        "-q",
        "tests",
        "-m",
        "not slow and not hypothesis_slow",
        *session.posargs,
    )

    # Public API snapshot test (kept separate from the main suite)
    session.run(
        "pytest",
        "-vv",
        TEST_PUBLIC_API_SNAPSHOT_SCRIPT,
    )

    # Pyright
    py_ver = session.python
    if not isinstance(py_ver, str) or not py_ver:
        raise RuntimeError(f"Unexpected session.python value: {py_ver!r}")

    session.run(
        "pyright",
        "--pythonversion",
        py_ver,
    )


@nox.session(python=PYTHONS)
def test_entrypoints(session: nox.Session) -> None:
    """Verify that both 'topmark' and 'python -m topmark' are functional."""
    # Install the current project so the 'topmark' command is created
    session.install(".")

    # Define the environment variables for tracing
    debug_env: dict[str, str] = {"TOPMARK_LOG_LEVEL": "DEBUG"}

    # Print the sys.path of the Nox venv
    session.run(
        "python",
        "-c",
        "import sys; print('\\n'.join(sys.path))",
    )

    # Print the location of the installed topmark package
    session.run(
        "python",
        "-c",
        "import topmark; print(topmark.__file__)",
    )

    # 1. Test the console script entry point defined in pyproject.toml
    session.run(
        "topmark",
        "version",
        external=True,
        env=debug_env,
    )

    # 2. Test the module entry point defined in src/topmark/__main__.py
    session.run(
        "python",
        "-m",
        "topmark",
        "version",
        env=debug_env,
    )

    # 3. Test a subcommand to ensure Click context/registry initialized correctly
    session.run(
        "topmark",
        "registry",
        "filetypes",
        env=debug_env,
    )


@nox.session(python=CANONICAL_PYTHON)
def coverage(session: nox.Session) -> None:
    """Run tests with coverage and generate reports."""
    session.install("-e", DEPS_DEV)

    session.run(
        "pytest",
        "-q",
        "tests",
        "-m",
        "not slow and not hypothesis_slow",
        "--cov=topmark",
        "--cov-branch",
        "--cov-report=term-missing",
        "--cov-report=html",
        "--cov-report=xml",
        "--cov-report=json",
        *session.posargs,
    )


@nox.session
def lint(session: nox.Session) -> None:
    """Static analysis and custom validation."""
    session.install(DEPS_DEV)

    session.run(
        "ruff",
        "check",
        ".",
    )

    session.run(
        "pydoclint",
        "-q",
        "src/topmark",
        "tests",
        "tools",
    )

    # Clean mbake validation
    makefiles: list[str] = get_git_files(session, *MAKEFILE_PATTERNS)
    # makefiles = [f for f in makefiles if f] # Filter empty
    if makefiles:
        session.run(
            "mbake",
            "validate",
            "--config",
            ".bake.toml",
            *makefiles,
        )


@nox.session
def lint_fixall(session: nox.Session) -> None:
    """Run ruff with --fix (auto-fix lint issues)."""
    session.install(DEPS_DEV)

    session.run(
        "ruff",
        "check",
        "--fix",
        ".",
    )


@nox.session
def format_check(session: nox.Session) -> None:
    """Check formatting for code, markdown, and TOML."""
    session.install(DEPS_DEV)

    session.run(
        "ruff",
        "format",
        "--check",
        ".",
    )
    # Markdown check
    md_files: list[str] = get_git_files(session, *MARKDOWN_PATTERNS)
    if md_files:
        session.run(
            "mdformat",
            "--check",
            *md_files,
        )

    session.run(
        "taplo",
        "format",
        "--check",
        ".",
    )

    makefiles: list[str] = get_git_files(session, *MAKEFILE_PATTERNS)
    if makefiles:
        session.run(
            "mbake",
            "format",
            "--check",
            "--config",
            ".bake.toml",
            *makefiles,
        )


@nox.session
def format(session: nox.Session) -> None:
    """Format code, markdown, TOML, and Makefiles (auto-fix)."""
    session.install(DEPS_DEV)

    session.run(
        "ruff",
        "format",
        ".",
    )

    md_files: list[str] = get_git_files(session, *MARKDOWN_PATTERNS)
    if md_files:
        session.run("mdformat", *md_files)

    session.run(
        "taplo",
        "format",
        ".",
    )

    makefiles: list[str] = get_git_files(session, *MAKEFILE_PATTERNS)
    if makefiles:
        session.run(
            "mbake",
            "format",
            "--config",
            ".bake.toml",
            *makefiles,
        )


@nox.session
def docs(session: nox.Session) -> None:
    """Build documentation."""
    session.install(DEPS_DOCS)

    session.run(
        "mkdocs",
        "build",
        "--strict",
    )


@nox.session
def docs_serve(session: nox.Session) -> None:
    """Serve the docs locally (dev only)."""
    session.install(DEPS_DOCS)

    session.run(
        "mkdocs",
        "serve",
    )


@nox.session
def links(session: nox.Session) -> None:
    """Check links in docs/ and tracked Markdown files (requires system lychee)."""
    # No install needed if lychee is a system binary
    md_files: list[str] = get_git_files(session, *MARKDOWN_PATTERNS)

    run_lychee(session, md_files)


@nox.session
def links_src(session: nox.Session) -> None:
    """Check links found in Python docstrings under src/ (requires system lychee)."""
    py_files: list[str] = get_git_files(session, *SOURCE_PATTERNS)

    run_lychee(session, py_files)


@nox.session
def links_all(session: nox.Session) -> None:
    """Check links in docs/, tracked Markdown, and src/ docstrings (requires system lychee)."""
    md_files: list[str] = get_git_files(session, *MARKDOWN_PATTERNS)
    py_files: list[str] = get_git_files(session, *SOURCE_PATTERNS)

    run_lychee(session, md_files + py_files)


@nox.session
def links_site(session: nox.Session) -> None:
    """Check links in the built MkDocs site (includes generated pages).

    This session builds the documentation first so that pages generated by
    `mkdocs-gen-files` exist in the output. We then run lychee against the
    resulting `site/` directory.

    Note:
      - This session is network-dependent.
      - It is intentionally separate from `links` (which is pre-build and fast).
    """
    session.install(DEPS_DOCS)

    # Build docs strictly so generated pages exist.
    session.run(
        "mkdocs",
        "build",
        "--strict",
        "--config-file",
        "mkdocs.linkcheck.yml",
        external=True,
    )

    # Lychee can take a directory and will scan supported formats within.
    site_dir: str = str(pathlib.Path("site").resolve())
    run_lychee(session, ["site"], verbose=False, root_dir=site_dir)


@nox.session
def docstring_links(session: nox.Session) -> None:
    """Enforce docstring link style."""
    session.install(DEPS_DEV)

    session.run(
        "python",
        CHECK_DOCS_HYGIENE_SCRIPT,
        "--stats",
    )


@nox.session
def docs_hygiene(session: nox.Session) -> None:
    """Enforce lightweight Markdown snippet/include hygiene."""
    session.install(DEPS_DEV)

    session.run(
        "python",
        CHECK_DOCS_HYGIENE_SCRIPT,
        "--docs-hygiene",
        "--stats",
    )


@nox.session
def code_hygiene(session: nox.Session) -> None:
    """Enforce lightweight code hygiene (docstrings, inlines)."""
    session.install(DEPS_DEV)

    session.run(
        "python",
        CHECK_CODE_HYGIENE_SCRIPT,
    )


@nox.session(python=PYTHONS)
def api_snapshot(session: nox.Session) -> None:
    """Run the public API snapshot test (per Python version)."""
    session.log("Supported Python versions: " + ", ".join(PYTHONS))

    session.install(DEPS_DEV)

    # We add *session.posargs to the end of the command
    session.run(
        "pytest",
        "-vv",
        TEST_PUBLIC_API_SNAPSHOT_SCRIPT,
        *session.posargs,
    )


@nox.session
def property_test(session: nox.Session) -> None:
    """Run the long-running property tests (developer only)."""
    session.install(DEPS_DEV)

    session.run(
        "pytest",
        "-vv",
        "tests/pipeline/test_header_bounds_property.py",
    )


@nox.session(python=CANONICAL_PYTHON)
def perf_baseline(session: nox.Session) -> None:
    """Run local pipeline memory/allocation baseline benchmarks.

    By default this runs the full `baseline` suite and writes a preserved run
    under `artifacts/perf/`. Pass arguments after `--` to select another suite,
    run id, or output directory.
    """
    session.install(DEPS_DEV)

    args: list[str] = list(session.posargs) if session.posargs else ["--suite", "baseline"]
    session.run(
        "python",
        "tools/perf/pipeline_memory_baseline.py",
        *args,
    )


@nox.session(python=CANONICAL_PYTHON)
def release_check(session: nox.Session) -> None:
    """Release gate: quality + docs + packaging checks (single Python, offline-friendly).

    This session is intended as a fast, deterministic pre-release gate you can run locally
    and in CI. It intentionally avoids link checking (network-dependent).

    It runs:
      - Formatting checks (ruff, mdformat, taplo, mbake)
      - Lint checks (ruff, pydoclint)
      - Docstring link style checks (`tools/docs/check_docs_hygiene.py`)
      - Markdown snippet/include hygiene checks (`tools/docs/check_docs_hygiene.py --docs-hygiene`)
      - Code prose hygiene checks (`tools/docs/check_code_hygiene.py`)
      - Docs build in strict mode (mkdocs)
      - Packaging build + metadata checks (build, twine)
      - Tests + pyright for the session Python
    """
    # Tooling / QA deps, including docs dependencies because pyright checks tools/docs/.
    session.install(DEPS_QA)
    # Docs deps (mkdocs, plugins)
    session.install(DEPS_DOCS)

    # --- Quality gates (mirror existing sessions, but as a single gate) ---
    session.run(
        "ruff",
        "format",
        "--check",
        ".",
    )
    session.run(
        "ruff",
        "check",
        ".",
    )
    session.run(
        "pydoclint",
        "-q",
        "src/topmark",
        "tests",
        "tools",
    )

    md_files: list[str] = get_git_files(session, *MARKDOWN_PATTERNS)
    if md_files:
        session.run(
            "mdformat",
            "--check",
            *md_files,
        )

    session.run(
        "taplo",
        "format",
        "--check",
        ".",
    )

    makefiles: list[str] = get_git_files(session, *MAKEFILE_PATTERNS)
    if makefiles:
        session.run(
            "mbake",
            "validate",
            "--config",
            ".bake.toml",
            *makefiles,
        )
        session.run(
            "mbake",
            "format",
            "--check",
            "--config",
            ".bake.toml",
            *makefiles,
        )

    # Docstring link style (custom tool)
    session.run(
        "python",
        CHECK_DOCS_HYGIENE_SCRIPT,
        "--stats",
    )

    # Markdown snippet/include hygiene (custom tool)
    session.run(
        "python",
        CHECK_DOCS_HYGIENE_SCRIPT,
        "--docs-hygiene",
        "--stats",
    )

    # Code hygiene (custom tool)
    session.run(
        "python",
        CHECK_CODE_HYGIENE_SCRIPT,
    )

    # Docs build (strict)
    session.run(
        "mkdocs",
        "build",
        "--strict",
    )

    # Tests
    session.run(
        "pytest",
        "-q",
        "tests",
        "-m",
        "not slow and not hypothesis_slow",
        *session.posargs,
    )
    # Entry point check -- We call it as a function to reuse the current session environment
    test_entrypoints(session)

    # Pyright
    py_ver = session.python
    if not isinstance(py_ver, str) or not py_ver:
        raise RuntimeError(f"Unexpected session.python value: {py_ver!r}")
    session.run(
        "pyright",
        "--pythonversion",
        py_ver,
    )

    # Packaging checks (clean dist/ first to avoid stale artifacts)
    session.run(
        "python",
        "-c",
        "import shutil; shutil.rmtree('dist', ignore_errors=True)",
    )
    session.run(
        "uv",
        "build",
        "--sdist",
        "--wheel",
    )
    session.run(
        "twine",
        "check",
        "dist/*",
    )


@nox.session(python=False)
def release_full(session: nox.Session) -> None:
    """Full release gate: run serial QA gates + links + packaging + the Python matrix.

    This is a convenience meta-session that orchestrates other sessions.
    It is network-dependent because it includes lychee-based link checks.

    Notes:
      - Requires `lychee` to be available as a system binary for `links_all`.
      - Runs `qa_api` for all configured Python versions (pytest + API snapshot + pyright).
      - Uses `package_check` for build/twine verification.

    Any arguments passed after `--` are forwarded to the per-Python pytest run.
    """
    # Orchestrate in a separate nox process to reuse existing sessions and keep definitions DRY.
    # Serial, non-matrix gates first:
    session.run(
        "nox",
        "-s",
        "format_check",
        external=True,
    )
    session.run(
        "nox",
        "-s",
        "lint",
        external=True,
    )
    session.run(
        "nox",
        "-s",
        "docstring_links",
        external=True,
    )
    session.run(
        "nox",
        "-s",
        "docs_hygiene",
        external=True,
    )
    session.run(
        "nox",
        "-s",
        "code_hygiene",
        external=True,
    )
    session.run(
        "nox",
        "-s",
        "docs",
        external=True,
    )
    session.run(
        "nox",
        "-s",
        "links_site",
        external=True,
    )
    session.run(
        "nox",
        "-s",
        "links_all",
        external=True,
    )

    # Verify CLI entrypoints across the matrix
    session.run(
        "nox",
        "-s",
        "test_entrypoints",
        external=True,
    )

    session.run(
        "nox",
        "-s",
        "package_check",
        external=True,
    )

    # Parallelize the per-Python QA+snapshot+typecheck gate across versions.
    jobs_s: str = os.environ.get("JOBS", "5")
    try:
        jobs = int(jobs_s)
    except ValueError as e:
        raise RuntimeError(f"Invalid JOBS value {jobs_s!r}; expected an integer") from e

    pythons: list[str] = PYTHONS
    session.run(
        "make",
        "-j",
        str(jobs),
        *(f"release-qa-api-{py}" for py in pythons),
        external=True,
    )
