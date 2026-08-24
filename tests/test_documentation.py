import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = ("doctor", "estimate", "copy", "generate", "edit", "ecommerce", "workbench", "batch-edit", "detail", "replica", "derive", "history")


def test_references_exist_and_cover_commands() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for linked in re.findall(r"`(references/[^`]+)`", skill):
        assert (ROOT / linked).is_file(), linked
    commands = (ROOT / "references/commands.md").read_text(encoding="utf-8")
    for command in COMMANDS:
        assert f"`{command}`" in commands


def test_task_schema_has_every_business_workflow() -> None:
    schema = (ROOT / "references/task-schema.md").read_text(encoding="utf-8")
    for workflow in ("ecommerce", "workbench", "batch-edit", "detail", "replica"):
        assert f'"workflow": "{workflow}"' in schema


def test_documentation_does_not_show_a_real_key() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in [ROOT / "README.md", ROOT / "SKILL.md", *sorted((ROOT / "references").glob("*.md"))])
    assert not re.search(r"Bearer\s+[A-Za-z0-9_-]{16,}", text)
    assert "JD_LLM_API_KEY=sk-" not in text


def test_readme_has_three_step_beginner_flow() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for text in (
        "第一步：让 Codex 安装",
        "第二步：直接描述需求",
        "第三步：确认调用量并安全输入 Key",
        "不需要理解 Skill、命令行或 JSON",
    ):
        assert text in readme


def test_skill_automates_bootstrap_and_routing() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for text in (
        "install.ps1",
        "scripts/run.ps1",
        "Do not ask novice users to choose a CLI command",
    ):
        assert text in skill
