[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $Utf8NoBom
$OutputEncoding = $Utf8NoBom
$Root = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$ExitCode = 1
$InjectedKey = $false
$PlainKey = $null
$SecureKey = $null

if ($CliArgs.Count -gt 0 -and $CliArgs[0] -eq "--") {
    if ($CliArgs.Count -eq 1) {
        $CliArgs = @()
    } else {
        $CliArgs = @($CliArgs[1..($CliArgs.Count - 1)])
    }
}
if ($CliArgs.Count -eq 0) {
    $CliArgs = @("--help")
}

try {
    if (-not (Test-Path -LiteralPath $Python)) {
        Write-Host "首次使用，正在自动准备运行环境..."
        & (Join-Path $Root "install.ps1") -SkipGatewayCheck
        if ($LASTEXITCODE -ne 0) {
            throw "自动安装未完成。"
        }
    }

    $KnownCommands = @("doctor", "estimate", "history", "export", "copy", "generate", "edit", "derive", "ecommerce", "workbench", "batch-edit", "detail", "replica")
    $CommandName = $CliArgs | Where-Object { $KnownCommands -contains $_ } | Select-Object -First 1
    $OfflineCommands = @("doctor", "estimate", "history", "export")
    $NeedsKey = $CommandName -and $OfflineCommands -notcontains $CommandName -and $CliArgs -contains "--yes"

    if ($NeedsKey -and -not $env:JD_LLM_API_KEY) {
        Write-Host "该操作会调用 Oxygen。Key 只用于本次命令，不会保存。" -ForegroundColor Yellow
        $SecureKey = Read-Host "请输入你的 Oxygen Key（输入内容不会显示）" -AsSecureString
        $Pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureKey)
        try {
            $PlainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($Pointer)
        } finally {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($Pointer)
        }
        if ([string]::IsNullOrWhiteSpace($PlainKey)) {
            throw "未输入 Oxygen Key，已取消执行。"
        }
        $env:JD_LLM_API_KEY = $PlainKey
        $InjectedKey = $true
    }

    & $Python (Join-Path $Root "scripts\jx_joyer.py") @CliArgs
    $ExitCode = $LASTEXITCODE
} catch {
    Write-Error $_.Exception.Message
    $ExitCode = 1
} finally {
    if ($InjectedKey) {
        Remove-Item Env:JD_LLM_API_KEY -ErrorAction SilentlyContinue
    }
    $PlainKey = $null
    $SecureKey = $null
}

exit $ExitCode
