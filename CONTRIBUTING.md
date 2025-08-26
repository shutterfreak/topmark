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
- Ruff (format & lint), mypy, Pyright, Taplo, mdformat, plus standard hygiene hooks.

**Why are there repeated banners during hooks?** Pre-commit batches filenames to respect OS argument
limits, so hooks may run multiple times per invocation. We keep the output quiet in hooks using
`--quiet`.

**Run TopMark’s manual fixer via pre-commit** (if enabled locally):

```bash
pre-commit run topmark-apply --all-files --hook-stage manual
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
- [ ] **Tests added/updated and `make test` passes**
- [ ] **Ran `pre-commit run --all-files`** (or `make pre-commit-run`)
- [ ] **Docs updated as needed**
  - [ ] README
  - [ ] `docs/usage/*`
  - [ ] examples
- [ ] **User-facing changes called out** in the PR description (new flags/behavior)
- [ ] **Version updated** in `pyproject.toml` if preparing a release
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
version = "0.2.0"
```

______________________________________________________________________

## 🧩 TopMark configuration (this repo)

TopMark reads configuration from `[tool.topmark]` in `pyproject.toml` (or a `topmark.toml`). Useful
CLI flags:

- `--skip-compliant` — only show files requiring changes
- `--skip-unsupported` — hide recognized‑but‑unsupported formats (e.g., strict JSON)
- `--apply` — perform changes (otherwise dry-run)

CI-friendly check:

```bash
topmark check --skip-compliant --skip-unsupported --quiet
```

______________________________________________________________________

## 🛠 Make targets cheat-sheet

```sh
# Setup
make venv              # create .venv + pip-tools
make setup             # venv + compile locks + sync dev

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
