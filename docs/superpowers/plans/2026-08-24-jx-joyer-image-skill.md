# JX Joyer Image Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. The source repository forbids Codex subagents, so `subagent-driven-development`, `create_thread`, and parallel agents must not be used.

**Goal:** Build and publicly publish a reusable Codex Skill with a Python CLI that directly calls the JD Oxygen gateway and reproduces the current image-generation workflows of JX Joyer Image Studio without depending on the website.

**Architecture:** A compact `SKILL.md` routes Codex to a single Python CLI. The CLI shares one hardened gateway client across modular workflows, writes non-secret local task manifests, and performs image normalization locally. Workflow modules independently reimplement the current website behavior from audited source semantics rather than importing or calling the Space application.

**Tech Stack:** Python 3.11+, `httpx`, `Pillow`, `pydantic`, `pytest`, standard-library `argparse`, Codex Skill metadata, GitHub CLI.

---

## Source boundaries

Use the Space repository only as a read-only behavioral reference while implementing the independent skill repository.

- Source root: `../..`
- Skill repository root: `.`
- Do not modify, import, package, or publish files from the parent repository.
- Do not access Space project 349, `ct.space.jd.com`, `/app/data`, or any external merchant production resource.
- Reimplement behavior in Python; do not copy large TypeScript source blocks verbatim into the public repository.
- Never run a real Oxygen request unless the user separately authorizes a paid live smoke test and supplies `JD_LLM_API_KEY` through the process environment.

## Planned file map

- `SKILL.md`: skill discovery, routing, safety rules, and command selection.
- `agents/openai.yaml`: display name, description, and default prompt metadata.
- `pyproject.toml`: package metadata, dependencies, console entry point, and pytest settings.
- `README.md`: installation, environment, examples, capability matrix, and security notes.
- `LICENSE`: MIT license.
- `.gitignore`: Python caches, virtual environments, local outputs, secrets, and test artifacts.
- `scripts/jx_joyer.py`: repository-local executable wrapper.
- `src/jx_joyer/constants.py`: fixed gateway/model values and supported dimensions.
- `src/jx_joyer/errors.py`: stable user-facing error classes and mappings.
- `src/jx_joyer/models.py`: validated task specifications and manifests.
- `src/jx_joyer/client.py`: Oxygen text, generation, and edit transport.
- `src/jx_joyer/images.py`: image loading, Data URL conversion, resizing, cropping, JPEG output, and concatenation.
- `src/jx_joyer/storage.py`: task directories, atomic manifest writes, history listing, and cleanup.
- `src/jx_joyer/prompts/*.py`: independently written prompt builders for common, ecommerce, detail, workbench, derivative, and replica flows.
- `src/jx_joyer/workflows/*.py`: one workflow module per CLI capability.
- `src/jx_joyer/cli.py`: argument parsing, task dispatch, JSON output, and exit codes.
- `references/commands.md`: complete CLI reference.
- `references/task-schema.md`: JSON task formats with safe examples.
- `references/capabilities.md`: website-to-skill capability mapping.
- `references/security.md`: credential, logging, output, and live-call rules.
- `tests/`: offline unit and CLI integration tests.

### Task 1: Scaffold the public Skill package

**Files:**
- Create: `SKILL.md`
- Create: `agents/openai.yaml`
- Create: `README.md`
- Create: `LICENSE`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `scripts/jx_joyer.py`
- Test: `tests/test_package_layout.py`

- [ ] **Step 1: Write the package-layout test**

```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `python -m pytest tests/test_package_layout.py -q`

Expected: failure listing the missing scaffold files.

- [ ] **Step 3: Create the minimal package metadata**

Use package name `jx-joyer-image-skill`, Python requirement `>=3.11`, dependencies `httpx>=0.27,<1`, `Pillow>=10,<12`, and `pydantic>=2.8,<3`. Define console script `jx-joyer = "jx_joyer.cli:main"`. Add pytest as an optional `dev` dependency. Add an MIT license naming `CTctikki` as copyright holder.

Create `scripts/jx_joyer.py` as a thin wrapper:

```python
from jx_joyer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add Skill metadata**

`SKILL.md` frontmatter must use:

```yaml
---
name: jx-joyer-image
description: Use when JD colleagues ask Codex to create ecommerce product images, product detail images, free-form generations, reference-image edits, batch edits, derivative edits, or hit-image replicas through the internal Oxygen image models.
---
```

Correct the frontmatter key to `description` during implementation. Keep the body short and route detailed command syntax to `references/`.

