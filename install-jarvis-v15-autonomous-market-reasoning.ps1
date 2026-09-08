param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260909-JARVIS-V15-autonomous-market-reasoning"
$RemoteRef = "origin/$TargetBranch"
$ExpectedV141Base = "c28f7e522063ad0aff02fb40ef157a722235bce0"

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
        "jarvis_runtime_supervisor_v15",
        "jarvis_runtime_supervisor_v141",
        "jarvis_runtime_supervisor_v14",
        "jarvis_runtime_supervisor_v13",
        "jarvis_runtime_supervisor_v12",
        "start_jarvis_master_v15.py",
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

function Wait-V15Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/api/v14.1/paper-authority",
        "http://127.0.0.1:8797/api/v15/paper-authority",
        "http://127.0.0.1:8787/api/v14.1/status",
        "http://127.0.0.1:8787/api/v15/status",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/v14.1/status",
        "http://127.0.0.1:8799/api/v15/status"
    )

    $deadline = [DateTime]::UtcNow.AddSeconds(260)
    $contractReady = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            try {
                $masterHome = (Invoke-WebRequest -Uri "http://127.0.0.1:8797/" -UseBasicParsing -TimeoutSec 12).Content
                $master = Invoke-RestMethod -Uri "http://127.0.0.1:8797/api/v15/paper-authority" -TimeoutSec 12
                $quant = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/v15/status" -TimeoutSec 12
                $controller = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/paper/portfolio-controller" -TimeoutSec 25
                $completion = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/v15/status" -TimeoutSec 12
                $active = @($controller.active_mandates)

                if (
                    $masterHome.Contains("V8 UNIFIED INTELLIGENCE") -and
                    $master.success -eq $true -and
                    $master.version -eq "15.0" -and
                    $master.service -eq "JARVIS_MASTER_V15_AUTONOMOUS_MARKET_REASONING_BRIDGE" -and
                    $master.protected_master_identity -eq "V8_UNIFIED_INTELLIGENCE" -and
                    $master.v15_bridge_installed -eq $true -and
                    $master.market_reasoning_ready -eq $true -and
                    $master.portfolio_allocator_ready -eq $true -and
                    $master.v141_risk_geometry_preserved -eq $true -and
                    $master.permanent_agents -eq 29 -and
                    $master.live_execution -eq $false -and
                    $quant.success -eq $true -and
                    $quant.version -eq "15.0" -and
                    $quant.service -eq "JARVIS_QUANT_V15_AUTONOMOUS_MARKET_REASONING" -and
                    $quant.runtime.installed -eq $true -and
                    $quant.runtime.v141_risk_geometry_installed -eq $true -and
                    $quant.runtime.fractional_constraint_aware_sizing -eq $true -and
                    $quant.decision.decision_authority -eq "PORTFOLIO_ADJUSTED_CONTEXTUAL_UTILITY_CONTINUOUS_RISK" -and
                    $quant.decision.portfolio_allocator_can_only_reduce_v14_risk -eq $true -and
                    $quant.invalid_risk_levels_hard_blocker_preserved -eq $true -and
                    $controller.success -eq $true -and
                    $active -contains "INTRADAY" -and
                    $active -contains "SWING" -and
                    $active -contains "INVESTMENT" -and
                    $completion.success -eq $true -and
                    $completion.version -eq "15.0" -and
                    $completion.service -eq "JARVIS_AUTONOMOUS_MARKET_REASONING_OS" -and
                    $completion.runtime_bridge_installed -eq $true -and
                    $completion.quant_reasoning_ready -eq $true -and
                    $completion.v141_risk_geometry_preserved -eq $true -and
                    $completion.permanent_agents -eq 29 -and
                    $completion.live_execution -eq $false -and
                    $completion.automatic_broker_order -eq $false
                ) {
                    $contractReady = $true
                    foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
                    Write-Host "PASS protected V8 Master + V15 autonomous reasoning authority" -ForegroundColor Green
                    Write-Host "PASS V14.1 verified risk geometry remains upstream" -ForegroundColor Green
                    Write-Host "PASS INTRADAY / SWING / INVESTMENT independent paper mandates" -ForegroundColor Green
                    Write-Host "PASS portfolio allocator can only reduce V14 paper risk" -ForegroundColor Green
                    Write-Host "PASS permanent 29-agent boundary" -ForegroundColor Green
                    Write-Host "PASS live broker execution locked" -ForegroundColor Green
                    break
                }
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
        throw "V15 runtime verification failed."
    }

    Write-Host "BTC V15 AUTONOMOUS REASONING TRACE > authoritative Quant profiles..." -ForegroundColor Cyan
    try {
        $btc = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/v15/reasoning-trace?symbol=BTC&persist=1" -TimeoutSec 170
        if ($btc.success -eq $true) {
            Write-Host "BTC DATA / REASONING SAMPLE: PASS" -ForegroundColor Green
        }
        else {
            Write-Host "BTC DATA / REASONING SAMPLE: DEGRADED" -ForegroundColor DarkYellow
        }
        Write-Host "BTC profiles              : $(@($btc.samples).Count)"
        Write-Host "BTC actionable            : $($btc.actionable_count)"
        Write-Host "BTC size-ready            : $($btc.size_ready_count)"
        Write-Host "BTC best action           : $($btc.best_action)"
        Write-Host "BTC best EV (R)           : $($btc.best_expected_value_r)"
        Write-Host "BTC portfolio utility     : $($btc.best_portfolio_utility)"
        Write-Host "BTC legacy score          : $($btc.best_legacy_score) (observability only)"
        if ($null -ne $btc.best_sample) {
            Write-Host "BTC best profile          : $($btc.best_sample.profile)"
            Write-Host "BTC candidate side        : $($btc.best_sample.candidate_side)"
            Write-Host "BTC geometry state        : $($btc.best_sample.risk_geometry.state)"
            Write-Host "BTC dominant hypothesis   : $($btc.best_sample.market_reasoning.dominant_hypothesis.name)"
            Write-Host "BTC pipeline stop reason  : $($btc.best_sample.pipeline_stop_reason)"
            Write-Host "BTC entry/stop/target     : $($btc.best_sample.entry) / $($btc.best_sample.stop) / $($btc.best_sample.target)"
        }
        if ($btc.execution_pipeline_ready -eq $true) {
            Write-Host "BTC V15 EXECUTION PIPELINE: READY FOR PAPER DESK" -ForegroundColor Green
        }
        else {
            Write-Host "BTC V15 EXECUTION PIPELINE: NOT CURRENTLY ACTIONABLE (market-state diagnostic, not release failure)" -ForegroundColor DarkYellow
        }
    }
    catch {
        Write-Host "BTC V15 TRACE: DEGRADED ($($_.Exception.Message))" -ForegroundColor DarkYellow
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
    throw "Working tree is not clean. Preserve unrelated work before V15 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V15 AUTONOMOUS MARKET REASONING" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v15-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $ExpectedV141Base HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V15 is not descended from verified V14.1 checkpoint $ExpectedV141Base."
    }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "omni\trading_intelligence\market_reasoning_v15.py",
        "omni\trading_intelligence\autonomous_decision_engine_v15.py",
        "omni\trading_intelligence\causal_trade_review_v15.py",
        "workstation\market_belief_store_v15.py",
        "workstation\position_intelligence_v15.py",
        "workstation\execution_forensics_v15.py",
        "workstation\v15_runtime_bridges.py",
        "workstation\quant_terminal_v15_bridge.py",
        "workstation\completion_console_v15.py",
        "workstation\jarvis_os_v15_bridge.py",
        "scripts\runtime_supervisor_safety_v15.py",
        "scripts\jarvis_runtime_supervisor_v15.py",
        "start_jarvis_master_v15.py",
        "tests\test_v15_autonomous_market_reasoning.py",
        "tests\test_v15_runtime_contracts.py",
        "workstation\quant_terminal_v2_static\v15_market_reasoning_runtime.js",
        "workstation\completion_console_static\v15_market_reasoning.js"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V15 file is missing: $file"
        }
    }
    Write-Host "Critical V15 autonomous reasoning surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\trading_intelligence\market_reasoning_v15.py" `
        "omni\trading_intelligence\autonomous_decision_engine_v15.py" `
        "omni\trading_intelligence\causal_trade_review_v15.py" `
        "workstation\market_belief_store_v15.py" `
        "workstation\position_intelligence_v15.py" `
        "workstation\execution_forensics_v15.py" `
        "workstation\v15_runtime_bridges.py" `
        "workstation\quant_terminal_v15_bridge.py" `
        "workstation\completion_console_v15.py" `
        "workstation\jarvis_os_v15_bridge.py" `
        "scripts\runtime_supervisor_safety_v15.py" `
        "scripts\jarvis_runtime_supervisor_v15.py" `
        "start_jarvis_master_v15.py" `
        "start_jarvis_quant_terminal.py" `
        "start_jarvis_completion_console.py" `
        "tests\test_v15_autonomous_market_reasoning.py" `
        "tests\test_v15_runtime_contracts.py"
    if ($LASTEXITCODE -ne 0) { throw "V15 Python compile failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        foreach ($script in @(
            "workstation\quant_terminal_v2_static\v15_market_reasoning_runtime.js",
            "workstation\quant_terminal_v2_static\v141_risk_geometry_runtime.js",
            "workstation\completion_console_static\v15_market_reasoning.js"
        )) {
            & $Node.Source --check $script
            if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax failed: $script" }
        }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow
    }

    Write-Host "V15 AUTONOMOUS REASONING SAFETY CONTRACT" -ForegroundColor Cyan
    & $Python -c "from omni.agent_registry import default_agent_specs; from omni.trading_intelligence.autonomous_decision_engine_v15 import AUTONOMOUS_DECISION_ENGINE_V15; from workstation.v15_runtime_bridges import install_v15_runtime_bridges; from scripts.runtime_supervisor_safety_v15 import status as ss; n={s.name for s in default_agent_specs()}; assert len(n)==29 and 'critic' in n; p=AUTONOMOUS_DECISION_ENGINE_V15.status(); assert p['portfolio_allocator_can_only_reduce_v14_risk'] and p['legacy_score_execution_authority'] is False and p['live_execution'] is False; r=install_v15_runtime_bridges(); assert r['installed'] and r['v141_risk_geometry_installed'] and r['fractional_constraint_aware_sizing'] and not r['live_execution']; s=ss(); assert s['single_supervisor_os_lease'] and s['unique_atomic_snapshot_tempfiles']; print('PASS 29 specialists + critic, V14.1 geometry, V15 utility, supervisor safety, paper-only')"
    if ($LASTEXITCODE -ne 0) { throw "V15 safety contract failed." }

    Write-Host "V15 DETERMINISTIC INTELLIGENCE + EXECUTION PROOF" -ForegroundColor Cyan
    & $Python -m unittest -q tests.test_v15_autonomous_market_reasoning tests.test_v15_runtime_contracts
    if ($LASTEXITCODE -ne 0) { throw "V15 deterministic reasoning proof failed." }
    Write-Host "Market beliefs + competing hypotheses: PASS" -ForegroundColor Green
    Write-Host "Portfolio utility allocation vs legacy score: PASS" -ForegroundColor Green
    Write-Host "Low-confidence positive EV remains continuous paper risk: PASS" -ForegroundColor Green
    Write-Host "V14.1 geometry -> fractional BTC Paper Desk open: PASS" -ForegroundColor Green
    Write-Host "Decision quality separated from outcome: PASS" -ForegroundColor Green
    Write-Host "Supervisor shared state.tmp race removed: PASS" -ForegroundColor Green

    Write-Host "TARGETED REGRESSION > V15 + V14.1 + V14 + V13 + V12 + V11 + V10 + V8.1/V8/V7" -ForegroundColor Cyan
    & $Python -m unittest -q `
        tests.test_v15_autonomous_market_reasoning `
        tests.test_v15_runtime_contracts `
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
    if ($LASTEXITCODE -ne 0) { throw "Targeted V15 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V15 release gate" -ForegroundColor Cyan
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
        throw "Working tree changed during V15 verification.`n$PostTestsDirty"
    }
    Write-Host "Clean-tree verification: PASS" -ForegroundColor Green

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V15 AUTONOMOUS MARKET REASONING" -ForegroundColor Cyan
        Stop-TrustedJarvisProcesses
        $oldNoBrowser = $env:JARVIS_NO_BROWSER
        $env:JARVIS_NO_BROWSER = "1"
        $runtime = Start-Process -FilePath $Python -ArgumentList @("-m", "scripts.jarvis_runtime_supervisor_v15") -WorkingDirectory $Root -WindowStyle Hidden -PassThru
        if ($null -eq $oldNoBrowser) { Remove-Item Env:JARVIS_NO_BROWSER -ErrorAction SilentlyContinue }
        else { $env:JARVIS_NO_BROWSER = $oldNoBrowser }
        Write-Host "Runtime supervisor PID: $($runtime.Id)"
        Wait-V15Runtime
    }
    else {
        Write-Host "Runtime launch: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow
    }

    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V15 AUTONOMOUS MARKET REASONING: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Market state             : PERSISTENT VERIFIED-EVIDENCE BELIEFS"
    Write-Host "Hypotheses               : COMPETING / EXPLAINABLE / MODEL ESTIMATES"
    Write-Host "Decision authority       : PORTFOLIO-ADJUSTED CONTEXTUAL UTILITY"
    Write-Host "V14.1 risk geometry      : PRESERVED"
    Write-Host "Legacy score             : OBSERVABILITY ONLY"
    Write-Host "Confidence               : SIZE INPUT / NOT BINARY EXECUTION GATE"
    Write-Host "Portfolio allocator      : CAN ONLY REDUCE V14 PAPER RISK"
    Write-Host "Position intelligence    : RISK-REDUCING AUTO ACTION CONTRACT"
    Write-Host "Causal review            : DECISION QUALITY != OUTCOME"
    Write-Host "Supervisor safety        : SINGLE LEASE + UNIQUE ATOMIC SNAPSHOT TEMPFILES"
    Write-Host "Permanent agents         : 29 PRESERVED"
    Write-Host "External actions         : APPROVAL GATED"
    Write-Host "Real execution           : LOCKED"
    Write-Host "Backup branch            : $BackupBranch"
    Write-Host "Installed HEAD           : $Head"
}
catch {
    $Failure = $_
    Write-Host ""
    Write-Host "V15 INSTALL FAILED: $($Failure.Exception.Message)" -ForegroundColor Red
    try { Stop-TrustedJarvisProcesses } catch {}
    try {
        if ($PreviousBranch) {
            & git switch $PreviousBranch
            if ($LASTEXITCODE -ne 0) { throw "Could not switch back to $PreviousBranch" }
            & git reset --hard $PreviousHead
            if ($LASTEXITCODE -ne 0) { throw "Could not reset previous checkpoint" }
        }
        else {
            & git checkout --detach $PreviousHead
        }
        Write-Host "Rolled back to previous checkpoint: $PreviousHead" -ForegroundColor Yellow
        Write-Host "Backup retained: $BackupBranch" -ForegroundColor Yellow
    }
    catch {
        Write-Host "ROLLBACK WARNING: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Backup retained: $BackupBranch" -ForegroundColor Yellow
    }
    throw $Failure
}
