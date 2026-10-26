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

## Related pages

- [Upgrading TopMark](upgrading.md)
- [Python support policy](python-support.md)
- [CI integration](ci.md)
- [Pre-commit integration](pre-commit.md)
