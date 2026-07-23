# topmark:header:start
#
#   project      : TopMark
#   file         : test_cli_types.py
#   file_relpath : tests/cli/test_cli_types.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""CLI Click parameter type contract tests."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import click
import pytest

from topmark.cli.cli_types import CliWriteMode
from topmark.cli.cli_types import EnumChoiceParam
from topmark.cli.cli_types import FileTypeParam
from topmark.cli.cli_types import GlobParam

if TYPE_CHECKING:
    from click.shell_completion import CompletionItem


class _Mode(Enum):
    """Small enum used to pin enum choice parsing behavior."""

    DRY_RUN = "dry_run"
    APPLY = "apply"


def test_cli_write_mode_is_a_typed_cli_only_choice() -> None:
    """Write-mode parsing should return the private CLI-boundary enum."""
    param: EnumChoiceParam[CliWriteMode] = EnumChoiceParam(CliWriteMode)

    assert param.choices == ["atomic", "inplace", "stdout"]
    assert param.convert("atomic", None, None) is CliWriteMode.ATOMIC
    assert param.convert("inplace", None, None) is CliWriteMode.INPLACE
    assert param.convert("stdout", None, None) is CliWriteMode.STDOUT


def test_enum_choice_param_accepts_only_canonical_kebab_case() -> None:
    """Kebab-case enum choices should accept only exact displayed spellings."""
    param: EnumChoiceParam[_Mode] = EnumChoiceParam(_Mode, kebab_case=True)

    assert param.choices == ["dry-run", "apply"]
    assert param.convert("dry-run", None, None) is _Mode.DRY_RUN
    assert param.convert("apply", None, None) is _Mode.APPLY
    assert param.convert(_Mode.DRY_RUN, None, None) is _Mode.DRY_RUN
    assert repr(param) == "EnumChoiceParam(_Mode)"


@pytest.mark.parametrize(
    ("invalid_value", "canonical_value"),
    [
        pytest.param("DRY-RUN", "dry-run", id="uppercase-kebab"),
        pytest.param("Dry-Run", "dry-run", id="mixed-case-kebab"),
        pytest.param("dry_run", "dry-run", id="lowercase-snake"),
        pytest.param("DRY_RUN", "dry-run", id="uppercase-snake"),
        pytest.param("Dry_Run", "dry-run", id="mixed-case-snake"),
        pytest.param("APPLY", "apply", id="uppercase-single-word"),
        pytest.param("Apply", "apply", id="mixed-case-single-word"),
    ],
)
def test_enum_choice_param_suggests_canonical_lowercase_kebab_case(
    invalid_value: str,
    canonical_value: str,
) -> None:
    """Known case and delimiter variants should suggest the canonical CLI token."""
    param: EnumChoiceParam[_Mode] = EnumChoiceParam(_Mode, kebab_case=True)
    option = click.Option(["--mode"])

    with pytest.raises(click.BadParameter) as exc_info:
        param.convert(invalid_value, option, click.Context(click.Command("check")))

    assert exc_info.value.param is option
    assert str(exc_info.value) == (
        f"Invalid value '{invalid_value}'. Did you mean '{canonical_value}'? "
        "Must be one of: dry-run, apply"
    )


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        pytest.param("", ["dry-run", "apply"], id="empty"),
        pytest.param("dry-", ["dry-run"], id="kebab-prefix"),
        pytest.param("DRY-", [], id="uppercase-prefix"),
        pytest.param("Dry-", [], id="mixed-case-prefix"),
        pytest.param("dry_", [], id="snake-prefix"),
        pytest.param("app", ["apply"], id="single-word-prefix"),
        pytest.param("APP", [], id="uppercase-single-word-prefix"),
        pytest.param("zzz", [], id="unrelated-prefix"),
    ],
)
def test_enum_choice_param_completes_only_canonical_values(
    prefix: str,
    expected: list[str],
) -> None:
    """Completion should filter and emit only accepted display spellings."""
    param: EnumChoiceParam[_Mode] = EnumChoiceParam(_Mode, kebab_case=True)
    completions: list[CompletionItem] = param.shell_complete(
        click.Context(click.Command("check")), click.Option(["--mode"]), prefix
    )

    assert [item.value for item in completions] == expected


