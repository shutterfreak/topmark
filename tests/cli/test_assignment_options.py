# topmark:header:start
#
#   project      : TopMark
#   file         : test_assignment_options.py
#   file_relpath : tests/cli/test_assignment_options.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI token parsing and end-to-end ordered assignment behavior."""

from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click
import pytest
from click.testing import CliRunner
from click.testing import Result

from tests.cli.conftest import assert_rich_output_no_such_option
from tests.helpers.json import parse_json_object
from topmark.cli.assignments import AssignmentCommand
from topmark.cli.assignments import cli_file_type_rules
from topmark.cli.assignments import parse_assignment_value
from topmark.cli.keys import CliCmd
from topmark.cli.keys import CliOpt
from topmark.cli.main import cli
from topmark.core.constants import TOPMARK_START_MARKER
from topmark.core.exit_codes import ExitCode
from topmark.core.formats import OutputFormat
from topmark.core.typing_guards import as_object_dict
from topmark.core.typing_guards import is_any_list
from topmark.pipeline.reporting import ReportScope

if TYPE_CHECKING:
    from topmark.config.assignments import FileTypeRule


@pytest.mark.parametrize(
    "pattern",
    [
        "*.json",
        "a=b=c",
        "a:b:c",
        "with spaces",
        "é雪",
        "a,b",
        "a[12]?*",
        r"a\[1\]",
        " leading",
        "trailing ",
        "-leading",
        r"dir\file",
    ],
)
@pytest.mark.parametrize("joined", [False, True])
def test_token_preservation(
    pattern: str,
    *,
    joined: bool,
) -> None:
    """The TopMark parser and Click orchestration preserve exact pattern suffixes."""
    assert parse_assignment_value("jsonc=" + pattern) == {
        "file_type": "jsonc",
        "patterns": [pattern],
    }
    captured: list[str] = []

    @click.command(cls=AssignmentCommand)
    @click.option(CliOpt.ASSIGN_FILETYPE, multiple=True, expose_value=False)
    @click.option(CliOpt.INFER_FILETYPE, multiple=True, expose_value=False)
    def command() -> None:
        rules: list[FileTypeRule] = cli_file_type_rules(click.get_current_context())
        captured.extend(p for rule in rules for p in rule.patterns)
        assert [r.action for r in rules] == ["assign", "infer", "assign"]

    args: list[str] = []
    for name, value in [
        (CliOpt.ASSIGN_FILETYPE, "jsonc=" + pattern),
        (CliOpt.INFER_FILETYPE, pattern),
        (CliOpt.ASSIGN_FILETYPE, "topmark:jsonc=" + pattern),
    ]:
        args.extend([name + "=" + value] if joined else [name, value])
    result: Result = CliRunner().invoke(command, args)
    assert result.exit_code == 0, result.output
    assert captured == [pattern] * 3


@pytest.mark.parametrize(
    "value",
    [
        "jsonc",
        "=*.json",
        "jsonc=",
        "",
        " jsonc=*.json",
        "jsonc =*.json",
        "missing=*",
        "topmark:jsonc:extra=*",
        "jsonc=!x",
        "jsonc=#x",
    ],
)
def test_invalid_cli_values(
    value: str,
) -> None:
    """Malformed options fail before command execution with actionable errors."""
    result: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.PROBE,
            CliOpt.NO_CONFIG,
            CliOpt.ASSIGN_FILETYPE,
            value,
        ],
    )
    assert result.exit_code == 2, result.output


