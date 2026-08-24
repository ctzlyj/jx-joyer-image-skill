from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_skill_files_exist() -> None:
    for relative in (
        "SKILL.md",
        "agents/openai.yaml",
        "README.md",
        "LICENSE",
        "pyproject.toml",
        "scripts/jx_joyer.py",
    ):
        assert (ROOT / relative).is_file(), relative


def test_secret_files_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".env" in ignore
    assert "jx-joyer-output/" in ignore


def test_script_wrapper_can_import_installed_package() -> None:
    import subprocess
    import sys
    result = subprocess.run([sys.executable, str(ROOT / "scripts/jx_joyer.py"), "--help"], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ecommerce" in result.stdout