`agents/openai.yaml` must identify the skill as “JX Joyer Image” and instruct Codex to inspect inputs, choose the matching workflow, and execute directly once requirements are clear.

- [ ] **Step 5: Run package checks**

Run: `python -m pytest tests/test_package_layout.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add SKILL.md agents/openai.yaml README.md LICENSE .gitignore pyproject.toml scripts/jx_joyer.py tests/test_package_layout.py
git commit -m "chore: scaffold JX Joyer image skill"
```

### Task 2: Define constants, models, and safe local storage

**Files:**
- Create: `src/jx_joyer/__init__.py`
- Create: `src/jx_joyer/constants.py`
- Create: `src/jx_joyer/models.py`
- Create: `src/jx_joyer/storage.py`
- Test: `tests/test_models.py`
- Test: `tests/test_storage.py`

- [ ] **Step 1: Write failing model and storage tests**

Cover these invariants:

```python
import pytest
from pydantic import ValidationError
from jx_joyer.models import EcommerceSpec, TaskManifest


def test_ecommerce_defaults_to_square_2k() -> None:
    spec = EcommerceSpec(product_name="测试商品", prompt="突出商品")
    assert spec.aspect_ratio == "1:1"
    assert spec.quality == "2K"


def test_three_by_four_4k_maps_to_2448_by_3264() -> None:
    spec = EcommerceSpec(product_name="测试商品", prompt="突出商品", aspect_ratio="3:4", quality="4K")
    assert spec.provider_size == "2448x3264"


def test_manifest_rejects_api_key_fields() -> None:
    with pytest.raises(ValidationError):
        TaskManifest(kind="generate", request={"api_key": "forbidden"})
```

Add storage tests that create two manifests under `tmp_path`, assert newest-first ordering, verify atomic replacement leaves valid JSON, and assert traversal IDs such as `../outside` are rejected.

Use `tmp_path`; never use a real user directory or credential.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_models.py tests/test_storage.py -q`

Expected: import failures because the modules do not exist.

- [ ] **Step 3: Implement constants and Pydantic models**

Define fixed constants:

```python
BASE_URL = "http://llm-gw.jd.local/v1"
TEXT_MODEL = "GPT-5.6-Sol-joybuilder"
IMAGE_MODEL = "GPT-image-2-joybuilder"
TEXT_CONCURRENCY = 20
IMAGE_CONCURRENCY = 4
IMAGE_STARTS_PER_SECOND = 1
TIMEOUT_SECONDS = 600
MAX_ATTEMPTS = 4
```

Define enums/models for task status, image source, aspect ratio, quality, ecommerce image type, product copy, prompt input, output asset, retry metadata, and task manifest. Reject unknown credential-like fields including `api_key`, `authorization`, `cookie`, and `x_jd_oxygen_key`.

- [ ] **Step 4: Implement task storage**

`TaskStore` must expose:

Implement `TaskStore.create(kind, request)`, `load(task_id)`, `save(manifest)`, `list(kind=None, limit=20)`, and `delete(task_id)`. `create` returns a validated `TaskManifest`; `load` rejects missing or escaping IDs; `save` performs temporary-file replacement; `list` sorts by creation time descending; `delete` only removes a resolved child task directory.

Write JSON to a temporary sibling and replace atomically. Resolve all paths and reject traversal outside the configured output root.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_models.py tests/test_storage.py -q`

Expected: all tests pass.

```bash
git add scripts/jx_joyer tests/test_models.py tests/test_storage.py
git commit -m "feat: add task models and safe local storage"
```

### Task 3: Implement the shared Oxygen client

**Files:**
- Create: `src/jx_joyer/client.py`
- Create: `src/jx_joyer/errors.py`
- Test: `tests/test_client.py`

**Reference:**
- `${CODEX_HOME}/skills/jd-internal-llm-api/assets/jd_internal_client.py`
- `../../src/server/ai/jd-internal-client.ts`
- `../../src/server/ai/jd-provider-errors.ts`

- [ ] **Step 1: Write failing transport tests**

Use `httpx.MockTransport` and verify:

```python
import base64
import httpx
import pytest
from jx_joyer.client import OxygenClient


def test_generate_image_uses_generations_without_image_field() -> None:
    requests: list[httpx.Request] = []
    expected = b"generated"

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json={"data": [{"b64_json": base64.b64encode(expected).decode()}]})

    client = OxygenClient(api_key="test-key", transport=httpx.MockTransport(handler), sleep=lambda _: None)
    assert client.generate_image(prompt="商品主图", size="1024x1024") == expected
    payload = __import__("json").loads(requests[0].content)
    assert requests[0].url.path.endswith("/images/generations")
    assert payload == {"model": "GPT-image-2-joybuilder", "prompt": "商品主图", "size": "1024x1024"}
```

