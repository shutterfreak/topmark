<!--
topmark:header:start

  project      : TopMark
  file         : CONTRIBUTING.md
  file_relpath : CONTRIBUTING.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Contributing to TopMark

Thank you for your interest in contributing to **TopMark**!\
This guide explains how to set up your environment, run checks, contribute code, and prepare
releases.

______________________________________________________________________

## 🧰 Prerequisites

- **Python 3.10–3.14**
- **Git**
- **make** (for convenience targets)
- **uv** (install and keep it on your `PATH`)
- **nox** (installed as part of the project extras / QA workflow)

Optional (for local testing across multiple versions):

```bash
pyenv install 3.14.2 3.13.11 3.12.12 3.11.14 3.10.19
pyenv local 3.14.2 3.13.11 3.12.12 3.11.14 3.10.19
```

______________________________________________________________________

## 🚀 Quick Start

```bash
# Clone and enter the repo
git clone https://github.com/shutterfreak/topmark.git
cd topmark

# Create local editor venv (optional for IDE/Pyright import resolution)
make venv
make venv-sync-dev

# Run core quality checks and tests
make verify     # lint, formatting, docs, links
make test       # tox default envs

# Run tests locally (current interpreter only)
make pytest     # supports PYTEST_PAR="-n auto"
```

> **Note**: `.venv` is the standard local development environment for IDE integration and
> interactive work. It is managed with `uv` and intended for editor support (for example Pyright
> import resolution). All automated validation, testing, and CI parity checks still run through
> isolated `nox` environments.

______________________________________________________________________

## 🧪 Testing

Run the full tox test matrix:

```bash
make test
```

Run local pytest directly:

```bash
make pytest
make pytest PYTEST_PAR="-n auto"
```

Run long-running property-based Hypothesis tests (manual opt-in):

```bash
make property-test
```

### Configuration architecture note

TopMark separates configuration into three layers:

- TOML layer (`topmark.toml`) — discovery, parsing, and whole-source TOML schema validation (unknown
  sections/keys, malformed shapes), plus source-local options (e.g. `[config].root`,
  `strict_config_checking`)
- Config layer (`topmark.config`) — deserialization of validated layered config fragments and
  layered merge into a mutable config draft
- Runtime layer (`topmark.runtime`) — execution-time options and overrides

Configuration loading follows a staged model:

1. resolve TOML sources (defaults, discovered config, `--config`, CLI context)
1. validate each whole-source TOML fragment
1. extract the layered config fragment
1. deserialize and merge into a mutable config draft
1. evaluate effective config validity across staged validation logs
1. freeze into the final `Config`

Source-local options such as `strict_config_checking` are resolved during configuration loading and
influence validation behaviour, but do not become layered `Config` fields. In the current
implementation, effective strictness is applied across staged config-loading diagnostics:

- TOML-source diagnostics
- merged-config diagnostics
- runtime-applicability diagnostics

The flattened compatibility diagnostics view remains available for reporting and current
machine/API/CLI surfaces. CLI/API overrides (`--strict` / `--no-strict`) take precedence for the
current run.

The main integration helper is:

- `resolve_toml_sources_and_build_config_draft()`

### Developer validation (optional)

Enable lightweight registry and strategy checks while developing or debugging:

```bash
TOPMARK_VALIDATE=1 make test
# or
TOPMARK_VALIDATE=1 pytest -q
```

What this checks (dev-only; zero-cost in normal runs):

- Every registered header **processor** maps to a known **FileType**.
- XML/HTML-like processors use the **character-offset** strategy: they must return `NO_LINE_ANCHOR`
  from `get_header_insertion_index()` and compute an offset in `get_header_insertion_char_offset()`.

These validations help catch subtle registry or placement regressions early (e.g., typos in type
keys, accidental line-based use in XML processors).

______________________________________________________________________

## 🧹 Linting and Formatting

TopMark enforces strict linting and consistent formatting:

- **Ruff** — linting & formatting
- **pydoclint** — docstring checks
- **mdformat** — Markdown formatting
- **Taplo** — TOML formatting

Commands:

```bash
make lint            # ruff + pydoclint
make lint-fixall     # auto-fix lint issues
make format-check    # check formatting
make format          # auto-format all
make docstring-links # enforce docstring link style
```

### Linting policy

TopMark treats Ruff, Pyright, and the supporting tools as the single source of truth for code style
and typing rules:

- **Ruff**:

  - Enforces import style and modern syntax via the `UP` ruleset (pyupgrade), including:
    - Using builtin generics (`list[...]`, `dict[...]`, `tuple[...]`) instead of `typing.List` /
      `typing.Dict` / `typing.Tuple`.
    - Importing abstract collections from `collections.abc` (e.g. `Iterable`, `Mapping`, `Sequence`,
      `Callable`, `Iterator`) rather than from `typing`.
  - Enforces moving type-only imports under `if TYPE_CHECKING:` via the `TC` rules.
  - Acts as the primary linter for style, unused code, and import ordering.

