# topmark:header:start
#
#   project      : TopMark
#   file         : Makefile
#   file_relpath : Makefile
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

.PHONY: \
	check-venv check-lychee \
	help \
	test verify lint lint-fixall \
	format-check format docstring-links \
	pytest \
	property-test \
	docs-build docs-serve docs-clean \
	links links-all links-site links-src \
	api-snapshot api-snapshot-dev api-snapshot-update api-snapshot-ensure-clean \
	venv venv-sync-dev venv-sync-dev-docs venv-sync-docs venv-clean \
	lock-compile-prod lock-compile-dev lock-compile-docs \
	lock-dry-run-prod lock-dry-run-dev lock-dry-run-docs \
	lock-upgrade-prod lock-upgrade-dev lock-upgrade-docs \
	package-check release-check release-full release-qa-api-%

.DEFAULT_GOAL := help
NOX ?= nox
NOX_FLAGS ?= --no-verbose       # keep quiet by default; CI can override
PYTEST_PAR ?= # e.g. set PYTEST_PAR="-n auto" or "-n 4"
PY ?= python
VENV := .venv
VENV_BIN := $(VENV)/bin

PUBLIC_API_JSON := tests/api/public_api_snapshot.json

# Simple tool presence checks
check-venv:
	@command -v $(NOX) >/dev/null 2>&1 || (echo "❌ nox not found. Install with: pipx install nox" && exit 1)

check-lychee:
	@command -v lychee >/dev/null 2>&1 || (echo "❌ lychee not found. Install with: brew install lychee" && exit 1)

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Core:"
	@echo "  test            Run the test suite (nox: qa)"
	@echo "  pytest          Run tests with current interpreter (no nox); supports PYTEST_PAR=-n auto"
	@echo "  verify          Run formatting checks, lint, and one typecheck env"
	@echo "  lint            Run ruff + pydoclint + mbake"
	@echo "  lint-fixall     Run ruff with --fix (auto-fix lint issues)"
	@echo "  format-check    Check code/markdown/toml/Makefile formatting"
	@echo "  format          Format code/markdown/toml/Makefile (auto-fix)"
	@echo "  docstring-links Enforce docstring link style (tools/check_docstring_links.py)"
	@echo "  property-test   Run Hypothesis hardening tests (manual, opt-in)"
	@echo ""
	@echo "  release-check   Run the deterministic pre-release gate (nox: release_check)"
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
	@echo "  venv            Create .venv with lock tooling (pip-tools)"
	@echo "  venv-sync-dev   pip-sync requirements-dev.txt into .venv"
	@echo "  venv-sync-dev-docs   pip-sync requirements-dev.txt and requirements-docs.txt into .venv"
	@echo "  venv-sync-docs  pip-sync requirements-docs.txt into .venv (removes DEV-only packages from .venv)"
	@echo "  venv-clean      Remove .venv"
	@echo ""
	@echo "Lock management (pip-compile; run manually when you choose to refresh pins):"
	@echo "  lock-compile-prod     requirements.in  -> requirements.txt"
	@echo "  lock-compile-dev      requirements-dev.in -> requirements-dev.txt"
	@echo "  lock-compile-docs     requirements-docs.in -> requirements-docs.txt"
	@echo ""
	@echo "  lock-dry-run-prod     Preview upgrades for prod lock (no file changes)"
	@echo "  lock-dry-run-dev      Preview upgrades for dev lock (no file changes)"
	@echo "  lock-dry-run-docs     Preview upgrades for docs lock (no file changes)"
	@echo ""
	@echo "  lock-upgrade-prod     Upgrade pins in requirements.txt"
	@echo "  lock-upgrade-dev      Upgrade pins in requirements-dev.txt"
	@echo "  lock-upgrade-docs     Upgrade pins in requirements-docs.txt"

test: check-venv
	@echo "Running tests via nox..."
	# We pass -- followed by the variable.
	# If PYTEST_PAR is empty, it does nothing; if it has "-n auto", pytest receives it.
	$(NOX) $(NOX_FLAGS) -s qa -- $(PYTEST_PAR)

verify: check-venv
	@echo "Running non-destructive checks via nox..."
	$(NOX) $(NOX_FLAGS) -s format_check -s lint -s docstring_links -s links -s docs
	@echo "All quality checks passed!"

release-check: check-venv
	@echo "Running release gate (deterministic) via nox..."
	$(NOX) $(NOX_FLAGS) -s release_check

package-check: check-venv
	@echo "Running packaging sanity checks via nox..."
	$(NOX) $(NOX_FLAGS) -s package_check

# Number of parallel jobs for matrix-style targets (used by release-full).
# Override at invocation time, e.g. `make release-full JOBS=5`.
JOBS ?= 5

# We can find the versions by asking Nox (which now knows them from the TOML)
# This keeps the Makefile clean.
RELEASE_PYTHONS := $(shell $(NOX) -l | awk '{print $$1}' | grep '^qa_api-' | cut -d'-' -f2 | sort -V)

release-full: check-venv check-lychee
	@echo "Running full release gate for versions: $(RELEASE_PYTHONS) (serial gates + parallel Python matrix)..."
	# Serial, non-matrix gates first:
	$(NOX) $(NOX_FLAGS) -s format_check -s lint -s docstring_links -s docs -s links_all -s package_check
	# Parallelize the per-Python QA+snapshot+typecheck gate across versions:
	$(MAKE) -j $(JOBS) $(addprefix release-qa-api-,$(RELEASE_PYTHONS))

# Per-Python release gate that reuses one env for: pytest + api snapshot + pyright
release-qa-api-%: check-venv
	@echo "QA+API snapshot (one env) for Python $*"
	$(NOX) $(NOX_FLAGS) -s qa_api -p $* -- $(PYTEST_PAR)

