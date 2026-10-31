# topmark:header:start
#
#   project      : TopMark
#   file         : check_commit_message_hook.py
#   file_relpath : tools/ci/check_commit_message_hook.py
#   license      : MIT
#   copyright    : (c) 2025 Olivier Biot
#
# topmark:header:end

"""Exercise the configured commit-message hook in an isolated Git repository."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

_ROOT: Path = Path(__file__).resolve().parents[2]
_SIGNOFF = "\n\nSigned-off-by: Example Person <person@example.com>\n"


def _executable(name: str) -> str:
    path: str | None = shutil.which(name)
    if path is None:
        raise RuntimeError(f"Required executable not found: {name}")
    return path


def _run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    # The executable is resolved from PATH and all arguments are fixed or temporary paths.
    return subprocess.run(  # noqa: S603
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def main() -> None:
    """Run representative commit-message checks without changing the checkout."""
    git: str = _executable("git")
    precommit: str = _executable("pre-commit")
    cases: tuple[tuple[str, str, str | None], ...] = (
        ("valid", "fix: handle empty values" + _SIGNOFF, None),
        ("missing sign-off", "fix: handle empty values\n", "CC012"),
        ("malformed sign-off", "fix: handle empty values\n\nSigned-off-by: Example\n", "CC012"),
        ("invalid type", "invalid: handle empty values" + _SIGNOFF, "CC001"),
        ("breaking change", "feat(cli)!: add validation" + _SIGNOFF, None),
        ("non-imperative subject", "fix: fixed empty values" + _SIGNOFF, "CC003"),
        ("72-character subject", "fix: " + "a" * 67 + _SIGNOFF, None),
        ("73-character subject", "fix: " + "a" * 68 + _SIGNOFF, "CC004"),
        ("long body", "fix: handle empty values\n\n" + "b" * 200 + _SIGNOFF, None),
    )
    with tempfile.TemporaryDirectory(prefix="topmark-commit-policy-") as directory:
        root = Path(directory)
        result: subprocess.CompletedProcess[str] = _run(
            [
                git,
                "init",
                "--quiet",
                str(root),
            ],
            root,
        )
        if result.returncode:
            raise RuntimeError(f"Could not initialize temporary repository: {result.stderr}")
        (root / ".github").mkdir()
        shutil.copyfile(_ROOT / ".pre-commit-config.yaml", root / ".pre-commit-config.yaml")
        shutil.copyfile(_ROOT / ".github/cchk.toml", root / ".github/cchk.toml")
        message: Path = root / "message"
        for label, text, expected_rule in cases:
            message.write_text(text, encoding="utf-8")
            result = _run(
                [
                    precommit,
                    "run",
                    "check-message",
                    "--hook-stage",
                    "commit-msg",
                    "--commit-msg-filename",
                    str(message),
                ],
                root,
            )
            output: str = result.stdout + result.stderr
            passed: bool = (
                result.returncode == 0
                if expected_rule is None
                else (result.returncode == 1 and expected_rule in output)
            )
            if not passed:
                raise RuntimeError(f"Commit hook case {label!r} failed:\n{output}")
            print(f"Commit hook case {label}: passed")


if __name__ == "__main__":
    main()