- **Typing imports**:

  - Reserve `typing` imports for: `TYPE_CHECKING`, `Any`, `Final`, `Literal`, `Protocol`,
    `TypedDict`, `TypeVar`, `ParamSpec`, `TypeGuard`, `NamedTuple`, `TextIO`, `IO`, and `cast`.
  - Import abstract collections from `collections.abc` (not from `typing`).
  - Prefer PEP 604 unions (e.g. `X | None`) over `typing.Optional[X]`.

- **Type checking**:

  - Pyright runs in `strict` mode for `src/` and `tests/`.
  - Public APIs must be fully annotated and pass Pyright without `# type: ignore` (exceptions must
    be documented and justified in code comments).

- **Docstrings**:

  - Use Google-style docstrings with explicit `Args:`, `Returns:`, and `Raises:` sections for public
    functions, methods, and classes.
  - Keep docstrings import-safe: avoid heavy imports or side effects at module import time.
  - Treat the `Raises:` section as part of the **observable caller contract**. For public APIs, it
    may document exceptions intentionally propagated from delegated helpers when those exceptions
    are part of the supported behavior.
  - Do **not** introduce redundant `try/except: raise` blocks solely to satisfy docstring linting.
    Prefer accurate `Raises:` documentation and let lower-level helpers remain the source of truth
    for validation and invariants.
  - When a public façade or delegation helper intentionally documents propagated exceptions that are
    not raised syntactically in its own body, use a targeted `# noqa: DOC503` on the **closing
    docstring line** and include a short rationale.

- **Pre-commit**:

  - Pre-commit hooks are optional but recommended and primarily run Pyright, Ruff, Taplo, mdformat,
    pydoclint, TopMark header checks, and related hygiene tools.
  - We rely on Ruff to enforce import and typing style.

______________________________________________________________________

### Dependency versioning: ranges and locks

TopMark uses a two-layer dependency strategy:

- **`pyproject.toml`** defines *compatibility ranges*:

  - Runtime and extras are expressed as `>=` / `<` ranges (for example `click>=8.3.1,<9.0.0`).
  - This describes what TopMark is compatible with, without forcing users to install our exact dev
    versions.

- **`uv.lock`** holds the *resolved lock state*:

  - `uv.lock` is the committed dependency lock used as the canonical reproducible dependency graph.
  - CI, release automation, and local development all derive from this uv-managed lock workflow.

When updating dependencies:

1. Adjust **ranges** in `pyproject.toml` if compatibility changes.

1. Refresh the lock with:

   ```bash
   make uv-lock
   # or, to upgrade resolved versions within the allowed ranges:
   make uv-lock-upgrade
   ```

1. Commit both the updated `pyproject.toml` and `uv.lock` together.

______________________________________________________________________

## 🧠 Type Checking

Run strict **Pyright** type checks via `nox`:

```bash
nox -s qa -p 3.13
```

Or run all verification checks (format, lint, links, docs):

```bash
make verify
```

______________________________________________________________________

## 📚 Documentation

Build or serve the docs through tox:

```bash
make docs-build   # strict build (CI)
make docs-serve   # local live-reload server
```

Configuration-related documentation lives under `docs/configuration/` and reflects the TOML → Config
→ Runtime separation introduced in recent refactors.

MkDocs configuration lives in `mkdocs.yml`, and documentation dependencies are installed from the
`docs` extra declared in `pyproject.toml` and resolved through `uv.lock`.

______________________________________________________________________

## 🔒 API Stability

TopMark enforces a **stable public API** across Python 3.10–3.14.

```bash
make api-snapshot-dev         # quick local check
make api-snapshot             # tox matrix check
make api-snapshot-update      # regenerate snapshot (interactive)
make api-snapshot-ensure-clean  # fail if snapshot differs from Git index
```

If the snapshot changes **intentionally**, commit the updated JSON, update `CHANGELOG.md`, and make
sure the next release tag reflects the intended version stage. TopMark uses Git tags as the single
source of truth for versioning via `setuptools-scm`, so there is no manual version bump in
`pyproject.toml`.

______________________________________________________________________

## 📦 Packaging

TopMark follows PEP 517/518 standards.

Build and verify artifacts:

```bash
uv build
twine check dist/*
```

Upload to PyPI (or TestPyPI):

```bash
twine upload dist/*
# or:
twine upload --repository testpypi dist/*
```

Releases are typically handled by GitHub Actions when tags are pushed.

TopMark uses a two-stage release pipeline:

