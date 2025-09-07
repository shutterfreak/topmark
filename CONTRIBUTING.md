<!--
topmark:header:start

  file         : CONTRIBUTING.md
  file_relpath : CONTRIBUTING.md
  project      : TopMark
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Contributing to TopMark

Thanks for your interest in **TopMark**! This guide explains how to set up your environment, run
quality checks, work with documentation, and use the pre-commit hooks. It mirrors the automation
available in the **Makefile** and the repo’s **pre-commit** config.

## 📂 Where things live

- **README.md** — overview, features, usage, examples
- **INSTALL.md** — installation & development setup
- **CONTRIBUTING.md** — contributor guide (this file)
- **docs/** — MkDocs documentation site
  - **docs/index.md** — docs landing page
  - **docs/usage/** — detailed usage guides (pre-commit, header placement, file types, …)
  - **docs/ci/** — CI/CD workflows
  - **docs/api/** — API reference
- **Makefile** — development automation (setup, lint, test, docs, packaging)
- **.pre-commit-config.yaml** — enabled hooks for this repo
- **.pre-commit-hooks.yaml** — hook definitions exported to consumer repos

______________________________________________________________________

## 🧰 Prerequisites

- Python **3.10–3.13** (use `pyenv` if you plan to run `tox` across versions)
- `virtualenv` (or an equivalent tool)
- `make`

Optional:

- `pre-commit` (global install not required; the Makefile uses the venv)
- `pyenv` (for managing multiple Python versions)

______________________________________________________________________

## 🚀 Quick start

```bash
# 1) Clone and enter the repo
git clone https://github.com/shutterfreak/topmark.git
cd topmark

# 2) Create a dev environment and install tooling
make setup                   # venv + compile lock files + sync dev deps
# 2b) (Optional) install TopMark in editable mode to run the CLI from your checkout
make dev-install

# 3) Install Git hooks and (optionally) refresh hook versions
make pre-commit-install      # install the pre-commit hooks
make pre-commit-autoupdate   # update the pre-commit hook repo versions

# 4) Verify everything (format check, lint, types, docs build)
make verify
```

> ℹ️ `make compile` / `make compile-dev` use `pip-compile --strip-extras` to keep lock files
> reproducible.
>
> ⚠️ Use `pip-tools >= 7.4` to avoid deprecation warnings.

### ▶ Run the CLI from your checkout (optional)

If you want to execute `topmark` from this working tree, install it in editable mode:

```bash
make dev-install
```

Verify:

```bash
topmark version
```

______________________________________________________________________

## 🧪 Tests

Run the test suite:

```bash
make test
```

### Python version compatibility

TopMark supports Python 3.10–3.13.

To ensure compatibility, use [tox](https://tox.wiki/) to run tests and type checks across all
supported versions.

You must install the required Python versions prior to testing with `tox`. With `pyenv`:

```bash
# Install interpreters (examples)
pyenv install 3.10.14 3.11.9 3.12.5 3.13.0

# Make them visible in this repo (so tox finds all versions):
pyenv local 3.10.14 3.11.9 3.12.5 3.13.0

# or for the current shell:
pyenv shell 3.10.14 3.11.9 3.12.5 3.13.0

# Run
tox                # all envs (tests + type checks)
tox -e py311       # a single env
tox run-parallel   # parallel run
```

______________________________________________________________________

## 🎨 Formatting & linting

We keep the codebase tidy with:

- **Ruff** (format + lint)
- **Pyright** and **mypy** (static typing)
- **mdformat** (+tables) for Markdown
- **Taplo** for TOML

Common tasks:

```bash
make format         # apply formatting (code, Markdown, TOML)
make format-check   # check formatting without changing files
make lint           # ruff + pyright + mypy
make lint-fixall    # auto-fix fixable lint issues (ruff)
```

Markdown formatting is handled by `mdformat` with the `mdformat-tables` plugin, and configuration is
read from `pyproject.toml`.

Taplo schema catalog lookups are disabled to avoid CI timeouts; see `[tool.taplo.schemas]` in
`pyproject.toml`.

______________________________________________________________________

## 📚 Documentation

Docs are built with **MkDocs (Material)** and **mkdocstrings** using a dedicated env `.rtd`.

```bash
make rtd-venv       # create .rtd and install docs extras
make docs-serve     # live-reload dev server
make docs-build     # strict build into ./site
make docs-deploy    # deploy to GitHub Pages (gh-pages)
```

- Navigation: `mkdocs.yml`
- Pre-commit guide: `docs/usage/pre-commit.md` (full guide)

______________________________________________________________________

## 🪝 Pre-commit hooks

Install and run:

```bash
make pre-commit-install
pre-commit run --all-files
```

Clean caches / update hook repos:

```bash
make pre-commit-clean
make pre-commit-autoupdate
```

**Hooks in this repo** (see `.pre-commit-config.yaml`):

- **`topmark-check`** — validates headers (non-destructive). Runs on `pre-commit` / `pre-push`.
- **`topmark-apply`** — inserts/updates headers. **Manual** only by default; may modify files.
- Ruff (format & lint), mypy, Pyright, Taplo, mdformat, plus standard hygiene hooks.

**Why are there repeated banners during hooks?** Pre-commit batches filenames to respect OS argument
limits, so hooks may run multiple times per invocation. We keep the output quiet in hooks using
`--quiet`.

**Run TopMark’s manual fixer via pre-commit** (if enabled locally):

```bash
pre-commit run topmark-apply --all-files --hook-stage manual
# Or target specific files:
pre-commit run topmark-apply -- path/to/file1 path/to/file2
```

______________________________________________________________________

## 🧾 Commit & PR guidelines

- Keep commits focused; use clear, imperative messages.
- Include tests and docs when changing behavior.
- Ensure `make verify` passes before opening a PR.
- Call out breaking changes clearly.

### Conventional Commits

Please format commit messages according to the Conventional Commits spec:

```text
<type>[optional scope]: <short summary>

[optional body]

[optional footer(s)]
```

- **Common types:** `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`,
  `chore`, `revert`
- **Examples**
  - `feat(cli): add --skip-unsupported flag`
  - `fix(renderer): avoid duplicating header when shebang present`
  - `docs(pre-commit): document manual topmark-apply invocation`
  - `ci(release): publish wheels for py3.13`

> Tip: keep subject lines ≤ 72 chars; use the body for motivation and tradeoffs.

### Pull Request checklist

Use this checklist before requesting review:

- [ ] **PR title follows Conventional Commits** (e.g., `feat: add pre-commit hook`)
- [ ] **Linked issue referenced** (e.g., `Closes #123`)
- [ ] **`make verify` passes locally** (format, lint, types, docs build)
- [ ] **Tests added/updated** for code changes **and `make test` passes**
- [ ] **Ran `pre-commit run --all-files`** (or `make pre-commit-run`)
- [ ] **Docs updated as needed**
  - [ ] README
  - [ ] `docs/usage/*`
  - [ ] examples
- [ ] **User-facing changes called out** in the PR description (new flags/behavior)
- [ ] **Version updated** in `pyproject.toml` if preparing a release
- [ ] **Public API snapshot updated** if stable API surface changed (see
  tests/api/test_public_api_snapshot.py)
- [ ] **Commits are focused**; squashed/rebased where appropriate

## 📦 Build

TopMark follows [PEP 517/518](https://peps.python.org/pep-0517/) standards.

To build source and wheel distributions:

```bash
make build
```

This creates a `dist/` folder containing `.tar.gz` and `.whl` files.

______________________________________________________________________

## 🚀 Publish to PyPI

Releases are handled by **GitHub Actions** (see `.github/workflows/release.yml`). Releases are
triggered by pushing a tag:

- `vX.Y.Z-rcN` → publish release candidate to **TestPyPI**
- `vX.Y.Z` → publish to **PyPI** and create a GitHub Release

Manual uploads (less common):

```bash
.venv/bin/twine check dist/*
.venv/bin/twine upload dist/*
# or: .venv/bin/twine upload --repository testpypi dist/*
```

______________________________________________________________________

## 📄 Versioning

Update the version in `pyproject.toml` before tagging:

```toml
[project]
version = "0.3.1"
```

### 🔒 Stability policy

TopMark follows **semantic versioning** for its public Python surfaces:

- **Stable**: `topmark.api` (functions, return types) and the facade `topmark.registry.Registry`.
- **Advanced** (subject to change between minor versions): low-level registries `FileTypeRegistry`
  and `HeaderProcessorRegistry`, and internal modules under `topmark.pipeline` and
  `topmark.filetypes`.

Mutation helpers exposed on the facade (e.g., `Registry.register_filetype`) are part of the public
API but mutate **global process state**. Prefer using them in tests and controlled plugin
initialization paths.

**Breaking changes** to stable surfaces require a **major** version bump.

### 🧪 SemVer guardrails during development

We enforce API stability with tests and CI checks:

1. **Public import smoke tests** — ensure `from topmark import api` and
   `from topmark.registry import Registry` remain valid.
1. **Facade shape tests** — check that `Registry.filetypes()`, `Registry.processors()` and
   `Registry.bindings()` expose read-only mappings/tuples as expected.
1. **Public API snapshot (optional gate)** — `tests/api/test_public_api_snapshot.py` compares
   current public function signatures (and facade methods) with a committed JSON baseline
   (`tests/api/public_api_snapshot.json`).
   - Day-to-day development: the test **skips** if the baseline is absent.
   - Before release: generate the baseline (instructions are in the test docstring), commit it, and
     ensure the test passes.
1. **CI version bump check (recommended)** — in CI, if the snapshot file changes in a PR, require
   that `project.version` in `pyproject.toml` is bumped accordingly.

#### Conventional Commits → SemVer mapping

- `fix:` → patch
- `feat:` → minor (unless it breaks the stable API)
- `feat!:` or `BREAKING CHANGE:` → major
- `refactor:`, `perf:`, `docs:`, `test:`, `build:`, `ci:`, `chore:` → no version bump by themselves,
  unless they impact the stable API surface.

#### Release checklist additions

- Generate/refresh `tests/api/public_api_snapshot.json` and commit it.
- Confirm `pyproject.toml` version is bumped to reflect the change type.

______________________________________________________________________

## 🛠 Make targets cheat-sheet

```sh
# Setup
make venv              # create .venv + pip-tools
make setup             # venv + compile locks + sync dev
make dev-install       # install TopMark in editable mode into .venv

# Dev deps
make compile-dev       # compile requirements-dev.txt
make dev               # sync .venv with dev requirements
make upgrade-dev       # upgrade and sync dev env

# Quality
make format            # format code/markdown/toml
make format-check      # check formatting only
make lint              # ruff + pyright + mypy
make lint-fixall       # autofix lint issues (ruff)
make test              # run tests
make verify            # non-destructive checks + docs build

# Docs
make rtd-venv          # create .rtd docs env
make docs-serve        # serve with live reload
make docs-build        # strict build
make docs-deploy       # gh-pages deploy

# Hooks
make pre-commit-install
make pre-commit-run
make pre-commit-autoupdate
make pre-commit-refresh
make pre-commit-clean
make pre-commit-uninstall

# Packaging
make build             # wheel + sdist
make git-archive       # time-stamped git archive
make source-snapshot   # snapshot current working tree
```

______________________________________________________________________

## ❓ Troubleshooting

If you’re stuck, open an issue with your OS, Python version, and the command you ran:
<https://github.com/shutterfreak/topmark/issues>.

Happy coding! 🎉
