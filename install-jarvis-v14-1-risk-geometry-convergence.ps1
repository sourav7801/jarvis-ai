param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260908-JARVIS-V14-1-risk-geometry-convergence"
$RemoteRef = "origin/$TargetBranch"
$ExpectedV14Base = "282d458ca0def949be126fed208afece8dcef5bd"

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
        "jarvis_runtime_supervisor_v141",
        "jarvis_runtime_supervisor_v14",
        "jarvis_runtime_supervisor_v13",
        "jarvis_runtime_supervisor_v12",
        "start_jarvis_master_v141.py",
        "start_jarvis_master_v14.py",
        "start_jarvis_master_v13.py",
        "start_jarvis_master_v12.py",
        "start_jarvis_v3.py",
        "start_jarvis_quant_terminal.py",
        "start_jarvis_nautilus_core.py",
        "start_jarvis_completion_console.py",
        "start_jarvis_native_voice.ps1"
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

function Wait-V141Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/api/v14/paper-authority",
        "http://127.0.0.1:8797/api/v14.1/paper-authority",
        "http://127.0.0.1:8787/api/v14/execution-authority",
        "http://127.0.0.1:8787/api/v14.1/status",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/v14/status",
        "http://127.0.0.1:8799/api/v14.1/status"
    )

    $deadline = [DateTime]::UtcNow.AddSeconds(240)
    $contractReady = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            try {
                $masterHome = (Invoke-WebRequest -Uri "http://127.0.0.1:8797/" -UseBasicParsing -TimeoutSec 12).Content
                $master = Invoke-RestMethod -Uri "http://127.0.0.1:8797/api/v14.1/paper-authority" -TimeoutSec 12
                $quant = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/v14.1/status" -TimeoutSec 12
                $controller = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/paper/portfolio-controller" -TimeoutSec 25
                $completion = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/v14.1/status" -TimeoutSec 12
                $active = @($controller.active_mandates)

                $contractReady = [bool](
                    $masterHome.Contains("V8 UNIFIED INTELLIGENCE") -and
                    $master.success -eq $true -and
                    $master.version -eq "14.1" -and
                    $master.service -eq "JARVIS_MASTER_V141_RISK_GEOMETRY_BRIDGE" -and
                    $master.v141_bridge_installed -eq $true -and
                    $master.scan_wrapper_installed -eq $true -and
                    $master.legacy_qualification_required_for_geometry -eq $false -and
                    $master.invalid_risk_levels_hard_blocker_preserved -eq $true -and
                    $master.live_execution -eq $false -and
                    $quant.success -eq $true -and
                    $quant.version -eq "14.1" -and
                    $quant.service -eq "JARVIS_QUANT_V141_RISK_GEOMETRY_CONVERGENCE" -and
                    $quant.runtime.installed -eq $true -and
                    $quant.runtime.scan_wrapper_installed -eq $true -and
                    $quant.runtime.upstream_legacy_qualification_can_suppress_geometry -eq $false -and
                    $quant.invalid_risk_levels_hard_blocker_preserved -eq $true -and
                    $quant.live_execution -eq $false -and
                    $controller.success -eq $true -and
                    $active -contains "INTRADAY" -and
                    $active -contains "SWING" -and
                    $active -contains "INVESTMENT" -and
                    $completion.success -eq $true -and
                    $completion.version -eq "14.1" -and
                    $completion.service -eq "JARVIS_RISK_GEOMETRY_CONVERGENCE_OS" -and
                    $completion.runtime_bridge_installed -eq $true -and
                    $completion.scan_wrapper_installed -eq $true -and
                    $completion.quant_risk_geometry_ready -eq $true -and
                    $completion.permanent_agents -eq 29 -and
                    $completion.live_execution -eq $false -and
                    $completion.automatic_broker_order -eq $false
                )
                if ($contractReady) { break }
            }
            catch {
                Write-Host "Runtime contract not ready yet: $($_.Exception.Message)" -ForegroundColor DarkYellow
            }
        }
        Start-Sleep -Seconds 2
    }

    if (-not $contractReady) {
        foreach ($url in $required) {
            if (Test-Http200 $url) { Write-Host "200  $url" -ForegroundColor Green }
            else { Write-Host "FAIL $url" -ForegroundColor Red }
        }
        throw "V14.1 runtime verification failed."
    }

    foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
    Write-Host "PASS protected V8 Master + V14.1 risk-geometry authority" -ForegroundColor Green
    Write-Host "PASS legacy qualification no longer suppresses executable geometry" -ForegroundColor Green
    Write-Host "PASS INVALID_RISK_LEVELS remains hard when verified geometry is unavailable" -ForegroundColor Green
    Write-Host "PASS V14 positive contextual-EV authority preserved" -ForegroundColor Green
    Write-Host "PASS INTRADAY / SWING / INVESTMENT paper mandates" -ForegroundColor Green
    Write-Host "PASS permanent 29-agent boundary" -ForegroundColor Green
    Write-Host "PASS live broker execution locked" -ForegroundColor Green

    Write-Host "BTC V14.1 EXECUTION TRACE > authoritative Quant profiles..." -ForegroundColor Cyan
    try {
        $btc = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/v14.1/execution-trace?symbol=BTC" -TimeoutSec 150
        if ($btc.data_sample_pass -eq $true) {
            Write-Host "BTC DATA SAMPLE: PASS" -ForegroundColor Green
        }
        else {
            Write-Host "BTC DATA SAMPLE: DEGRADED / PROVIDER UNAVAILABLE" -ForegroundColor DarkYellow
        }
        Write-Host "BTC profiles              : $(@($btc.samples).Count)"
        Write-Host "BTC actionable            : $($btc.actionable_count)"
        Write-Host "BTC size-ready            : $($btc.size_ready_count)"
        Write-Host "BTC best action           : $($btc.best_action)"
        Write-Host "BTC best EV (R)           : $($btc.best_expected_value_r)"
        Write-Host "BTC legacy score          : $($btc.best_legacy_score) (observability only)"
        if ($null -ne $btc.best_sample) {
            Write-Host "BTC best profile          : $($btc.best_sample.profile)"
            Write-Host "BTC candidate side        : $($btc.best_sample.candidate_side)"
            Write-Host "BTC geometry state        : $($btc.best_sample.risk_geometry.state)"
            Write-Host "BTC pipeline stop reason  : $($btc.best_sample.pipeline_stop_reason)"
            Write-Host "BTC entry/stop/target     : $($btc.best_sample.entry) / $($btc.best_sample.stop) / $($btc.best_sample.target)"
        }
        if ($btc.execution_pipeline_ready -eq $true) {
            Write-Host "BTC EXECUTION PIPELINE: READY FOR PAPER DESK OPEN" -ForegroundColor Green
        }
        else {
            Write-Host "BTC EXECUTION PIPELINE: NOT CURRENTLY ACTIONABLE (diagnostic, not release failure)" -ForegroundColor DarkYellow
            Write-Host "Data connectivity is explicitly NOT treated as execution proof." -ForegroundColor DarkYellow
        }
    }
    catch {
        Write-Host "BTC V14.1 TRACE: DEGRADED ($($_.Exception.Message))" -ForegroundColor DarkYellow
        Write-Host "External/public provider availability is not a deterministic code-release failure." -ForegroundColor DarkYellow
    }
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
    throw "Working tree is not clean. Preserve unrelated work before V14.1 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V14.1 RISK-GEOMETRY CONVERGENCE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v141-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $ExpectedV14Base HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V14.1 is not descended from verified V14 checkpoint $ExpectedV14Base."
    }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "workstation\risk_geometry_v141.py",
        "workstation\v141_runtime_bridges.py",
        "workstation\quant_terminal_v141_bridge.py",
        "workstation\completion_console_v141.py",
        "workstation\jarvis_os_v141_bridge.py",
        "scripts\jarvis_runtime_supervisor_v141.py",
        "start_jarvis_master_v141.py",
        "start_jarvis_quant_terminal.py",
        "start_jarvis_completion_console.py",
        "tests\test_v141_risk_geometry_convergence.py",
        "tests\test_v141_runtime_contracts.py",
        "docs\JARVIS_V14_1_RISK_GEOMETRY_CONVERGENCE.md",
        "data\roadmap\jarvis_v14_1_risk_geometry_convergence.json"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V14.1 file is missing: $file"
        }
    }
    Write-Host "Critical V14.1 risk-geometry surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "workstation\risk_geometry_v141.py" `
        "workstation\v141_runtime_bridges.py" `
        "workstation\quant_terminal_v141_bridge.py" `
        "workstation\completion_console_v141.py" `
        "workstation\jarvis_os_v141_bridge.py" `
        "scripts\jarvis_runtime_supervisor_v141.py" `
        "start_jarvis_master_v141.py" `
        "start_jarvis_quant_terminal.py" `
        "start_jarvis_completion_console.py" `
        "tests\test_v141_risk_geometry_convergence.py" `
        "tests\test_v141_runtime_contracts.py"
    if ($LASTEXITCODE -ne 0) { throw "V14.1 Python compile failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    Write-Host "V14.1 DETERMINISTIC RISK-GEOMETRY PROOF" -ForegroundColor Cyan
    & $Python -m unittest -q tests.test_v141_risk_geometry_convergence
    if ($LASTEXITCODE -ne 0) { throw "V14.1 deterministic risk-geometry proof failed." }
    Write-Host "Low legacy score can retain derived geometry: PASS" -ForegroundColor Green
    Write-Host "Stale/missing geometry still preserves INVALID_RISK_LEVELS: PASS" -ForegroundColor Green
    Write-Host "No synthetic market data: PASS" -ForegroundColor Green

    Write-Host "V14.1 SAFETY CONTRACT" -ForegroundColor Cyan
    & $Python -c "from omni.agent_registry import default_agent_specs; from workstation.risk_geometry_v141 import status as g; from workstation.v141_runtime_bridges import install_v141_runtime_bridges; n={s.name for s in default_agent_specs()}; assert len(n)==29 and 'critic' in n; r=install_v141_runtime_bridges(); assert r['installed'] and r['scan_wrapper_installed']; s=g(); assert s['verified_completed_bar_evidence_only'] and s['invalid_risk_levels_remains_hard_blocker_when_geometry_unavailable']; assert not s['data_fabricated'] and not r['live_execution'] and not r['automatic_broker_order']; print('PASS 29 specialists + critic, verified geometry, hard invalid-risk boundary, paper-only')"
    if ($LASTEXITCODE -ne 0) { throw "V14.1 safety contract failed." }

    Write-Host "TARGETED REGRESSION > V14.1 + V14 + V13 + V12 + V11 + V10 + V8.1/V8/V7" -ForegroundColor Cyan
    & $Python -m unittest -q `
        tests.test_v141_risk_geometry_convergence `
        tests.test_v141_runtime_contracts `
        tests.test_v14_autonomous_execution_intelligence `
        tests.test_v14_runtime_contracts `
        tests.test_v13_adaptive_intelligence_os `
        tests.test_v13_runtime_contracts `
        tests.test_v13_runtime_integration_hardening `
        tests.test_v13_adaptive_discovery `
        tests.test_v13_paper_execution_sizing `
        tests.test_v12_adaptive_market_intelligence `
        tests.test_v12_adaptive_runtime_contracts `
        tests.test_v11_cognitive_execution_convergence `
        tests.test_v11_runtime_and_safety `
        tests.test_v11_quant_runtime_bridges `
        tests.test_v10_advanced_autonomy_convergence `
        tests.test_v81_trading_decision_execution_repair `
        tests.test_paper_trade_action_router `
        tests.test_paper_portfolio_controller `
        tests.test_v8_unified_intelligence_os `
        tests.test_v7_project_completion
    if ($LASTEXITCODE -ne 0) { throw "Targeted V14.1 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V14.1 release gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "Full regression: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow
    }

    Write-Host "PROTECTED CORE + SOURCE SAFETY" -ForegroundColor Cyan
    & $Python -c "from omni.core_integrity import verify_protected_core; from omni.agent_registry import default_agent_specs; c=verify_protected_core(); assert c.ok; n={s.name for s in default_agent_specs()}; assert len(n)==29 and 'critic' in n; print('PASS Protected Core + 29 specialists including critic')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core verification failed." }

    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed." }
    $PostTestsDirty = (& git status --porcelain) -join "`n"
    if ($PostTestsDirty.Trim()) {
        throw "Working tree changed during V14.1 verification.`n$PostTestsDirty"
    }
    Write-Host "Clean-tree verification: PASS" -ForegroundColor Green

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V14.1 RISK-GEOMETRY CONVERGENCE" -ForegroundColor Cyan
        Stop-TrustedJarvisProcesses
        $oldNoBrowser = $env:JARVIS_NO_BROWSER
        $env:JARVIS_NO_BROWSER = "1"
        $runtime = Start-Process -FilePath $Python -ArgumentList @("-m", "scripts.jarvis_runtime_supervisor_v141") -WorkingDirectory $Root -WindowStyle Hidden -PassThru
        if ($null -eq $oldNoBrowser) { Remove-Item Env:JARVIS_NO_BROWSER -ErrorAction SilentlyContinue }
        else { $env:JARVIS_NO_BROWSER = $oldNoBrowser }
        Write-Host "Runtime supervisor PID: $($runtime.Id)"
        Wait-V141Runtime
    }
    else {
        Write-Host "Runtime launch: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow
    }

    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V14.1 RISK-GEOMETRY CONVERGENCE: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Risk geometry             : VERIFIED COMPLETED-BAR CLOSE + ATR + STRUCTURE"
    Write-Host "Legacy qualified required : NO"
    Write-Host "INVALID_RISK_LEVELS       : HARD WHEN VERIFIED GEOMETRY UNAVAILABLE"
    Write-Host "Decision authority        : POSITIVE CONTEXTUAL EV / CONTINUOUS RISK"
    Write-Host "67/68/70 thresholds       : OBSERVABILITY ONLY"
    Write-Host "Fractional sizing         : CONSTRAINT-AWARE / VERIFIED STEP"
    Write-Host "BTC data pass             : SEPARATE FROM EXECUTION-PIPELINE READINESS"
    Write-Host "Permanent agents          : 29 PRESERVED"
    Write-Host "Real execution            : LOCKED"
    Write-Host "Backup branch             : $BackupBranch"
    Write-Host "Installed HEAD            : $Head"
}
catch {
    Write-Host ""
    Write-Host "V14.1 INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Stop-TrustedJarvisProcesses
    try {
        if ($PreviousBranch) {
            Invoke-Git @("switch", $PreviousBranch)
            Invoke-Git @("reset", "--hard", $PreviousHead)
        }
        else {
            Invoke-Git @("checkout", "--detach", $PreviousHead)
        }
        Write-Host "Rolled back to previous checkpoint: $PreviousHead" -ForegroundColor Yellow
        Write-Host "Backup retained: $BackupBranch" -ForegroundColor Yellow
    }
    catch {
        Write-Host "Automatic rollback encountered an error. Backup branch remains available: $BackupBranch" -ForegroundColor Red
    }
    throw
}
