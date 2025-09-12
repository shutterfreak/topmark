# topmark:header:start
#
#   project      : TopMark
#   file         : Makefile
#   file_relpath : Makefile
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

# Pattern note:
# Destructive targets are split into two:
# - `.target` is the non-interactive implementation (scriptable)
# - `target` is the user-facing version with confirmation prompt
# Only the interactive targets are listed in the help menu.

.PHONY: build check-venv check-rtd-venv clean compile compile-dev dev dev-install \
		docs-build docs-deploy docs-serve docs-verify \
		format format-check git-archive help install lint lint-fixall \
		pre-commit-autoupdate pre-commit-clean pre-commit-install \
		pre-commit-refresh pre-commit-run pre-commit-uninstall \
		public-api-check public-api-ensure-clean public-api-update \
		rtd-venv setup source-snapshot \
		sync-dev sync-dev-confirm sync-prod sync-prod-confirm \
		test uninstall uninstall-confirm update-instructions-json upgrade-dev upgrade-pro venv verify

.DEFAULT_GOAL := help

PYTHON := python
VENV = .venv
VENV_BIN = $(VENV)/bin
RTD_VENV = .rtd
RTD_VENV_BIN = $(RTD_VENV)/bin
MKDOCS_RTD := $(RTD_VENV_BIN)/mkdocs
PUBLIC_API_JSON := tests/api/public_api_snapshot.json

# Define the root directory of the project, relative to the Makefile
PROJECT_ROOT := $(dir $(realpath $(lastword $(MAKEFILE_LIST))))

# Define target directories as Make variables
# This is a better practice than defining them inside the shell commands
GIT_ARCHIVE_DIR := $(PROJECT_ROOT)archives/git
SOURCE_SNAPSHOT_DIR := $(PROJECT_ROOT)archives/code-snapshot

# A dedicated target for creating the directories
# Use an order-only prerequisite to ensure the directories exist before the main targets run
# The `|` indicates that the `archives` and `git` targets are only for ordering
# and don't need to be checked for freshness against the main targets.
$(GIT_ARCHIVE_DIR) $(SOURCE_SNAPSHOT_DIR):
	mkdir -p $@

# ----------------------------------------------------------------------------------------------------------------------
# Help: Show categorized make targets
# ----------------------------------------------------------------------------------------------------------------------

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Setup:"
	@echo "  venv                     Create virtual environment (.venv) and install pip-tools"
	@echo "  setup                    Run full dev setup (venv, compile locks, sync dev)"
	@echo "  dev-install              Install TopMark in editable mode into the active venv"
	@echo ""
	@echo "Production / Install:"
	@echo "  compile                  Compile production dependencies"
	@echo "  install                  Install production dependencies"
	@echo "  upgrade-prod             Upgrade prod lock file with pip-compile -U (requirements.in → requirements.txt)"
	@echo "  sync-prod                Sync .venv with production requirements"
	@echo "  uninstall                Uninstall all packages in the environment"
	@echo ""
	@echo "Development / Quality:"
	@echo "  dev                      Install development dependencies"
	@echo "  compile-dev              Compile development dependencies"
	@echo "  upgrade-dev              Upgrade lock file with pip-compile -U and sync dev env"
	@echo "  sync-dev                 Sync .venv with dev requirements"
	@echo ""
	@echo "  verify                   Run all non-destructive checks (formatting, linting, type-checking)"
	@echo "  format-check             Check code formatting without modifying files"
	@echo "  format                   Format code (ruff, mdformat, taplo)"
	@echo "  lint                     Run linters (ruff, pydoclint, pyright)"
	@echo "  lint-fixall              Run linters and automatically fix fixable linting errors"
	@echo ""
	@echo "  test                     Run tests"
	@echo ""
	@echo "  public-api-check         Check whether the public API snapshot changed"
	@echo "  public-api-update        Regenerate tests/api/public_api_snapshot.json"
	@echo "  public-api-ensure-clean  Fail if the public API snapshot differs from the baseline"
	@echo ""
	@echo "Documentation:"
	@echo "  rtd-venv                 Create RTD docs virtual environment (.rtd) and install docs deps"
	@echo "  upgrade-rtd              Upgrade lock file with pip-compile -U and sync docs env"
	@echo ""
	@echo "  docs-serve               Serve docs locally (uses .rtd) with live reload"
	@echo "  docs-build               Build docs strictly (uses .rtd)"
	@echo "  docs-verify              Alias for docs-build (CI-friendly)"
	@echo "  docs-deploy              Deploy docs to GitHub Pages (gh-deploy) from .rtd"

	@echo ""
	@echo "Packaging:"
	@echo "  build                    Build the project"
	@echo "  git-archive              Build a time-stamped git archive of the project"
	@echo "  source-snapshot          Create a time-stamped source snapshot archive of the current state"
	@echo "                           (not necessarily committed)."
	@echo ""
	@echo "pre-commit Hooks:"
	@echo "  pre-commit-install       Install Git pre-commit hook defined in .pre-commit-config.yaml"
	@echo "  pre-commit-run           Run all pre-commit hooks on all tracked files"
	@echo "  pre-commit-autoupdate    Update pinned hook versions in .pre-commit-config.yaml"
	@echo "  pre-commit-refresh       Autoupdate and clean all pre-commit environments"
	@echo "  pre-commit-clean         Clean cached hook environments"
	@echo "  pre-commit-uninstall     Remove Git pre-commit hook"
	@echo ""
	@echo "Maintenance:"
	@echo "  clean                    Remove Python cache and build artifacts"
	@echo ""
	@echo "NOTES:"
	@echo " ⚠️ Requires pip-tools >= 7.4 to support --strip-extras, which is used in the Makefile to prepare for pip-tools 8.0 default behavior."