def _probe(
    output: str,
) -> dict[str, object]:
    """Read the first probe payload from a JSON document."""
    probes: object = parse_json_object(output)["probes"]
    assert is_any_list(probes) and probes
    return as_object_dict(probes[0])


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("fmt", [OutputFormat.JSON, OutputFormat.NDJSON])
def test_cli_interleaving_winner_and_machine_verbosity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    reverse: bool,
    fmt: OutputFormat,
) -> None:
    """Actual command-line interleaving reverses the winner in both machine formats."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "test.json").write_text("{}\n", encoding="utf-8")
    options: list[str] = [
        f"{CliOpt.ASSIGN_FILETYPE}=jsonc=*.json",
        CliOpt.INFER_FILETYPE,
        "*.json",
    ]
    if reverse:
        options = [
            f"{CliOpt.INFER_FILETYPE}=*.json",
            CliOpt.ASSIGN_FILETYPE,
            "jsonc=*.json",
        ]
    args: list[str] = [
        CliCmd.PROBE,
        "test.json",
        CliOpt.NO_CONFIG,
        CliOpt.OUTPUT_FORMAT,
        fmt.value,
        *options,
    ]
    runner = CliRunner()
    normal: Result = runner.invoke(cli, args)
    verbose: Result = runner.invoke(cli, [*args, "-vv"])
    assert normal.exit_code == verbose.exit_code
    assert normal.stdout == verbose.stdout
    assert (
        '"selection_method": "assignment"' in normal.stdout
        if reverse
        else '"selection_method": "inference"' in normal.stdout
    )
    if fmt == OutputFormat.JSON:
        probe: dict[str, object] = _probe(normal.stdout)
        matches: object = probe["rule_matches"]
        assert is_any_list(matches) and len(matches) == 2
        assert as_object_dict(matches[-1])["selected"] is True
        if reverse:
            assert probe["candidates"] == []
            assert "score" not in as_object_dict(probe["selected_file_type"])


def test_jsonc_check_idempotence_and_strip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Comment-free assigned JSONC inserts once and strips through the bound processor."""
    monkeypatch.chdir(tmp_path)
    path: Path = tmp_path / "service.json"
    path.write_text("{}\n", encoding="utf-8")
    runner = CliRunner()
    options: list[str] = [
        CliOpt.NO_CONFIG,
        CliOpt.ASSIGN_FILETYPE,
        "jsonc=*.json",
    ]
    first: Result = runner.invoke(
        cli,
        [
            CliCmd.CHECK,
            "service.json",
            CliOpt.APPLY_CHANGES,
            *options,
        ],
    )
    assert first.exit_code == 0, first.output
    inserted: str = path.read_text(encoding="utf-8")
    assert TOPMARK_START_MARKER in inserted
    second: Result = runner.invoke(
        cli,
        [
            CliCmd.CHECK,
            "service.json",
            CliOpt.APPLY_CHANGES,
            *options,
        ],
    )
    assert second.exit_code == 0, second.output
    assert path.read_text(encoding="utf-8") == inserted
    stripped: Result = runner.invoke(
        cli,
        [
            CliCmd.STRIP,
            "service.json",
            CliOpt.APPLY_CHANGES,
            *options,
        ],
    )
    assert stripped.exit_code == 0, stripped.output
    assert path.read_text(encoding="utf-8") == "{}\n"


def test_cli_descendant_rules_are_discovered_from_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Root-invoked descendant rules override ancestors without leaking into siblings."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "topmark.toml").write_text(
        """[config]
root = true
[[files.file_type_assignments]]
file_type = "jsonc"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    for name in ("local", "sibling"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "a.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "local/topmark.toml").write_text(
        """[[files.file_type_assignments]]
action = "infer"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    cli_result: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.PROBE,
            ".",
            f"{CliOpt.OUTPUT_FORMAT}=json",
        ],
    )
    assert cli_result.exit_code in (0, 69), cli_result.output
    assert '"action": "infer"' in cli_result.stdout


