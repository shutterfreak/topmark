# topmark:header:start
#
#   project      : TopMark
#   file         : Makefile
#   file_relpath : Makefile
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

.DEFAULT_GOAL := help
NOX ?= nox
NOX_FLAGS ?= --no-verbose       # keep quiet by default; CI can override
PYTEST_PAR ?= # e.g. set PYTEST_PAR="-n auto" or "-n 4" for pytest-capable targets
PY ?= python
VENV := .venv
VENV_BIN := $(VENV)/bin
UV ?= uv

PUBLIC_API_JSON := tests/api/public_api_snapshot.json

# Simple tool presence checks
.PHONY: check-venv
check-venv:
	@command -v $(NOX) >/dev/null 2>&1 || (echo "❌ nox not found. Install with: pipx install nox" && exit 1)

.PHONY: check-lychee
check-lychee:
	@command -v lychee >/dev/null 2>&1 || (echo "❌ lychee not found. Install with: brew install lychee" && exit 1)

.PHONY: check-uv
check-uv:
	@command -v $(UV) >/dev/null 2>&1 || (echo "❌ uv not found. Install uv and ensure it is on PATH." && exit 1)

.PHONY: help
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Core:"
	@echo "  verify          Run formatting checks, lint, and one typecheck env"
	@echo "  pre-pr          Run the recommended local pre-PR gate; supports PYTEST_PAR=-n auto"
	@echo "  lint            Run ruff + pydoclint + mbake"
	@echo "  lint-fixall     Run ruff with --fix (auto-fix lint issues)"
	@echo "  format-check    Check code/markdown/toml/Makefile formatting"
	@echo "  format          Format code/markdown/toml/Makefile (auto-fix)"
	@echo "  format-docstrings  Auto-format docstrings using pydocstringformatter"
	@echo "  docstring-links Enforce Python docstring link style"
	@echo "  docs-hygiene    Check Markdown/MkDocs documentation hygiene"
	@echo "  code-hygiene    Check Python comments/docstrings/string prose hygiene"
	@echo "  hygiene         Run all prose/documentation hygiene checks"
	@echo "Tests:"
	@echo "  test            Run the test suite (nox: qa); supports PYTEST_PAR=-n auto"
	@echo "  pytest          Run tests with current interpreter (no nox), skipping Hypothesis slow tests; supports PYTEST_PAR=-n auto"
	@echo "  pytest-full     Run all tests with current interpreter (no nox); supports PYTEST_PAR=-n auto"
	@echo "  coverage        Run coverage testing; supports PYTEST_PAR=-n auto"
	@echo "  coverage-erase  Erase coverage testing output (.coverage coverage.xml coverage.json htmlcov .coverage.*)"
	@echo "  property-test   Run Hypothesis hardening tests (manual, opt-in)"
	@echo "  perf-baseline   Run pipeline memory/allocation baselines (manual, opt-in)"
	@echo ""
	@echo "  release-check   Run the deterministic pre-release gate; supports PYTEST_PAR=-n auto"
	@echo "  release-full    Run the full release gate incl. links + packaging + Python matrix"
	@echo ""
	@echo "  package-check   Run package sanity checks (nox: package_check)"
	@echo ""
	@echo "Docs:"
	@echo "  docs-build      Build docs strictly (nox: docs)"
	@echo "  docs-serve      Serve docs locally (nox: docs_serve)"
	@echo "  docs-clean      Remove MkDocs build output (site/)"
	@echo ""
	@echo "Misc:"
	@echo "  links           Check links in docs/ and tracked Markdown (nox: links)"
	@echo "  links-src       Check links found in Python docstrings under src/ (nox: links_src)"
	@echo "  links-all       Check links in docs/, tracked Markdown, and Python docstrings (nox: links_all)"
	@echo "  links-site      Check links in the built MkDocs site (includes generated pages)"
	@echo ""
	@echo "  api-snapshot-dev         Check API snapshot with current interpreter (fast local)"
	@echo "  api-snapshot             Check API snapshot across all supported Pythons (nox: api_snapshot)"
	@echo "  api-snapshot-update      Regenerate tests/api/public_api_snapshot.json (interactive)"
	@echo "  api-snapshot-ensure-clean  Fail if snapshot differs from Git index"
	@echo ""
	@echo "Local editor venv (optional, for Pyright/import resolution in IDE):"
	@echo "  venv            Create .venv via uv"
	@echo "  venv-sync-dev   Sync dev/test/typing extras into .venv"
	@echo "  venv-sync-all   Sync dev/test/typing/docs extras into .venv"
	@echo "  venv-sync-docs  Sync docs extras into .venv (removes DEV-only packages from .venv)"
	@echo "  venv-clean      Remove .venv"
	@echo ""
	@echo "UV project lock workflow:"
	@echo "  uv-lock         Generate or refresh uv.lock from pyproject.toml"
	@echo "  uv-lock-upgrade Refresh uv.lock with dependency upgrades"

