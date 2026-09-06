param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260907-JARVIS-V6-3-full-advanced-single-patch"
$RemoteRef = "origin/$TargetBranch"

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) {
        throw "git $($GitArgs -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Get-JarvisPython {
    $candidates = @(
        (Join-Path $Root ".venv\Scripts\python.exe"),
        (Join-Path $Root ".venv-new\Scripts\python.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            & $candidate -c "import omni, workstation" *> $null
            if ($LASTEXITCODE -eq 0) {
                return $candidate
            }
        }
    }
    throw "No healthy JARVIS Python environment was found."
}

function Stop-TrustedJarvisProcesses {
    $markers = @(
        "jarvis_runtime_supervisor",
        "start_jarvis_v3.py",
        "start_jarvis_quant_terminal.py",
        "start_jarvis_nautilus_core.py"
    )
    $rows = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue
    foreach ($row in $rows) {
        if ([int]$row.ProcessId -eq $PID) { continue }
        $command = [string]$row.CommandLine
        if (-not $command) { continue }
        if ($command.IndexOf($Root, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) { continue }
        $trusted = $false
        foreach ($marker in $markers) {
            if ($command.IndexOf($marker, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
                $trusted = $true
                break
            }
        }
        if (-not $trusted) { continue }
        Write-Host "STOP > trusted JARVIS process PID $($row.ProcessId)" -ForegroundColor DarkYellow
        Stop-Process -Id ([int]$row.ProcessId) -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

function Test-Http200 {
    param([Parameter(Mandatory = $true)][string]$Url)
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 5
        return [int]$response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Wait-JarvisRuntime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/intelligence.html",
        "http://127.0.0.1:8787/intelligence.js",
        "http://127.0.0.1:8787/lightweight-charts.standalone.production.js",
        "http://127.0.0.1:8787/adaptive_brain_runtime.js",
        "http://127.0.0.1:8787/api/intelligence/status",
        "http://127.0.0.1:8787/api/intelligence/module?module=learning&symbol=BTC&profile=15m_only"
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(55)
    $pending = @($required)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            foreach ($url in $required) {
                Write-Host "200  $url" -ForegroundColor Green
            }
            return
        }
        Start-Sleep -Seconds 1
    }
    foreach ($url in $required) {
        if (Test-Http200 $url) {
            Write-Host "200  $url" -ForegroundColor Green
        }
        else {
            Write-Host "FAIL $url" -ForegroundColor Red
        }
    }
    throw "JARVIS V6.3 runtime verification failed for: $($pending -join ', ')"
}

if (-not (Test-Path (Join-Path $Root ".git"))) {
    throw "$Root is not the JARVIS Git working tree."
}

Set-Location $Root

$PreviousBranch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read current Git branch." }
$PreviousHead = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read current Git HEAD." }
$Dirty = (& git status --porcelain) -join "`n"
if ($LASTEXITCODE -ne 0) { throw "Unable to read Git status." }
if ($Dirty.Trim()) {
    throw "Working tree is not clean. Commit or stash unrelated work before the V6.3 full patch.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V6.3 FULL ADVANCED SINGLE PATCH" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)

$BackupBranch = "jarvis-backup/v63-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
Invoke-Git @("branch", $BackupBranch, $PreviousHead)
Write-Host "Backup branch   : $BackupBranch" -ForegroundColor Yellow

try {
    Stop-TrustedJarvisProcesses

    & git show-ref --verify --quiet "refs/heads/$TargetBranch"
    $LocalTargetExists = $LASTEXITCODE -eq 0
    if ($LocalTargetExists) {
        Invoke-Git @("switch", $TargetBranch)
        Invoke-Git @("merge", "--ff-only", $RemoteRef)
    }
    else {
        Invoke-Git @("switch", "-c", $TargetBranch, "--track", $RemoteRef)
    }

    $Python = Get-JarvisPython
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $((& git rev-parse --short HEAD).Trim())"

    $criticalFiles = @(
        "omni\workspace_command_center.py",
        "workstation\jarvis_os_v3_assets\company.html",
        "workstation\paper_trading_desk.py",
        "workstation\paper_portfolio_controller.py",
        "workstation\options_chain_analytics.py",
        "workstation\quant_intelligence_modules.py",
        "omni\trading_intelligence\adaptive_quant_brain.py",
        "omni\trading_intelligence\strategy_research_lab.py",
        "omni\trading_intelligence\trade_learning_engine.py",
        "omni\trading_intelligence\self_improvement_coordinator.py",
        "workstation\quant_terminal_v2_static\intelligence.html",
        "workstation\quant_terminal_v2_static\intelligence.js",
        "workstation\quant_terminal_v2_static\option_chart_runtime.js",
        "workstation\quant_terminal_v2_static\paper_desk_runtime.js",
        "workstation\quant_terminal_v2_static\advanced_terminal_runtime.js",
        "workstation\quant_terminal_v2_static\adaptive_brain_runtime.js",
        "scripts\jarvis_runtime_supervisor_v62.py"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V6.3 file is missing: $file"
        }
    }
    Write-Host "Critical advanced surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "workstation\quant_intelligence_modules.py" `
        "omni\trading_intelligence\adaptive_quant_brain.py" `
        "omni\trading_intelligence\strategy_research_lab.py" `
        "omni\trading_intelligence\trade_learning_engine.py" `
        "omni\trading_intelligence\self_improvement_coordinator.py" `
        "scripts\jarvis_runtime_supervisor_v62.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        & $Node.Source --check "workstation\quant_terminal_v2_static\intelligence.js"
        if ($LASTEXITCODE -ne 0) { throw "intelligence.js syntax validation failed." }
        & $Node.Source --check "workstation\quant_terminal_v2_static\adaptive_brain_runtime.js"
        if ($LASTEXITCODE -ne 0) { throw "adaptive_brain_runtime.js syntax validation failed." }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow
    }

    Write-Host "TARGETED REGRESSION > full advanced + recovery + runtime" -ForegroundColor Cyan
    & $Python -m unittest `
        tests.test_quant_v63_full_advanced `
        tests.test_quant_v6_adaptive_integration `
        tests.test_quant_v6_chart_runtime `
        tests.test_self_improvement_v6 `
        tests.test_workspace_command_center `
        tests.test_workspace_command_center_health `
        tests.test_company_terminal `
        tests.test_quant_terminal_v2 `
        tests.test_options_chain_analytics `
        tests.test_paper_trading_desk `
        tests.test_jarvis_runtime_supervisor `
        tests.test_runtime_supervisor_v62 `
        tests.test_quant_trading_intelligence_phase1_integration `
        -q
    if ($LASTEXITCODE -ne 0) { throw "Targeted V6.3 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > this can take a few minutes" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }

    Invoke-Git @("diff", "--check")
    $PostDirty = (& git status --porcelain) -join "`n"
    if ($PostDirty.Trim()) {
        throw "V6.3 validation unexpectedly modified the working tree.`n$PostDirty"
    }

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V6.3" -ForegroundColor Cyan
        Start-Process -FilePath (Join-Path $Root "JARVIS.bat")
        Wait-JarvisRuntime
    }

    Write-Host "" 
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V6.3 FULL ADVANCED PATCH: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Branch          : $TargetBranch"
    Write-Host "Backup          : $BackupBranch"
    Write-Host "Command Center  : PRESERVED"
    Write-Host "Company OS      : PRESERVED"
    Write-Host "Options         : OPTION CHAIN + OI/IV + OPTION CHARTS"
    Write-Host "Market Intel    : STRUCTURE + LIQUIDITY + ORDER-FLOW PROXY + FVG + PATTERNS"
    Write-Host "Paper Trading   : PORTFOLIO + JOURNAL + ENTRY EVIDENCE + RISK"
    Write-Host "Adaptive Brain  : ENABLED"
    Write-Host "Strategy Lab    : ENABLED"
    Write-Host "Learning        : BOUNDED PAPER OUTCOME LEARNING"
    Write-Host "Self Improve    : GOVERNED PAPER-CHALLENGER RESEARCH"
    Write-Host "Live execution  : LOCKED"
}
catch {
    Write-Host "" 
    Write-Host "V6.3 PATCH FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Stop-TrustedJarvisProcesses
    try {
        if ($PreviousBranch) {
            Invoke-Git @("switch", $PreviousBranch)
            Invoke-Git @("reset", "--hard", $PreviousHead)
        }
        else {
            Invoke-Git @("switch", "--detach", $PreviousHead)
        }
        Write-Host "Rolled back to previous JARVIS checkpoint: $PreviousHead" -ForegroundColor Yellow
        Write-Host "Backup retained: $BackupBranch" -ForegroundColor Yellow
        if (-not $NoLaunch) {
            Start-Process -FilePath (Join-Path $Root "JARVIS.bat")
        }
    }
    catch {
        Write-Host "Automatic rollback encountered an additional error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Backup branch remains available: $BackupBranch" -ForegroundColor Yellow
    }
    throw
}