# ----------------------------------------------------------------------------------------------------------------------
# Setup
# ----------------------------------------------------------------------------------------------------------------------

check-venv:
	@test -x "$(VENV_BIN)/$(PYTHON)" || (echo "❌ $(VENV) not found. Run: make venv" && exit 1)

venv:
	@test -d $(VENV) || ( \
		echo "Creating virtual environment..." && \
		virtualenv $(VENV) && \
		. $(VENV_BIN)/activate && \
		$(VENV_BIN)/pip install -U pip && \
		$(VENV_BIN)/pip install pip-tools \
	)
	@echo "Activate the virtual environment ($(VENV))  with: source $(VENV_BIN)/activate"

setup: venv compile compile-dev sync-dev
	@echo ""
	@echo "Project ready for development!"
	@echo ""
	@echo "NOTES:"
	@echo " * Activate the virtual environment ($(VENV))  with: source $(VENV_BIN)/activate"

dev-install: check-venv
	. $(VENV_BIN)/activate && \
	$(VENV_BIN)/pip install -e .

# ----------------------------------------------------------------------------------------------------------------------
# Production / Install
# ----------------------------------------------------------------------------------------------------------------------

compile: check-venv
	# Compile from .in, strip extras to keep lock files reproducible
	$(VENV_BIN)/pip-compile -c constraints.txt --strip-extras requirements.in

install: compile
	$(VENV_BIN)/pip install -r requirements.txt

upgrade-prod: check-venv
	$(VENV_BIN)/pip-compile --upgrade -c constraints.txt --strip-extras requirements.in

.sync-prod: check-venv
	$(VENV_BIN)/pip-sync requirements.txt

sync-prod:
	@read -p "⚠️  This will overwrite your current environment with requirements.txt. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .sync-prod

.uninstall: check-venv
	$(VENV_BIN)/pip freeze | xargs $(VENV_BIN)/pip uninstall -y

uninstall:
	@read -p "⚠️  This will uninstall all packages in the current environment. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .uninstall


# ----------------------------------------------------------------------------------------------------------------------
# Development / Quality
# ----------------------------------------------------------------------------------------------------------------------

compile-dev: check-venv
	# Compile from .in, strip extras to keep lock files reproducible
	$(VENV_BIN)/pip-compile -c constraints.txt --strip-extras requirements-dev.in