.PHONY: test
test: check-venv
	@echo "Running tests via nox..."
	# We pass -- followed by the variable.
	# If PYTEST_PAR is empty, it does nothing; if it has "-n auto", pytest receives it.
	$(NOX) $(NOX_FLAGS) -s qa -- $(PYTEST_PAR)

.PHONY: coverage
coverage: check-venv
	$(NOX) $(NOX_FLAGS) -s coverage -- $(PYTEST_PAR)

.PHONY: coverage-erase
coverage-erase:
	@rm -rf .coverage coverage.xml coverage.json htmlcov .coverage.*

.PHONY: verify
verify: check-venv
	@echo "Running non-destructive checks via nox..."
	$(NOX) $(NOX_FLAGS) -s format_check -s lint -s docstring_links -s docs_hygiene -s code_hygiene -s links -s docs
	@echo "All quality checks passed!"

.PHONY: pre-pr
pre-pr: check-venv
	@echo "Running recommended local pre-PR validation via nox..."
	$(NOX) $(NOX_FLAGS) -s pre_pr -- $(PYTEST_PAR)

.PHONY: release-check
release-check: check-venv
	@echo "Running release gate (deterministic) via nox..."
	$(NOX) $(NOX_FLAGS) -s release_check -- $(PYTEST_PAR)

.PHONY: package-check
package-check: check-venv
	@echo "Running packaging sanity checks via nox..."
	$(NOX) $(NOX_FLAGS) -s package_check

# Number of parallel jobs for matrix-style targets (used by release-full).
# Override at invocation time, e.g. `make release-full JOBS=5`.
JOBS ?= 5

# We can find the versions by asking Nox (which now knows them from the TOML)
# This keeps the Makefile clean.
RELEASE_PYTHONS := $(shell $(NOX) -l | awk '{print $$1}' | grep '^qa_api-' | cut -d'-' -f2 | sort -V)

.PHONY: release-full
release-full: check-venv check-lychee
	@echo "Running full release gate for versions: $(RELEASE_PYTHONS) (serial gates + parallel Python matrix)..."
	# Serial, non-matrix gates first:
	$(NOX) $(NOX_FLAGS) -s format_check -s lint -s docstring_links -s docs_hygiene -s code_hygiene -s docs -s links_all -s package_check
	# Parallelize the per-Python QA+snapshot+typecheck gate across versions:
	$(MAKE) -j $(JOBS) $(addprefix release-qa-api-,$(RELEASE_PYTHONS))

# Per-Python release gate that reuses one env for: pytest + api snapshot + pyright
release-qa-api-%: check-venv
	@echo "QA+API snapshot (one env) for Python $*"
	$(NOX) $(NOX_FLAGS) -s qa_api -p $* -- $(PYTEST_PAR)

.PHONY: lint
lint: check-venv
	$(NOX) $(NOX_FLAGS) -s lint

.PHONY: lint-fixall
lint-fixall: check-venv
	$(NOX) $(NOX_FLAGS) -s lint_fixall

.PHONY: format-check
format-check: check-venv
	$(NOX) $(NOX_FLAGS) -s format_check

.PHONY: format
format: check-venv
	$(NOX) $(NOX_FLAGS) -s format

.PHONY: format-docstrings
format-docstrings: check-uv
	@echo "Auto-formatting docstrings (settings from pyproject.toml)..."
	$(VENV_BIN)/pydocstringformatter --write src/topmark/ tools/

.PHONY: docstring-links
docstring-links: check-venv
	$(NOX) $(NOX_FLAGS) -s docstring_links

.PHONY: docs-hygiene
docs-hygiene: check-venv
	$(NOX) $(NOX_FLAGS) -s docs_hygiene

.PHONY: code-hygiene
code-hygiene:
	$(NOX) $(NOX_FLAGS) -s code_hygiene

.PHONY: hygiene
hygiene: docs-hygiene code-hygiene

# Run pytest directly (no nox) with the current interpreter
.PHONY: pytest
pytest:
	@echo "Running pytest locally -- skipping Hypothesis slow tests"
	pytest $(PYTEST_PAR) -m "not hypothesis_slow" -q

