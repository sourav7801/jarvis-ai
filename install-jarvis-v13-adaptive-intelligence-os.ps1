param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260908-JARVIS-V13-adaptive-intelligence-operating-system"
$RemoteRef = "origin/$TargetBranch"
$ExpectedV12Base = "5f4f40f056609342fc12ec14055292f8dbd926c6"

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

function Wait-V13Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/v8_runtime.js",
        "http://127.0.0.1:8797/api/v12/paper-authority",
        "http://127.0.0.1:8797/api/v13/paper-authority",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8787/api/scanner/multi",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/v13/status",
        "http://127.0.0.1:8799/api/overview",
        "http://127.0.0.1:8799/api/contextual-decision",
        "http://127.0.0.1:8799/api/contextual-memory",
        "http://127.0.0.1:8799/api/decision-forensics",
        "http://127.0.0.1:8799/api/portfolio-correlation",
        "http://127.0.0.1:8799/api/options-volatility",
        "http://127.0.0.1:8799/api/strategy-governance-v13"
    )

    $deadline = [DateTime]::UtcNow.AddSeconds(240)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            try {
                $masterHomeHtml = (Invoke-WebRequest -Uri "http://127.0.0.1:8797/" -UseBasicParsing -TimeoutSec 12).Content
                $masterV12 = Invoke-RestMethod -Uri "http://127.0.0.1:8797/api/v12/paper-authority" -TimeoutSec 12
                $masterV13 = Invoke-RestMethod -Uri "http://127.0.0.1:8797/api/v13/paper-authority" -TimeoutSec 12
                $quantHealth = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/health" -TimeoutSec 12
                $controller = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/paper/portfolio-controller" -TimeoutSec 25
                $scanner = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/scanner/multi" -TimeoutSec 25
                $completionHomeHtml = (Invoke-WebRequest -Uri "http://127.0.0.1:8799/" -UseBasicParsing -TimeoutSec 12).Content
                $v13 = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/v13/status" -TimeoutSec 12
                $overview = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/overview" -TimeoutSec 35
                $decision = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/contextual-decision" -TimeoutSec 15
                $memory = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/contextual-memory" -TimeoutSec 15
                $correlation = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/portfolio-correlation" -TimeoutSec 15
                $options = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/options-volatility" -TimeoutSec 15
                $strategy = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/strategy-governance-v13" -TimeoutSec 15

                $active = @($controller.active_mandates)
                $intraday = $controller.mandates.INTRADAY
                $swing = $controller.mandates.SWING
                $investment = $controller.mandates.INVESTMENT
                $fiveLane = $null
                $tenLane = $null
                try { $fiveLane = $intraday.lanes.'5M' } catch { $fiveLane = $null }
                try { $tenLane = $intraday.lanes.'10M' } catch { $tenLane = $null }
                $fiveAuthority = $null
                if ($null -ne $fiveLane) {
                    try { $fiveAuthority = $fiveLane.adaptive_intelligence.decision_authority } catch { $fiveAuthority = $null }
                }

                if (
                    $masterHomeHtml.Contains("V8 UNIFIED INTELLIGENCE") -and
                    $masterV12.success -eq $true -and
                    $masterV12.live_execution -eq $false -and
                    $masterV13.success -eq $true -and
                    $masterV13.version -eq "13.0" -and
                    $masterV13.service -eq "JARVIS_MASTER_V13_CONTEXTUAL_BRIDGE" -and
                    $masterV13.contextual_bridge_installed -eq $true -and
                    $masterV13.decision_authority -eq "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE" -and
                    $masterV13.live_execution -eq $false -and
                    $quantHealth.success -eq $true -and
                    $controller.success -eq $true -and
                    $active -contains "INTRADAY" -and
                    $active -contains "SWING" -and
                    $active -contains "INVESTMENT" -and
                    $null -ne $fiveLane -and
                    $fiveAuthority -eq "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE" -and
                    $null -ne $tenLane -and
                    $tenLane.profile -eq "10m_only" -and
                    $tenLane.live_execution -eq $false -and
                    $investment.allowed_sides.Count -eq 1 -and
                    $investment.allowed_sides[0] -eq "LONG" -and
                    $scanner.success -eq $true -and
                    $scanner.discovery_authority -eq "BOUNDED_CONTINUOUS_TOP_N_NOT_FIXED_SCORE_GATE" -and
                    $scanner.static_discovery_score_gate -eq $false -and
                    $scanner.score_contract.execution_authority -eq $false -and
                    $completionHomeHtml.Contains("V13 ADAPTIVE INTELLIGENCE") -and
                    $v13.success -eq $true -and
                    $v13.version -eq "13.0" -and
                    $v13.service -eq "JARVIS_ADAPTIVE_INTELLIGENCE_OPERATING_SYSTEM" -and
                    $v13.runtime_bridge_installed -eq $true -and
                    $v13.decision_authority -eq "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE" -and
                    $v13.permanent_agents -eq 29 -and
                    $v13.live_execution -eq $false -and
                    $v13.automatic_broker_order -eq $false -and
                    $overview.success -eq $true -and
                    $overview.version -eq "13.0" -and
                    $overview.decision_authority.model -eq "CONTEXTUAL_EXPECTED_VALUE_WITH_OUTCOME_MEMORY" -and
                    $decision.decision_authority -eq "CONTEXTUAL_EXPECTED_VALUE_NOT_STATIC_SCORE" -and
                    $decision.legacy_score_threshold_is_execution_authority -eq $false -and
                    $memory.synthetic_history -eq $false -and
                    $correlation.completed_bars_only -eq $true -and
                    $correlation.risk_can_only_be_reduced -eq $true -and
                    $options.dealer_positioning -eq "UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY" -and
                    $strategy.governance.automatic_promotion -eq $false -and
                    $strategy.governance.automatic_production_strategy_rewrite -eq $false
                ) {
                    foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
                    Write-Host "PASS protected V8 Master + V13 contextual authority" -ForegroundColor Green
                    Write-Host "PASS V12 compatibility authority endpoint" -ForegroundColor Green
                    Write-Host "PASS contextual INTRADAY / SWING / INVESTMENT runtime" -ForegroundColor Green
                    Write-Host "PASS continuous top-N discovery without fixed score cutoff" -ForegroundColor Green
                    Write-Host "PASS completed-bar correlation risk-reduction-only contract" -ForegroundColor Green
                    Write-Host "PASS decision forensics + contextual closed-paper memory" -ForegroundColor Green
                    Write-Host "PASS verified options volatility / no fake dealer positioning" -ForegroundColor Green
                    Write-Host "PASS governed strategy lifecycle / no auto promotion" -ForegroundColor Green
                    Write-Host "PASS permanent 29-agent boundary" -ForegroundColor Green
                    Write-Host "PASS live broker execution locked" -ForegroundColor Green

                    try {
                        Write-Host "BTC LIVE CONTEXTUAL SAMPLE > authoritative Quant profiles..." -ForegroundColor Cyan
                        $btc = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/adaptive-market/sample?symbol=BTC" -TimeoutSec 150
                        if ($btc.success -eq $true -and @($btc.samples).Count -gt 0) {
                            $bestAction = "WAIT"
                            $bestEv = $null
                            $bestScore = $null
                            $policyVersion = $null
                            if ($null -ne $btc.best_adaptive_sample) {
                                $bestAction = [string]$btc.best_adaptive_sample.adaptive.action
                                $bestEv = $btc.best_adaptive_sample.adaptive.expected_value_r
                                $bestScore = $btc.best_adaptive_sample.legacy_score
                                $policyVersion = $btc.best_adaptive_sample.adaptive.policy_version
                            }
                            Write-Host "BTC LIVE CONTEXTUAL SAMPLE: PASS" -ForegroundColor Green
                            Write-Host "BTC profiles      : $(@($btc.samples).Count)"
                            Write-Host "BTC actionable    : $($btc.actionable_count)"
                            Write-Host "BTC best action   : $bestAction"
                            Write-Host "BTC best EV (R)   : $bestEv"
                            Write-Host "BTC policy        : $policyVersion"
                            Write-Host "BTC legacy score  : $bestScore (observability only)"
                        }
                        else {
                            Write-Host "BTC LIVE CONTEXTUAL SAMPLE: DEGRADED (provider/data unavailable)" -ForegroundColor DarkYellow
                        }
                    }
                    catch {
                        Write-Host "BTC LIVE CONTEXTUAL SAMPLE: DEGRADED ($($_.Exception.Message))" -ForegroundColor DarkYellow
                        Write-Host "External/public provider availability is not a code-release failure." -ForegroundColor DarkYellow
                    }
                    return
                }
            }
            catch {
                Write-Host "Runtime contract not ready yet: $($_.Exception.Message)" -ForegroundColor DarkYellow
            }
        }
        Start-Sleep -Seconds 2
    }

    foreach ($url in $required) {
        if (Test-Http200 $url) { Write-Host "200  $url" -ForegroundColor Green }
        else { Write-Host "FAIL $url" -ForegroundColor Red }
    }
    throw "V13 runtime verification failed."
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
    throw "Working tree is not clean. Preserve unrelated work before V13 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V13 ADAPTIVE INTELLIGENCE OPERATING SYSTEM" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v13-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $ExpectedV12Base HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V13 is not descended from verified V12 checkpoint $ExpectedV12Base."
    }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "omni\trading_intelligence\contextual_outcome_memory.py",
        "omni\trading_intelligence\contextual_decision_engine_v13.py",
        "omni\trading_intelligence\decision_forensics_v13.py",
        "omni\trading_intelligence\options_volatility_synthesis_v13.py",
        "omni\trading_intelligence\strategy_governance_pipeline_v13.py",
        "workstation\dynamic_correlation_risk_v13.py",
        "workstation\adaptive_discovery_router_v13.py",
        "workstation\v13_runtime_bridges.py",
        "workstation\jarvis_os_v13_bridge.py",
        "workstation\completion_console_v13.py",
        "workstation\completion_console_static\v13_intelligence_os.js",
        "scripts\jarvis_runtime_supervisor_v13.py",
        "start_jarvis_master_v13.py",
        "start_jarvis_quant_terminal.py",
        "start_jarvis_completion_console.py",
        "tests\test_v13_adaptive_intelligence_os.py",
        "tests\test_v13_runtime_contracts.py",
        "tests\test_v13_adaptive_discovery.py",
        "data\roadmap\jarvis_v13_adaptive_intelligence_os.json",
        "docs\JARVIS_V13_ADAPTIVE_INTELLIGENCE_OS.md"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V13 file is missing: $file"
        }
    }
    Write-Host "Critical V13 contextual intelligence surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\trading_intelligence\contextual_outcome_memory.py" `
        "omni\trading_intelligence\contextual_decision_engine_v13.py" `
        "omni\trading_intelligence\decision_forensics_v13.py" `
        "omni\trading_intelligence\options_volatility_synthesis_v13.py" `
        "omni\trading_intelligence\strategy_governance_pipeline_v13.py" `
        "workstation\dynamic_correlation_risk_v13.py" `
        "workstation\adaptive_discovery_router_v13.py" `
        "workstation\v13_runtime_bridges.py" `
        "workstation\jarvis_os_v13_bridge.py" `
        "workstation\completion_console_v13.py" `
        "scripts\jarvis_runtime_supervisor_v13.py" `
        "start_jarvis_master_v13.py" `
        "start_jarvis_quant_terminal.py" `
        "start_jarvis_completion_console.py" `
        "tests\test_v13_adaptive_intelligence_os.py" `
        "tests\test_v13_runtime_contracts.py" `
        "tests\test_v13_adaptive_discovery.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        $scripts = @(
            "workstation\completion_console_static\v13_intelligence_os.js",
            "workstation\completion_console_static\v12_adaptive_market.js",
            "workstation\completion_console_static\v11_execution_mesh.js",
            "workstation\completion_console_static\v10_advanced.js",
            "workstation\completion_console_static\v93_world.js",
            "workstation\quant_terminal_v2_static\paper_desk_runtime.js",
            "workstation\quant_terminal_v2_static\v12_paper_intelligence.js"
        )
        foreach ($script in $scripts) {
            & $Node.Source --check $script
            if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax failed: $script" }
        }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow
    }

    Write-Host "V13 ADAPTIVE INTELLIGENCE SAFETY CONTRACT" -ForegroundColor Cyan
    & $Python -c "from omni.agent_registry import default_agent_specs; from omni.trading_intelligence.contextual_decision_engine_v13 import CONTEXTUAL_DECISION_ENGINE_V13; from workstation.dynamic_correlation_risk_v13 import DYNAMIC_CORRELATION_RISK_V13; from omni.trading_intelligence.options_volatility_synthesis_v13 import OPTIONS_VOLATILITY_SYNTHESIS_V13; from omni.trading_intelligence.strategy_governance_pipeline_v13 import STRATEGY_GOVERNANCE_PIPELINE_V13; names={s.name for s in default_agent_specs()}; assert len(names)==29 and 'critic' in names; d=CONTEXTUAL_DECISION_ENGINE_V13.status(); assert d['legacy_score_threshold_is_execution_authority'] is False and d['live_execution'] is False; c=DYNAMIC_CORRELATION_RISK_V13.snapshot(); assert c['risk_can_only_be_reduced'] is True and c['live_execution'] is False; o=OPTIONS_VOLATILITY_SYNTHESIS_V13.status(); assert o['dealer_positioning']=='UNAVAILABLE_WITHOUT_VERIFIED_INVENTORY' and o['live_execution'] is False; g=STRATEGY_GOVERNANCE_PIPELINE_V13.snapshot(limit=1); assert g['governance']['automatic_promotion'] is False and g['governance']['automatic_production_strategy_rewrite'] is False and g['live_execution'] is False"
    if ($LASTEXITCODE -ne 0) { throw "V13 safety contract failed." }
    Write-Host "Permanent agent contract (29 + legacy critic): PASS" -ForegroundColor Green
    Write-Host "Contextual score-independent authority: PASS" -ForegroundColor Green
    Write-Host "Correlation can only reduce risk: PASS" -ForegroundColor Green
    Write-Host "Options truthfulness / no fake dealer inventory: PASS" -ForegroundColor Green
    Write-Host "Strategy promotion governance: PASS" -ForegroundColor Green
    Write-Host "Real execution locked: PASS" -ForegroundColor Green

    Write-Host "TARGETED REGRESSION > V13 + V12 + V11 + V10 + V8.1/V8/V7" -ForegroundColor Cyan
    & $Python -m unittest -q `
        tests.test_v13_adaptive_intelligence_os `
        tests.test_v13_runtime_contracts `
        tests.test_v13_adaptive_discovery `
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
    if ($LASTEXITCODE -ne 0) { throw "Targeted V13 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V13 release gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "Full regression: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow
    }

    Write-Host "PROTECTED CORE + V13 SAFETY" -ForegroundColor Cyan
    & $Python -c "from omni.core_integrity import verify_protected_core; from omni.agent_registry import default_agent_specs; core=verify_protected_core(); assert core.ok; names={s.name for s in default_agent_specs()}; assert len(names)==29 and 'critic' in names; print('Protected Core import: PASS'); print('Permanent agent contract (29): PASS'); print('V13 safety boundary: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core / V13 safety validation failed." }

    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed after V13 tests." }
    $PostTestDirty = (& git status --porcelain) -join "`n"
    if ($PostTestDirty.Trim()) {
        throw "V13 tests left the working tree dirty.`n$PostTestDirty"
    }
    Write-Host "Working tree after tests: CLEAN" -ForegroundColor Green

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V13 ADAPTIVE INTELLIGENCE OS" -ForegroundColor Cyan
        Stop-TrustedJarvisProcesses
        $oldNoBrowser = $env:JARVIS_NO_BROWSER
        $env:JARVIS_NO_BROWSER = "1"
        $runtime = Start-Process -FilePath $Python -ArgumentList @("-m", "scripts.jarvis_runtime_supervisor_v13") -WorkingDirectory $Root -WindowStyle Hidden -PassThru
        if ($null -eq $oldNoBrowser) { Remove-Item Env:JARVIS_NO_BROWSER -ErrorAction SilentlyContinue }
        else { $env:JARVIS_NO_BROWSER = $oldNoBrowser }
        Write-Host "Runtime supervisor PID: $($runtime.Id)"
        Wait-V13Runtime
    }
    else {
        Write-Host "Runtime launch: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow
    }

    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V13 ADAPTIVE INTELLIGENCE OPERATING SYSTEM: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Decision authority      : CONTEXTUAL EV + OUTCOME MEMORY + UNCERTAINTY"
    Write-Host "67/68/70 thresholds     : OBSERVABILITY ONLY"
    Write-Host "Discovery               : CONTINUOUS TOP-N / NO FIXED SCORE GATE"
    Write-Host "Adaptive actions        : PRIMARY / PROBE / WAIT"
    Write-Host "Portfolio correlation   : COMPLETED BARS / RISK REDUCTION ONLY"
    Write-Host "Decision forensics      : BOUNDED / EXPLAINABLE"
    Write-Host "Options volatility      : VERIFIED DATA / NO FAKE DEALER GAMMA"
    Write-Host "Strategy lifecycle      : GOVERNED / OPERATOR APPROVAL FOR CHAMPION"
    Write-Host "Intraday                : MTF + 5M + 10M + 15M"
    Write-Host "Swing / Investment      : CONTEXTUAL ADAPTIVE"
    Write-Host "Permanent agents        : 29 PRESERVED"
    Write-Host "External actions        : APPROVAL GATED"
    Write-Host "Real execution          : LOCKED"
    Write-Host "Backup branch           : $BackupBranch"
    Write-Host "Installed HEAD          : $Head"
}
catch {
    Write-Host ""
    Write-Host "V13 INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Stop-TrustedJarvisProcesses
    try {
        Invoke-Git @("switch", $PreviousBranch)
        Invoke-Git @("reset", "--hard", $PreviousHead)
        Write-Host "Rolled back to previous checkpoint: $PreviousHead" -ForegroundColor Yellow
        Write-Host "Backup retained: $BackupBranch" -ForegroundColor Yellow
    }
    catch {
        Write-Host "Automatic rollback encountered an error. Backup branch remains available: $BackupBranch" -ForegroundColor Red
    }
    throw
}
