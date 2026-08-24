# JX Joyer Image Skill Zero-Friction Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This repository forbids subagents, so execute sequentially in the current task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add one-command Windows setup, secure per-run Oxygen Key input, automatic checks, and natural-language-first Skill guidance.

**Architecture:** Keep the Python workflows unchanged. `install.ps1` owns a repository-local virtual environment and diagnostics; `scripts/run.ps1` owns execution and temporary credentials. `SKILL.md` makes Codex choose commands and build task JSON for the user.

**Tech Stack:** PowerShell 5.1+, Python 3.11+, existing Python CLI, pytest, Markdown.

---

## File Map

- Create `install.ps1`: idempotent setup and Chinese diagnostics.
- Create `scripts/run.ps1`: local CLI launcher and masked Key prompt.
- Modify `SKILL.md`: automatic routing and first-run behavior.
- Modify `README.md`: three-step novice quick start and examples.
- Modify `references/commands.md`: wrapper-first advanced reference.
- Modify `tests/test_package_layout.py` and `tests/test_documentation.py`.
- Create `tests/test_powershell_scripts.py`.

### Task 1: Lock the beginner contract with failing tests

**Files:**
- Modify: `tests/test_package_layout.py`
- Modify: `tests/test_documentation.py`
- Create: `tests/test_powershell_scripts.py`

- [x] **Step 1: Require the new entrypoints and valid PowerShell syntax**

Add `install.ps1` and `scripts/run.ps1` to the required-file list, then parse each file:

```python
@pytest.mark.parametrize("relative", ["install.ps1", "scripts/run.ps1"])
def test_powershell_script_parses(relative: str) -> None:
    path = ROOT / relative
    command = "$e=$null;[Management.Automation.Language.Parser]::ParseFile(" + repr(str(path)) + ",[ref]$null,[ref]$e)|Out-Null;if($e.Count){exit 1}"
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command])
    assert result.returncode == 0
```

- [x] **Step 2: Specify novice documentation and routing**

```python
def test_readme_has_three_step_beginner_flow() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for text in ("第一步：让 Codex 安装", "第二步：直接描述需求", "第三步：确认调用量并安全输入 Key", "不需要理解 Skill、命令行或 JSON"):
        assert text in readme


def test_skill_automates_bootstrap_and_routing() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    for text in ("install.ps1", "scripts/run.ps1", "Do not ask novice users to choose a CLI command"):
        assert text in skill
```

- [x] **Step 3: Specify credential safety and offline doctor behavior**

```python
def test_runner_key_is_process_scoped() -> None:
    script = (ROOT / "scripts/run.ps1").read_text(encoding="utf-8")
    assert "Read-Host" in script and "-AsSecureString" in script
    assert "EnvironmentVariableTarget" not in script
    assert "Remove-Item Env:JD_LLM_API_KEY" in script


def test_runner_doctor_needs_no_key() -> None:
    env = os.environ.copy(); env.pop("JD_LLM_API_KEY", None)
    result = subprocess.run(["powershell", "-NoProfile", "-File", str(ROOT / "scripts/run.ps1"), "doctor"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert '"live_request_performed": false' in result.stdout.lower()
```

- [x] **Step 4: Verify RED**

Run: `.\.venv-validation\Scripts\python.exe -m pytest tests\test_package_layout.py tests\test_documentation.py tests\test_powershell_scripts.py -v`

Expected: failures because scripts and novice copy are missing.

### Task 2: Add installation and secure runner scripts

**Files:**
- Create: `install.ps1`
- Create: `scripts/run.ps1`

- [x] **Step 1: Implement idempotent `install.ps1`**

Use this flow: resolve `$PSScriptRoot`; find `py -3.11` or `python`; verify `sys.version_info >= (3, 11)`; create `.venv` only when missing; run `.venv\Scripts\python.exe -m pip install -e $PSScriptRoot`; run `scripts\jx_joyer.py doctor`; optionally test `llm-gw.jd.local:80`; print a Chinese success message. A gateway failure is only a VPN warning. Any Python or pip failure exits nonzero with a concise Chinese fix.

Core implementation:

```powershell
[CmdletBinding()]
param([switch]$SkipGatewayCheck)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3.11 -m venv (Join-Path $Root ".venv") }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv (Join-Path $Root ".venv") }
    else { throw "未找到 Python 3.11 或更高版本。" }
}
& $Python -m pip install --disable-pip-version-check -e $Root
if ($LASTEXITCODE -ne 0) { throw "依赖安装失败，请检查网络或 pip 配置。" }
& $Python (Join-Path $Root "scripts\jx_joyer.py") doctor
Write-Host "安装完成。现在直接向 Codex 描述你的图片需求。" -ForegroundColor Green
```

- [x] **Step 2: Implement `scripts/run.ps1`**

Detect the first known CLI command. Run `install.ps1` if `.venv` is absent. Do not prompt for `doctor`, `estimate`, or `history`. For model commands with no environment Key, use `Read-Host -AsSecureString`, convert only for the child process, and clear in `finally`:

