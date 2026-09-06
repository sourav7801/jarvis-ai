param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260907-JARVIS-V7-project-completion-core"
$RemoteRef = "origin/$TargetBranch"
$VerifiedV63 = "ade91b7526252bc29f3b2c4956919dcdc0ebef5c"

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
        if (-not (Test-Path $candidate)) { continue }
        & $candidate -c "import omni, workstation, numpy, pandas" *> $null
        if ($LASTEXITCODE -eq 0) { return $candidate }
    }
    throw "No healthy JARVIS Python environment was found."
}

function Stop-TrustedJarvisProcesses {
    $markers = @(
        "jarvis_runtime_supervisor",
        "start_jarvis_v3.py",
        "start_jarvis_quant_terminal.py",
        "start_jarvis_nautilus_core.py",
        "start_jarvis_completion_console.py"
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
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        return [int]$response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

function Wait-V7Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/intelligence.html",
        "http://127.0.0.1:8787/lightweight-charts.standalone.production.js",
        "http://127.0.0.1:8787/adaptive_brain_runtime.js",
        "http://127.0.0.1:8787/api/intelligence/status",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/completion"
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(80)
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
    throw "JARVIS V7 runtime verification failed for: $($pending -join ', ')"
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
    throw "Working tree is not clean. Commit or stash unrelated work before V7 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V7 PROJECT COMPLETION CORE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)

$BackupBranch = "jarvis-backup/v7-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
Invoke-Git @("branch", $BackupBranch, $PreviousHead)
Write-Host "Backup branch   : $BackupBranch" -ForegroundColor Yellow

try {
    Stop-TrustedJarvisProcesses

    & git show-ref --verify --quiet "refs/heads/$TargetBranch"
    if ($LASTEXITCODE -eq 0) {
        Invoke-Git @("switch", $TargetBranch)
        Invoke-Git @("merge", "--ff-only", $RemoteRef)
    }
    else {
        Invoke-Git @("switch", "-c", $TargetBranch, "--track", $RemoteRef)
    }

    & git merge-base --is-ancestor $VerifiedV63 HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V7 is not descended from the verified V6.3 checkpoint $VerifiedV63."
    }

    $Python = Get-JarvisPython
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $((& git rev-parse --short HEAD).Trim())"

    $criticalFiles = @(
        "omni\workspace_command_center.py",
        "omni\project_completion.py",
        "omni\code_intelligence.py",
        "omni\model_router_telemetry.py",
        "omni\mission_queue.py",
        "omni\trading_intelligence\robust_validation.py",
        "omni\trading_intelligence\champion_challenger.py",
        "workstation\correlation_risk_engine.py",
        "workstation\market_event_publishers.py",
        "workstation\completion_console.py",
        "workstation\completion_console_static\index.html",
        "workstation\completion_console_static\app.js",
        "workstation\completion_console_static\style.css",
        "scripts\jarvis_runtime_supervisor_v62.py",
        "scripts\jarvis_runtime_supervisor_v7.py",
        "start_jarvis_completion_console.py",
        "data\roadmap\jarvis_master_gap_map.json",
        "docs\JARVIS_MASTER_BLUEPRINT_STATUS.md"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V7 file is missing: $file"
        }
    }
    Write-Host "Critical completion surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\project_completion.py" `
        "omni\code_intelligence.py" `
        "omni\model_router_telemetry.py" `
        "omni\mission_queue.py" `
        "omni\trading_intelligence\robust_validation.py" `
        "omni\trading_intelligence\champion_challenger.py" `
        "workstation\correlation_risk_engine.py" `
        "workstation\market_event_publishers.py" `
        "workstation\completion_console.py" `
        "scripts\jarvis_runtime_supervisor_v7.py" `
        "start_jarvis_completion_console.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        & $Node.Source --check "workstation\completion_console_static\app.js"
        if ($LASTEXITCODE -ne 0) { throw "Completion Center JavaScript syntax validation failed." }
        & $Node.Source --check "workstation\quant_terminal_v2_static\intelligence.js"
        if ($LASTEXITCODE -ne 0) { throw "Quant Intelligence JavaScript regression failed." }
        & $Node.Source --check "workstation\quant_terminal_v2_static\adaptive_brain_runtime.js"
        if ($LASTEXITCODE -ne 0) { throw "Adaptive Brain JavaScript regression failed." }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow
    }

    Write-Host "TARGETED REGRESSION > V7 completion + V6.3 advanced baseline" -ForegroundColor Cyan
    & $Python -m unittest `
        tests.test_v7_project_completion `
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
    if ($LASTEXITCODE -ne 0) { throw "Targeted V7 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > repository completion gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }

    Write-Host "PROTECTED CORE + SAFETY" -ForegroundColor Cyan
    & $Python -c "import main; from omni.project_completion import snapshot; s=snapshot(); assert s['paper_only'] is True; assert s['live_execution'] is False; assert s['automatic_broker_order'] is False; print('Protected Core import: PASS'); print('V7 safety contract: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core or V7 safety validation failed." }

    Invoke-Git @("diff", "--check")
    $PostDirty = (& git status --porcelain) -join "`n"
    if ($PostDirty.Trim()) {
        throw "V7 validation unexpectedly modified the working tree.`n$PostDirty"
    }

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V7" -ForegroundColor Cyan
        Start-Process -FilePath (Join-Path $Root "JARVIS.bat")
        Wait-V7Runtime
    }

    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V7 PROJECT COMPLETION CORE: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Branch             : $TargetBranch"
    Write-Host "Backup             : $BackupBranch"
    Write-Host "V6.3 baseline      : PRESERVED"
    Write-Host "Completion Center  : http://127.0.0.1:8799"
    Write-Host "Completion Audit   : ENABLED"
    Write-Host "Code Intelligence  : ENABLED / READ ONLY"
    Write-Host "Mission Queue      : RESUMABLE / GOVERNED"
    Write-Host "Model Telemetry    : ENABLED"
    Write-Host "Market Events      : VERIFIED PUBLISHER ADAPTERS"
    Write-Host "Correlation Intel  : ENABLED / RESEARCH"
    Write-Host "Robust Validation  : OOS + BOOTSTRAP + COST STRESS"
    Write-Host "Champion/Challenger: PAPER / RESEARCH ONLY"
    Write-Host "External blockers  : SEPARATELY REPORTED"
    Write-Host "Live execution     : LOCKED"
}
catch {
    Write-Host ""
    Write-Host "V7 PATCH FAILED: $($_.Exception.Message)" -ForegroundColor Red
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
