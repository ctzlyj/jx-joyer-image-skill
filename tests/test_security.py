from pathlib import Path

from scripts.security_scan import scan_repository


def test_security_scan_rejects_bearer_token(tmp_path: Path) -> None:
    (tmp_path / "bad.txt").write_text("Authorization: " + "Bearer " + "abcdefghijklmnopqrstuvwxyz", encoding="utf-8")
    findings = scan_repository(tmp_path)
    assert any("bearer token" in finding.lower() for finding in findings)


def test_security_scan_accepts_safe_example(tmp_path: Path) -> None:
    (tmp_path / "safe.md").write_text("Set the JD_LLM_API_KEY environment variable at runtime.", encoding="utf-8")
    assert scan_repository(tmp_path) == []



def test_security_scan_ignores_virtual_environment_variants(tmp_path: Path) -> None:
    dependency = tmp_path / ".venv-validation" / "Lib" / "site-packages" / "dependency.py"
    dependency.parent.mkdir(parents=True)
    dependency.write_text("Cookie" + ": third-party-test-value", encoding="utf-8")
    assert scan_repository(tmp_path) == []


def test_security_scan_rejects_local_user_path_and_corporate_email(tmp_path: Path) -> None:
    value = "C:" + "\\Users\\employee\\secret.txt" + "\n" + "person" + "@company.local"
    (tmp_path / "leak.txt").write_text(value, encoding="utf-8")
    findings = scan_repository(tmp_path)
    assert any("local user path" in finding.lower() for finding in findings)
    assert any("corporate email" in finding.lower() for finding in findings)


def test_security_scan_checks_powershell_files(tmp_path: Path) -> None:
    value = "$env:JD_LLM_API_KEY = " + "'runtime-secret-value-123456'"
    (tmp_path / "leak.ps1").write_text(value, encoding="utf-8")
    findings = scan_repository(tmp_path)
    assert any("oxygen key assignment" in finding.lower() for finding in findings)