```powershell
[CmdletBinding()]
param([Parameter(ValueFromRemainingArguments=$true)][string[]]$CliArgs)
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) { & (Join-Path $Root "install.ps1") -SkipGatewayCheck }
$Known = @("doctor","estimate","history","copy","generate","edit","derive","ecommerce","workbench","batch-edit","detail","replica")
$CommandName = $CliArgs | Where-Object { $Known -contains $_ } | Select-Object -First 1
$NeedsKey = $CommandName -and @("doctor","estimate","history") -notcontains $CommandName
$InjectedKey = $false
try {
    if ($NeedsKey -and -not $env:JD_LLM_API_KEY) {
        $SecureKey = Read-Host "请输入 Oxygen Key（不会显示）" -AsSecureString
        $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
        try { $PlainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer) } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer) }
        $env:JD_LLM_API_KEY = $PlainKey
        $InjectedKey = $true
    }
    & $Python (Join-Path $Root "scripts\jx_joyer.py") @CliArgs
    $ExitCode = $LASTEXITCODE
} finally {
    if ($InjectedKey) { Remove-Item Env:JD_LLM_API_KEY -ErrorAction SilentlyContinue }
    $SecureKey = $null
}
exit $ExitCode
```

- [x] **Step 3: Verify GREEN for script tests**

Run: `.\.venv-validation\Scripts\python.exe -m pytest tests\test_package_layout.py tests\test_powershell_scripts.py -v`

Expected: all selected tests pass without an Oxygen request.

### Task 3: Make natural language the default interface

**Files:**
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `references/commands.md`

- [x] **Step 1: Add automatic behavior to `SKILL.md`**

Preserve all endpoint, model, estimation, and safety constraints. Add:

```markdown
## Default novice experience

- Treat natural-language requests as the interface. Do not ask novice users to choose a CLI command, workflow name, JSON schema, model, endpoint, or image API.
- If `.venv/Scripts/python.exe` is missing, explain the local installation and run `powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1`.
- Choose the workflow from the request and supplied images. Ask only for necessary information that cannot be safely inferred.
- Build task JSON in the approved output directory without exposing it unless requested.
- Invoke commands through `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 -- <arguments>`.
- Run `estimate`, summarize request counts in Chinese, and wait for confirmation before quota consumption.
- Let `scripts/run.ps1` show the masked Key prompt. Never ask users to paste a Key into chat.
```

- [x] **Step 2: Rewrite the README first screen**

Use these three primary actions before technical prerequisites:

```markdown
## 第一步：让 Codex 安装

把这句话发给 Codex：

> 请从 https://github.com/CTctikki/jx-joyer-image-skill 安装这个 Skill，并运行 install.ps1 完成环境检查。不要执行真实生图。

## 第二步：直接描述需求

不需要理解 Skill、命令行或 JSON。直接发送商品图和需求。

## 第三步：确认调用量并安全输入 Key

Codex 会先说明预计请求数。确认后，在终端遮罩输入自己的 Oxygen Key；不要把 Key 发到聊天中。
```

Add copyable examples for text-to-image, reference edits, ecommerce sets, details, batch edits, derivatives, and replicas. Move pip and direct CLI instructions under `高级用法`.

- [x] **Step 3: Make the wrapper the recommended command entrypoint**

In `references/commands.md`, lead with:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/run.ps1 -- doctor
```

State that `jx-joyer` is for users who manually activated the virtual environment.

- [x] **Step 4: Verify documentation and Skill validity**

Run: `.\.venv-validation\Scripts\python.exe -m pytest tests\test_documentation.py tests\test_package_layout.py -v`

Run: `.\.venv-validation\Scripts\python.exe "$env:CODEX_HOME\skills\.system\skill-creator\scripts\quick_validate.py" .`

Expected: selected tests pass and validator prints `Skill is valid!`.

### Task 4: Full verification and publication handoff

**Files:**
- Verify every changed source, script, test, and documentation file.

- [x] **Step 1: Run all tests**

Run: `.\.venv-validation\Scripts\python.exe -m pytest`

Expected: zero failures.

- [x] **Step 2: Run compile and security checks**

Run: `.\.venv-validation\Scripts\python.exe -m compileall -q src scripts`

Run: `.\.venv-validation\Scripts\python.exe scripts\security_scan.py`

Expected: both exit 0; scanner prints `security scan passed`.

- [x] **Step 3: Run offline smoke checks**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -SkipGatewayCheck`

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\run.ps1 doctor`

Expected: repeat installation succeeds, doctor reports `live_request_performed: false`, and no Key prompt appears.

- [x] **Step 4: Verify repository hygiene**

Run: `git diff --check` and `git status --short`.

Expected: only intentional source, test, plan, and documentation files; no `.env`, Key, virtual environment, output image, or task payload.

- [x] **Step 5: Prepare publication handoff**

Report exact test counts, changed files, local paths, and the public repository URL. Do not commit or push until the user explicitly requests publication.