def test_enum_choice_param_returns_none_for_optional_values() -> None:
    """Optional enum values should pass through None without conversion errors."""
    param: EnumChoiceParam[_Mode] = EnumChoiceParam(_Mode, kebab_case=True)

    assert param.convert(None, None, None) is None


def test_enum_choice_param_reports_invalid_values_with_display_choices() -> None:
    """Invalid enum input should produce Click's parameter error contract."""
    param: EnumChoiceParam[_Mode] = EnumChoiceParam(_Mode, kebab_case=True)

    with pytest.raises(click.BadParameter, match="dry-run, apply") as exc_info:
        param.convert("unknown_value", None, None)

    assert "Did you mean" not in str(exc_info.value)


def test_enum_choice_param_is_case_sensitive_by_default() -> None:
    """Enum choices should reject case-mismatched input by default."""
    param: EnumChoiceParam[_Mode] = EnumChoiceParam(_Mode, kebab_case=True)

    assert param.convert("apply", None, None) is _Mode.APPLY
    assert param.convert("dry-run", None, None) is _Mode.DRY_RUN
    with pytest.raises(click.BadParameter):
        param.convert("APPLY", None, None)
    with pytest.raises(click.BadParameter):
        param.convert("DRY-RUN", None, None)


def test_enum_choice_param_can_explicitly_be_case_insensitive() -> None:
    """Reusable enum choices may explicitly opt into case-insensitive matching."""
    param: EnumChoiceParam[_Mode] = EnumChoiceParam(
        _Mode,
        case_sensitive=False,
        kebab_case=True,
    )

    assert param.convert("APPLY", None, None) is _Mode.APPLY
    assert param.convert("DRY-RUN", None, None) is _Mode.DRY_RUN
    completions: list[CompletionItem] = param.shell_complete(
        click.Context(click.Command("check")),
        click.Option(["--mode"]),
        "DRY-",
    )
    assert [item.value for item in completions] == ["dry-run"]


def test_enum_choice_param_without_kebab_case_preserves_snake_case() -> None:
    """Delimiter strictness should apply only to kebab-case CLI parameters."""
    param: EnumChoiceParam[_Mode] = EnumChoiceParam(_Mode)

    assert param.choices == ["dry_run", "apply"]
    assert param.convert("dry_run", None, None) is _Mode.DRY_RUN
    with pytest.raises(click.BadParameter, match="Did you mean 'dry_run'"):
        param.convert("DRY_RUN", None, None)
    with pytest.raises(click.BadParameter):
        param.convert("dry-run", None, None)


def test_file_type_param_accepts_existing_files_and_rejects_directories(tmp_path: Path) -> None:
    """File path validation should distinguish files from directories."""
    source: Path = tmp_path / "source.py"
    source.write_text("print()\n", encoding="utf-8")

    assert (
        FileTypeParam(
            click.Context(click.Command("check")),
            click.Argument(["file"]),
            source,
        )
        == source
    )
    assert (
        FileTypeParam(
            click.Context(click.Command("check")),
            click.Argument(["file"]),
            None,
        )
        is None
    )

    with pytest.raises(click.BadParameter, match="File not found or not a file"):
        FileTypeParam(
            click.Context(click.Command("check")),
            click.Argument(["file"]),
            tmp_path,
        )


def test_glob_param_expands_relative_and_absolute_patterns(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Glob expansion should support relative and absolute patterns predictably."""
    (tmp_path / "a.py").write_text("print()\n", encoding="utf-8")
    (tmp_path / "b.txt").write_text("text\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    assert (
        GlobParam(
            click.Context(click.Command("check")),
            click.Argument(["path"]),
            None,
        )
        == []
    )
    assert GlobParam(
        click.Context(click.Command("check")),
        click.Argument(["path"]),
        "*.py",
    ) == [Path("a.py")]
    assert GlobParam(
        click.Context(click.Command("check")),
        click.Argument(["path"]),
        str(tmp_path / "*.txt"),
    ) == [tmp_path / "b.txt"]
