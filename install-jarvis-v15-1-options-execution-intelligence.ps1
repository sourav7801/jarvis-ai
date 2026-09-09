param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260909-JARVIS-V15-1-options-execution-intelligence"
$RemoteRef = "origin/$TargetBranch"
$ExpectedV15Base = "51f5923d5d5af755537f3cf8b75e167feac113cf"

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "git $($GitArgs -join ' ') failed with exit code $LASTEXITCODE" }
}

function Get-JarvisPython {
    foreach ($candidate in @(
        (Join-Path $Root ".venv\Scripts\python.exe"),
        (Join-Path $Root ".venv-new\Scripts\python.exe")
    )) {
        if (-not (Test-Path $candidate)) { continue }
        & $candidate -c "import omni, workstation, numpy, pandas" *> $null
        if ($LASTEXITCODE -eq 0) { return $candidate }
    }
    throw "No healthy JARVIS Python environment was found."
}

function Stop-TrustedJarvisProcesses {
    $markers = @(
        "jarvis_runtime_supervisor_v151",
        "jarvis_runtime_supervisor_v15",
        "jarvis_runtime_supervisor_v141",
        "jarvis_runtime_supervisor_v14",
        "jarvis_runtime_supervisor_v13",
        "jarvis_runtime_supervisor_v12",
        "start_jarvis_master_v151.py",
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
            if ($command.IndexOf($marker, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) { $trusted = $true; break }
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

function Wait-V151Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/api/v15/paper-authority",
        "http://127.0.0.1:8797/api/v15.1/paper-authority",
        "http://127.0.0.1:8787/api/v15/status",
        "http://127.0.0.1:8787/api/v15.1/status",
        "http://127.0.0.1:8787/api/v15.1/options/status",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/v15/status",
        "http://127.0.0.1:8799/api/v15.1/status"
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(280)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            try {
                $masterHome = (Invoke-WebRequest -Uri "http://127.0.0.1:8797/" -UseBasicParsing -TimeoutSec 12).Content
                $master = Invoke-RestMethod -Uri "http://127.0.0.1:8797/api/v15.1/paper-authority" -TimeoutSec 12
                $quant = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/v15.1/status" -TimeoutSec 12
                $options = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/v15.1/options/status" -TimeoutSec 12
                $controller = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/paper/portfolio-controller" -TimeoutSec 25
                $completion = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/v15.1/status" -TimeoutSec 12
                $active = @($controller.active_mandates)
                if (
                    $masterHome.Contains("V8 UNIFIED INTELLIGENCE") -and
                    $master.success -eq $true -and
                    $master.version -eq "15.1" -and
                    $master.service -eq "JARVIS_MASTER_V151_OPTIONS_EXECUTION_BRIDGE" -and
                    $master.protected_master_identity -eq "V8_UNIFIED_INTELLIGENCE" -and
                    $master.v151_bridge_installed -eq $true -and
                    $master.v15_market_reasoning_preserved -eq $true -and
                    $master.options_intelligence_ready -eq $true -and
                    $master.permanent_agents -eq 29 -and
                    $master.live_execution -eq $false -and
                    $quant.success -eq $true -and
                    $quant.version -eq "15.1" -and
                    $quant.service -eq "JARVIS_QUANT_V151_OPTIONS_EXECUTION_INTELLIGENCE" -and
                    $quant.v15_market_reasoning_preserved -eq $true -and
                    $quant.v141_risk_geometry_preserved -eq $true -and
                    $quant.read_only_chain_provider_preserved -eq $true -and
                    $quant.long_premium_only -eq $true -and
                    $quant.naked_option_selling -eq $false -and
                    $quant.live_execution -eq $false -and
                    $options.success -eq $true -and
                    $options.read_only_chain_provider_preserved -eq $true -and
                    $options.verified_chain_required_for_option_trade -eq $true -and
                    $controller.success -eq $true -and
                    $active -contains "INTRADAY" -and
                    $active -contains "SWING" -and
                    $active -contains "INVESTMENT" -and
                    $completion.success -eq $true -and
                    $completion.version -eq "15.1" -and
                    $completion.service -eq "JARVIS_OPTIONS_EXECUTION_INTELLIGENCE_OS" -and
                    $completion.runtime_bridge_installed -eq $true -and
                    $completion.quant_options_ready -eq $true -and
                    $completion.permanent_agents -eq 29 -and
                    $completion.live_execution -eq $false -and
                    $completion.automatic_broker_order -eq $false
                ) {
                    foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
                    Write-Host "PASS protected V8 Master + V15.1 options intelligence authority" -ForegroundColor Green
                    Write-Host "PASS V15 market reasoning + V14.1 risk geometry preserved" -ForegroundColor Green
                    Write-Host "PASS read-only option chain + paper long-premium boundary" -ForegroundColor Green
                    Write-Host "PASS INTRADAY / SWING / INVESTMENT paper mandates" -ForegroundColor Green
                    Write-Host "PASS permanent 29-agent boundary" -ForegroundColor Green
                    Write-Host "PASS live broker execution locked" -ForegroundColor Green
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
    throw "V15.1 runtime verification failed."
}

if (-not (Test-Path (Join-Path $Root ".git"))) { throw "$Root is not the JARVIS Git working tree." }
Set-Location $Root
$PreviousBranch = (& git branch --show-current).Trim()
$PreviousHead = (& git rev-parse HEAD).Trim()
$Dirty = (& git status --porcelain) -join "`n"
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Git state." }
if ($Dirty.Trim()) { throw "Working tree is not clean. Preserve unrelated work before V15.1 installation.`n$Dirty" }

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V15.1 OPTIONS EXECUTION INTELLIGENCE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v151-options-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $ExpectedV15Base HEAD
    if ($LASTEXITCODE -ne 0) { throw "V15.1 is not descended from verified V15 checkpoint $ExpectedV15Base." }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "omni\trading_intelligence\options_execution_intelligence_v151.py",
        "workstation\options_paper_execution_v151.py",
        "workstation\options_runtime_v151.py",
        "workstation\v151_runtime_bridges.py",
        "workstation\quant_terminal_v151_bridge.py",
        "workstation\completion_console_v151.py",
        "workstation\jarvis_os_v151_bridge.py",
        "scripts\jarvis_runtime_supervisor_v151.py",
        "start_jarvis_master_v151.py",
        "tests\test_v151_options_execution_intelligence.py",
        "tests\test_v151_runtime_contracts.py",
        "workstation\quant_terminal_v2_static\v151_options_execution_runtime.js",
        "workstation\completion_console_static\v151_options_execution.js"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) { throw "Critical V15.1 file is missing: $file" }
    }
    Write-Host "Critical V15.1 options execution surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\trading_intelligence\options_execution_intelligence_v151.py" `
        "workstation\options_paper_execution_v151.py" `
        "workstation\options_runtime_v151.py" `
        "workstation\v151_runtime_bridges.py" `
        "workstation\quant_terminal_v151_bridge.py" `
        "workstation\completion_console_v151.py" `
        "workstation\jarvis_os_v151_bridge.py" `
        "scripts\jarvis_runtime_supervisor_v151.py" `
        "start_jarvis_master_v151.py" `
        "start_jarvis_quant_terminal.py" `
        "start_jarvis_completion_console.py" `
        "tests\test_v151_options_execution_intelligence.py" `
        "tests\test_v151_runtime_contracts.py"
    if ($LASTEXITCODE -ne 0) { throw "V15.1 Python compile failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        foreach ($script in @(
            "workstation\quant_terminal_v2_static\v151_options_execution_runtime.js",
            "workstation\completion_console_static\v151_options_execution.js"
        )) {
            & $Node.Source --check $script
            if ($LASTEXITCODE -ne 0) { throw "JavaScript syntax failed: $script" }
        }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else { Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow }

    Write-Host "V15.1 OPTIONS SAFETY CONTRACT" -ForegroundColor Cyan
    & $Python -c "from omni.agent_registry import default_agent_specs; from omni.trading_intelligence.options_execution_intelligence_v151 import OPTIONS_EXECUTION_INTELLIGENCE_V151; from workstation.v151_runtime_bridges import install_v151_runtime_bridges; n={s.name for s in default_agent_specs()}; assert len(n)==29 and 'critic' in n; p=OPTIONS_EXECUTION_INTELLIGENCE_V151.status(); assert p['long_premium_only'] and not p['naked_option_selling'] and p['requires_verified_option_chain'] and not p['live_execution'] and not p['automatic_broker_order']; r=install_v151_runtime_bridges(); assert r['installed'] and r['v15_market_reasoning_preserved'] and r['v141_risk_geometry_preserved'] and not r['live_execution']; print('PASS 29 specialists + critic, V15 reasoning, verified options, paper-only long premium')"
    if ($LASTEXITCODE -ne 0) { throw "V15.1 safety contract failed." }

    Write-Host "V15.1 DETERMINISTIC OPTION INTELLIGENCE + PAPER EXECUTION PROOF" -ForegroundColor Cyan
    & $Python -m unittest -q tests.test_v151_options_execution_intelligence tests.test_v151_runtime_contracts
    if ($LASTEXITCODE -ne 0) { throw "V15.1 deterministic options proof failed." }
    Write-Host "Bullish call / bearish put contract expression: PASS" -ForegroundColor Green
    Write-Host "Bullish view does not force bad option trade: PASS" -ForegroundColor Green
    Write-Host "Verified chain + lot/tick fail-closed boundary: PASS" -ForegroundColor Green
    Write-Host "Missing Greeks remain unavailable / not fabricated: PASS" -ForegroundColor Green
    Write-Host "Premium risk geometry: PASS" -ForegroundColor Green
    Write-Host "Verified option plan -> Paper Desk lot open: PASS" -ForegroundColor Green

    Write-Host "TARGETED REGRESSION > V15.1 + V15 + V14.1 + V14 + V13 + V12 + V11 + V10 + V8.1/V8/V7" -ForegroundColor Cyan
    & $Python -m unittest -q `
        tests.test_v151_options_execution_intelligence `
        tests.test_v151_runtime_contracts `
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
    if ($LASTEXITCODE -ne 0) { throw "Targeted V15.1 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V15.1 release gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }
    else { Write-Host "Full regression: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow }

    Write-Host "PROTECTED CORE + SOURCE SAFETY" -ForegroundColor Cyan
    & $Python -c "from omni.core_integrity import verify_protected_core; from omni.agent_registry import default_agent_specs; c=verify_protected_core(); assert c.ok; n={s.name for s in default_agent_specs()}; assert len(n)==29 and 'critic' in n; print('PASS Protected Core + 29 specialists including critic')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core verification failed." }
    & git diff --check
    if ($LASTEXITCODE -ne 0) { throw "git diff --check failed." }
    $PostTestsDirty = (& git status --porcelain) -join "`n"
    if ($PostTestsDirty.Trim()) { throw "Working tree changed during V15.1 verification.`n$PostTestsDirty" }
    Write-Host "Clean-tree verification: PASS" -ForegroundColor Green

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V15.1 OPTIONS EXECUTION INTELLIGENCE" -ForegroundColor Cyan
        Stop-TrustedJarvisProcesses
        $oldNoBrowser = $env:JARVIS_NO_BROWSER
        $env:JARVIS_NO_BROWSER = "1"
        $runtime = Start-Process -FilePath $Python -ArgumentList @("-m", "scripts.jarvis_runtime_supervisor_v151") -WorkingDirectory $Root -WindowStyle Hidden -PassThru
        if ($null -eq $oldNoBrowser) { Remove-Item Env:JARVIS_NO_BROWSER -ErrorAction SilentlyContinue } else { $env:JARVIS_NO_BROWSER = $oldNoBrowser }
        Write-Host "Runtime supervisor PID: $($runtime.Id)"
        Wait-V151Runtime

        Write-Host "NIFTY V15.1 OPTIONS TRACE > live read-only provider diagnostic..." -ForegroundColor Cyan
        try {
            $plan = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/v15.1/options/plan?symbol=NIFTY&provider=fyers" -TimeoutSec 120
            Write-Host "NIFTY options action        : $($plan.action)"
            Write-Host "NIFTY options reason        : $($plan.reason)"
            Write-Host "Verified instrument specs  : $($plan.verified_instrument_specs)"
            if ($null -ne $plan.selected) {
                Write-Host "Selected contract           : $($plan.selected.symbol)"
                Write-Host "Option EV (R)               : $($plan.selected.option_expected_value_r)"
                Write-Host "Premium entry/stop/target   : $($plan.selected.risk_plan.entry) / $($plan.selected.risk_plan.stop) / $($plan.selected.risk_plan.target)"
            }
            if ($plan.executable -eq $true) { Write-Host "NIFTY OPTION PIPELINE: READY FOR PAPER DESK" -ForegroundColor Green }
            else { Write-Host "NIFTY OPTION PIPELINE: NOT CURRENTLY ACTIONABLE ($($plan.reason))" -ForegroundColor DarkYellow }
        }
        catch {
            Write-Host "NIFTY OPTION TRACE: DEGRADED ($($_.Exception.Message))" -ForegroundColor DarkYellow
            Write-Host "Provider/market availability is not a deterministic release failure." -ForegroundColor DarkYellow
        }
    }
    else { Write-Host "Runtime launch: SKIPPED BY EXPLICIT FLAG" -ForegroundColor DarkYellow }

    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V15.1 OPTIONS EXECUTION INTELLIGENCE: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Underlying intelligence   : V15 MARKET REASONING PRESERVED"
    Write-Host "Underlying risk geometry  : V14.1 VERIFIED GEOMETRY PRESERVED"
    Write-Host "Option chain              : VERIFIED + READ ONLY REQUIRED"
    Write-Host "Contract selection        : EXPIRY + STRIKE + SPREAD + LIQUIDITY + VERIFIED GREEKS/IV WHEN AVAILABLE"
    Write-Host "Option economics          : CAN REFUSE OPTION EVEN WHEN UNDERLYING IS DIRECTIONAL"
    Write-Host "Premium risk geometry     : MODEL RISK PLAN / NOT FUTURE QUOTES"
    Write-Host "Option execution          : PAPER LONG PREMIUM ONLY"
    Write-Host "Naked option selling      : DISABLED"
    Write-Host "Dealer positioning        : UNAVAILABLE WITHOUT VERIFIED INVENTORY"
    Write-Host "Permanent agents          : 29 PRESERVED"
    Write-Host "Real execution            : LOCKED"
    Write-Host "Backup branch             : $BackupBranch"
    Write-Host "Installed HEAD            : $Head"
}
catch {
    $Failure = $_
    Write-Host ""
    Write-Host "V15.1 INSTALL FAILED: $($Failure.Exception.Message)" -ForegroundColor Red
    try { Stop-TrustedJarvisProcesses } catch {}
    try {
        if ($PreviousBranch) {
            & git switch $PreviousBranch
            if ($LASTEXITCODE -ne 0) { throw "Could not switch back to $PreviousBranch" }
            & git reset --hard $PreviousHead
            if ($LASTEXITCODE -ne 0) { throw "Could not reset previous checkpoint" }
        }
        else { & git checkout --detach $PreviousHead }
        Write-Host "Rolled back to previous checkpoint: $PreviousHead" -ForegroundColor Yellow
        Write-Host "Backup retained: $BackupBranch" -ForegroundColor Yellow
    }
    catch {
        Write-Host "ROLLBACK WARNING: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Backup retained: $BackupBranch" -ForegroundColor Yellow
    }
    throw $Failure
}