@pytest.mark.parametrize(
    ("target", "extra", "status"),
    [
        ("jsonc", [CliOpt.EXCLUDE_FILE_TYPE, "jsonc"], "filtered"),
        ("jsonc", [CliOpt.EXCLUDE_FILE_TYPE, "json"], "resolved"),
        ("jsonc", [CliOpt.INCLUDE_FILE_TYPE, "json"], "filtered"),
        ("jsonc", [CliOpt.INCLUDE_FILE_TYPE, "jsonc"], "resolved"),
        ("json", [], "activation_blocked"),
        ("json-as-jsonc", [], "activation_blocked"),
        ("json-as-jsonc", [CliOpt.OPT_IN_FILE_TYPE, "json-as-jsonc"], "resolved"),
    ],
)
def test_assigned_outcomes_and_stdin(
    target: str,
    extra: list[str],
    status: str,
) -> None:
    """Synthetic filenames match rules while activation and filters retain their veto."""
    result: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.PROBE,
            "-",
            CliOpt.STDIN_FILENAME,
            "config/s.json",
            CliOpt.NO_CONFIG,
            CliOpt.ASSIGN_FILETYPE,
            target + "=config/*.json",
            f"{CliOpt.OUTPUT_FORMAT}=json",
            *extra,
        ],
        input="{}\n",
    )
    assert result.exit_code in (0, 69), result.output
    probe: dict[str, object] = _probe(result.stdout)
    assert probe["status"] == status
    assert probe["selection_method"] == "assignment"


def test_config_diagnostics_and_dump(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """File-agnostic validation diagnoses contradictory duplicates without filesystem scans."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    args: list[str] = [
        CliOpt.NO_CONFIG,
        CliOpt.ASSIGN_FILETYPE,
        "jsonc=missing*.json",
        CliOpt.INFER_FILETYPE,
        "missing*.json",
    ]
    normal: Result = runner.invoke(
        cli,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            *args,
        ],
    )
    strict: Result = runner.invoke(
        cli,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_CHECK,
            CliOpt.STRICT,
            *args,
        ],
    )
    assert normal.exit_code == 0, normal.output
    assert strict.exit_code == 78, strict.output
    dump: Result = runner.invoke(
        cli,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.NO_CONFIG,
            CliOpt.ASSIGN_FILETYPE,
            "git-meta=.aiderignore",
            f"{CliOpt.OUTPUT_FORMAT}=json",
        ],
    )
    assert dump.exit_code == 0, dump.output
    assert '"file_type": "topmark:git-meta"' in dump.stdout


def test_git_meta_assignment_processing_and_discovery_exclusions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assignments process selected dotfiles but cannot resurrect excluded inputs."""
    monkeypatch.chdir(tmp_path)
    path: Path = tmp_path / ".aiderignore"
    path.write_text("secrets/\n", encoding="utf-8")
    runner = CliRunner()
    options: list[str] = [
        CliOpt.NO_CONFIG,
        CliOpt.ASSIGN_FILETYPE,
        "git-meta=.aiderignore",
    ]
    applied: Result = runner.invoke(
        cli,
        [
            CliCmd.CHECK,
            ".aiderignore",
            CliOpt.APPLY_CHANGES,
            *options,
        ],
    )
    assert applied.exit_code == 0, applied.output
    assert f"# {TOPMARK_START_MARKER}" in path.read_text(encoding="utf-8")
    excluded: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            ".aiderignore",
            *options,
            CliOpt.EXCLUDE_PATTERNS,
            ".aiderignore",
            f"{CliOpt.OUTPUT_FORMAT}=json",
        ],
    )
    assert excluded.exit_code == 69, excluded.output
    assert _probe(excluded.stdout)["reason"] == "excluded_by_path_filter"


