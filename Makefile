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
	links links-src links-all \
	api-snapshot api-snapshot-dev api-snapshot-update api-snapshot-ensure-clean \
	venv venv-sync-dev venv-clean \
	lock-compile-prod lock-compile-dev lock-compile-docs \
	lock-dry-run-prod lock-dry-run-dev lock-dry-run-docs \
	lock-upgrade-prod lock-upgrade-dev lock-upgrade-docs

.DEFAULT_GOAL := help
TOX ?= tox
TOX_PAR ?=            # e.g. set TOX_PAR="-p auto" or "-p 4"
TOX_FLAGS ?= -q       # keep your quiet flag; CI can override
PYTEST_PAR ?=         # e.g. set PYTEST_PAR="-n auto" or "-n 4"
PY ?= python
VENV := .venv
VENV_BIN := $(VENV)/bin

PUBLIC_API_JSON := tests/api/public_api_snapshot.json

# Simple tool presence checks
check-venv:
	@command -v $(TOX) >/dev/null 2>&1 || (echo "❌ tox not found. Install with: pipx install tox" && exit 1)

check-lychee:
	@command -v lychee >/dev/null 2>&1 || (echo "❌ lychee not found. Install with: brew install lychee" && exit 1)

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Core:"
	@echo "  test            Run the test suite (tox default envs)"
	@echo "  pytest          Run tests with current interpreter (no tox); supports PYTEST_PAR=-n auto"
	@echo "  verify          Run formatting checks, lint, and one typecheck env"
	@echo "  lint            Run ruff + pydoclint"
	@echo "  lint-fixall     Run ruff with --fix (auto-fix lint issues)"
	@echo "  format-check    Check code/markdown/toml formatting"
	@echo "  format          Format code/markdown/toml (auto-fix)"
	@echo "  docstring-links Enforce docstring link style (tools/check_docstring_links.py)"
	@echo "  property-test   Run Hypothesis hardening tests (manual, opt-in)"
	@echo ""
	@echo "Docs:"
	@echo "  docs-build      Build docs strictly (tox: docs)"
	@echo "  docs-serve      Serve docs locally (tox: docs-serve)"
	@echo "  docs-clean      Remove MkDocs build output (site/)"
	@echo ""
	@echo "Misc:"
	@echo "  links           Check links in docs/ and *.md (tox: links)"
	@echo "  links-src       Check links found in Python docstrings under src/ (tox: links-src)"
	@echo "  links-all       Check links in docs/, *.md, and Python docstrings (tox: links-all)"
	@echo "  api-snapshot-dev         Check API snapshot with current interpreter (fast local)"
	@echo "  api-snapshot             Check API snapshot across all supported Pythons (tox label)"
	@echo "  api-snapshot-update      Regenerate tests/api/public_api_snapshot.json (interactive)"
	@echo "  api-snapshot-ensure-clean  Fail if snapshot differs from Git index"
	@echo ""
	@echo "Local editor venv (optional, for Pyright/import resolution in IDE):"
	@echo "  venv            Create .venv with pip-tools"
	@echo "  venv-sync-dev   pip-sync requirements-dev.txt into .venv"
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
	@echo "Running tests via tox..."
	$(TOX) $(TOX_PAR) $(TOX_FLAGS)

verify:
	@echo "Running non-destructive checks via tox..."
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e format-check -e lint -e links -e docs
	@echo "All quality checks passed!"

lint: check-venv
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e lint

lint-fixall: check-venv
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e lint-fixall

format-check: check-venv
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e format-check

format: check-venv
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e format

docstring-links: check-venv
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e docstring-links

# Run pytest directly (no tox) with the current interpreter
pytest:
	pytest $(PYTEST_PAR) -q

property-test:
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e property-test

docs-build:
	$(TOX) -e docs

docs-serve:
	$(TOX) -e docs-serve

docs-clean:
	rm -rf site

links: check-lychee
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e links

links-src: check-lychee
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e links-src

links-all: check-lychee links
	$(TOX) $(TOX_PAR) $(TOX_FLAGS) -e links-all

# Matrix (all supported Pythons via tox label)
api-snapshot:
	$(TOX) -m api-check

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

# ---- Optional local convenience venv for editor / pyright (tox still runs checks) ----
venv:
	@test -d $(VENV) || ( \
		echo "Creating $(VENV)..." && \
		$(PY) -m venv $(VENV) && \
		$(VENV_BIN)/pip install -U pip && \
		$(VENV_BIN)/pip install pip-tools \
	)
	@echo "Activate with: source $(VENV_BIN)/activate"

venv-sync-dev: venv
	$(VENV_BIN)/pip-sync requirements-dev.txt
	@echo "Synced dev deps into $(VENV)."

venv-clean:
	@rm -rf $(VENV)
	@echo "Removed $(VENV)."

# ---- Lock management (pins). These do NOT affect tox; tox uses the compiled locks. ----
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

