<!--
topmark:header:start

  project      : TopMark
  file         : contributing.md
  file_relpath : docs/contributing.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Contributor guide

This page is the hosted contributor entry point for TopMark.

The canonical contributor guide lives at the repository root:

- [CONTRIBUTING.md](https://github.com/shutterfreak/topmark/blob/main/CONTRIBUTING.md)

Use this page when browsing the hosted documentation site. Use the root `CONTRIBUTING.md` file when
working directly from a local checkout or GitHub.

______________________________________________________________________

## Start here

| Goal                                                     | Recommended page                                                                     |
| -------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Set up a local development environment                   | [Installation guide](install.md)                                                     |
| Understand contribution workflow and validation commands | [CONTRIBUTING.md](https://github.com/shutterfreak/topmark/blob/main/CONTRIBUTING.md) |
| Understand project architecture                          | [Architecture](dev/architecture.md)                                                  |
| Understand documentation conventions                     | [Documentation conventions](dev/documentation-conventions.md)                        |
| Understand CI and validation workflows                   | [CI documentation](ci/index.md)                                                      |
| Understand releases and publication                      | [Release process](dev/release-process.md)                                            |
| Review public API stability                              | [Public API](api/public.md)                                                          |
| Review internal API reference                            | [Internal API reference](api/internals.md)                                           |

______________________________________________________________________

## Repository map

Important repository entry points:

- `README.md` - project overview and GitHub/PyPI landing page
- `INSTALL.md` - canonical installation and contributor setup guide
- `CONTRIBUTING.md` - canonical contributor guide
- `CHANGELOG.md` - release history and compatibility notes
- `docs/` - MkDocs documentation source
- `src/topmark/` - TopMark package source code
- `tests/` - test suite
- `Makefile` - local development and validation commands
- `noxfile.py` - isolated validation sessions
- `.pre-commit-config.yaml` - repository-local pre-commit hooks
- `.pre-commit-hooks.yaml` - hooks exported to consumer repositories

______________________________________________________________________

## Contribution focus areas

Contributor-facing documentation is split by topic:

- [Development documentation](dev/index.md) covers architecture, public API policy, documentation
  conventions, release process, and roadmap material.
- [CI documentation](ci/index.md) covers how this repository validates itself and publishes
  artifacts.
- [Usage documentation](usage/index.md) covers the user-facing CLI, configuration, policies,
  integrations, and workflows.
- [Configuration documentation](configuration/index.md) covers configuration discovery, generated
  defaults, and schema-oriented reference material.

______________________________________________________________________

## Further reading

- [Installation guide](install.md)
- [Development documentation](dev/index.md)
- [Documentation conventions](dev/documentation-conventions.md)
- [CI workflow](ci/ci-workflow.md)
- [Release workflow](ci/release-workflow.md)
- [Published artifact validation](ci/published-artifact-validation.md)
- [Release process](dev/release-process.md)