def test_assigned_json_as_jsonc_keeps_insertion_guard(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct recognition of json-as-jsonc does not bypass its insertion guard."""
    monkeypatch.chdir(tmp_path)
    path: Path = tmp_path / "service.json"
    path.write_text("{}\n", encoding="utf-8")
    result: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.CHECK,
            "service.json",
            CliOpt.NO_CONFIG,
            CliOpt.APPLY_CHANGES,
            CliOpt.ASSIGN_FILETYPE,
            "json-as-jsonc=*.json",
            CliOpt.OPT_IN_FILE_TYPE,
            "json-as-jsonc",
        ],
    )
    assert result.exit_code in (0, 1), result.output
    assert path.read_text(encoding="utf-8") == "{}\n"


def test_toml_pyproject_explicit_and_cli_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same-directory sources and explicit sources precede CLI in stable order."""
    monkeypatch.chdir(tmp_path)
    path: Path = tmp_path / "a.json"
    path.write_text("{}\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """[tool.topmark.config]
root = true
[[tool.topmark.files.file_type_assignments]]
file_type = "jsonc"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    (tmp_path / "topmark.toml").write_text(
        """[[files.file_type_assignments]]
action = "infer"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    explicit: Path = tmp_path / "extra.toml"
    explicit.write_text(
        """[[files.file_type_assignments]]
file_type = "jsonc"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    runner = CliRunner()
    base: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            "a.json",
            f"{CliOpt.OUTPUT_FORMAT}=json",
        ],
    )
    assert _probe(base.stdout)["selection_method"] == "inference"
    override: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            "a.json",
            CliOpt.CONFIG_FILES,
            "extra.toml",
            f"{CliOpt.OUTPUT_FORMAT}=json",
        ],
    )
    assert _probe(override.stdout)["selection_method"] == "assignment"
    final: Result = runner.invoke(
        cli,
        [
            CliCmd.PROBE,
            "a.json",
            CliOpt.CONFIG_FILES,
            "extra.toml",
            CliOpt.INFER_FILETYPE,
            "*.json",
            f"{CliOpt.OUTPUT_FORMAT}=json",
        ],
    )
    assert _probe(final.stdout)["selection_method"] == "inference"
    matches: object = _probe(final.stdout)["rule_matches"]
    assert is_any_list(matches) and len(matches) == 4
    assert [as_object_dict(m)["action"] for m in matches] == [
        "assign",
        "infer",
        "assign",
        "infer",
    ]


@pytest.mark.parametrize("fmt", ["text", "markdown"])
def test_human_winner_and_verbose_superseded_rules(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fmt: str,
) -> None:
    """TEXT progressively reveals superseded matches; Markdown always includes them."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.json").write_text("{}\n", encoding="utf-8")
    args: list[str] = [
        CliCmd.PROBE,
        "a.json",
        CliOpt.NO_CONFIG,
        CliOpt.ASSIGN_FILETYPE,
        "jsonc=*.json",
        CliOpt.INFER_FILETYPE,
        "a.json",
        CliOpt.OUTPUT_FORMAT,
        fmt,
    ]
    runner = CliRunner()
    concise: Result = runner.invoke(cli, args)
    verbose: Result = runner.invoke(cli, [*args, "-v"])
    assert concise.exit_code == verbose.exit_code
    assert "winning infer" in concise.stdout
    if fmt == "markdown":
        assert concise.stdout == verbose.stdout
        assert "superseded assign" in concise.stdout
    else:
        assert "superseded assign" not in concise.stdout
    assert "superseded assign" in verbose.stdout


@pytest.mark.parametrize("label_args", [["-vvl", CliOpt.INFER_FILETYPE], ["-vvl--infer-filetype"]])
def test_rule_token_capture_respects_other_values_and_end_of_options(
    label_args: list[str],
) -> None:
    """Click option values and positional tokens must not become phantom rule options."""
    captured: list[str] = []

    @click.command(cls=AssignmentCommand)
    @click.option(CliOpt.ASSIGN_FILETYPE, multiple=True, expose_value=False)
    @click.option(CliOpt.INFER_FILETYPE, multiple=True, expose_value=False)
    @click.option("-v", count=True, expose_value=False)
    @click.option("-l", "--label", expose_value=False)
    @click.argument("paths", nargs=-1)
    def command(paths: tuple[str, ...]) -> None:
        assert paths == (f"{CliOpt.ASSIGN_FILETYPE}=jsonc=phantom",)
        captured.extend(r.action for r in cli_file_type_rules(click.get_current_context()))

    result: Result = CliRunner().invoke(
        command,
        [
            *label_args,
            f"{CliOpt.ASSIGN_FILETYPE}=jsonc=*.json",
            "--",
            f"{CliOpt.ASSIGN_FILETYPE}=jsonc=phantom",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured == ["assign"]


def test_assignment_policy_scope_does_not_leak_to_siblings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assigned types retain the policy from their own effective configuration scope."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "topmark.toml").write_text(
        """[config]
