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
UV ?= uv
# Nox is a project development dependency.  Running it through uv keeps its
# version and the nox-uv plugin aligned with the project's locked dev extra.
NOX ?= $(UV) run --extra dev nox
NOX_FLAGS ?= --no-verbose       # keep quiet by default; CI can override
PYTEST_PAR ?= # e.g. set PYTEST_PAR="-n auto" or "-n 4" for pytest-capable targets
PY ?= python
VENV := .venv

PUBLIC_API_JSON := tests/api/public_api_snapshot.json

# Simple tool presence checks
.PHONY: check-uv
check-uv:
	@command -v $(UV) >/dev/null 2>&1 || \
		(echo "❌ uv not found. Install uv for your platform and ensure it is on PATH. See CONTRIBUTING.md." && exit 1)

.PHONY: check-nox
check-nox: check-uv
	@$(NOX) --version >/dev/null 2>&1 || \
		(echo "❌ Nox could not run through the project's dev extra. See CONTRIBUTING.md for setup help." && exit 1)

.PHONY: check-lychee
check-lychee:
	@command -v lychee >/dev/null 2>&1 || \
		(echo "❌ lychee not found. Install Lychee for your platform and ensure it is on PATH. See CONTRIBUTING.md." && exit 1)

.PHONY: help
help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "Quality checks:"
	@echo "  verify          Run non-test quality checks: formatting, lint, docs, and links"
	@echo "  pre-pr          Run the recommended local pre-PR gate; supports PYTEST_PAR=\"-n auto\""
	@echo "  lint            Run ruff + pydoclint + mbake"
	@echo "  lint-fixall     Run ruff with --fix (auto-fix lint issues)"
	@echo "  format-check    Check code/markdown/toml/Makefile formatting"
	@echo "  format          Format code/markdown/toml/Makefile (auto-fix)"
	@echo "  format-docstrings  Auto-format docstrings using pydocstringformatter"
	@echo "  docstring-links Enforce Python docstring link style"
	@echo "  docs-hygiene    Check Markdown/Zensical documentation hygiene"
	@echo "  code-hygiene    Check Python comments/docstrings/string prose hygiene"
	@echo "  hygiene         Run all prose/documentation hygiene checks"
	@echo ""
	@echo "Testing:"
	@echo "  test            Run the test suite (nox: qa); supports PYTEST_PAR=\"-n auto\""
	@echo "  smoke           Run the fast marker-selected smoke suite (nox: smoke)"
	@echo "  pytest          Run current-interpreter tests, excluding slow Hypothesis tests; supports PYTEST_PAR=\"-n auto\""
	@echo "  pytest-full     Run all current-interpreter tests; supports PYTEST_PAR=\"-n auto\""
	@echo "  coverage        Run coverage testing; supports PYTEST_PAR=\"-n auto\""
	@echo "  coverage-changed  Diagnose uncovered changed source lines; run coverage first"
	@echo "  coverage-erase  Remove local coverage output"
	@echo "  property-test   Run Hypothesis hardening tests (manual, opt-in)"
	@echo "  perf-baseline   Run pipeline memory/allocation baselines (manual, opt-in)"
	@echo ""
	@echo "Release and packaging:"
	@echo "  release-check   Run the deterministic pre-release gate; supports PYTEST_PAR=\"-n auto\""
	@echo "  release-full    Run the full Nox release gate, including the supported-Python matrix"
	@echo "  package-check   Run package sanity checks (nox: package_check)"
	@echo ""
	@echo "Documentation:"
	@echo "  docs-build      Build docs strictly (nox: docs)"
	@echo "  docs-serve      Serve docs locally (nox: docs_serve)"
	@echo "  docs-clean      Remove disposable Zensical build output"
	@echo ""
	@echo "Link checks:"
	@echo "  links           Check links in docs/ and tracked Markdown (nox: links)"
	@echo "  links-src       Check links found in Python docstrings under src/ (nox: links_src)"
	@echo "  links-all       Check links in docs/, tracked Markdown, and Python docstrings (nox: links_all)"
	@echo "  links-site      Check built-site links and project-owned hosted documentation routes"
	@echo ""
	@echo "Public API contracts:"
	@echo "  api-snapshot-dev         Check structured API contracts with current interpreter (fast local)"
	@echo "  api-snapshot             Check structured API contracts across all supported Pythons"
	@echo "  api-snapshot-update      Regenerate the structured public API snapshot (interactive)"
	@echo "  api-snapshot-ensure-clean  Fail if snapshot differs from Git index"
	@echo ""
	@echo "Local editor environment (optional, for Pyright/import resolution in IDE):"
	@echo "  venv            Create an empty .venv via uv (sync targets create it when needed)"
	@echo "  venv-sync-dev   Sync dev/test/typing extras into .venv"
	@echo "  venv-sync-all   Sync dev/test/typing/docs extras into .venv"
	@echo "  venv-sync-docs  Sync docs extras into .venv (removes dev/test/typing packages)"
	@echo "  venv-clean      Remove .venv"
	@echo ""
	@echo "UV project lock workflow:"
	@echo "  uv-lock         Generate or refresh uv.lock from pyproject.toml"
	@echo "  uv-lock-upgrade Refresh uv.lock with dependency upgrades"
	@echo ""
	@echo "Platform notes: Make recipes require a POSIX shell. On Windows, use Git Bash or WSL."
	@echo "Setup details: see CONTRIBUTING.md"

