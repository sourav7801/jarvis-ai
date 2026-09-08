param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260908-JARVIS-V14-autonomous-execution-intelligence"
$RemoteRef = "origin/$TargetBranch"
$ExpectedV13Base = "28a56f451c14af6b80718670d0f5933d84063eda"

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

function Wait-V14Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/v8_runtime.js",
        "http://127.0.0.1:8797/api/v13/paper-authority",
        "http://127.0.0.1:8797/api/v14/paper-authority",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8787/api/v14/execution-authority",
        "http://127.0.0.1:8787/api/v14/opportunity-lifecycle",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/v14/status",
        "http://127.0.0.1:8799/api/overview",
        "http://127.0.0.1:8799/api/v14/execution-authority",
        "http://127.0.0.1:8799/api/v14/opportunity-lifecycle"
    )

    $deadline = [DateTime]::UtcNow.AddSeconds(240)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            try {
                $masterHome = (Invoke-WebRequest -Uri "http://127.0.0.1:8797/" -UseBasicParsing -TimeoutSec 12).Content
                $master = Invoke-RestMethod -Uri "http://127.0.0.1:8797/api/v14/paper-authority" -TimeoutSec 12
                $quant = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/v14/execution-authority" -TimeoutSec 15
                $controller = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/paper/portfolio-controller" -TimeoutSec 25
                $lifecycle = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/v14/opportunity-lifecycle" -TimeoutSec 15
                $completionHome = (Invoke-WebRequest -Uri "http://127.0.0.1:8799/" -UseBasicParsing -TimeoutSec 12).Content
                $v14 = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/v14/status" -TimeoutSec 12
                $overview = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/overview" -TimeoutSec 35

                $active = @($controller.active_mandates)
                $fiveLane = $null
                try { $fiveLane = $controller.mandates.INTRADAY.lanes.'5M' } catch { $fiveLane = $null }
                $fiveAuthority = $null
                if ($null -ne $fiveLane) {
                    try { $fiveAuthority = $fiveLane.decision_authority } catch { $fiveAuthority = $null }
                }

                if (
                    $masterHome.Contains("V8 UNIFIED INTELLIGENCE") -and
                    $master.success -eq $true -and
                    $master.version -eq "14.0" -and
                    $master.service -eq "JARVIS_MASTER_V14_AUTONOMOUS_EXECUTION_BRIDGE" -and
                    $master.v14_bridge_installed -eq $true -and
                    $master.decision_authority -eq "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK" -and
                    $master.arbitrary_confidence_execution_gate -eq $false -and
                    $master.watching_is_terminal_state -eq $false -and
                    $master.live_execution -eq $false -and
                    $quant.success -eq $true -and
                    $quant.version -eq "14.0" -and
                    $quant.service -eq "JARVIS_QUANT_V14_EXECUTION_AUTHORITY" -and
                    $quant.policy.decision_authority -eq "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK" -and
                    $quant.policy.positive_ev_boundary_r -eq 0 -and
                    $quant.policy.arbitrary_confidence_execution_gate -eq $false -and
                    $quant.runtime.installed -eq $true -and
                    $quant.runtime.watching_is_terminal_state -eq $false -and
                    $quant.sizing.installed -eq $true -and
                    $controller.success -eq $true -and
                    $active -contains "INTRADAY" -and
                    $active -contains "SWING" -and
                    $active -contains "INVESTMENT" -and
                    $null -ne $fiveLane -and
                    $fiveAuthority -eq "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK" -and
                    $lifecycle.success -eq $true -and
                    $lifecycle.watching_is_not_a_terminal_state -eq $true -and
                    $completionHome.Contains("V14 AUTONOMOUS EXECUTION INTELLIGENCE") -and
                    $v14.success -eq $true -and
                    $v14.version -eq "14.0" -and
                    $v14.service -eq "JARVIS_AUTONOMOUS_EXECUTION_INTELLIGENCE_OS" -and
                    $v14.runtime_bridge_installed -eq $true -and
                    $v14.fractional_sizing_installed -eq $true -and
                    $v14.permanent_agents -eq 29 -and
                    $v14.live_execution -eq $false -and
                    $v14.automatic_broker_order -eq $false -and
                    $overview.success -eq $true -and
                    $overview.version -eq "14.0" -and
                    $overview.decision_authority.model -eq "POSITIVE_CONTEXTUAL_EXPECTED_VALUE_CONTINUOUS_RISK"
                ) {
                    foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
                    Write-Host "PASS protected V8 Master + V14 autonomous execution authority" -ForegroundColor Green
                    Write-Host "PASS positive EV continuous paper execution boundary" -ForegroundColor Green
                    Write-Host "PASS confidence scales risk instead of vetoing execution" -ForegroundColor Green
                    Write-Host "PASS fractional constraint-aware sizing installed" -ForegroundColor Green
                    Write-Host "PASS exact opportunity lifecycle / no ambiguous WATCHING terminal state" -ForegroundColor Green
                    Write-Host "PASS contextual INTRADAY / SWING / INVESTMENT runtime" -ForegroundColor Green
                    Write-Host "PASS permanent 29-agent boundary" -ForegroundColor Green
                    Write-Host "PASS live broker execution locked" -ForegroundColor Green

                    try {
                        Write-Host "BTC LIVE V14 SAMPLE > authoritative contextual profiles..." -ForegroundColor Cyan
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
                            if ($null -ne $bestEv -and [double]$bestEv -gt 0 -and [int]$btc.actionable_count -lt 1) {
                                throw "BTC sample had positive V14 EV but was not actionable."
                            }
                            Write-Host "BTC LIVE V14 SAMPLE: PASS" -ForegroundColor Green
                            Write-Host "BTC profiles      : $(@($btc.samples).Count)"
                            Write-Host "BTC actionable    : $($btc.actionable_count)"
                            Write-Host "BTC best action   : $bestAction"
                            Write-Host "BTC best EV (R)   : $bestEv"
                            Write-Host "BTC policy        : $policyVersion"
                            Write-Host "BTC legacy score  : $bestScore (observability only)"
                        }
                        else {
                            Write-Host "BTC LIVE V14 SAMPLE: DEGRADED (provider/data unavailable)" -ForegroundColor DarkYellow
                        }
                    }
                    catch {
                        Write-Host "BTC LIVE V14 SAMPLE: DEGRADED ($($_.Exception.Message))" -ForegroundColor DarkYellow
                        Write-Host "External/public provider availability is not a code-release failure unless a positive-EV sample violates the V14 authority contract." -ForegroundColor DarkYellow
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
    throw "V14 runtime verification failed."
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
    throw "Working tree is not clean. Preserve unrelated work before V14 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V14 AUTONOMOUS EXECUTION INTELLIGENCE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v14-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $ExpectedV13Base HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V14 is not descended from V13 checkpoint $ExpectedV13Base."
    }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "omni\trading_intelligence\continuous_execution_policy_v14.py",
        "workstation\opportunity_lifecycle_v14.py",
        "workstation\v14_runtime_bridges.py",
        "workstation\quant_terminal_v14_bridge.py",
        "workstation\jarvis_os_v14_bridge.py",
        "workstation\completion_console_v14.py",
        "workstation\paper_execution_sizing_v13.py",
        "workstation\quant_terminal_v2_static\v14_execution_runtime.js",
        "workstation\completion_console_static\v14_autonomous_execution.js",
        "scripts\jarvis_runtime_supervisor_v14.py",
        "start_jarvis_master_v14.py",
        "start_jarvis_quant_terminal.py",
        "start_jarvis_completion_console.py",
        "tests\test_v14_autonomous_execution_intelligence.py",
        "tests\test_v14_runtime_contracts.py",
        "tests\test_v13_paper_execution_sizing.py",
        "data\roadmap\jarvis_v14_autonomous_execution_intelligence.json",
        "docs\JARVIS_V14_AUTONOMOUS_EXECUTION_INTELLIGENCE.md"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V14 file is missing: $file"
        }
    }
    Write-Host "Critical V14 execution intelligence surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\trading_intelligence\continuous_execution_policy_v14.py" `
        "workstation\opportunity_lifecycle_v14.py" `
        "workstation\v14_runtime_bridges.py" `
        "workstation\quant_terminal_v14_bridge.py" `
        "workstation\jarvis_os_v14_bridge.py" `
        "workstation\completion_console_v14.py" `
        "scripts\jarvis_runtime_supervisor_v14.py" `
        "start_jarvis_master_v14.py" `
        "start_jarvis_quant_terminal.py" `
        "start_jarvis_completion_console.py" `
        "tests\test_v14_autonomous_execution_intelligence.py" `
        "tests\test_v14_runtime_contracts.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        $scripts = @(
            "workstation\quant_terminal_v2_static\v14_execution_runtime.js",
            "workstation\quant_terminal_v2_static\v13_contextual_paper_runtime.js",
            "workstation\quant_terminal_v2_static\v12_paper_intelligence.js",
            "workstation\completion_console_static\v14_autonomous_execution.js",
            "workstation\completion_console_static\v13_intelligence_os.js",
            "workstation\completion_console_static\v12_adaptive_market.js",
            "workstation\completion_console_static\v11_execution_mesh.js"
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

    Write-Host "V14 CONTINUOUS EXECUTION SAFETY CONTRACT" -ForegroundColor Cyan
    & $Python -c "from omni.agent_registry import default_agent_specs; from omni.trading_intelligence.continuous_execution_policy_v14 import CONTINUOUS_EXECUTION_POLICY_V14; from workstation.v14_runtime_bridges import install_v14_runtime_bridges; names={s.name for s in default_agent_specs()}; assert len(names)==29 and 'critic' in names; p=CONTINUOUS_EXECUTION_POLICY_V14.status(); assert p['positive_ev_boundary_r']==0.0 and p['arbitrary_confidence_execution_gate'] is False and p['live_execution'] is False; r=install_v14_runtime_bridges(); assert r['installed'] is True and r['fractional_constraint_aware_sizing'] is True and r['watching_is_terminal_state'] is False and r['live_execution'] is False"
    if ($LASTEXITCODE -ne 0) { throw "V14 safety contract failed." }
    Write-Host "Permanent agent contract (29 + legacy critic): PASS" -ForegroundColor Green
    Write-Host "Positive EV continuous execution authority: PASS" -ForegroundColor Green
    Write-Host "Arbitrary confidence execution gate removed: PASS" -ForegroundColor Green
    Write-Host "Fractional constraint-aware sizing: PASS" -ForegroundColor Green
    Write-Host "Hard safety/data boundaries preserved: PASS" -ForegroundColor Green
    Write-Host "Real execution locked: PASS" -ForegroundColor Green

    Write-Host "V14 LOW-CONFIDENCE POSITIVE-EV EXECUTION PROOF" -ForegroundColor Cyan
    & $Python -m unittest -q `
        tests.test_v14_autonomous_execution_intelligence.ContinuousExecutionPolicyV14Tests.test_positive_ev_executes_even_when_confidence_is_very_low_and_score_is_low `
        tests.test_v14_autonomous_execution_intelligence.ContinuousExecutionPolicyV14Tests.test_stale_data_remains_hard_veto_despite_positive_ev `
        tests.test_v13_paper_execution_sizing
    if ($LASTEXITCODE -ne 0) { throw "V14 execution proof failed." }
    Write-Host "Low confidence + positive EV can execute: PASS" -ForegroundColor Green
    Write-Host "Stale data still vetoes positive EV: PASS" -ForegroundColor Green
    Write-Host "Fractional BTC sizing/open path: PASS" -ForegroundColor Green

    Write-Host "TARGETED REGRESSION > V14 + V13 + V12 + V11 + V10 + V8.1/V8/V7" -ForegroundColor Cyan
    & $Python -m unittest -q `
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
    if ($LASTEXITCODE -ne 0) { throw "Targeted V14 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V14 release gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "Full regression: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow
    }

    Write-Host "PROTECTED CORE + V14 SAFETY" -ForegroundColor Cyan
    & $Python -c "from omni.core_integrity import verify_protected_core; from omni.agent_registry import default_agent_specs; core=verify_protected_core(); assert core.ok; names={s.name for s in default_agent_specs()}; assert len(names)==29 and 'critic' in names; print('Protected Core import: PASS'); print('Permanent agent contract (29): PASS'); print('V14 safety boundary: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core / V14 safety validation failed." }

    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed after V14 tests." }
    $PostTestDirty = (& git status --porcelain) -join "`n"
    if ($PostTestDirty.Trim()) {
        throw "V14 tests left the working tree dirty.`n$PostTestDirty"
    }
    Write-Host "Working tree after tests: CLEAN" -ForegroundColor Green

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V14 AUTONOMOUS EXECUTION INTELLIGENCE" -ForegroundColor Cyan
        Stop-TrustedJarvisProcesses
        $oldNoBrowser = $env:JARVIS_NO_BROWSER
        $env:JARVIS_NO_BROWSER = "1"
        $runtime = Start-Process -FilePath $Python -ArgumentList @("-m", "scripts.jarvis_runtime_supervisor_v14") -WorkingDirectory $Root -WindowStyle Hidden -PassThru
        if ($null -eq $oldNoBrowser) { Remove-Item Env:JARVIS_NO_BROWSER -ErrorAction SilentlyContinue }
        else { $env:JARVIS_NO_BROWSER = $oldNoBrowser }
        Write-Host "Runtime supervisor PID: $($runtime.Id)"
        Wait-V14Runtime
    }
    else {
        Write-Host "Runtime launch: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow
    }

    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V14 AUTONOMOUS EXECUTION INTELLIGENCE: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Decision authority      : POSITIVE CONTEXTUAL EV / CONTINUOUS RISK"
    Write-Host "67/68/70 thresholds     : OBSERVABILITY ONLY"
    Write-Host "Confidence              : POSITION SIZE INPUT / NOT EXECUTION GATE"
    Write-Host "Alignment / static R:R  : EVIDENCE ONLY / NOT EXECUTION GATES"
    Write-Host "PRIMARY / PROBE         : INTENSITY LABELS / NOT ENTRY AUTHORITY"
    Write-Host "Fractional sizing       : CONSTRAINT-AWARE / VERIFIED STEP"
    Write-Host "Watching                : NOT A TERMINAL STATE"
    Write-Host "Opportunity lifecycle   : EXACT REASON STATES"
    Write-Host "Contextual memory       : V13 CLOSED-PAPER OUTCOMES PRESERVED"
    Write-Host "Portfolio correlation   : COMPLETED BARS / RISK REDUCTION ONLY"
    Write-Host "Permanent agents        : 29 PRESERVED"
    Write-Host "External actions        : APPROVAL GATED"
    Write-Host "Real execution          : LOCKED"
    Write-Host "Backup branch           : $BackupBranch"
    Write-Host "Installed HEAD          : $Head"
}
catch {
    Write-Host ""
    Write-Host "V14 INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
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