root = true
[[files.file_type_assignments]]
file_type = "jsonc"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    for directory in ("local", "sibling"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "a.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "local/topmark.toml").write_text(
        """[policy_by_type."topmark:jsonc"]
header_mutation_mode = "update_only"
""",
        encoding="utf-8",
    )
    result: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.CHECK,
            ".",
            CliOpt.APPLY_CHANGES,
            CliOpt.INCLUDE_FILE_TYPE,
            "jsonc",
        ],
    )
    assert result.exit_code == 0, result.output
    assert (tmp_path / "local/a.json").read_text(encoding="utf-8") == "{}\n"
    assert TOPMARK_START_MARKER in (tmp_path / "sibling/a.json").read_text(encoding="utf-8")


def test_assignment_activation_consent_stays_in_its_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Local opt-in consent authorizes local assignments without authorizing siblings."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "topmark.toml").write_text(
        """[config]
root = true
[[files.file_type_assignments]]
file_type = "json-as-jsonc"
patterns = ["*.json"]
""",
        encoding="utf-8",
    )
    for directory in ("local", "sibling"):
        (tmp_path / directory).mkdir()
        (tmp_path / directory / "a.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "local/topmark.toml").write_text(
        """[files]
opt_in_file_types = ["json-as-jsonc"]
""",
        encoding="utf-8",
    )
    output: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.PROBE,
            ".",
            CliOpt.INCLUDE_FILE_TYPE,
            "json-as-jsonc",
            f"{CliOpt.OUTPUT_FORMAT}=json",
        ],
    )
    payloads: object = parse_json_object(output.stdout)["probes"]
    assert is_any_list(payloads)
    statuses: dict[str, object] = {
        str(as_object_dict(p)["path"]).split("/")[-2]: as_object_dict(p)["status"] for p in payloads
    }
    assert statuses == {
        "local": "resolved",
        "sibling": "activation_blocked",
    }


@pytest.mark.parametrize(("suffix", "status"), [("json", "filtered"), ("unknown", "unsupported")])
def test_filtered_inference_control_keeps_winner_and_superseded_provenance(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    suffix: str,
    status: str,
) -> None:
    """A type-filtered inference winner remains visible instead of disappearing at discovery."""
    monkeypatch.chdir(tmp_path)
    filename: str = "a." + suffix
    (tmp_path / filename).write_text("{}\n", encoding="utf-8")
    result: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.PROBE,
            filename,
            CliOpt.NO_CONFIG,
            CliOpt.ASSIGN_FILETYPE,
            "jsonc=*",
            CliOpt.INFER_FILETYPE,
            filename,
            CliOpt.INCLUDE_FILE_TYPE,
            "python",
            f"{CliOpt.OUTPUT_FORMAT}=json",
        ],
    )
    assert result.exit_code == 69, result.output
    probe: dict[str, object] = _probe(result.stdout)
    assert probe["status"] == status
    assert probe["reason"] == (
        "excluded_by_file_type_filter" if status == "filtered" else "no_candidates"
    )
    assert probe["selection_method"] == "inference"
    matches: object = probe["rule_matches"]
    assert is_any_list(matches) and len(matches) == 2
    assert as_object_dict(matches[-1])["action"] == "infer"


