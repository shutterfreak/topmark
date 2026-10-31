# topmark:header:start
#
#   project      : TopMark
#   file         : test_contribution_policy.py
#   file_relpath : tests/tools/ci/test_contribution_policy.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Tests for contribution policy consistency validation."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest

from tools.ci import check_commit_message_hook as hook
from tools.ci import check_contribution_policy as policy

ROOT: Path = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "returncode, output",
    [
        (3, "installation failed"),
        (1, "CC001"),
    ],
)
def test_hook_runner_rejects_unrelated_failures(
    monkeypatch: pytest.MonkeyPatch,
    returncode: int,
    output: str,
) -> None:
    """An infrastructure error or wrong rule cannot satisfy a negative case."""

    def run(
        command: list[str],
        cwd: Path,
    ) -> subprocess.CompletedProcess[str]:
        if command[0] == "git":
            return subprocess.CompletedProcess(command, 0, "", "")
        message: str = Path(command[-1]).read_text(encoding="utf-8")
        if "Signed-off-by" in message:
            return subprocess.CompletedProcess(command, 0, "", "")
        return subprocess.CompletedProcess(command, returncode, output, "")

    def executable(
        name: str,
    ) -> str:
        return name

    monkeypatch.setattr(hook, "_executable", executable)
    monkeypatch.setattr(hook, "_run", run)
    with pytest.raises(RuntimeError, match="missing sign-off"):
        hook.main()


_REQUIRED_PATHS: tuple[str, ...] = (
    ".github/ISSUE_TEMPLATE/**",
    ".github/pull_request_template.md",
    ".github/.markdownlint.jsonc",
    ".github/cchk.toml",
    "AGENTS.md",
)


def _write_policy(
    root: Path,
    *,
    title_types: str = "feat\nfix\n",
    pr_paths: tuple[str, ...] = _REQUIRED_PATHS,
    precommit_paths: tuple[str, ...] = _REQUIRED_PATHS,
) -> None:
    """Write minimal workflow fixtures from independently specified structures."""
    title_workflow: dict[str, object] = {
        "jobs": {
            "validate-title": {
                "steps": [
                    {
                        "uses": "amannn/action-semantic-pull-request@v1",
                        "with": {"types": title_types},
                    }
                ]
            }
        }
    }
    ci_workflow: dict[str, object] = {
        "on": {"pull_request": {"paths": pr_paths}},
        "jobs": {
            "changes": {
                "steps": [
                    {
                        "uses": "dorny/paths-filter@v1",
                        "with": {"filters": json.dumps({"precommit": precommit_paths})},
                    }
                ]
            }
        },
    }
    files: dict[str, str] = {
        ".github/cchk.toml": '[commit]\nallow_commit_types = ["feat", "fix"]\n',
        # JSON is a YAML 1.2 subset, including for the embedded filter document.
        ".github/workflows/ci.yml": json.dumps(ci_workflow),
        ".github/workflows/pull-request-title.yml": json.dumps(title_workflow),
    }
    for relative, content in files.items():
        destination: Path = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def test_contribution_policy_is_consistent() -> None:
    """Check the actual repository's title types and contributor path coverage."""
    policy.check_policy(ROOT)


@pytest.mark.parametrize(
    "content",
    [
        "",
        "commit = 'invalid'\n",
        "commit = []\n",
    ],
)
def test_rejects_missing_or_non_table_commit_policy(
    tmp_path: Path,
    content: str,
) -> None:
    """Require a commit policy table before reading its allowed types."""
    _write_policy(tmp_path)
    (tmp_path / ".github/cchk.toml").write_text(content, encoding="utf-8")
    with pytest.raises(TypeError, match=r"must define a \[commit\] table"):
        policy.check_policy(tmp_path)


@pytest.mark.parametrize(
    "content",
    [
        "[commit]\n",
        "[commit]\nallow_commit_types = 'fix'\n",
        "[commit]\nallow_commit_types = 42\n",
        '[commit]\nallow_commit_types = ["fix", 42]\n',
    ],
)
def test_rejects_missing_or_invalid_allowed_types(
    tmp_path: Path,
    content: str,
) -> None:
    """Reject missing values, non-lists, and lists containing non-strings."""
    _write_policy(tmp_path)
    (tmp_path / ".github/cchk.toml").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="commit.allow_commit_types must be a list of strings"):
        policy.check_policy(tmp_path)


def test_rejects_mismatched_title_types(
    tmp_path: Path,
) -> None:
    """Report a type added to one policy without updating the other."""
    _write_policy(tmp_path, title_types="feat\nother\n")
    with pytest.raises(ValueError, match="types differ"):
        policy.check_policy(tmp_path)