dev: compile-dev
	$(VENV_BIN)/pip-sync requirements-dev.txt

upgrade-dev: check-venv
	$(VENV_BIN)/pip-compile --upgrade -c constraints.txt --strip-extras requirements-dev.in

.sync-dev: check-venv
	$(VENV_BIN)/pip-sync requirements-dev.txt

sync-dev:
	@read -p "⚠️  This will overwrite your current dev environment with requirements-dev.txt. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .sync-dev

# The 'verify' target runs all non-destructive checks
verify: check-venv format-check lint rtd-venv docs-verify
	@echo "All quality checks passed!"

format-check: check-venv
	@echo "Checking code formatting..."
	$(VENV_BIN)/ruff format --check .
	@echo "Checking MarkDown formatting..."
	# mdformat automatically uses the .mdformat.yml exclude file
	git ls-files -- '*.md' | xargs -r $(VENV_BIN)/mdformat --check
	@echo "Checking TOML formatting..."
	$(VENV_BIN)/taplo format --check .

format: check-venv
	@echo "Formatting code..."
	$(VENV_BIN)/ruff format .
	@echo "Formatting MarkDown..."
	# mdformat automatically uses the .mdformat.yml exclude file
	git ls-files -- '*.md' | xargs -r $(VENV_BIN)/mdformat
	@echo "Formatting TOML..."
	$(VENV_BIN)/taplo format .

lint: check-venv
	@echo "Running linters..."
	$(VENV_BIN)/ruff check .
	git ls-files '*.py' | xargs -r $(VENV_BIN)/pydoclint -q
	$(VENV_BIN)/pyright src tests

.lint-fixall: check-venv
	@echo "Running linters and automatically fixing fixable linting errors..."
	$(VENV_BIN)/ruff check --fix .

lint-fixall:
	@read -p "⚠️  This will try to fix (overwrite) all fixable linting errors. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .lint-fixall

test: check-venv
	@echo "Running tests..."
	$(VENV_BIN)/pytest

public-api-check: check-venv
	@$(VENV_BIN)/pytest -qq tests/api/test_public_api_snapshot.py && \
	echo "✅ Public API snapshot unchanged."

.public-api-update: check-venv
	@$(VENV_BIN)/$(PYTHON) tools/api_snapshot.py "$(PUBLIC_API_JSON)"
	@if git diff --quiet -- "$(PUBLIC_API_JSON)" ; then \
		echo "✅ Public API snapshot unchanged: $(PUBLIC_API_JSON)"; \
	else \
		git --no-pager diff -- "$(PUBLIC_API_JSON)"; \
		echo "⚠️  Public API snapshot UPDATED: $(PUBLIC_API_JSON)"; \
		echo "⚠️  Review diff, add $(PUBLIC_API_JSON) to git, bump version & update CHANGELOG."; \
	fi

public-api-update:
	@read -p "⚠️  This will overwrite the public API snapshot. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .public-api-update

# Fails if the snapshot differs from index
public-api-ensure-clean: check-venv
	@if git diff --quiet -- "$(PUBLIC_API_JSON)"; then \
		echo "✅ Public API snapshot clean: $(PUBLIC_API_JSON)"; \
	else \
		git --no-pager diff -- "$(PUBLIC_API_JSON)"; \
		echo "❌ Public API snapshot differs. Re-run: make public-api-update"; \
		exit 1; \
	fi

# ----------------------------------------------------------------------------------------------------------------------
# Documentation
# ----------------------------------------------------------------------------------------------------------------------

check-rtd-venv:
	@test -x "$(RTD_VENV_BIN)/$(PYTHON)" || (echo "❌ $(RTD_VENV) not found. Run: make rtd-venv" && exit 1)