@pytest.mark.parametrize(
    "filename",
    [
        "literal[1] 'quoted'.json",
        pytest.param(
            "trailing.json ",
            marks=pytest.mark.skipif(
                sys.platform == "win32",
                reason="Windows filesystem paths do not preserve trailing-space filenames",
            ),
        ),
    ],
)
@pytest.mark.parametrize("source", ["cli", "toml"])
@pytest.mark.parametrize("command", [CliCmd.CHECK, CliCmd.STRIP])
@pytest.mark.parametrize("fmt", [OutputFormat.TEXT, OutputFormat.MARKDOWN])
def test_assignment_guidance_command_can_be_replayed_for_one_literal_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    source: str,
    filename: str,
    command: str,
    fmt: OutputFormat,
) -> None:
    """Per-file remediation replays the assigned type without depending on the broad source rule."""
    monkeypatch.chdir(tmp_path)
    directory: Path = tmp_path / "tests"
    directory.mkdir()
    path: Path = directory / filename
    path.write_text("{}\n", encoding="utf-8")
    options: list[str] = [
        CliOpt.ASSIGN_FILETYPE,
        "jsonc=tests/**/*.json*",
    ]
    if source == "toml":
        (tmp_path / "topmark.toml").write_text(
            """[config]
root = true
[[files.file_type_assignments]]
file_type = "jsonc"
patterns = ["tests/**/*.json*"]
""",
            encoding="utf-8",
        )
        options = []
    runner = CliRunner()
    if command == CliCmd.STRIP:
        prepare: Result = runner.invoke(
            cli,
            [
                CliCmd.CHECK,
                "tests",
                CliOpt.APPLY_CHANGES,
                *options,
            ],
        )
        assert prepare.exit_code == 0, prepare.output
    preview: Result = runner.invoke(
        cli,
        [
            command,
            "tests",
            CliOpt.OUTPUT_FORMAT,
            fmt,
            *options,
        ],
    )
    assert preview.exit_code == ExitCode.WOULD_CHANGE, preview.output
    suggested: str = preview.stdout.split("Run `", 1)[1].split("`", 1)[0]
    args: list[str] = shlex.split(suggested)
    assert args[:3] == [
        "topmark",
        command,
        CliOpt.ASSIGN_FILETYPE,
    ]
    assert args[3].startswith("topmark:jsonc=")
    assert "**" not in args[3]
    # Human command paths may use native separators; rule patterns always use POSIX.
    assert Path(args[-1]) == path.relative_to(tmp_path)
    assert args[3].partition("=")[2].startswith("tests/")
    # Remove the source rule to prove the suggestion carries its own exact assignment.
    if source == "toml":
        (tmp_path / "topmark.toml").unlink()
    applied: Result = runner.invoke(cli, args[1:])
    assert applied.exit_code == 0, applied.output
    content: str = path.read_text(encoding="utf-8")
    assert (TOPMARK_START_MARKER in content) is (command == CliCmd.CHECK)
    if command == "strip":
        assert content == "{}\n"


