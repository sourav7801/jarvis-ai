param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260907-JARVIS-V9-autonomous-cognitive-workstation"
$RemoteRef = "origin/$TargetBranch"
$VerifiedV81 = "a42b07cc3996e26dcfe7b67d2db8928bf1e6f4c9"

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
    catch { return $false }
}

function Wait-V9Release1Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/v8_runtime.js",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/intelligence.html",
        "http://127.0.0.1:8787/paper_desk_runtime.js",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/overview",
        "http://127.0.0.1:8799/api/completion",
        "http://127.0.0.1:8799/api/executive"
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(110)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            $paperJs = (Invoke-WebRequest -Uri "http://127.0.0.1:8787/paper_desk_runtime.js" -UseBasicParsing -TimeoutSec 10).Content
            $overview = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/overview" -TimeoutSec 10
            if (
                $paperJs.Contains("V8.1 INDEPENDENT HORIZONS") -and
                $paperJs.Contains("paper-narrow") -and
                $paperJs.Contains("Awaiting qualifying completed-bar evidence.") -and
                $overview.success -eq $true -and
                $overview.safety.paper_only -eq $true -and
                $overview.safety.live_execution -eq $false -and
                $overview.safety.automatic_broker_order -eq $false
            ) {
                foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
                Write-Host "PASS V9 responsive Paper Desk marker" -ForegroundColor Green
                Write-Host "PASS Completion fault-isolated overview contract" -ForegroundColor Green
                return
            }
        }
        Start-Sleep -Seconds 1
    }
    throw "V9 Release 1 runtime verification failed."
}

if (-not (Test-Path (Join-Path $Root ".git"))) {
    throw "$Root is not the JARVIS Git working tree."
}

Set-Location $Root
$PreviousBranch = (& git branch --show-current).Trim()
$PreviousHead = (& git rev-parse HEAD).Trim()
$Dirty = (& git status --porcelain) -join "`n"
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Git state." }
if ($Dirty.Trim()) {
    throw "Working tree is not clean. Preserve unrelated work before V9 Release 1 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V9 RELEASE 1 - PAPER DESK + COMPLETION HARDENING" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v9r1-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $VerifiedV81 HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V9 Release 1 is not descended from verified V8.1 checkpoint $VerifiedV81."
    }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "omni\subsystem_snapshot.py",
        "workstation\completion_console.py",
        "workstation\quant_terminal_v2_static\paper_desk_runtime.js",
        "tests\test_completion_fault_isolation.py",
        "tests\test_v9_paper_desk_ux.py"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V9 Release 1 file is missing: $file"
        }
    }
    Write-Host "Critical V9 Release 1 surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\subsystem_snapshot.py" `
        "workstation\completion_console.py" `
        "tests\test_completion_fault_isolation.py" `
        "tests\test_v9_paper_desk_ux.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        & $Node.Source --check "workstation\quant_terminal_v2_static\paper_desk_runtime.js"
        if ($LASTEXITCODE -ne 0) { throw "V9 Paper Desk JavaScript syntax validation failed." }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow
    }

    Write-Host "TARGETED REGRESSION > V9 Release 1 + V8.1/V8 compatibility" -ForegroundColor Cyan
    & $Python -m unittest `
        tests.test_completion_fault_isolation `
        tests.test_v9_paper_desk_ux `
        tests.test_v81_trading_decision_execution_repair `
        tests.test_paper_portfolio_controller `
        tests.test_paper_trading_desk `
        tests.test_v8_unified_intelligence_os `
        tests.test_v7_project_completion `
        tests.test_agent_registry `
        tests.test_brain `
        tests.test_meta_agents `
        tests.test_universal_learning_v5 `
        -q
    if ($LASTEXITCODE -ne 0) { throw "Targeted V9 Release 1 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V9 Release 1 gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }

    Write-Host "PROTECTED CORE + V9 SAFETY" -ForegroundColor Cyan
    & $Python -c "import main; from omni.agent_registry import default_agent_specs; from workstation.paper_portfolio_controller import paper_portfolio_controller; from workstation.completion_console import overview_payload; s=paper_portfolio_controller.status(); o=overview_payload(); assert len(default_agent_specs()) == 29; assert s['paper_only'] is True; assert s['live_execution'] is False; assert o['success'] is True; assert o['safety']['paper_only'] is True; assert o['safety']['live_execution'] is False; assert o['safety']['automatic_broker_order'] is False; print('Protected Core import: PASS'); print('Permanent agent contract (29): PASS'); print('Completion overview: PASS'); print('Paper-only safety: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core or V9 safety validation failed." }

    Invoke-Git @("diff", "--check")
    $PostDirty = (& git status --porcelain) -join "`n"
    if ($PostDirty.Trim()) {
        throw "V9 Release 1 validation unexpectedly modified the working tree.`n$PostDirty"
    }

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V9 RELEASE 1" -ForegroundColor Cyan
        Start-Process -FilePath (Join-Path $Root "JARVIS.bat")
        Wait-V9Release1Runtime
    }

    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V9 RELEASE 1: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Branch               : $TargetBranch"
    Write-Host "Head                 : $Head"
    Write-Host "Backup               : $BackupBranch"
    Write-Host "Verified V8.1 base   : PRESERVED"
    Write-Host "Paper Desk           : RESPONSIVE / NO HORIZONTAL DECISION SCROLL"
    Write-Host "Mandates             : INTRADAY / SWING / INVESTMENT SEPARATE"
    Write-Host "Missing scores       : DASH / NOT ZERO"
    Write-Host "Completion overview  : FAULT ISOLATED"
    Write-Host "External actions     : APPROVAL GATED"
    Write-Host "Real execution       : LOCKED"
}
catch {
    Write-Host ""
    Write-Host "V9 RELEASE 1 FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Stop-TrustedJarvisProcesses
    try {
        if ($PreviousBranch) {
            Invoke-Git @("switch", $PreviousBranch)
            Invoke-Git @("reset", "--hard", $PreviousHead)
        }
        else {
            Invoke-Git @("switch", "--detach", $PreviousHead)
        }
        Write-Host "Rolled back to previous checkpoint: $PreviousHead" -ForegroundColor Yellow
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
