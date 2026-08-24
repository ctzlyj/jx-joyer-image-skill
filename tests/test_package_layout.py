from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_required_skill_files_exist() -> None:
    for relative in (
        "SKILL.md",
        "agents/openai.yaml",
        "README.md",
        "LICENSE",
        "pyproject.toml",
        "install.ps1",
        "scripts/jx_joyer.py",
        "scripts/run.ps1",
    ):
        assert (ROOT / relative).is_file(), relative


@pytest.mark.parametrize("relative", ["install.ps1", "scripts/run.ps1"])
def test_powershell_script_parses(relative: str) -> None:
    path = str(ROOT / relative).replace("'", "''")
    command = (
        "$tokens=$null; $errors=$null; "
        f"[System.Management.Automation.Language.Parser]::ParseFile('{path}', [ref]$tokens, [ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
    )
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stderr


def test_secret_files_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignore
    assert "jx-joyer-output/" in ignore


def test_script_wrapper_can_import_installed_package() -> None:
    result = subprocess.run([sys.executable, str(ROOT / "scripts/jx_joyer.py"), "--help"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert result.returncode == 0, result.stderr
    assert "ecommerce" in result.stdout