lint: check-venv
	$(NOX) $(NOX_FLAGS) -s lint

lint-fixall: check-venv
	$(NOX) $(NOX_FLAGS) -s lint_fixall

format-check: check-venv
	$(NOX) $(NOX_FLAGS) -s format_check

format: check-venv
	$(NOX) $(NOX_FLAGS) -s format

docstring-links: check-venv
	$(NOX) $(NOX_FLAGS) -s docstring_links

# Run pytest directly (no nox) with the current interpreter
pytest:
	pytest $(PYTEST_PAR) -q

property-test: check-venv
	$(NOX) $(NOX_FLAGS) -s property_test

docs-build: check-venv
	$(NOX) $(NOX_FLAGS) -s docs

docs-serve: check-venv
	$(NOX) $(NOX_FLAGS) -s docs_serve

docs-clean:
	rm -rf site

links: check-lychee
	$(NOX) $(NOX_FLAGS) -s links

links-src: check-lychee
	$(NOX) $(NOX_FLAGS) -s links_src

links-all: check-lychee
	$(NOX) $(NOX_FLAGS) -s links_all

links-site: check-lychee
	$(NOX) $(NOX_FLAGS) -s links_site

api-snapshot: check-venv
	$(NOX) $(NOX_FLAGS) -s api_snapshot

# Local fast check (current interpreter only)
api-snapshot-dev: check-venv
	@$(VENV_BIN)/pytest -qq tests/api/test_public_api_snapshot.py && \
	echo "✅ Public API snapshot unchanged."

# Update snapshot (interactive)
.api-snapshot-update: check-venv
	@$(VENV_BIN)/$(PY) tools/api_snapshot.py "$(PUBLIC_API_JSON)"
	@if git diff --quiet -- "$(PUBLIC_API_JSON)" ; then \
		echo "✅ Public API snapshot unchanged: $(PUBLIC_API_JSON)"; \
	else \
		git --no-pager diff -- "$(PUBLIC_API_JSON)"; \
		echo "⚠️  Public API snapshot UPDATED: $(PUBLIC_API_JSON)"; \
		echo "⚠️  Review diff, add $(PUBLIC_API_JSON) to git, bump version & update CHANGELOG."; \
	fi

api-snapshot-update:
	@read -p "⚠️  This will overwrite the public API snapshot. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	$(MAKE) .api-snapshot-update

# Fail if snapshot differs from index
api-snapshot-ensure-clean: check-venv
	@if git diff --quiet -- "$(PUBLIC_API_JSON)"; then \
		echo "✅ Public API snapshot clean: $(PUBLIC_API_JSON)"; \
	else \
		git --no-pager diff -- "$(PUBLIC_API_JSON)"; \
		echo "❌ Public API snapshot differs. Re-run: make api-snapshot-update"; \
		exit 1; \
	fi

# ---- Optional local convenience venv for editor / pyright (nox still runs checks) ----

# NOTE: Do NOT auto-upgrade pip here. New pip releases occasionally break pip-tools.
# The lock toolchain is managed via the project's `.[lock]` extra instead.
venv:
	@test -d $(VENV) || ( \
		echo "Creating $(VENV)..." && \
		$(PY) -m venv $(VENV) && \
		$(VENV_BIN)/pip install -e ".[lock]" \
		)
	@echo "Activate with: source $(VENV_BIN)/activate"

venv-sync-dev: venv
	$(VENV_BIN)/pip-sync requirements-dev.txt
	@echo "Synced dev deps into $(VENV)."

# Sync docs-only deps into the shared venv.
# NOTE: pip-sync enforces an exact set of packages; running this will remove dev-only tools
# not present in requirements-docs.txt. Prefer venv-sync-dev-docs for a combined environment.
venv-sync-docs: venv
	$(VENV_BIN)/pip-sync requirements-docs.txt
	@echo "Synced docs deps into $(VENV)."

# Sync the UNION of dev + docs deps into the shared venv.
# This is the recommended target for local MkDocs development and VS Code import resolution.
venv-sync-dev-docs: venv
	$(VENV_BIN)/pip-sync requirements-dev.txt requirements-docs.txt
	@echo "Synced dev+docs deps into $(VENV)."

venv-clean:
	@rm -rf $(VENV)
	@echo "Removed $(VENV)."

# ---- Lock management (pins). These do NOT affect nox; nox uses the compiled locks. ----
lock-compile-prod: venv
	$(VENV_BIN)/pip-compile -q -c constraints.txt --strip-extras requirements.in

lock-compile-dev: venv
	$(VENV_BIN)/pip-compile -q -c constraints.txt --strip-extras requirements-dev.in

lock-compile-docs: venv
	$(VENV_BIN)/pip-compile -q -c constraints.txt --strip-extras requirements-docs.in

# (Preview) dry-run upgrade helpers — show solver changes without writing files
lock-dry-run-prod: venv
	$(VENV_BIN)/pip-compile -U -c constraints.txt --strip-extras --dry-run requirements.in

lock-dry-run-dev: venv
	$(VENV_BIN)/pip-compile -U -c constraints.txt --strip-extras --dry-run requirements-dev.in

lock-dry-run-docs: venv
	$(VENV_BIN)/pip-compile -U -c constraints.txt --strip-extras --dry-run requirements-docs.in

# Upgrade helpers — write solver changes to files:
lock-upgrade-prod: venv
	$(VENV_BIN)/pip-compile -U -c constraints.txt --strip-extras requirements.in

lock-upgrade-dev: venv
	$(VENV_BIN)/pip-compile -U -c constraints.txt --strip-extras requirements-dev.in

lock-upgrade-docs: venv
	$(VENV_BIN)/pip-compile -U -c constraints.txt --strip-extras requirements-docs.in