def test_rejects_missing_title_type_block(
    tmp_path: Path,
) -> None:
    """Report a title action with no allowed types input."""
    _write_policy(tmp_path)
    workflow: Path = tmp_path / ".github/workflows/pull-request-title.yml"
    workflow.write_text(
        "jobs: {validate-title: {steps: [{uses: amannn/action-semantic-pull-request@v1,"
        " with: {}}]}}\n",
        encoding="utf-8",
    )
    with pytest.raises(TypeError, match="PR title workflow types must be text"):
        policy.check_policy(tmp_path)


def test_rejects_missing_pr_trigger_path(
    tmp_path: Path,
) -> None:
    """Report contributor files missing from the PR workflow trigger."""
    _write_policy(
        tmp_path,
        pr_paths=tuple(path for path in _REQUIRED_PATHS if path != "AGENTS.md"),
    )
    with pytest.raises(ValueError, match="PR paths.*AGENTS.md"):
        policy.check_policy(tmp_path)


@pytest.mark.parametrize(
    "content, message",
    [
        ("on: {pull_request: {paths: invalid}}\n", "workflow jobs must be a mapping"),
        ("on: {pull_request: {paths: []}}\njobs: {changes: {steps: []}}\n", "exactly one"),
        ("on: invalid\n", "CI workflow on must be a mapping"),
    ],
)
def test_rejects_invalid_ci_structure(
    tmp_path: Path,
    content: str,
    message: str,
) -> None:
    """Report missing or invalid workflow structures."""
    _write_policy(tmp_path)
    (tmp_path / ".github/workflows/ci.yml").write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=message):
        policy.check_policy(tmp_path)


@pytest.mark.parametrize(
    "ci_workflow, title_workflow",
    [
        (
            dedent(
                """\
                on:
                  pull_request:
                    paths:
                      - '.github/ISSUE_TEMPLATE/**'
                      - '.github/pull_request_template.md'
                      - '.github/.markdownlint.jsonc'
                      - '.github/cchk.toml'
                      - AGENTS.md
                jobs:
                  changes:
                    steps:
                      - uses: dorny/paths-filter@v1
                        with:
                          filters: |
                            precommit:
                              - '.github/ISSUE_TEMPLATE/**'
                              - '.github/pull_request_template.md'
                              - '.github/.markdownlint.jsonc'
                              - '.github/cchk.toml'
                              - AGENTS.md
                """
            ),
            dedent(
                """\
                jobs:
                  validate-title:
                    steps:
                      - uses: amannn/action-semantic-pull-request@v1
                        with:
                          types: |
                            feat
                            fix
                """
            ),
        ),
        (
            dedent(
                """\
                jobs:
                  changes:
                    steps:
                      - with:
                          filters: >-
                            {precommit: [".github/ISSUE_TEMPLATE/**",
                            ".github/pull_request_template.md", ".github/.markdownlint.jsonc",
                            ".github/cchk.toml", "AGENTS.md"]}
                        uses: dorny/paths-filter@v1
                on: {pull_request: {paths: [".github/ISSUE_TEMPLATE/**",
                  ".github/pull_request_template.md", ".github/.markdownlint.jsonc",
                  ".github/cchk.toml", "AGENTS.md"]}}
                """
            ),
            dedent(
                """\
                jobs: {validate-title: {steps: [{with: {types: "fix feat"},
                  uses: amannn/action-semantic-pull-request@v1}]}}
                """
            ),
        ),
    ],
    ids=["block-style", "flow-style"],
)
def test_yaml_formatting_does_not_change_checks(
    tmp_path: Path,
    ci_workflow: str,
    title_workflow: str,
) -> None:
    """Accept independently written equivalent YAML with different presentations."""
    _write_policy(tmp_path)
    (tmp_path / ".github/workflows/ci.yml").write_text(ci_workflow, encoding="utf-8")
    (tmp_path / ".github/workflows/pull-request-title.yml").write_text(
        title_workflow, encoding="utf-8"
    )
    policy.check_policy(tmp_path)


def test_rejects_missing_precommit_path(
    tmp_path: Path,
) -> None:
    """Report contributor files missing from the pre-commit change filter."""
    _write_policy(
        tmp_path,
        precommit_paths=tuple(path for path in _REQUIRED_PATHS if path != "AGENTS.md"),
    )
    with pytest.raises(ValueError, match="pre-commit paths.*AGENTS.md"):
        policy.check_policy(tmp_path)
