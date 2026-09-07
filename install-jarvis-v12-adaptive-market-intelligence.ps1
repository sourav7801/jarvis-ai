param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260908-JARVIS-V12-adaptive-market-intelligence-release"
$RemoteRef = "origin/$TargetBranch"
$ExpectedV11Base = "3fa42cdca66423d4a7284c9e4c81eb571aac9029"

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

function Wait-V12Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/v8_runtime.js",
        "http://127.0.0.1:8797/api/v12/paper-authority",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8787/api/scanner/multi",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/v12/status",
        "http://127.0.0.1:8799/api/overview",
        "http://127.0.0.1:8799/api/adaptive-policy"
    )

    $deadline = [DateTime]::UtcNow.AddSeconds(210)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            try {
                $masterHomeHtml = (Invoke-WebRequest -Uri "http://127.0.0.1:8797/" -UseBasicParsing -TimeoutSec 12).Content
                $masterAuthority = Invoke-RestMethod -Uri "http://127.0.0.1:8797/api/v12/paper-authority" -TimeoutSec 12
                $quantHealth = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/health" -TimeoutSec 12
                $controller = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/paper/portfolio-controller" -TimeoutSec 20
                $scanner = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/scanner/multi" -TimeoutSec 20
                $completionHomeHtml = (Invoke-WebRequest -Uri "http://127.0.0.1:8799/" -UseBasicParsing -TimeoutSec 12).Content
                $v12 = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/v12/status" -TimeoutSec 12
                $overview = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/overview" -TimeoutSec 30
                $policy = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/adaptive-policy" -TimeoutSec 12

                $active = @($controller.active_mandates)
                $intraday = $controller.mandates.INTRADAY
                $swing = $controller.mandates.SWING
                $investment = $controller.mandates.INVESTMENT
                $tenLane = $null
                try { $tenLane = $intraday.lanes.'10M' } catch { $tenLane = $null }

                if (
                    $masterHomeHtml.Contains("V8 UNIFIED INTELLIGENCE") -and
                    $masterAuthority.success -eq $true -and
                    $masterAuthority.service -eq "JARVIS_MASTER_V12_ADAPTIVE_BRIDGE" -and
                    $masterAuthority.adaptive_bridge_installed -eq $true -and
                    $masterAuthority.decision_authority -eq "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE" -and
                    $masterAuthority.live_execution -eq $false -and
                    $quantHealth.success -eq $true -and
                    $controller.success -eq $true -and
                    $controller.decision_authority -eq "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE" -and
                    $active -contains "INTRADAY" -and
                    $active -contains "SWING" -and
                    $active -contains "INVESTMENT" -and
                    $intraday.decision_authority -eq "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE" -and
                    $swing.decision_authority -eq "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE" -and
                    $investment.decision_authority -eq "ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE" -and
                    $intraday.live_execution -eq $false -and
                    $swing.live_execution -eq $false -and
                    $investment.live_execution -eq $false -and
                    $null -ne $tenLane -and
                    $tenLane.profile -eq "10m_only" -and
                    $tenLane.live_execution -eq $false -and
                    $scanner.success -eq $true -and
                    $scanner.score_contract.execution_authority -eq $false -and
                    $completionHomeHtml.Contains("V12 ADAPTIVE MARKET INTELLIGENCE") -and
                    $v12.success -eq $true -and
                    $v12.version -eq "12.0" -and
                    $v12.service -eq "JARVIS_ADAPTIVE_MARKET_INTELLIGENCE" -and
                    $v12.permanent_agents -eq 29 -and
                    $v12.live_execution -eq $false -and
                    $v12.automatic_broker_order -eq $false -and
                    $overview.success -eq $true -and
                    $overview.version -eq "12.0" -and
                    $overview.decision_authority.model -eq "CONTINUOUS_EVIDENCE_EXPECTED_VALUE" -and
                    $policy.legacy_score_threshold_is_execution_authority -eq $false -and
                    $policy.legacy_alignment_threshold_is_execution_authority -eq $false -and
                    $policy.legacy_risk_reward_threshold_is_execution_authority -eq $false -and
                    $policy.live_execution -eq $false -and
                    $policy.automatic_broker_order -eq $false
                ) {
                    foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
                    Write-Host "PASS protected V8 Master + V12 adaptive authority" -ForegroundColor Green
                    Write-Host "PASS adaptive INTRADAY / SWING / INVESTMENT runtime" -ForegroundColor Green
                    Write-Host "PASS 10m completed-bar lane retained" -ForegroundColor Green
                    Write-Host "PASS static 67/68/70 execution authority removed" -ForegroundColor Green
                    Write-Host "PASS 29 permanent-agent boundary" -ForegroundColor Green
                    Write-Host "PASS live broker execution locked" -ForegroundColor Green

                    try {
                        Write-Host "BTC LIVE SAMPLE > evaluating authoritative Quant profiles..." -ForegroundColor Cyan
                        $btc = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/adaptive-market/sample?symbol=BTC" -TimeoutSec 120
                        if ($btc.success -eq $true -and @($btc.samples).Count -gt 0) {
                            $bestAction = "WAIT"
                            $bestEv = $null
                            $bestScore = $null
                            if ($null -ne $btc.best_adaptive_sample) {
                                $bestAction = [string]$btc.best_adaptive_sample.adaptive.action
                                $bestEv = $btc.best_adaptive_sample.adaptive.expected_value_r
                                $bestScore = $btc.best_adaptive_sample.legacy_score
                            }
                            Write-Host "BTC LIVE SAMPLE: PASS" -ForegroundColor Green
                            Write-Host "BTC profiles      : $(@($btc.samples).Count)"
                            Write-Host "BTC actionable    : $($btc.actionable_count)"
                            Write-Host "BTC best action   : $bestAction"
                            Write-Host "BTC best EV (R)   : $bestEv"
                            Write-Host "BTC legacy score  : $bestScore (observability only)"
                        }
                        else {
                            Write-Host "BTC LIVE SAMPLE: DEGRADED (provider/data unavailable; core V12 remains verified)" -ForegroundColor DarkYellow
                        }
                    }
                    catch {
                        Write-Host "BTC LIVE SAMPLE: DEGRADED ($($_.Exception.Message))" -ForegroundColor DarkYellow
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
    throw "V12 runtime verification failed."
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
    throw "Working tree is not clean. Preserve unrelated work before V12 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V12 ADAPTIVE MARKET INTELLIGENCE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v12-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $ExpectedV11Base HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V12 is not descended from verified V11 checkpoint $ExpectedV11Base."
    }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "omni\trading_intelligence\adaptive_opportunity_policy.py",
        "workstation\adaptive_paper_autonomy_engine.py",
        "workstation\adaptive_direct_trade_bridge.py",
        "workstation\v12_runtime_bridges.py",
        "workstation\adaptive_market_sampler.py",
        "workstation\intraday_lane_group.py",
        "workstation\paper_portfolio_controller.py",
        "workstation\jarvis_os_v12_bridge.py",
        "workstation\completion_console_v12.py",
        "workstation\completion_console_static\v12_adaptive_market.js",
        "workstation\quant_terminal_v2_static\v12_paper_intelligence.js",
        "scripts\jarvis_runtime_supervisor_v12.py",
        "start_jarvis_master_v12.py",
        "start_jarvis_quant_terminal.py",
        "start_jarvis_completion_console.py",
        "tests\test_v12_adaptive_market_intelligence.py",
        "tests\test_v12_adaptive_runtime_contracts.py",
        "data\roadmap\jarvis_v12_adaptive_market_intelligence.json",
        "docs\JARVIS_V12_ADAPTIVE_MARKET_INTELLIGENCE.md"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V12 file is missing: $file"
        }
    }
    Write-Host "Critical V12 adaptive surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\trading_intelligence\adaptive_opportunity_policy.py" `
        "workstation\adaptive_paper_autonomy_engine.py" `
        "workstation\adaptive_direct_trade_bridge.py" `
        "workstation\v12_runtime_bridges.py" `
        "workstation\adaptive_market_sampler.py" `
        "workstation\intraday_lane_group.py" `
        "workstation\paper_portfolio_controller.py" `
        "workstation\jarvis_os_v12_bridge.py" `
        "workstation\completion_console_v12.py" `
        "scripts\jarvis_runtime_supervisor_v12.py" `
        "start_jarvis_master_v12.py" `
        "start_jarvis_quant_terminal.py" `
        "start_jarvis_completion_console.py" `
        "tests\test_v12_adaptive_market_intelligence.py" `
        "tests\test_v12_adaptive_runtime_contracts.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        $scripts = @(
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

    Write-Host "V12 ADAPTIVE INTELLIGENCE SAFETY CONTRACT" -ForegroundColor Cyan
    & $Python -c "from omni.agent_registry import default_agent_specs; from omni.trading_intelligence.adaptive_opportunity_policy import ADAPTIVE_OPPORTUNITY_POLICY,HARD_BLOCKERS; specs={s.name for s in default_agent_specs()}; assert len(specs)==29 and 'critic' in specs; p=ADAPTIVE_OPPORTUNITY_POLICY.status(); assert p['legacy_score_threshold_is_execution_authority'] is False and p['legacy_alignment_threshold_is_execution_authority'] is False and p['legacy_risk_reward_threshold_is_execution_authority'] is False; assert 'STALE_MARKET_DATA' in HARD_BLOCKERS; assert p['live_execution'] is False and p['automatic_broker_order'] is False"
    if ($LASTEXITCODE -ne 0) { throw "V12 safety contract failed." }
    Write-Host "Permanent agent contract (29 + legacy critic): PASS" -ForegroundColor Green
    Write-Host "Static numeric execution gates removed from V12 authority: PASS" -ForegroundColor Green
    Write-Host "Hard data/safety blockers preserved: PASS" -ForegroundColor Green
    Write-Host "Real execution locked: PASS" -ForegroundColor Green

    Write-Host "V12 LOW-SCORE / HARD-BLOCKER DECISION PROOF" -ForegroundColor Cyan
    & $Python -c "from omni.trading_intelligence.adaptive_opportunity_policy import ADAPTIVE_OPPORTUNITY_POLICY; row={'success':True,'symbol':'BTC','profile':'adaptive_intraday','qualified':False,'side':'WAIT','candidate_side':'LONG','score':66.0,'alignment':75.0,'risk_reward':2.0,'entry':79000.0,'stop':78750.0,'target':79500.0,'regime':'TRENDING','blockers':['SCORE_BELOW_GATE'],'reasons_not_to_trade':['SCORE_BELOW_GATE'],'pattern_confirmation':{'state':'CONFIRMED_BREAKOUT','direction':'BULLISH'},'votes':[{'strategy':'TEST','family':'trend','side':'LONG','regime_compatible':True}],'evidence':[{'available':True,'fresh':True,'timeframe':'5m'},{'available':True,'fresh':True,'timeframe':'15m'}],'decisions':[{'timeframe':'5m','side':'LONG'},{'timeframe':'15m','side':'LONG'}]}; d=ADAPTIVE_OPPORTUNITY_POLICY.evaluate(row,learning_state={}); assert d['executable'] is True and 'SCORE_BELOW_GATE' not in d['hard_blockers'] and 'SCORE_BELOW_GATE' in d['soft_evidence']; stale=dict(row); stale['blockers']=['STALE_MARKET_DATA']; stale['reasons_not_to_trade']=['STALE_MARKET_DATA']; d2=ADAPTIVE_OPPORTUNITY_POLICY.evaluate(stale,learning_state={}); assert d2['executable'] is False and 'STALE_MARKET_DATA' in d2['hard_blockers']; print('score66_action=',d['action'],'ev=',d['expected_value_r'],'confidence=',d['confidence'])"
    if ($LASTEXITCODE -ne 0) { throw "V12 adaptive decision proof failed." }
    Write-Host "Score 66 can trade on positive EV: PASS" -ForegroundColor Green
    Write-Host "Stale data still vetoes high score: PASS" -ForegroundColor Green

    Write-Host "TARGETED REGRESSION > V12 + V11 + V10 + V8.1/V8/V7 compatibility" -ForegroundColor Cyan
    & $Python -m unittest -q `
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
    if ($LASTEXITCODE -ne 0) { throw "Targeted V12 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V12 release gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "Full regression: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow
    }

    Write-Host "PROTECTED CORE + V12 SAFETY" -ForegroundColor Cyan
    & $Python -c "from omni.core_integrity import verify_protected_core; from omni.agent_registry import default_agent_specs; from workstation.paper_portfolio_controller import paper_portfolio_controller; core=verify_protected_core(); assert core.ok; names={s.name for s in default_agent_specs()}; assert len(names)==29 and 'critic' in names; c=paper_portfolio_controller.status(); assert c['decision_authority']=='ADAPTIVE_EXPECTED_VALUE_NOT_STATIC_SCORE'; assert c['live_execution'] is False; assert c['mandates']['INVESTMENT']['allowed_sides']==['LONG']; print('Protected Core import: PASS'); print('Permanent agent contract (29): PASS'); print('Adaptive controller safety: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core / V12 safety validation failed." }

    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed after V12 tests." }
    $PostTestDirty = (& git status --porcelain) -join "`n"
    if ($PostTestDirty.Trim()) {
        throw "V12 tests left the working tree dirty.`n$PostTestDirty"
    }
    Write-Host "Working tree after tests: CLEAN" -ForegroundColor Green

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V12 ADAPTIVE MARKET INTELLIGENCE" -ForegroundColor Cyan
        Stop-TrustedJarvisProcesses
        $oldNoBrowser = $env:JARVIS_NO_BROWSER
        $env:JARVIS_NO_BROWSER = "1"
        $runtime = Start-Process -FilePath $Python -ArgumentList @("-m", "scripts.jarvis_runtime_supervisor_v12") -WorkingDirectory $Root -WindowStyle Hidden -PassThru
        if ($null -eq $oldNoBrowser) { Remove-Item Env:JARVIS_NO_BROWSER -ErrorAction SilentlyContinue }
        else { $env:JARVIS_NO_BROWSER = $oldNoBrowser }
        Write-Host "Runtime supervisor PID: $($runtime.Id)"
        Wait-V12Runtime
    }
    else {
        Write-Host "Runtime launch: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow
    }

    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V12 ADAPTIVE MARKET INTELLIGENCE: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Decision authority      : ADAPTIVE EV / UNCERTAINTY / OUTCOME LEARNING"
    Write-Host "67/68/70 thresholds     : OBSERVABILITY ONLY"
    Write-Host "Adaptive actions        : PRIMARY / PROBE / WAIT"
    Write-Host "Direct paper commands   : CONFIDENCE-SCALED"
    Write-Host "Live mark validation    : ADAPTIVE EDGE RECHECK"
    Write-Host "Intraday                : MTF + 5M + 10M + 15M"
    Write-Host "Swing / Investment      : ADAPTIVE"
    Write-Host "Permanent agents        : 29 PRESERVED"
    Write-Host "External actions        : APPROVAL GATED"
    Write-Host "Real execution          : LOCKED"
    Write-Host "Backup branch           : $BackupBranch"
    Write-Host "Installed HEAD          : $Head"
}
catch {
    Write-Host "" 
    Write-Host "V12 INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
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
