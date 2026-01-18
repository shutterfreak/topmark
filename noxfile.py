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
  - `docstring_links`: Enforce docstring link style (custom tool).
  - `qa`: Per-Python session that runs pytest and pyright.
  - `qa_api`: Per-Python session that runs pytest + API snapshot + pyright in one env.
  - `api_snapshot`: Public API snapshot test (per Python).
  - `property_test`: Long-running property tests (opt-in).
  - `package_check`: Build sdist/wheel and validate metadata (twine).
  - `release_check`: Deterministic pre-release gate (single Python, offline-friendly).
  - `release_full`: Full release gate (serial QA + links + packaging + matrix).

Notes:
  - The default venv backend is `uv` (via `nox-uv`) for faster environment sync.
  - File lists are resolved from git via `git ls-files` to avoid scanning ignored files.

Common invocations:
  - `nox -s lint`
  - `nox -s format_check`
  - `nox -s docs`
  - `nox -s qa` (runs for all configured Python versions)
"""

from __future__ import annotations

import os
import pathlib
import sys
import warnings
from typing import TYPE_CHECKING, Any, cast

import nox

if TYPE_CHECKING:
    from collections.abc import Callable

# Handle TOML parsing based on Python version or available libraries

if sys.version_info >= (3, 11):
    # tomllib is available since Python version 3.11
    import tomllib

    _toml_loads = cast("Callable[[str], dict[str, Any]]", tomllib.loads)  # type: ignore[assignment]
else:
    import toml

    _toml_loads = cast("Callable[[str], dict[str, Any]]", toml.loads)  # type: ignore[assignment]

CURRENT_PYTHON_VERSION: str = f"{sys.version_info[0]}.{sys.version_info[1]}"

# --- Dynamic Python Version Resolution ---


def _parse_pyproject_toml() -> dict[str, Any]:
    """Parse `pyproject.toml` using stdlib TOML parsing.

    This runs at **noxfile import time**, so it must not depend on project
    runtime dependencies.

    Returns:
        dict[str, Any]: Parsed TOML document (top-level table).
    """
    path: pathlib.Path = pathlib.Path(__file__).parent / "pyproject.toml"
    if not path.exists():
        return {}

    data: str = path.read_text(encoding="utf-8")

    # Handle TOML parsing based on Python version or available libraries
    try:
        parsed = _toml_loads(data)
    except Exception:
        return {}

    return parsed


def get_supported_pythons() -> list[str]:
    """Resolve supported Python versions from `pyproject.toml` classifiers.

    Returns:
        list[str]: Supported versions like ["3.10", "3.11", ...], sorted.
    """
    doc: dict[str, Any] = _parse_pyproject_toml()
    project_any = doc.get("project")

    # Error checking for missing project table
    if not isinstance(project_any, dict):
        warnings.warn(
            "Could not find 'project' table in pyproject.toml. "
            f"Falling back to Python {CURRENT_PYTHON_VERSION}.",
            RuntimeWarning,
            stacklevel=2,
        )
        return [CURRENT_PYTHON_VERSION]

    project: dict[str, Any] = cast("dict[str, Any]", project_any)

    classifiers_any = project.get("classifiers")
    if not isinstance(classifiers_any, list):
        warnings.warn(
            "Could not find 'classifiers' in pyproject.toml. "
            f"Falling back to Python {CURRENT_PYTHON_VERSION}.",
            RuntimeWarning,
            stacklevel=2,
        )
        return [CURRENT_PYTHON_VERSION]

    classifiers: list[str] = cast("list[str]", classifiers_any)

    prefix = "Programming Language :: Python :: "
    versions: list[str] = []

    for c in classifiers:
        if not c.startswith(prefix):
            continue
        v: str = c.removeprefix(prefix).strip()
        # Accept only X.Y numeric versions.
        parts: list[str] = v.split(".")
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            continue
        versions.append(f"{int(parts[0])}.{int(parts[1])}")

    # Sort numerically ("3.10" after "3.9", etc.)
    def _key(s: str) -> tuple[int, int]:
        major_s, minor_s = s.split(".")
        return int(major_s), int(minor_s)

    out: list[str] = sorted(set(versions), key=_key)
    if out:
        return out

    warnings.warn(
        "No Python versions found in classifiers. "
        f"Falling back to Python {CURRENT_PYTHON_VERSION}.",
        RuntimeWarning,
        stacklevel=2,
    )
    return [CURRENT_PYTHON_VERSION]


# Resolve versions once at startup
PYTHONS: list[str] = get_supported_pythons()

# Global options
# Keep defaults fast; run QA (multi-Python) explicitly or in CI.
nox.options.sessions = ["lint", "format_check", "docs"]
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

# If using nox-uv, sessions use session.install the same way,
# but installs are performed via uv under the hood.


def get_git_files(session: nox.Session, *specs: str) -> list[str]:
    """Return tracked files matching the given git pathspecs.

    Args:
        session (nox.Session): Current nox session.
        *specs (str): One or more git pathspecs (e.g. `:(glob)docs/**/*.md`).

    Returns:
        list[str]: Tracked file paths, one per line.
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


