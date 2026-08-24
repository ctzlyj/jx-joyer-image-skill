import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def test_runner_key_is_process_scoped() -> None:
    script = (ROOT / "scripts/run.ps1").read_text(encoding="utf-8")
    assert "Read-Host" in script
    assert "-AsSecureString" in script
    assert "EnvironmentVariableTarget" not in script
    assert "SetEnvironmentVariable" not in script
    assert "Remove-Item Env:JD_LLM_API_KEY" in script


def test_runner_doctor_needs_no_key() -> None:
    env = os.environ.copy()
    env.pop("JD_LLM_API_KEY", None)
    result = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/run.ps1"), "doctor"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 0, result.stderr
    assert '"live_request_performed": false' in result.stdout.lower()



def test_runner_does_not_prompt_for_key_before_confirmation() -> None:
    env = os.environ.copy()
    env.pop("JD_LLM_API_KEY", None)
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ROOT / "scripts/run.ps1"),
            "generate",
            "--prompt",
            "test only",
        ],
        cwd=ROOT,
        env=env,
        input="",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode == 2
    assert "Oxygen Key" not in result.stdout
