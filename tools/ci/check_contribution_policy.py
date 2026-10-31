# topmark:header:start
#
#   project      : TopMark
#   file         : check_contribution_policy.py
#   file_relpath : tools/ci/check_contribution_policy.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Validate contribution policy and CI path consistency."""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from typing import TypeGuard
from typing import cast

from ruamel.yaml import YAML


class _YamlLoader(Protocol):
    def load(
        self,
        stream: str,
    ) -> object:
        """Load a YAML document from text."""
        ...


_ROOT: Path = Path(__file__).resolve().parents[2]


# Keep these guards local so this repository tool does not depend on TopMark's runtime package.


def is_mapping(
    obj: object,
) -> TypeGuard[Mapping[object, object]]:
    """Check whether a value is a mapping without validating its contents."""
    return isinstance(obj, Mapping)


def is_any_list(
    obj: object,
) -> TypeGuard[list[object]]:
    """Check whether a value is a list without validating its contents."""
    return isinstance(obj, list)


def is_str_list(
    obj: object,
) -> TypeGuard[list[str]]:
    """Check whether a value is a list containing only strings."""
    return is_any_list(obj) and all(isinstance(x, str) for x in obj)


def _mapping(
    value: object,
    label: str,
) -> Mapping[object, object]:
    """Require a mapping at a named configuration location."""
    if not is_mapping(value):
        raise ValueError(f"{label} must be a mapping")
    return value


def _load_yaml(
    text: str,
    label: str,
) -> Mapping[object, object]:
    """Load YAML 1.2 safely and require a mapping at its root."""
    # ruamel.yaml leaves the stream type partly unknown; this boundary accepts text.
    loader: _YamlLoader = cast("_YamlLoader", YAML(typ="safe", pure=True))
    value: object = loader.load(text)
    return _mapping(value, label)


def _action_inputs(
    workflow: Mapping[object, object],
    job: str,
    action: str,
) -> Mapping[object, object]:
    """Find exactly one action in a job and return its inputs."""
    jobs: Mapping[object, object] = _mapping(workflow.get("jobs"), "workflow jobs")
    job_config: Mapping[object, object] = _mapping(jobs.get(job), f"job {job}")
    steps: object = job_config.get("steps")
    if not is_any_list(steps):
        raise ValueError(f"job {job} steps must be a list")
    matches: list[Mapping[object, object]] = []
    for step in steps:
        step_config: Mapping[object, object] = _mapping(step, f"job {job} step")
        uses: object = step_config.get("uses")
        if isinstance(uses, str) and uses.startswith(f"{action}@"):
            matches.append(step_config)
    if len(matches) != 1:
        raise ValueError(f"job {job} must contain exactly one {action} action")
    return _mapping(matches[0].get("with"), f"{action} inputs")


def check_policy(
    root: Path,
) -> None:
    """Check contribution policy and CI path alignment in a repository."""
    policy: dict[str, object] = tomllib.loads(
        (root / ".github/cchk.toml").read_text(encoding="utf-8")
    )

    commit_policy: object = policy.get("commit")
    if not is_mapping(commit_policy):
        raise TypeError("cchk.toml must define a [commit] table")

    commit_types: object = commit_policy.get("allow_commit_types")
    if not is_str_list(commit_types):
        raise ValueError("commit.allow_commit_types must be a list of strings")

    title_workflow: Mapping[object, object] = _load_yaml(
        (root / ".github/workflows/pull-request-title.yml").read_text(encoding="utf-8"),
        "PR title workflow",
    )
    title_inputs: Mapping[object, object] = _action_inputs(
        title_workflow, "validate-title", "amannn/action-semantic-pull-request"
    )
    title_type_text: object = title_inputs.get("types")
    if not isinstance(title_type_text, str):
        raise TypeError("PR title workflow types must be text")
    title_types: list[str] = title_type_text.split()

    if set(commit_types) != set(title_types):
        raise ValueError(f"Commit and PR title types differ: {commit_types!r} != {title_types!r}")

    ci: Mapping[object, object] = _load_yaml(
        (root / ".github/workflows/ci.yml").read_text(encoding="utf-8"),
        "CI workflow",
    )
    triggers: Mapping[object, object] = _mapping(
        ci.get("on"),
        "CI workflow on",
    )
    pull_request: Mapping[object, object] = _mapping(
        triggers.get("pull_request"),
        "CI workflow pull_request",
    )
    pr_paths: object = pull_request.get("paths")
    inputs: Mapping[object, object] = _action_inputs(
        ci,
        "changes",
        "dorny/paths-filter",
    )
    filters_text: object = inputs.get("filters")
    if not isinstance(filters_text, str):
        raise TypeError("paths-filter filters must be text")
    filters: Mapping[object, object] = _load_yaml(
        filters_text,
        "paths-filter filters",
    )
    precommit_paths: object = filters.get("precommit")
    if not is_str_list(pr_paths):
        raise ValueError("PR paths must be a list of strings")
    if not is_str_list(precommit_paths):
        raise ValueError("pre-commit paths must be a list of strings")
    required = (
        ".github/ISSUE_TEMPLATE/**",
        ".github/pull_request_template.md",
        ".github/.markdownlint.jsonc",
        ".github/cchk.toml",
        "AGENTS.md",
    )
    for path in required:
        for label, section in (
            ("PR paths", pr_paths),
            ("pre-commit paths", precommit_paths),
        ):
            if path not in section:
                raise ValueError(f"{label} do not include {path}")


def main() -> None:
    """Check contribution policy and CI path alignment."""
    check_policy(_ROOT)
    print("Contribution policy checks passed")


if __name__ == "__main__":
    main()