.PHONY: verify
verify: check-nox check-lychee
	$(NOX) $(NOX_FLAGS) -s verify

.PHONY: pre-pr
pre-pr: check-nox
	@echo "Running recommended local pre-PR validation via nox..."
	$(NOX) $(NOX_FLAGS) -s pre_pr -- $(PYTEST_PAR)

.PHONY: lint
lint: check-nox
	$(NOX) $(NOX_FLAGS) -s lint

.PHONY: lint-fixall
lint-fixall: check-nox
	$(NOX) $(NOX_FLAGS) -s lint_fixall

.PHONY: format-check
format-check: check-nox
	$(NOX) $(NOX_FLAGS) -s format_check

.PHONY: format
format: check-nox
	$(NOX) $(NOX_FLAGS) -s format

.PHONY: format-docstrings
format-docstrings: check-uv
	@echo "Auto-formatting docstrings (settings from pyproject.toml)..."
	$(UV) run --extra dev pydocstringformatter --write src/topmark/ tools/

.PHONY: docstring-links
docstring-links: check-nox
	$(NOX) $(NOX_FLAGS) -s docstring_links

.PHONY: docs-hygiene
docs-hygiene: check-nox
	$(NOX) $(NOX_FLAGS) -s docs_hygiene

.PHONY: code-hygiene
code-hygiene: check-nox
	$(NOX) $(NOX_FLAGS) -s code_hygiene

.PHONY: hygiene
hygiene: docs-hygiene code-hygiene

# ---- Testing --------------------------------------------------------------
# Pass PYTEST_PAR after `--` so nox forwards it directly to pytest. When the
# variable is empty, no additional argument is passed.
.PHONY: test
test: check-nox
	@echo "Running tests via nox..."
	$(NOX) $(NOX_FLAGS) -s qa -- $(PYTEST_PAR)

.PHONY: smoke
smoke: check-nox
	$(NOX) $(NOX_FLAGS) -s smoke

# Run pytest directly (without nox) using the current interpreter.
.PHONY: pytest
pytest: check-uv
	@echo "Running pytest locally -- skipping Hypothesis slow tests"
	$(UV) run --extra dev --extra typing --extra test pytest $(PYTEST_PAR) -m "not hypothesis_slow" -q

.PHONY: pytest-full
pytest-full: check-uv
	@echo "Running all pytest locally -- including Hypothesis slow tests"
	$(UV) run --extra dev --extra typing --extra test pytest $(PYTEST_PAR) -q

.PHONY: coverage
coverage: check-nox
	$(NOX) $(NOX_FLAGS) -s coverage -- $(PYTEST_PAR)

.PHONY: coverage-changed
coverage-changed: check-nox
	$(NOX) $(NOX_FLAGS) -s coverage_changed -- $(COVERAGE_CHANGED_ARGS)

# These files and directories are generated only by the coverage session.
# `rm -rf` is available in the supported POSIX shells, Git Bash, and WSL.
.PHONY: coverage-erase
coverage-erase:
	@rm -rf .coverage coverage.xml coverage.json htmlcov .coverage.*

.PHONY: property-test
property-test: check-nox
	$(NOX) $(NOX_FLAGS) -s property_test

.PHONY: perf-baseline
perf-baseline: check-nox
	$(NOX) $(NOX_FLAGS) -s perf_baseline

# ---- Release and packaging ------------------------------------------------
.PHONY: release-check
release-check: check-nox
	@echo "Running release gate (deterministic) via nox..."
	$(NOX) $(NOX_FLAGS) -s release_check -- $(PYTEST_PAR)

.PHONY: release-full
release-full: check-nox check-lychee
	$(NOX) $(NOX_FLAGS) -s release_full -- $(PYTEST_PAR)

.PHONY: package-check
package-check: check-nox
	@echo "Running packaging sanity checks via nox..."
	$(NOX) $(NOX_FLAGS) -s package_check

# ---- Documentation --------------------------------------------------------
.PHONY: docs-build
docs-build: check-nox
	$(NOX) $(NOX_FLAGS) -s docs

