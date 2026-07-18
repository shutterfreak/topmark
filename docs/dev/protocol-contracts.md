<!--
topmark:header:start

  project      : TopMark
  file         : protocol-contracts.md
  file_relpath : docs/dev/protocol-contracts.md
  license      : MIT
  copyright    : (c) 2025 Olivier Biot

topmark:header:end
-->

# Protocol contracts and conformance

TopMark uses `typing.Protocol` for narrow structural contracts between subsystems. A protocol is not
an executable base class: Pyright validates signatures, properties, mutability, variance, and return
types, while pytest validates real runtime behavior. Protocols normally remain structural; concrete
implementations should not inherit from them merely to make conformance nominal.

This page records the production protocol inventory audited for
[GitHub issue #263](https://github.com/shutterfreak/topmark/issues/263) and establishes the policy
for future protocol changes.

## Classification and verification policy

TopMark classifies protocols as:

- **plugin-facing compatibility contracts**, whose members affect integration compatibility even
  when they are not exported by the `topmark.api` facade;
- **public-adjacent integration contracts**, used at documented CLI, registry, or extension seams;
- **internal architectural seams**, which let durable and mutable models remain interchangeable;
- **local typing/import-cycle helpers**, which expose only the subset needed by one owner;
- **private implementation helpers**, which deliberately stay inside one implementation boundary;
- **obsolete or temporary aids**, which have no current provider or consumer and should not gain
  artificial tests merely to preserve them.

Add a Pyright-only fixture under `tests/typecheck/<subsystem>/` when a real concrete provider is
intended to satisfy a protocol, that relationship matters architecturally, and ordinary production
typing does not make the relationship sufficiently explicit. A verifier accepts the real concrete
type and returns the protocol type. Keep type-only imports under `TYPE_CHECKING`; do not use `Any`,
`cast()`, ignored errors, unreachable calls, nominal test subclasses, or artificial doubles.

These fixtures are not pytest tests. They are never invoked and do not contribute runtime coverage;
strict Pyright analysis is the assertion. Positive conformance fixtures must remain clean on both
supported edge versions. TopMark does not currently have an expected-diagnostic harness, so do not
add deliberately failing negative examples.

______________________________________________________________________

## Verified production inventory

The audit found 27 production protocols. Protocols defined only in tests are excluded. The issue's
reference to `topmark.processors.mixins` is stale: that module now contains concrete mixins and no
protocol.

| Protocol                                                 | Classification and purpose                                                                            | Intended providers                                                                                                                              | Verification decision                                                                                                                                                                                                           |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `api.protocols.PublicFileType`                           | Plugin-facing compatibility vocabulary for historical file-type metadata.                             | No canonical TopMark provider; current plugins register concrete `FileType` instances, whose identity and policy model differs from this shape. | No fixture: manufacturing a provider would falsely imply registry acceptance. Retained as public-adjacent compatibility surface pending an explicit compatibility decision.                                                     |
| `api.protocols.PublicHeaderProcessor`                    | Plugin-facing compatibility vocabulary for historical processor metadata and mutable binding.         | No canonical provider satisfying its nested `PublicFileType` binding; current registration accepts `HeaderProcessor` subclasses.                | No fixture for the same reason; member changes remain integration-sensitive.                                                                                                                                                    |
| `cli.cli_types.ParamTypeBase`                            | Local type-check-only helper preventing imprecise Click stubs from introducing `Any`.                 | `EnumChoiceParam` during static analysis; at runtime the alias is `click.ParamType`.                                                            | No separate fixture: inheritance in the defining module makes conformance unavoidable.                                                                                                                                          |
| `cli.console.protocols.ConsoleProtocol`                  | Public-adjacent CLI output seam and dynamic CLI-state boundary.                                       | `Console`, `StdConsole`, and compatible injected consoles.                                                                                      | Concrete classes inherit the protocol directly, so production definitions enforce signatures. Runtime guard behavior is covered by CLI state tests.                                                                             |
| `config.policy.HasPolicyConfig`                          | Local import-cycle helper exposing resolved policy only.                                              | `FrozenConfig`. `MutableConfig` intentionally does not conform because it contains unresolved `MutablePolicy` values.                           | Explicit `FrozenConfig` fixture added; the stale docstring claim about `MutableConfig` was corrected.                                                                                                                           |
| `diagnostic.types.DiagnosticsLike`                       | Internal read-only observation seam for mutable and frozen diagnostic containers.                     | `MutableDiagnosticLog`, `FrozenDiagnosticLog`.                                                                                                  | Explicit fixtures protect both interchangeable providers.                                                                                                                                                                       |
| `filetypes.model.ContentMatcher`                         | Public-adjacent integration contract for content-based recognition.                                   | Built-in `looks_like_jsonc` and plugin callables stored on `FileType`.                                                                          | Explicit built-in callable fixture; runtime behavior remains covered by detector and content-gate tests.                                                                                                                        |
| `filetypes.model.PreInsertHeaderProcessorView`           | Local read-only method surface used by pre-insert checkers.                                           | `HeaderProcessor` and its concrete subclasses.                                                                                                  | Explicit `HeaderProcessor` fixture protects the checker-facing signature.                                                                                                                                                       |
| `filetypes.model.PreInsertContextView`                   | Internal adapter seam exposing only pre-insert inputs.                                                | `PreInsertViewAdapter`.                                                                                                                         | Explicit adapter fixture protects property types and read-only shape.                                                                                                                                                           |
| `filetypes.model.InsertChecker`                          | Public-adjacent integration contract for pre-insert advice.                                           | `json_like_can_insert`, `xml_can_insert`, and compatible plugin callables.                                                                      | Explicit fixtures protect both built-in checker signatures; behavior remains in focused checker tests.                                                                                                                          |
| `pipeline.context.protocols.SupportsPolicyEvaluation`    | Local import-cycle helper for policy and outcome snapshot evaluation.                                 | `ProcessingContext`.                                                                                                                            | Existing explicit fixture retained.                                                                                                                                                                                             |
| `pipeline.engine.SupportsPipelineExitStatus`             | Internal read-only status subset for exit selection.                                                  | `ProcessingStatus`, `StatusSnapshot`, reached through their owning context/result.                                                              | Verified transitively through the two outer-result fixtures; a separate nested fixture would duplicate the same relationship.                                                                                                   |
| `pipeline.engine.SupportsPipelineExitResult`             | Internal mutable/durable result seam for exit selection.                                              | `ProcessingContext`, `ProcessingResult`.                                                                                                        | Explicit fixtures protect both sides of the reduction boundary.                                                                                                                                                                 |
| `pipeline.outcomes.SupportsOutcomeStatus`                | Internal status subset for outcome classification.                                                    | `ProcessingStatus`, `StatusSnapshot`, reached through context/result.                                                                           | Verified transitively through outer classification fixtures.                                                                                                                                                                    |
| `pipeline.outcomes.SupportsOutcomeFlags`                 | Internal policy-aware outcome subset.                                                                 | Context-derived `OutcomeSnapshot` and the durable result's stored `OutcomeSnapshot`.                                                            | Verified transitively through outer classification fixtures and typed snapshot construction.                                                                                                                                    |
| `pipeline.outcomes.SupportsOutcomeClassification`        | Internal mutable/durable result seam for outcome bucketing.                                           | `ProcessingContext`, `ProcessingResult`.                                                                                                        | Explicit fixtures protect both providers.                                                                                                                                                                                       |
| `pipeline.pre_insert_advisory.SupportsPreInsertAdvisory` | Local reduction helper for durable advisory snapshots.                                                | `ProcessingContext`.                                                                                                                            | No dedicated fixture: `ProcessingResult.from_context()` passes a typed context to `PreInsertAdvisorySnapshot.from_context()`, making conformance unavoidable in production.                                                     |
| `pipeline.protocols.Step[Ctx]`                           | Internal generic lifecycle and view-consumption contract for pipeline execution.                      | `BaseStep` and all concrete step subclasses.                                                                                                    | Explicit `BaseStep[ProcessingContext]` relationship protects lifecycle signatures and metadata; typed pipeline catalogues cover concrete steps.                                                                                 |
| `pipeline.reporting.SupportsReportStatus`                | Internal status subset for human report filtering.                                                    | `ProcessingStatus`, `StatusSnapshot`, reached through context/result.                                                                           | Verified transitively through outer report fixtures.                                                                                                                                                                            |
| `pipeline.reporting.SupportsReportFiltering`             | Internal mutable/durable result seam for report filtering.                                            | `ProcessingContext`, `ProcessingResult`.                                                                                                        | Explicit fixtures protect both providers.                                                                                                                                                                                       |
| `pipeline.views.Releasable`                              | Internal lifecycle seam requiring safe, idempotent buffer release.                                    | File, header, builder, render, updated, diff, and edit views.                                                                                   | `ListFileImageView` is explicitly checked; the remaining view classes inherit the protocol and runtime pruning tests protect release behavior.                                                                                  |
| `pipeline.views.FileImageView`                           | Internal read-only, releasable logical-line view.                                                     | `ListFileImageView`.                                                                                                                            | Explicit fixture protects line iteration, counting, and release together.                                                                                                                                                       |
| `pipeline.views.UpdatedContent`                          | Internal repeatable updated-content abstraction used by comparer, planner, context, and writer paths. | `SegmentUpdatedContent`.                                                                                                                        | Explicit fixture plus existing repeatability and runtime-dispatch tests.                                                                                                                                                        |
| `pipeline.steps.writer.WriteSink`                        | Internal callable-like destination seam for final writes.                                             | `StdoutSink`, `InplaceFileSink`, `AtomicFileSink`.                                                                                              | Explicit fixtures cover all three sinks; focused writer tests own I/O behavior.                                                                                                                                                 |
| `processors.base.RuntimeConfigLike`                      | Local import-cycle helper for processor rendering settings.                                           | `FrozenConfig`.                                                                                                                                 | Explicit fixture protects the minimal configuration surface.                                                                                                                                                                    |
| `processors.base.ProcessingContextLike`                  | Local import-cycle helper for processor views and mutable diagnostics.                                | `ProcessingContext`.                                                                                                                            | Explicit fixture protects the minimal processor dependency surface.                                                                                                                                                             |
| `runtime.model._PipelineSelectionLike`                   | Private import-cycle helper keeping runtime state independent of the pipeline catalogue.              | `PipelineSelection`.                                                                                                                            | No dedicated fixture: several typed production calls pass `PipelineSelection` to `RunOptions.from_pipeline_selection()`, so Pyright already enforces it; importing the private protocol into tests would violate its ownership. |

The audit found no members of actively consumed protocols that can be narrowed safely. Read-only
properties remain read-only, `Step[Ctx]` remains generic, `UpdatedContent` retains repeatable
iteration, `Releasable` retains idempotent release expectations, and plugin-facing mutable
attributes remain unchanged.

______________________________________________________________________

## Runtime-checkable protocols

Use `@runtime_checkable` only when runtime attribute-presence checks are intentional or downstream
compatibility already permits `isinstance(value, ProtocolType)`. Such checks validate attribute
presence, not parameter types, return types, mutability, or behavior. They never replace Pyright.

The audited runtime-checkable protocols are:

| Protocol                       | TopMark runtime use                                                                                           | Decision                                                                                                            |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `ConsoleProtocol`              | CLI state uses the stricter `is_console_protocol()` callable guard rather than `isinstance()`.                | Retain the decorator for compatibility; existing CLI tests cover accepted real consoles and rejected invalid state. |
| `ContentMatcher`               | Stored and called as a typed callable; no protocol `isinstance()` check.                                      | Retain for plugin compatibility; no attribute-presence-only test.                                                   |
| `PreInsertHeaderProcessorView` | Consumed through the typed adapter/checker path; no `isinstance()` check.                                     | Retain for compatibility; static signature fixture is the meaningful protection.                                    |
| `PreInsertContextView`         | Consumed through `PreInsertViewAdapter`; no `isinstance()` check.                                             | Retain for compatibility; adapter behavior and static conformance are covered.                                      |
| `InsertChecker`                | Stored and invoked as a typed callable; no `isinstance()` check.                                              | Retain for plugin compatibility; checker behavior and static signatures are covered separately.                     |
| `Releasable`                   | Views are owned through typed slots and released directly; no `isinstance()` check.                           | Retain because downstream lifecycle checks may rely on it; pruning tests validate real release behavior.            |
| `UpdatedContent`               | `ProcessingContext` and planner logic intentionally use `isinstance()` to select repeatable-content handling. | Retain; existing context, planner, updated-content, and writer tests exercise the real boundary.                    |

No decorator was added or removed. Removing a runtime decorator could break downstream
`isinstance()` use even where TopMark itself relies only on static typing.

______________________________________________________________________

## Coverage interpretation

Coverage measures executable behavior, not structural compatibility. Never import a protocol-only
module, instantiate a protocol, invoke an ellipsis body, or add fake implementations merely to
increase its percentage.

The coverage exclusion matches a complete class suite whose base list contains direct `Protocol`,
generic `Protocol[...]`, or `Protocol` alongside other bases. It therefore handles all of:

```python
class Direct(Protocol):
class Step(Protocol[Ctx]):
class FileImageView(Releasable, Protocol):
```

It does not omit modules. Definition-only modules can consequently remain visible at 0% when their
only measurable statements are imports and the test run never imports them. That transparent result
is preferable to omitting whole modules: a future runtime helper added beside a protocol remains
measured automatically. Modules such as `cli.console.protocols`, which contain the executable
`is_console_protocol()` guard, remain fully measured.

______________________________________________________________________

## Adding or changing a protocol

For each new or changed protocol:

1. Name its owner and classification, concrete providers, and consumers.
1. Keep the surface minimal and read-only unless mutation is part of the contract.
1. Add a `tests/typecheck` fixture only for a durable, otherwise non-obvious relationship.
1. Use `@runtime_checkable` only for an intentional dynamic boundary and test TopMark's real control
   flow, not protocol metadata.
1. Treat public or plugin-facing member changes as compatibility changes; update documentation,
   focused tests, and the changelog when observable behavior changes.
1. Run strict Pyright for Python 3.10 and 3.14. Run pytest only for executable behavior changes.
1. Interpret protocol coverage through this policy rather than as a target percentage.