Add equivalent complete tests for `/responses`, `/images/edits`, multiple Data URLs, both supported base64 response keys, 429 `Retry-After`, retry exhaustion, sanitized non-retryable errors, and missing `JD_LLM_API_KEY`.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_client.py -q`

Expected: import failures.

- [ ] **Step 3: Implement the client**

Expose:

Expose `OxygenClient.from_environment()`, `generate_text(instructions, input_text)`, `generate_image(prompt, size)`, `edit_image(prompt, images, size)`, and `close()`. Each generation method returns decoded bytes or text and raises a sanitized `OxygenApiError` containing status, stable category, retryability, and a bounded detail string.

Use separate text and image semaphores, one shared sliding-window image limiter, and dependency-injected sleep/random functions for deterministic tests. Send `Authorization: Bearer <key>`, never expose that header in exceptions. `from_environment` must fail with a concise setup message when `JD_LLM_API_KEY` is absent.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_client.py -q`

Expected: all tests pass.

```bash
git add src/jx_joyer/client.py src/jx_joyer/errors.py tests/test_client.py
git commit -m "feat: add hardened Oxygen API client"
```

### Task 4: Add image handling and normalization

**Files:**
- Create: `src/jx_joyer/images.py`
- Test: `tests/test_images.py`

**Reference:**
- `../../src/server/ecommerce/image-normalizer.ts`
- `../../src/server/workbench/image-normalizer.ts`
- `../../src/server/render/`

- [ ] **Step 1: Write failing image tests**

Generate synthetic images with Pillow and cover:

```python
from PIL import Image
from jx_joyer.images import normalize_ecommerce_image


def test_ecommerce_portrait_normalizes_to_600_by_800_jpeg(tmp_path) -> None:
    source = tmp_path / "source.png"
    target = tmp_path / "result.jpg"
    Image.new("RGB", (1152, 1536), "red").save(source)
    normalize_ecommerce_image(source, target, aspect_ratio="3:4")
    with Image.open(target) as result:
        assert result.format == "JPEG"
        assert result.size == (600, 800)
```

Add complete tests for square normalization, MIME-aware Data URLs, adaptive aspect preservation, ordered vertical concatenation, alpha compositing, corrupt inputs, and output-path traversal rejection.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_images.py -q`

Expected: import failures.

- [ ] **Step 3: Implement image utilities**

Expose pure functions for MIME detection, Data URL encoding, dimensions, contain/cover transforms, JPEG normalization, preview generation, and vertical concatenation. Preserve alpha only when the requested output format supports it; otherwise composite onto white.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_images.py -q`

Expected: all tests pass.

```bash
git add src/jx_joyer/images.py tests/test_images.py
git commit -m "feat: add deterministic image processing"
```

### Task 5: Reimplement prompt builders

**Files:**
- Create: `src/jx_joyer/prompts/__init__.py`
- Create: `src/jx_joyer/prompts/common.py`
- Create: `src/jx_joyer/prompts/ecommerce.py`
- Create: `src/jx_joyer/prompts/detail.py`
- Create: `src/jx_joyer/prompts/workbench.py`
- Create: `src/jx_joyer/prompts/replica.py`
- Test: `tests/test_prompts.py`

**Reference:**
- `../../src/server/ecommerce/copy.ts`
- `../../src/server/ecommerce/image-tasks.ts`
- `../../src/server/ai/copy-prompt.ts`
- `../../src/server/ai/image-prompt.ts`
- `../../src/server/ai/segment-generation-spec.ts`
- `../../src/server/workbench/generation-plan.ts`
- `../../src/server/images/derivative-prompt.ts`
- `../../src/server/replica/prompt.ts`
- `../../src/server/replica/copy.ts`

- [ ] **Step 1: Write failing behavioral tests**

Assert semantic invariants rather than copying complete prompt strings:

```python
from jx_joyer.prompts.ecommerce import build_ecommerce_prompt


def test_ecommerce_prompt_contains_selected_task_and_manual_copy() -> None:
    prompt = build_ecommerce_prompt(
        task_type="sellingPoints",
        product_name="测试商品",
        user_prompt="清爽夏日风",
        selling_points=["轻量", "耐用", "易清洁"],
        long_title="测试长标题",
        short_title="测试短标题",
        aspect_ratio="3:4",
    )
    assert "卖点图" in prompt
    assert "轻量" in prompt
    assert "测试长标题" in prompt
    assert "3:4" in prompt
```