.PHONY: docs-serve
docs-serve: check-nox
	$(NOX) $(NOX_FLAGS) -s docs_serve

.PHONY: docs-clean
docs-clean:
	@rm -rf .zensical

.PHONY: links
links: check-nox check-lychee
	$(NOX) $(NOX_FLAGS) -s links

.PHONY: links-src
links-src: check-nox check-lychee
	$(NOX) $(NOX_FLAGS) -s links_src

.PHONY: links-all
links-all: check-nox check-lychee
	$(NOX) $(NOX_FLAGS) -s links_all

.PHONY: links-site
links-site: check-nox check-lychee
	$(NOX) $(NOX_FLAGS) -s links_site

# Fast local check using only the current interpreter.
.PHONY: api-snapshot-dev
api-snapshot-dev: check-uv
	@$(UV) run --extra dev --extra typing --extra test pytest -qq tests/api/test_public_api_snapshot.py tests/api/test_api_snapshot_generator.py && \
	echo "✅ Public API snapshot unchanged."

.PHONY: api-snapshot
api-snapshot: check-nox
	$(NOX) $(NOX_FLAGS) -s api_snapshot

# Update the snapshot only after an explicit, portable POSIX-shell confirmation.
.PHONY: .api-snapshot-update
.api-snapshot-update: check-uv
	@$(UV) run --extra dev --extra typing --extra test $(PY) tools/api_snapshot.py "$(PUBLIC_API_JSON)"
	@if git diff --quiet -- "$(PUBLIC_API_JSON)" ; then \
		echo "✅ Public API snapshot unchanged: $(PUBLIC_API_JSON)"; \
	else \
		git --no-pager diff -- "$(PUBLIC_API_JSON)"; \
		echo "⚠️  Public API snapshot UPDATED: $(PUBLIC_API_JSON)"; \
		echo "⚠️  Review diff, add $(PUBLIC_API_JSON) to git, and update CHANGELOG."; \
	fi

.PHONY: api-snapshot-update
api-snapshot-update:
	@printf '%s' "⚠️  This will overwrite the public API snapshot. Continue? [y/N] "; \
	IFS= read -r confirm; \
	if [ "$$confirm" = "y" ]; then \
		$(MAKE) .api-snapshot-update; \
	else \
		echo "Snapshot update cancelled."; \
	fi

# Fail if snapshot differs from index
.PHONY: api-snapshot-ensure-clean
api-snapshot-ensure-clean: check-nox
	@if git diff --quiet -- "$(PUBLIC_API_JSON)"; then \
		echo "✅ Public API snapshot clean: $(PUBLIC_API_JSON)"; \
	else \
		git --no-pager diff -- "$(PUBLIC_API_JSON)"; \
		echo "❌ Public API snapshot differs. Re-run: make api-snapshot-update"; \
		exit 1; \
	fi

# ---- Optional local editor environment ------------------------------------
# Keep a project-local .venv for IDE integration; uv manages it directly.
.PHONY: venv
venv: check-uv
	@test -d $(VENV) || ( \
		echo "Creating $(VENV) via uv..." && \
		$(UV) venv $(VENV) \
		)
	@echo "Activation is optional: uv run can execute project commands directly."
	@echo "POSIX shells: source $(VENV)/bin/activate"
	@echo "PowerShell: $(VENV)\\Scripts\\Activate.ps1"

.PHONY: venv-sync-dev
venv-sync-dev: check-uv
	$(UV) sync --extra dev --extra typing --extra test
	@echo "Synced dev/test/typing extras into $(VENV)."

# Sync the union of dev/test/typing/docs extras. This is the recommended local
# environment for Zensical work and VS Code import resolution.
.PHONY: venv-sync-all
venv-sync-all: check-uv
	$(UV) sync --extra dev --extra typing --extra test --extra docs
	@echo "Synced dev/test/typing/docs extras into $(VENV)."

# Sync docs-only extras into the shared venv. This removes dev/test/typing
# tools, so prefer venv-sync-all when one environment must serve every task.
.PHONY: venv-sync-docs
venv-sync-docs: check-uv
	$(UV) sync --extra docs
	@echo "Synced docs extras into $(VENV)."

.PHONY: venv-clean
venv-clean:
	@case "$(VENV)" in ""|.|./|..|../|/) \
		echo "❌ Refusing to remove unsafe VENV path: $(VENV)"; exit 2;; \
	esac
	@rm -rf "$(VENV)"
	@echo "Removed $(VENV)."

# ---- Dependency lock workflow ---------------------------------------------
.PHONY: uv-lock
uv-lock: check-uv
	$(UV) lock

.PHONY: uv-lock-upgrade
uv-lock-upgrade: check-uv
	$(UV) lock --upgrade
