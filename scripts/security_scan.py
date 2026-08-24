from __future__ import annotations

import re
from pathlib import Path
import sys

TEXT_SUFFIXES = {".md", ".py", ".toml", ".yaml", ".yml", ".json", ".txt"}
SKIP_PARTS = {".git", ".venv", ".pytest_cache", "__pycache__", "jx-joyer-output"}
PATTERNS = {
    "private key": re.compile("BEGIN " + "PRIVATE KEY"),
    "bearer token": re.compile("Bearer" + r"\s+[A-Za-z0-9_.-]{16,}"),
    "oxygen key assignment": re.compile(r"JD_LLM_API_KEY\s*=\s*['\"]?(?!<|\$|your-|Read-Host|read\s)[^\s'\"]{12,}", re.IGNORECASE),
    "cookie header": re.compile("Cookie" + r"\s*:\s*[^<\s][^\r\n]{12,}", re.IGNORECASE),
    "local user path": re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s]+", re.IGNORECASE),
    "corporate email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.local", re.IGNORECASE),
}


def scan_repository(root: str | Path) -> list[str]:
    base = Path(root).resolve()
    findings: list[str] = []
    for path in base.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES or any(part in SKIP_PARTS or part.startswith(".venv") for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(base)}:{line}: {label}")
    return findings


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = scan_repository(root)
    if findings:
        print("\n".join(findings), file=sys.stderr)
        return 1
    print("security scan passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
