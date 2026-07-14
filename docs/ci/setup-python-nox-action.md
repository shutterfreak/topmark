<!--
topmark:header:start

  project      : TopMark
  file         : setup-python-nox-action.md
  file_relpath : docs/ci/setup-python-nox-action.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Setup Python + nox action

This page documents `.github/actions/setup-python-nox/action.yml`.

The `setup-python-nox` composite action is TopMark's shared GitHub Actions bootstrap layer for jobs
that require Python, `uv`, caching, and the `nox` toolchain.

{% include-markdown "\_snippets/terminology.md" %}

## Purpose

The action provides a consistent bootstrap environment across CI and release workflows without
duplicating Python and tooling setup logic in multiple workflow files.

It intentionally remains lightweight and workflow-neutral:

- it installs the requested Python version;
- it configures `uv` without enabling the built-in `setup-uv` cache integration;
- it restores and populates the `uv` cache;
- it installs `nox` and `nox-uv`;
- it does not execute project validation logic itself.

Validation behavior remains defined by workflow jobs and nox sessions rather than by the bootstrap
action.

______________________________________________________________________

## Inputs

| Input            | Required | Default | Purpose                                                   |
| ---------------- | -------- | ------- | --------------------------------------------------------- |
| `python-version` | No       | `3.x`   | Python version to install for the calling workflow or job |

The action intentionally does not hard-code TopMark's canonical Python version internally.

`actions/setup-python` resolves selectors such as `3.x` to a concrete installed interpreter. The
action passes that resolved version to `setup-uv`, ensuring `UV_PYTHON` identifies the interpreter
that is actually available to subsequent `uv pip --system` commands.

Workflows are expected to pass:

- the resolved canonical Python version for project-validation jobs;
- or an explicit bootstrap/runtime version for metadata or release-helper jobs.

This separation keeps workflow policy visible at the workflow layer rather than embedding project
version policy inside the shared composite action.

______________________________________________________________________

## Bootstrap steps

The action performs the following steps:

| Step            | Purpose                                                |
| --------------- | ------------------------------------------------------ |
| `Set up Python` | Install the requested Python version                   |
| `Set up uv`     | Install the `uv` package manager                       |
| `Cache uv`      | Restore and persist the shared `uv` cache              |
| `Bootstrap nox` | Install `nox` and `nox-uv` into the runner environment |

The cache key includes:

- runner operating system;
- resolved Python version;
- `pyproject.toml`;
- `uv.lock`;
- `noxfile.py`.

This keeps cache invalidation aligned with dependency and tooling changes.

______________________________________________________________________

## Workflow integration

The action is primarily consumed by `.github/workflows/ci.yml`.

CI jobs use it in two modes:

| Usage mode                 | Purpose                                                       |
| -------------------------- | ------------------------------------------------------------- |
| Canonical validation setup | Run nox sessions using the resolved canonical Python version  |
| Metadata/bootstrap setup   | Resolve Python metadata and bootstrap helper jobs using `3.x` |

The CI workflow resolves supported and canonical Python versions through:

```bash
nox -s print_python_matrix
```

That metadata is then consumed by workflow jobs so the Python matrix and canonical single-version
jobs follow `pyproject.toml` automatically.

The release workflow intentionally uses explicit release-tooling Python configuration rather than
deriving its privileged runtime from repository-source metadata.

______________________________________________________________________

## Bootstrap trust boundary

TopMark intentionally keeps this composite action limited to:

1. Python installation;
1. uv installation;
1. explicit uv cache restoration and persistence;
1. nox/nox-uv bootstrap.

Project validation, release artifact creation, package publication, and published-package validation
remain owned by the calling workflows and nox sessions. This keeps the shared bootstrap layer stable
without turning it into a hidden validation or release-policy surface.

______________________________________________________________________

## Cache behavior

The action intentionally uses explicit `actions/cache` integration to cache the `uv` package cache
while keeping the `setup-uv` built-in cache integration disabled:

```text
~/.cache/uv
```

The cache key includes the resolved Python version so caches remain isolated across interpreter
versions.

> [!NOTE] Keeping a single explicit cache owner avoids noisy cache-reservation race warnings when
> multiple CI jobs run concurrently with the same bootstrap inputs.

The cache is intentionally scoped to dependency/bootstrap acceleration only. It is not used to cache
project build artifacts, release artifacts, or workflow outputs.

______________________________________________________________________

## Local reproduction

Composite GitHub Actions cannot be executed directly outside GitHub Actions runners.

The closest local equivalent is:

```bash
uv pip install nox nox-uv
nox -s print_python_matrix
```

Typical local validation commands remain:

```bash
nox -s qa -p 3.14
nox -s coverage -p 3.14
```

The concrete canonical Python version shown above is expected to move when the supported Python
range changes.

______________________________________________________________________

## Maintenance notes

When editing this action:

- keep the action focused on bootstrap/setup behavior only;
- avoid embedding project validation policy inside the action;
- keep Python-version policy controlled by workflows and nox metadata;
- keep cache keys aligned with dependency-resolution inputs;
- keep `setup-uv` cache ownership disabled while explicit workflow cache steps remain authoritative;
- keep action pins synchronized with the rest of the repository workflows;
- avoid adding project-specific release logic to this shared bootstrap layer.

Do not move validation or release-governance logic into this action unless the workflow architecture
is deliberately redesigned.

______________________________________________________________________

## Related pages

{% include-markdown "\_snippets/ci/related-pages.md" %}