rtd-venv:
	@test -d $(RTD_VENV) || ( \
		echo "Creating ReadTheDocs virtual environment..." && \
		virtualenv $(RTD_VENV) && \
		. $(RTD_VENV_BIN)/activate && \
		$(RTD_VENV_BIN)/pip install -U pip && \
		$(RTD_VENV_BIN)/pip install -c constraints.txt ".[docs]" && \
		$(RTD_VENV_BIN)/pip install pip-tools \
	)
	@echo "Activate the ReadTheDocs virtual environment ($(RTD_VENV))  with: source $(RTD_VENV_BIN)/activate"

upgrade-rtd: check-rtd-venv
	$(RTD_VENV_BIN)/pip-compile --upgrade -c constraints.txt --strip-extras requirements-docs.in

docs-verify: check-rtd-venv
	$(MKDOCS_RTD) build --strict

docs-build: check-rtd-venv
	$(MKDOCS_RTD) build --strict

.docs-serve: check-rtd-venv
	$(MKDOCS_RTD) serve

docs-serve:
	@read -p "Start MkDocs dev server? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .docs-serve

.docs-deploy: check-rtd-venv
	$(MKDOCS_RTD) gh-deploy --force

docs-deploy:
	@read -p "⚠️  This will deploy the 'site' to GitHub Pages (gh-pages). Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .docs-deploy


# ----------------------------------------------------------------------------------------------------------------------
# Packaging
# ----------------------------------------------------------------------------------------------------------------------

build: check-venv
	@echo "Building source and wheel distributions..."
	$(VENV_BIN)/$(PYTHON) -m build

git-archive: check-venv  | $(GIT_ARCHIVE_DIR)
	@echo "Creating a time-stamped git archive..."
	@timestamp=$$(date +%Y%m%d-%H%M%S) ; \
	TARGET_FILE="$(GIT_ARCHIVE_DIR)/topmark-$${timestamp}.tar.gz" ; \
	git archive --format=tar HEAD | gzip > "$$TARGET_FILE" && \
	echo "Archive created: $$TARGET_FILE"

source-snapshot: check-venv | $(SOURCE_SNAPSHOT_DIR)
	@echo "Creating a time-stamped source snapshot archive..."
	@echo "NOTE: this will create an archive of the current source snapshot (not necessarily committed)."
	@timestamp=$$(date +%Y%m%d-%H%M%S) ; \
	TARGET_FILE="$(SOURCE_SNAPSHOT_DIR)/topmark-$${timestamp}_uncommitted.tar.gz" ; \
	git ls-files -c -o --exclude-standard | sort -u | tar -czf "$$TARGET_FILE" -T - && \
	echo "Archive created: $$TARGET_FILE"


# ----------------------------------------------------------------------------------------------------------------------
# pre-commit Hooks
# ----------------------------------------------------------------------------------------------------------------------

pre-commit-install: check-venv
	$(VENV_BIN)/pre-commit install

pre-commit-run: check-venv
	$(VENV_BIN)/pre-commit run --all-files

.pre-commit-autoupdate: check-venv
	$(VENV_BIN)/pre-commit autoupdate

pre-commit-autoupdate:
	@read -p "⚠️  This will update pinned versions in .pre-commit-config.yaml. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .pre-commit-autoupdate

pre-commit-clean: check-venv
	$(VENV_BIN)/pre-commit clean

.pre-commit-refresh: check-venv
	$(VENV_BIN)/pre-commit autoupdate && \
	$(VENV_BIN)/pre-commit clean

pre-commit-refresh:
	@read -p "⚠️  This will autoupdate all pre-commit hooks and clean existing hook caches. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .pre-commit-refresh

pre-commit-uninstall: check-venv
	$(VENV_BIN)/pre-commit uninstall


# ----------------------------------------------------------------------------------------------------------------------
# Maintenance
# ----------------------------------------------------------------------------------------------------------------------

.clean:
	@echo "Cleaning build artifacts..."
	find . -type d -name '__pycache__' -exec rm -r {} +;
	find . -type f -name '*.pyc' -delete

clean:
	@read -p "⚠️  This will delete all build artifacts. Continue? [y/N] " confirm && [ "$$confirm" = "y" ] && \
	make .clean