- CI (`ci.yml`) builds release artifacts (`sdist` and `wheel`) on tag pushes in an **unprivileged
  context** and uploads them as workflow artifacts.
- The release workflow (`release.yml`) runs in a **privileged `workflow_run` context**, downloads
  these artifacts, verifies version/tag consistency and checksums, and publishes them:
  - **prereleases** to [TestPyPI](https://test.pypi.org/project/topmark/)
  - **final releases** to [PyPI](https://pypi.org/project/topmark/)

This design ensures that repository build logic is never executed in the privileged release workflow
and aligns with GitHub security best practices and CodeQL recommendations.

TopMark uses **Git tags as the single source of truth** for package versions. Versions are derived
at build time via `setuptools-scm`, and built artifacts include generated version metadata.

______________________________________________________________________

## 🪝 Pre-commit Hooks

Pre-commit hooks are **optional but recommended**. They mirror the checks run by `make verify` and
`make lint`.

```bash
pre-commit install
pre-commit run --all-files
pre-commit autoupdate
```

Available hooks include:

- `topmark-check` — validates headers (non-destructive)
- `topmark-apply` — updates headers (manual only)
- Ruff (format/lint), Taplo, mdformat, Pyright, and hygiene checks

Run the TopMark fixer manually (`--hook-stage manual`):

```bash
pre-commit run topmark-apply --hook-stage manual --all-files
# Or target specific files:
pre-commit run topmark-apply --hook-stage manual --files path/to/file1 path/to/file2
```

______________________________________________________________________

## 💬 Commit & PR Guidelines

### Conventional Commits

Follow the [Conventional Commits](https://www.conventionalcommits.org/) standard:

```text
<type>[optional scope]: <short summary>

[optional body]
[optional footer(s)]
```

**Common types:**\
`feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert`

**Examples:**

- `feat(cli): add --skip-unsupported flag`
- `fix(renderer): avoid duplicate header insertion`

Keep messages short (≤72 chars) and use the body to explain *why*.

### Pull Request Checklist

- [ ] PR title follows Conventional Commits
- [ ] Linked issue referenced
- [ ] `make verify` and `make test` pass
- [ ] Docs updated if needed
- [ ] Public API snapshot updated if applicable
- [ ] Release tag / changelog plan is correct for release-related PRs

______________________________________________________________________

## 🧾 Versioning Policy

TopMark uses **Semantic Versioning (SemVer)** to describe compatibility intent:

- `fix:` → patch
- `feat:` → minor
- `feat!:` or `BREAKING CHANGE:` → major

Stable API: `topmark.api` and `topmark.registry.registry.Registry`\
Advanced/internal APIs may change between minor versions.

### PEP 440 and Git-tag-based versioning

TopMark uses [PEP 440](https://peps.python.org/pep-0440/) version identifiers for packaging, but
package versions are **not** maintained manually in `pyproject.toml`.

Instead, TopMark uses **Git tags as the single source of truth**:

- package versions are derived at build time via `setuptools-scm`
- runtime version reporting uses generated package version metadata
- release automation validates the SCM-derived artifact version against the release tag

Typical release tag forms used in this project are:

- Final releases: `vX.Y.Z`
- Alpha releases: `vX.Y.ZaN`
- Beta releases: `vX.Y.ZbN`
- Release candidates: `vX.Y.ZrcN`

Legacy dashed prerelease tags such as `vX.Y.Z-aN`, `vX.Y.Z-bN`, and `vX.Y.Z-rcN` remain supported
for backward compatibility, but compact PEP 440 tag forms are preferred for new releases.

Examples:

- `v1.0.0a1` → first alpha release
- `v1.0.0b1` → first beta release
- `v1.0.0rc1` → first release candidate
- `v1.0.0` → final release

Between tags, development builds may report SCM-derived versions such as:

- `1.0.0a1.dev3+g<commit>` (PEP 440)
- `1.0.0-dev.3+g<commit>` or equivalent project SemVer rendering, depending on CLI mode

### Before release

1. Refresh `tests/api/public_api_snapshot.json` if the public API changed.

1. Update `CHANGELOG.md`.

1. Commit the release-ready changes.

1. Create and push the intended release tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

> [!NOTE] CI must succeed on the tag push, including artifact upload, before the release workflow
> runs.

______________________________________________________________________

## 🧭 Troubleshooting

- **Missing tools:** run `make venv` then `make venv-sync-dev`
- **mkdocs errors:** run `make venv-sync-all` or `make docs-serve` to ensure the docs extras are
  installed
- **Python version errors:** install interpreters via `pyenv`
- **Permission issues (Windows):**\
  Run PowerShell as Administrator and execute\
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

______________________________________________________________________

Happy coding! 🎉
