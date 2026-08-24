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