@nox.session(python=CURRENT_PYTHON_VERSION)
def package_check(session: nox.Session) -> None:
    """Build sdist/wheel and validate distribution metadata (twine).

    This is a lightweight packaging sanity check used by release gates.
    """
    session.install("-r", "requirements-dev.txt")

    # Ensure a clean dist/ to avoid stale artifacts influencing checks.
    session.run(
        "python",
        "-c",
        "import shutil; shutil.rmtree('dist', ignore_errors=True)",
    )

    session.run("python", "-m", "build", "--sdist", "--wheel")
    session.run("twine", "check", "dist/*")


def run_lychee(session: nox.Session, targets: list[str], *, chunk_size: int = 50) -> None:
    """Run lychee against a set of targets.

    Lychee can be invoked with many file paths. For large repositories, passing
    everything in one go may exceed OS argument-length limits. We therefore run
    lychee in chunks.

    Args:
        session (nox.Session): Current nox session.
        targets (list[str]): Target paths to scan.
        chunk_size (int): Maximum number of paths per lychee invocation.

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
        session.run(
            "lychee",
            "--config",
            "lychee.toml",
            "--no-progress",
            "--verbose",
            *chunk,
            external=True,
        )


@nox.session(python=PYTHONS)
def qa(session: nox.Session) -> None:
    """Run tests + pyright (per Python version)."""
    session.log("Supported Python versions: " + ", ".join(PYTHONS))

    session.install("-r", "requirements-dev.txt")

    # We add *session.posargs to the end of the command
    session.run("pytest", "-q", "tests", "-m", "not slow and not hypothesis_slow", *session.posargs)

    # `nox.Session.python` is typed broadly in nox' stubs (it can reflect decorator inputs),
    # but within a running session it should be a concrete interpreter version string.
    py_ver = session.python
    if not isinstance(py_ver, str) or not py_ver:
        raise RuntimeError(f"Unexpected session.python value: {py_ver!r}")

    session.run("pyright", "--pythonversion", py_ver)


@nox.session(python=PYTHONS)
def qa_api(session: nox.Session) -> None:
    """Run tests + API snapshot + pyright (per Python version) in one env.

    This is useful for release/CI gates where we want to reuse the same virtual
    environment for pytest + pyright + the API snapshot test.

    Any arguments passed after `--` are forwarded to the main pytest run.
    """
    session.log("Supported Python versions: " + ", ".join(PYTHONS))

    session.install("-r", "requirements-dev.txt")

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
    session.run("pytest", "-vv", "tests/api/test_public_api_snapshot.py")

    # Pyright
    py_ver = session.python
    if not isinstance(py_ver, str) or not py_ver:
        raise RuntimeError(f"Unexpected session.python value: {py_ver!r}")

    session.run("pyright", "--pythonversion", py_ver)


@nox.session
def lint(session: nox.Session) -> None:
    """Static analysis and custom validation."""
    session.install("-r", "requirements-dev.txt")

    session.run("ruff", "check", ".")

    session.run("pydoclint", "-q", "src/topmark", "tests", "tools")

    # Clean mbake validation
    makefiles: list[str] = get_git_files(session, *MAKEFILE_PATTERNS)
    # makefiles = [f for f in makefiles if f] # Filter empty
    if makefiles:
        session.run("mbake", "validate", "--config", ".bake.toml", *makefiles)


@nox.session
def lint_fixall(session: nox.Session) -> None:
    """Run ruff with --fix (auto-fix lint issues)."""
    session.install("-r", "requirements-dev.txt")

    session.run("ruff", "check", "--fix", ".")


@nox.session
def format_check(session: nox.Session) -> None:
    """Check formatting for code, markdown, and TOML."""
    session.install("-r", "requirements-dev.txt")

    session.run("ruff", "format", "--check", ".")
    # Markdown check
    md_files: list[str] = get_git_files(session, *MARKDOWN_PATTERNS)
    if md_files:
        session.run("mdformat", "--check", *md_files)

    session.run("taplo", "format", "--check", ".")

    makefiles: list[str] = get_git_files(session, *MAKEFILE_PATTERNS)
    if makefiles:
        session.run("mbake", "format", "--check", "--config", ".bake.toml", *makefiles)


@nox.session
def format(session: nox.Session) -> None:
    """Format code, markdown, TOML, and Makefiles (auto-fix)."""
    session.install("-r", "requirements-dev.txt")

    session.run("ruff", "format", ".")

    md_files: list[str] = get_git_files(session, *MARKDOWN_PATTERNS)
    if md_files:
        session.run("mdformat", *md_files)

    session.run("taplo", "format", ".")

    makefiles: list[str] = get_git_files(session, *MAKEFILE_PATTERNS)
    if makefiles:
        session.run("mbake", "format", "--config", ".bake.toml", *makefiles)


@nox.session
def docs(session: nox.Session) -> None:
    """Build documentation."""
    session.install("-r", "requirements-docs.txt")

    session.run("mkdocs", "build", "--strict")


@nox.session
def docs_serve(session: nox.Session) -> None:
    """Serve the docs locally (dev only)."""
    session.install("-r", "requirements-docs.txt")

    session.run("mkdocs", "serve")


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
def docstring_links(session: nox.Session) -> None:
    """Enforce docstring link style."""
    session.install("-r", "requirements-dev.txt")

    session.run("python", "tools/check_docstring_links.py", "--stats")


@nox.session(python=PYTHONS)
def api_snapshot(session: nox.Session) -> None:
    """Run the public API snapshot test (per Python version)."""
    session.log("Supported Python versions: " + ", ".join(PYTHONS))

    session.install("-r", "requirements-dev.txt")

    # We add *session.posargs to the end of the command
    session.run("pytest", "-vv", "tests/api/test_public_api_snapshot.py", *session.posargs)


@nox.session
def property_test(session: nox.Session) -> None:
    """Run the long-running property tests (developer only)."""
    session.install("-r", "requirements-dev.txt")

    session.run("pytest", "-vv", "tests/pipeline/test_header_bounds_property.py")


@nox.session(python=CURRENT_PYTHON_VERSION)
def release_check(session: nox.Session) -> None:
    """Release gate: quality + docs + packaging checks (single Python, offline-friendly).

    This session is intended as a fast, deterministic pre-release gate you can run locally
    and in CI. It intentionally avoids link checking (network-dependent).

    It runs:
      - Formatting checks (ruff, mdformat, taplo, mbake)
      - Lint checks (ruff, pydoclint)
      - Docstring link style checks (tools/check_docstring_links.py)
      - Docs build in strict mode (mkdocs)
      - Packaging build + metadata checks (build, twine)
      - Tests + pyright for the session Python
    """
    # Tooling / QA deps
    session.install("-r", "requirements-dev.txt")
    # Docs deps (mkdocs, plugins)
    session.install("-r", "requirements-docs.txt")

    # --- Quality gates (mirror existing sessions, but as a single gate) ---
    session.run("ruff", "format", "--check", ".")
    session.run("ruff", "check", ".")
    session.run("pydoclint", "-q", "src/topmark", "tests", "tools")

    md_files: list[str] = get_git_files(session, *MARKDOWN_PATTERNS)
    if md_files:
        session.run("mdformat", "--check", *md_files)

    session.run("taplo", "format", "--check", ".")

    makefiles: list[str] = get_git_files(session, *MAKEFILE_PATTERNS)
    if makefiles:
        session.run("mbake", "validate", "--config", ".bake.toml", *makefiles)
        session.run("mbake", "format", "--check", "--config", ".bake.toml", *makefiles)

    # Docstring link style (custom tool)
    session.run("python", "tools/check_docstring_links.py", "--stats")

    # Docs build (strict)
    session.run("mkdocs", "build", "--strict")

    # Tests
    session.run("pytest", "-q", "tests", "-m", "not slow and not hypothesis_slow", *session.posargs)

    # Pyright
    py_ver = session.python
    if not isinstance(py_ver, str) or not py_ver:
        raise RuntimeError(f"Unexpected session.python value: {py_ver!r}")
    session.run("pyright", "--pythonversion", py_ver)

    # Packaging checks (clean dist/ first to avoid stale artifacts)
    session.run(
        "python",
        "-c",
        "import shutil; shutil.rmtree('dist', ignore_errors=True)",
    )
    session.run("python", "-m", "build", "--sdist", "--wheel")
    session.run("twine", "check", "dist/*")


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
    session.run("nox", "-s", "format_check", external=True)
    session.run("nox", "-s", "lint", external=True)
    session.run("nox", "-s", "docstring_links", external=True)
    session.run("nox", "-s", "docs", external=True)
    session.run("nox", "-s", "links_all", external=True)

    session.run("nox", "-s", "package_check", external=True)

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