.PHONY: pytest-full
pytest-full:
	@echo "Running all pytest locally -- including Hypothesis slow tests"
	pytest $(PYTEST_PAR) -q

.PHONY: property-test
property-test: check-venv
	$(NOX) $(NOX_FLAGS) -s property_test

.PHONY: perf-baseline
perf-baseline: check-venv
	$(NOX) $(NOX_FLAGS) -s perf_baseline

.PHONY: docs-build
docs-build: check-venv
	$(NOX) $(NOX_FLAGS) -s docs

.PHONY: docs-serve
docs-serve: check-venv
	$(NOX) $(NOX_FLAGS) -s docs_serve

.PHONY: docs-clean
docs-clean:
	rm -rf site

.PHONY: links
links: check-lychee
	$(NOX) $(NOX_FLAGS) -s links

.PHONY: links-src
links-src: check-lychee
	$(NOX) $(NOX_FLAGS) -s links_src

.PHONY: links-all
links-all: check-lychee
	$(NOX) $(NOX_FLAGS) -s links_all

.PHONY: links-site
links-site: check-lychee
	$(NOX) $(NOX_FLAGS) -s links_site

.PHONY: api-snapshot
api-snapshot: check-venv
	$(NOX) $(NOX_FLAGS) -s api_snapshot

# Local fast check (current interpreter only)
.PHONY: api-snapshot-dev
api-snapshot-dev: check-venv
	@$(VENV_BIN)/pytest -qq tests/api/test_public_api_snapshot.py && \
	echo "✅ Public API snapshot unchanged."

# Update snapshot (interactive)
.PHONY: .api-snapshot-update
.api-snapshot-update: check-venv
	@$(VENV_BIN)/$(PY) tools/api_snapshot.py "$(PUBLIC_API_JSON)"
	@if git diff --quiet -- "$(PUBLIC_API_JSON)" ; then \
		echo "✅ Public API snapshot unchanged: $(PUBLIC_API_JSON)"; \
	else \
		git --no-pager diff -- "$(PUBLIC_API_JSON)"; \
		echo "⚠️  Public API snapshot UPDATED: $(PUBLIC_API_JSON)"; \
		echo "⚠️  Review diff, add $(PUBLIC_API_JSON) to git, bump version & update CHANGELOG."; \
	fi

.PHONY: api-snapshot-update
api-snapshot-update:
	@read -p "⚠️  This will overwrite the public API snapshot. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	$(MAKE) .api-snapshot-update

# Fail if snapshot differs from index
.PHONY: api-snapshot-ensure-clean
api-snapshot-ensure-clean: check-venv
	@if git diff --quiet -- "$(PUBLIC_API_JSON)"; then \
		echo "✅ Public API snapshot clean: $(PUBLIC_API_JSON)"; \
	else \
		git --no-pager diff -- "$(PUBLIC_API_JSON)"; \
		echo "❌ Public API snapshot differs. Re-run: make api-snapshot-update"; \
		exit 1; \
	fi

#
# ---- Optional local convenience venv for editor / pyright ----
#
# Local editor venv bootstrap.
# We keep a project-local .venv for IDE integration, and let uv manage it directly.
.PHONY: venv
venv: check-uv
	@test -d $(VENV) || ( \
		echo "Creating $(VENV) via uv..." && \
		$(UV) venv $(VENV) \
		)
	@echo "Activate with: source $(VENV_BIN)/activate"

.PHONY: venv-sync-dev
venv-sync-dev: venv
	$(UV) sync --extra dev --extra typing --extra test
	@echo "Synced dev/test/typing extras into $(VENV)."

# Sync docs-only extras into the shared venv.
# NOTE: running this will remove dev/test/typing tools which are not part of the docs environment.
# Prefer venv-sync-all for a combined environment.
.PHONY: venv-sync-docs
venv-sync-docs: venv
	$(UV) sync --extra docs
	@echo "Synced docs extras into $(VENV)."

# Sync the union of dev/test/typing/docs extras into the shared venv.
# This is the recommended target for local MkDocs development and VS Code import resolution.
.PHONY: venv-sync-all
venv-sync-all: venv
	$(UV) sync --extra dev --extra typing --extra test --extra docs
	@echo "Synced dev/test/typing/docs extras into $(VENV)."

.PHONY: venv-clean
venv-clean:
	@rm -rf $(VENV)
	@echo "Removed $(VENV)."

#
# ---- UV project lock workflow (canonical dependency management) ----
.PHONY: uv-lock
uv-lock: check-uv
	$(UV) lock

.PHONY: uv-lock-upgrade
uv-lock-upgrade: check-uv
	$(UV) lock --upgrade