@pytest.mark.parametrize("fmt", ["text", "markdown"])
def test_inference_control_guidance_does_not_pin_an_assignment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fmt: str,
) -> None:
    """A winning inference control keeps automatic recognition in the suggested rerun."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sample.py").write_text("{}\n", encoding="utf-8")
    result: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.CHECK,
            "sample.py",
            CliOpt.NO_CONFIG,
            CliOpt.ASSIGN_FILETYPE,
            "jsonc=*.py",
            CliOpt.INFER_FILETYPE,
            "sample.py",
            CliOpt.OUTPUT_FORMAT,
            fmt,
        ],
    )
    assert result.exit_code == ExitCode.WOULD_CHANGE, result.output
    suggested: str = result.stdout.split("Run `", 1)[1].split("`", 1)[0]
    assert CliOpt.ASSIGN_FILETYPE not in shlex.split(suggested)


@pytest.mark.parametrize("fmt", [OutputFormat.JSON, OutputFormat.NDJSON])
@pytest.mark.parametrize(
    ("selection", "assigned"),
    [
        ("automatic", False),
        ("assign", True),
        ("infer", False),
        ("unsupported", None),
    ],
)
def test_processing_machine_origin_flag_is_stable_across_verbosity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fmt: OutputFormat,
    selection: str,
    assigned: bool | None,
) -> None:
    """Processing machine payloads expose compact origin independently of human verbosity."""
    monkeypatch.chdir(tmp_path)
    filename: str = "sample.unknown" if selection == "unsupported" else "sample.py"
    (tmp_path / filename).write_text("{}\n", encoding="utf-8")
    options: list[str] = []
    if selection in ("assign", "infer"):
        options.extend([CliOpt.ASSIGN_FILETYPE, "jsonc=*"])
    if selection == "infer":
        options.extend([CliOpt.INFER_FILETYPE, filename])
    args: list[str] = [
        CliCmd.CHECK,
        filename,
        CliOpt.NO_CONFIG,
        CliOpt.REPORT,
        ReportScope.ALL,
        CliOpt.OUTPUT_FORMAT,
        fmt.value,
        *options,
    ]
    runner = CliRunner()
    normal: Result = runner.invoke(cli, args)
    verbose: Result = runner.invoke(cli, [*args, "-vv"])
    assert normal.exit_code == verbose.exit_code
    assert normal.stdout == verbose.stdout
    if fmt == OutputFormat.JSON:
        results: object = parse_json_object(normal.stdout)["results"]
        assert is_any_list(results) and len(results) == 1
        result: dict[str, object] = as_object_dict(results[0])
    else:  # fmt == OutputFormat.NDJSON:
        records: list[dict[str, object]] = [
            parse_json_object(line) for line in normal.stdout.splitlines()
        ]
        results = [
            as_object_dict(record["result"]) for record in records if record["kind"] == "result"
        ]
        assert len(results) == 1
        result = results[0]
    assert result["file_type_assigned"] is assigned


def test_rule_token_capture_defers_unknown_short_option_error_to_click() -> None:
    """An unknown short option keeps Click's parser error without executing the callback."""

    @click.command(cls=AssignmentCommand)
    @click.option(CliOpt.ASSIGN_FILETYPE, multiple=True, expose_value=False)
    def command() -> None:
        pytest.fail("Invalid arguments must not execute the callback")

    result: Result = CliRunner().invoke(
        command,
        [
            "-Z",
            f"{CliOpt.ASSIGN_FILETYPE}=jsonc=*.json",
        ],
    )
    assert_rich_output_no_such_option(result, option_name="-Z")


@pytest.mark.parametrize(
    "output_format",
    [
        OutputFormat.TEXT,
        OutputFormat.MARKDOWN,
        OutputFormat.JSON,
        OutputFormat.NDJSON,
    ],
)
def test_cli_rule_source_labels_across_output_formats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_format: OutputFormat,
) -> None:
    """Probe presentation preserves the component and enclosing override labels."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.json").write_text("{}\n", encoding="utf-8")
    result: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.PROBE,
            "a.json",
            CliOpt.NO_CONFIG,
            CliOpt.ASSIGN_FILETYPE,
            "jsonc=*.json",
            CliOpt.OUTPUT_FORMAT,
            output_format.value,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "<CLI assignments>" in result.stdout
    if output_format in ("json", "ndjson"):
        assert "<CLI overrides>" in result.stdout
    assert "SyntheticConfigSource" not in result.stdout
    assert (tmp_path / "<CLI overrides>").as_posix() not in result.stdout


@pytest.mark.parametrize(
    "output_format",
    [
        OutputFormat.TEXT,
        OutputFormat.MARKDOWN,
        OutputFormat.JSON,
        OutputFormat.NDJSON,
    ],
)
def test_cli_dump_source_labels_across_output_formats(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    output_format: OutputFormat,
) -> None:
    """Layered dumps preserve default, override, and assignment spellings."""
    monkeypatch.chdir(tmp_path)
    result: Result = CliRunner().invoke(
        cli,
        [
            CliCmd.CONFIG,
            CliCmd.CONFIG_DUMP,
            CliOpt.NO_CONFIG,
            CliOpt.SHOW_CONFIG_LAYERS,
            CliOpt.ASSIGN_FILETYPE,
            "jsonc=*.json",
            CliOpt.OUTPUT_FORMAT,
            output_format.value,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "<defaults>" in result.stdout
    assert "<CLI overrides>" in result.stdout
    assert "<CLI assignments>" in result.stdout
    assert "SyntheticConfigSource" not in result.stdout
