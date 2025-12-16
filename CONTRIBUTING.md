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
This guide explains how to set up your environment, run checks, contribute code, and prepare releases.

______________________________________________________________________

## 🧰 Prerequisites

- **Python 3.10–3.14**
- **Git**
- **make** (for convenience targets)
- **tox** (`pipx install tox` or `pip install tox`)
- **pip-tools ≥ 7.4** (installed automatically by `make venv`)

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

> **Note**: `.venv` is for IDE and Pyright support; tox runs isolated environments for checks.

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

TopMark treats Ruff, Pyright, and the supporting tools as the single source of truth
for code style and typing rules:

- **Ruff**:

  - Enforces import style and modern syntax via the `UP` ruleset (pyupgrade), including:
    - Using builtin generics (`list[...]`, `dict[...]`, `tuple[...]`) instead of
      `typing.List` / `typing.Dict` / `typing.Tuple`.
    - Importing abstract collections from `collections.abc` (e.g. `Iterable`, `Mapping`,
      `Sequence`, `Callable`, `Iterator`) rather than from `typing`.
  - Enforces moving type-only imports under `if TYPE_CHECKING:` via the `TC` rules.
  - Acts as the primary linter for style, unused code, and import ordering.

- **Typing imports**:

  - Reserve `typing` imports for: `TYPE_CHECKING`, `Any`, `Final`, `Literal`, `Protocol`,
    `TypedDict`, `TypeVar`, `ParamSpec`, `TypeGuard`, `NamedTuple`, `TextIO`, `IO`,
    and `cast`.
  - Import abstract collections from `collections.abc` (not from `typing`).
  - Prefer PEP 604 unions (e.g. `X | None`) over `typing.Optional[X]`.

- **Type checking**:

  - Pyright runs in `strict` mode for `src/` and `tests/`.
  - Public APIs must be fully annotated and pass Pyright without `# type: ignore`
    (exceptions must be documented and justified in code comments).

- **Docstrings**:

  - Use Google-style docstrings with explicit `Args:`, `Returns:`, and `Raises:` sections
    for public functions, methods, and classes.
  - Keep docstrings import-safe: avoid heavy imports or side effects at module import time.

- **Pre-commit**:

  - Pre-commit hooks are optional but recommended and primarily run Ruff, Taplo, mdformat,
    TopMark header checks, and related hygiene tools.
  - We rely on Ruff (with `UP`/`TC` enabled) to enforce import/typing style; no additional
    grep-based hooks for typing/collections imports are needed.

______________________________________________________________________

### Dependency versioning: ranges vs pins

TopMark uses a two-layer dependency strategy:

- **`pyproject.toml`** defines *compatibility ranges*:

  - Runtime and extras are expressed as `>=` / `<` ranges (for example
    `click>=8.3.1,<9.0.0`).
  - This describes what TopMark is compatible with, without forcing users to
    install our exact dev versions.

- **`requirements*.txt`** (generated via `pip-tools`) hold *exact pins*:

  - `requirements.txt` and `requirements-dev.txt` are compiled from
    `pyproject.toml` and are used for local development, CI, and tox.
  - They contain `==` pins and act as the reproducible snapshot of the
    dependencies we actually test against.

When updating dependencies:

1. Adjust **ranges** in `pyproject.toml` if compatibility changes.
1. Regenerate **pins** with `pip-compile` (see comments at the top of each
   `requirements*.txt` file).
1. Commit both the updated `pyproject.toml` and requirements files together.

______________________________________________________________________

## 🧠 Type Checking

Run strict **Pyright** type checks via tox:

```bash
tox -e py313-typecheck
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

MkDocs configuration lives in `mkdocs.yml`, with dependencies pinned in `requirements-docs.txt`.

______________________________________________________________________

## 🔒 API Stability

TopMark enforces a **stable public API** across Python 3.10–3.14.

```bash
make api-snapshot-dev         # quick local check
make api-snapshot             # tox matrix check
make api-snapshot-update      # regenerate snapshot (interactive)
make api-snapshot-ensure-clean  # fail if snapshot differs from Git index
```

If the snapshot changes **intentionally**, commit the updated JSON and bump the version in `pyproject.toml`.

______________________________________________________________________

## 📦 Packaging

TopMark follows PEP 517/518 standards.

Build and verify artifacts:

```bash
python -m build
python -m twine check dist/*
```

Upload to PyPI (or TestPyPI):

```bash
python -m twine upload dist/*
# or:
python -m twine upload --repository testpypi dist/*
```

Releases are typically handled by GitHub Actions when tags are pushed.

______________________________________________________________________

## 🪝 Pre-commit Hooks

Pre-commit hooks are **optional but recommended**. They mirror the checks run by `make verify` and `make lint`.

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
- [ ] Version bumped in `pyproject.toml` for releases

______________________________________________________________________

## 🧾 Versioning Policy

TopMark uses **Semantic Versioning (SemVer)**:

- `fix:` → patch
- `feat:` → minor
- `feat!:` or `BREAKING CHANGE:` → major

Stable API: `topmark.api` and `topmark.registry.Registry`\
Advanced/internal APIs may change between minor versions.

Before release:

1. Refresh `tests/api/public_api_snapshot.json`

1. Bump version in `pyproject.toml`

1. Commit and tag:

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

______________________________________________________________________

## 🧭 Troubleshooting

- **Missing tools:** run `make venv` then `make venv-sync-dev`
- **mkdocs errors:** try `make docs-serve` to detect missing plugins
- **Python version errors:** install interpreters via `pyenv`
- **Permission issues (Windows):**\
  Run PowerShell as Administrator and execute\
  `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

______________________________________________________________________

Happy coding! 🎉