Add complete semantic tests for missing-field-only copy requests, detail facts and module constraints, workbench ratio/reference roles, derivative ratio inheritance, and separate template/product roles in replica prompts.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_prompts.py -q`

Expected: import failures.

- [ ] **Step 3: Implement independent prompt builders**

Each builder must accept validated models and return deterministic prompt text. Preserve current functional rules, including product identity protection, Chinese copy constraints, selected-field completion, reference-image role ordering, task-specific composition, and avoidance of unsupported claims. Do not reproduce source comments or TypeScript structure verbatim.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_prompts.py -q`

Expected: all tests pass.

```bash
git add src/jx_joyer/prompts tests/test_prompts.py
git commit -m "feat: add image workflow prompt builders"
```

### Task 6: Add core copy, generate, edit, derive, and history commands

**Files:**
- Create: `src/jx_joyer/workflows/__init__.py`
- Create: `src/jx_joyer/workflows/core.py`
- Create: `src/jx_joyer/cli.py`
- Test: `tests/test_core_workflows.py`
- Test: `tests/test_cli_core.py`

- [ ] **Step 1: Write failing workflow and CLI tests**

Cover text generation, no-reference routing, multi-reference editing, derivative edits, task manifests, JSON stdout, non-zero exit codes, and absence of credentials in output.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_core_workflows.py tests/test_cli_core.py -q`

Expected: import failures or unknown commands.

- [ ] **Step 3: Implement core workflows**

`WorkflowContext` owns one `OxygenClient` and one `TaskStore`. Each workflow creates a manifest before model execution, updates status after each asset, writes image bytes atomically, and records sanitized errors. `generate` must call `/images/generations`; `edit` and `derive` must call `/images/edits`.

- [ ] **Step 4: Implement CLI dispatch**

Use `argparse` subcommands `doctor`, `copy`, `generate`, `edit`, `derive`, and `history`. Support `--task-file` for structured JSON and concise direct flags for simple tasks. Emit one JSON object to stdout; send human diagnostics to stderr without secrets.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_core_workflows.py tests/test_cli_core.py -q`

Expected: all tests pass.

```bash
git add src/jx_joyer/workflows src/jx_joyer/cli.py tests/test_core_workflows.py tests/test_cli_core.py
git commit -m "feat: add core generation CLI commands"
```

### Task 7: Implement ecommerce workflows

**Files:**
- Create: `src/jx_joyer/workflows/ecommerce.py`
- Test: `tests/test_ecommerce_workflow.py`

**Reference:**
- `../../src/shared/ecommerce.ts`
- `../../src/server/ecommerce/ecommerce-service.ts`
- `../../src/server/ecommerce/image-tasks.ts`
- `../../src/server/ecommerce/image-normalizer.ts`

- [ ] **Step 1: Write failing ecommerce tests**

Cover all six image types, selected-type ordering, manual copy preservation, missing selected copy generation, 1:1 and 3:4 Provider dimensions, final JPEG dimensions, partial failure, retry, and derivative ratio inheritance.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_ecommerce_workflow.py -q`

Expected: import failure.

- [ ] **Step 3: Implement ecommerce orchestration**

Expose `run_ecommerce(spec, context)`, `retry_ecommerce(task_id, asset_ids, context)`, and `derive_ecommerce(task_id, asset_id, instruction, context)`. Use a bounded worker pool of four sharing the process client. Preserve task order in manifests even when requests finish out of order.

- [ ] **Step 4: Add CLI command and examples**

Add `ecommerce --task-file <json>`, `ecommerce --retry <task-id> --asset <id>`, and `ecommerce --derive <task-id> --asset <id> --instruction <text>`.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest tests/test_ecommerce_workflow.py tests/test_cli_core.py -q`

Expected: all tests pass.

```bash
git add src/jx_joyer/workflows/ecommerce.py src/jx_joyer/cli.py tests/test_ecommerce_workflow.py
git commit -m "feat: add ecommerce image-set workflow"
```

### Task 8: Implement workbench and batch editing

**Files:**
- Create: `src/jx_joyer/workflows/workbench.py`
- Create: `src/jx_joyer/workflows/batch_edit.py`
- Test: `tests/test_workbench_workflow.py`
- Test: `tests/test_batch_edit_workflow.py`

