<!--
topmark:header:start

  project      : TopMark
  file         : upgrading-to-3.0.md
  file_relpath : docs/usage/upgrading-to-3.0.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Upgrading to TopMark 3.0

TopMark 3.0 drops support for Python 3.10. Upgrade the interpreter used by every TopMark
installation, CI job, and pre-commit environment before installing TopMark 3.0.

If you are upgrading from a release earlier than 2.0, complete each intervening major-version guide
in order. See [Upgrading TopMark](upgrading.md) to select the complete upgrade path.

______________________________________________________________________

## Upgrade Python first

TopMark 3.0 requires Python 3.11 or later. Check the interpreter before upgrading the package:

```bash
python --version
python -m pip install --upgrade "topmark>=3.0"
topmark version
```

Update any version selectors used by your automation, including CI matrices, container images,
`pyenv` configuration, and dependency-manager environments. Recreate virtual environments that were
created with Python 3.10; an existing virtual environment cannot be upgraded in place to a new
Python minor release.

______________________________________________________________________

## Review nested configuration

TopMark 3.0 discovers configuration sources below a directory processing target. When you run a
processing command such as `topmark check .`, a nested `topmark.toml` or `pyproject.toml` now
applies to files in its own directory tree, without changing configuration for siblings. Earlier
releases could leave those sources undiscovered unless the nested directory or file was named as an
input explicitly.

Review repositories that already contain nested configuration before upgrading. Their effective
settings can now change file selection or header rendering when processed from a higher directory.
Use `root = true` in a nested source when it should stop inheriting project configuration above its
directory, and run your usual dry-run check to review the result:

```bash
topmark config check --strict
topmark check --report noncompliant .
```

See [Configuration discovery](../configuration/discovery.md) for precedence, source scope, and
explicit-configuration behavior. This intentional compatibility change resolves [#486].

File-type filters also use each input's scoped configuration during discovery. Policies and
activation consent from one subtree no longer leak into siblings. Explicit CLI overrides and API
policy overlays remain final invocation layers, so they survive per-file scoped recomputation. These
corrections can change selection and processing in existing multi-input runs; review
`include_file_types`, `exclude_file_types`, opt-in consent, and per-type policies in nested sources.
These fixes are tracked in [#488](https://github.com/shutterfreak/topmark/issues/488) and
[#489](https://github.com/shutterfreak/topmark/issues/489).

______________________________________________________________________

## Handle API configuration failures

Public `check()`, `strip()`, and `probe()` now raise `ConfigValidationError` before processing if
any configuration stage contains an error. Warnings also fail when resolved source strictness is
true. Explicit mapping seeds retain `config.strict`; frozen seeds retain diagnostics but do not
carry source-local strictness. Explicit policy and type-filter overrides are applied before
validation.

Earlier API versions could continue after configuration errors or process files despite a discovered
`strict = true` preference. New file-type assignments are covered by this same validation boundary.
Update integrations to correct invalid inputs and handle configuration failures. The streaming
variants raise when iteration starts, before any events are yielded or processing files are changed.
Successful result and event shapes, and public function signatures, remain unchanged.

See [Public API configuration](../api/public.md#configuration-via-mappings) and
[#490](https://github.com/shutterfreak/topmark/issues/490).

______________________________________________________________________

## Update repository automation

Search repository automation for Python 3.10 references and replace them with a supported version or
a metadata-derived matrix. In GitHub Actions, prefer a matrix maintained by your project policy over
a stale hard-coded Python 3.10 entry.

If you use TopMark's pre-commit hook, recreate the hook environment after upgrading its Python
runtime:

```bash
pre-commit clean
pre-commit install
pre-commit run --all-files
```

Run your normal CI and a dry-run TopMark check after updating the runtime:

```bash
topmark config check --strict
topmark check --report noncompliant .
```

______________________________________________________________________

## Supported-runtime policy

TopMark tracks CPython's maintained feature-release series. See the
[Python support policy](python-support.md) for the current supported range and lifecycle rules.

______________________________________________________________________

## Assign existing file types explicitly

TopMark 3.0 adds ordered `files.file_type_assignments`, `--assign-filetype TYPE=GLOB`, and
`--infer-filetype GLOB`. These rules select existing registered types and preserve activation,
filters, processor bindings, insertion checks, and runtime eligibility. A winning `infer` rule
restores ordinary automatic recognition for selected paths. CLI occurrences interleave in their
actual argument order. See [Configuration](configuration.md#assign-existing-file-types).

Empty rule arrays retain inherited assignments. A separate clear-all inheritance setting is
intentionally deferred from the initial release. New declarative types, processor-binding overrides,
and direct path-to-processor selection are also outside this feature.

Probe machine output and public API results add `selection_method` and `rule_matches`. Consumers
should accept these additive fields and use the explicit selection method instead of expecting a
score for every selected type. Portable project files should retain authored relative rules;
configuration dumps preserve absolute origin bases/scopes when reloaded from another location.

______________________________________________________________________

## Related pages

- [Upgrading TopMark](upgrading.md)
- [Python support policy](python-support.md)
- [CI integration](ci.md)
- [Pre-commit integration](pre-commit.md)
