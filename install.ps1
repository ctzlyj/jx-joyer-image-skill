[CmdletBinding()]
param(
    [switch]$SkipGatewayCheck
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$Root = $PSScriptRoot
$VenvDirectory = Join-Path $Root ".venv"
$VenvPython = Join-Path $VenvDirectory "Scripts\python.exe"

function Invoke-BasePython {
    param([string[]]$Arguments)

    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 @Arguments
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python @Arguments
    } else {
        throw "未找到 Python 3.11 或更高版本。请先安装 Python，再重新运行 install.ps1。"
    }

    if ($LASTEXITCODE -ne 0) {
        throw "需要 Python 3.11 或更高版本，请安装或升级 Python。"
    }
}

try {
    Write-Host "[1/4] 检查 Python..."
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        Invoke-BasePython -Arguments @("-c", "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)")
        Write-Host "[2/4] 创建独立运行环境..."
        Invoke-BasePython -Arguments @("-m", "venv", $VenvDirectory)
    } else {
        & $VenvPython -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)"
        if ($LASTEXITCODE -ne 0) {
            throw "现有 .venv 的 Python 版本低于 3.11，请删除该虚拟环境后重新安装。"
        }
        Write-Host "[2/4] 独立运行环境已存在，继续检查。"
    }

    Write-Host "[3/4] 安装并检查 JX Joyer Image..."
    & $VenvPython -m pip install --disable-pip-version-check -e $Root
    if ($LASTEXITCODE -ne 0) {
        throw "依赖安装失败，请检查网络或 pip 配置。"
    }

    & $VenvPython (Join-Path $Root "scripts\jx_joyer.py") doctor
    if ($LASTEXITCODE -ne 0) {
        throw "CLI 环境自检失败。"
    }

    if (-not $SkipGatewayCheck) {
        Write-Host "[4/4] 检查京东内网..."
        try {
            $null = [System.Net.Dns]::GetHostAddresses("llm-gw.jd.local")
            Write-Host "已识别 Oxygen 网关地址。" -ForegroundColor Green
        } catch {
            Write-Warning "暂时无法识别 llm-gw.jd.local。使用真实生图前，请连接京东内网或 VPN。"
        }
    } else {
        Write-Host "[4/4] 已跳过内网检查。"
    }

    Write-Host "安装完成。现在直接向 Codex 描述你想生成或修改的图片。" -ForegroundColor Green
    exit 0
} catch {
    Write-Error ("安装失败：" + $_.Exception.Message)
    exit 1
}