**Reference:**
- `../../src/server/workbench/generation-plan.ts`
- `../../src/server/workbench/workbench-service.ts`
- `../../src/server/workbench/routes.ts`

- [ ] **Step 1: Write failing tests**

Cover pure generation, multi-reference edit, repeated output count, fixed/custom/adaptive sizing, common references, per-source batch prompts, partial failures, retry with original parameters, and the absence of fidelity-outpaint behavior.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_workbench_workflow.py tests/test_batch_edit_workflow.py -q`

Expected: import failures.

- [ ] **Step 3: Implement workbench orchestration**

Route zero references to `generate_image` and one or more references to `edit_image`. Build explicit generation plans before issuing requests so the CLI can report the exact paid request count.

- [ ] **Step 4: Implement batch editing**

Treat each source image as an independent edit item, prepend any common references in stable order, preserve requested ratio semantics, and retry only failed items. Do not lock original pixels or synthesize outpaint masks.

- [ ] **Step 5: Add CLI commands, run tests, and commit**

Run: `python -m pytest tests/test_workbench_workflow.py tests/test_batch_edit_workflow.py -q`

Expected: all tests pass.

```bash
git add src/jx_joyer/workflows/workbench.py src/jx_joyer/workflows/batch_edit.py src/jx_joyer/cli.py tests/test_workbench_workflow.py tests/test_batch_edit_workflow.py
git commit -m "feat: add workbench and batch edit workflows"
```

### Task 9: Implement detail-page projects

**Files:**
- Create: `src/jx_joyer/workflows/detail.py`
- Test: `tests/test_detail_workflow.py`

**Reference:**
- `../../src/shared/domain.ts`
- `../../src/server/ai/copy-prompt.ts`
- `../../src/server/ai/image-prompt.ts`
- `../../src/server/ai/segment-generation-spec.ts`
- `../../src/server/projects/`
- `../../src/server/render/`

- [ ] **Step 1: Write failing detail tests**

Cover project creation, facts, copy generation, segment order, generate-one, generate-all, partial failures, revisions, restore, derive, and final long-image export.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_detail_workflow.py -q`

Expected: import failure.

- [ ] **Step 3: Implement local detail projects**

Define a stable project JSON schema with source images, facts, copy, segment settings, current revision, and revision history. Keep image bytes in the project task directory and all paths relative.

- [ ] **Step 4: Implement generation and export**

Generate segments in the website-defined order, using the correct module-specific dimensions and prompts. A failed segment must not discard successful segments. Export by vertically concatenating the selected current revisions.

- [ ] **Step 5: Add CLI commands, run tests, and commit**

Support `detail create`, `detail copy`, `detail generate`, `detail derive`, `detail restore`, and `detail export`.

Run: `python -m pytest tests/test_detail_workflow.py -q`

Expected: all tests pass.

```bash
git add src/jx_joyer/workflows/detail.py src/jx_joyer/cli.py tests/test_detail_workflow.py
git commit -m "feat: add product detail workflow"
```

### Task 10: Implement hit-image replica workflows

**Files:**
- Create: `src/jx_joyer/workflows/replica.py`
- Test: `tests/test_replica_workflow.py`

**Reference:**
- `../../src/server/replica/routes.ts`
- `../../src/server/replica/prompt.ts`
- `../../src/server/replica/copy.ts`
- `../../src/server/replica/generation-queue.ts`

- [ ] **Step 1: Write failing replica tests**

Cover template analysis parsing, editable slices, answer persistence, copy generation, all-slice generation, single-slice retry, product/template reference ordering, revisions, and cancellation state.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_replica_workflow.py -q`

Expected: import failure.

- [ ] **Step 3: Implement replica orchestration**

Use the text model for structured analysis and copy. Validate its JSON response before saving. Use the image edit endpoint for each accepted slice with template images and product references in deterministic order. Record each revision independently.

- [ ] **Step 4: Add CLI commands, run tests, and commit**

Support `replica analyze`, `replica configure`, `replica copy`, `replica generate`, and `replica cancel`.

Run: `python -m pytest tests/test_replica_workflow.py -q`

Expected: all tests pass.

```bash
git add src/jx_joyer/workflows/replica.py src/jx_joyer/cli.py tests/test_replica_workflow.py
git commit -m "feat: add hit-image replica workflow"
```

### Task 11: Write operator and Codex documentation

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Create: `references/commands.md`
- Create: `references/task-schema.md`
- Create: `references/capabilities.md`
- Create: `references/security.md`
- Test: `tests/test_documentation.py`

- [ ] **Step 1: Write failing documentation tests**

Verify every CLI command appears in the command reference, every task schema has a safe example, all examples omit real-looking keys, and `SKILL.md` links only to existing files.

- [ ] **Step 2: Verify tests fail**

Run: `python -m pytest tests/test_documentation.py -q`

Expected: failure because references do not exist.

- [ ] **Step 3: Write progressive-disclosure documentation**

Document installation with `python -m pip install -e .`, runtime Key setup for PowerShell/Bash without showing a real value, capability examples, optional request-count lookup, output locations, troubleshooting, and explicit non-goals. Explain that the internal hostname works only on JD network/VPN.

- [ ] **Step 4: Run tests and commit**

Run: `python -m pytest tests/test_documentation.py -q`

Expected: all tests pass.

```bash
git add SKILL.md README.md references tests/test_documentation.py
git commit -m "docs: add Skill and CLI usage guides"
```

### Task 12: Validate security and complete behavior

**Files:**
- Create: `scripts/security_scan.py`
- Create: `tests/test_security.py`
- Modify: files identified by validation failures only

- [ ] **Step 1: Add repository security checks**

Scan tracked files for private keys, bearer tokens, realistic Oxygen keys, cookies, `.env` files, full image Data URLs, absolute local user paths, Space deployment addresses, and external merchant production paths. Permit only the documented internal gateway hostname and fixed model identifiers.

- [ ] **Step 2: Run focused and full test suites**

```bash
python -m pytest -q
python scripts/security_scan.py
python ${CODEX_HOME}/skills/.system/skill-creator/scripts/quick_validate.py .
python scripts/jx_joyer.py doctor
```

Expected: tests, security scan, and Skill validation pass. `doctor` reports environment readiness without calling a model; it may report that the runtime Key is absent.

- [ ] **Step 3: Build and install in a clean virtual environment**

```powershell
python -m venv .venv-validation
.\.venv-validation\Scripts\python -m pip install -e ".[dev]"
.\.venv-validation\Scripts\python -m pytest -q
.\.venv-validation\Scripts\jx-joyer --help
```

Expected: installation succeeds, tests pass, and help lists all documented commands.

- [ ] **Step 4: Verify parent repository isolation**

Run: `git -C ../.. status --short`

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add scripts/security_scan.py tests/test_security.py
git commit -m "test: validate skill security and behavior"
```

### Task 13: Prepare and publish the public GitHub repository

**Files:**
- Modify: Git metadata only

- [ ] **Step 1: Confirm GitHub authentication and repository availability**

```bash
gh auth status
gh repo view CTctikki/jx-joyer-image-skill
```

Expected: authenticated as an account allowed to create under `CTctikki`; repository lookup either returns not found or identifies the intended empty repository. Stop if an unrelated repository already exists.

- [ ] **Step 2: Replace internal commit identity before publication**

Set repository-local identity and rewrite unpublished commits so no corporate `.local` email remains:

```bash
git config user.name CTctikki
git config user.email CTctikki@users.noreply.github.com
git rebase --root --exec "git commit --amend --no-edit --reset-author"
```

Run: `git log --format="%H %an <%ae>"`

Expected: every commit uses the public-safe noreply identity.

- [ ] **Step 3: Run final publication gate**

```bash
python -m pytest -q
python scripts/security_scan.py
python ${CODEX_HOME}/skills/.system/skill-creator/scripts/quick_validate.py .
git status --short
git diff --check
git grep -n -E "@[A-Za-z0-9.-]+\\.local"
git -C ../.. status --short
```

Expected: all validations pass; both repositories are clean; identity scan has no matches.

- [ ] **Step 4: Create and push the public repository**

```bash
gh repo create CTctikki/jx-joyer-image-skill --public --source . --remote origin --push --description "Codex skill and Python CLI for JD Oxygen ecommerce image workflows"
```

Expected: repository is public, default branch is `main`, and local `HEAD` equals `origin/main`.

- [ ] **Step 5: Verify published contents**

```bash
gh repo view CTctikki/jx-joyer-image-skill --json nameWithOwner,visibility,url,defaultBranchRef
git rev-parse HEAD
git rev-parse origin/main
git status --short
```

Expected: visibility is `PUBLIC`, branch is `main`, commit hashes match, and the worktree is clean. Report the repository URL without running a live Oxygen request.
