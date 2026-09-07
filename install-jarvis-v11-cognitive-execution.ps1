param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260908-JARVIS-V11-cognitive-execution-convergence"
$RemoteRef = "origin/$TargetBranch"
$ExpectedV10Base = "61feea6f310a70adffd75b71696e1d7084d18f0c"

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

function Wait-V11Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/v8_runtime.js",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8787/api/scanner/multi",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/v11_execution_mesh.js",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/v11/status",
        "http://127.0.0.1:8799/api/execution-mesh",
        "http://127.0.0.1:8799/api/derived-timeframe",
        "http://127.0.0.1:8799/api/discovery-routing"
    )

    $deadline = [DateTime]::UtcNow.AddSeconds(180)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            try {
                $completionHomeHtml = (Invoke-WebRequest -Uri "http://127.0.0.1:8799/" -UseBasicParsing -TimeoutSec 12).Content
                $overview = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/overview" -TimeoutSec 25
                $quantHealth = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/health" -TimeoutSec 12
                $controller = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/paper/portfolio-controller" -TimeoutSec 15
                $scanner = Invoke-RestMethod -Uri "http://127.0.0.1:8787/api/scanner/multi" -TimeoutSec 15
                $execution = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/execution-mesh" -TimeoutSec 12
                $decision = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/trading-decision-mesh" -TimeoutSec 25
                $derived = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/derived-timeframe" -TimeoutSec 15
                $routing = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/discovery-routing" -TimeoutSec 15
                $v11 = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/v11/status" -TimeoutSec 12
                $v10Autonomy = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/autonomy" -TimeoutSec 12
                $v10Critic = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/critic" -TimeoutSec 12

                $tenLane = $null
                try { $tenLane = $controller.mandates.INTRADAY.lanes.'10M' } catch { $tenLane = $null }

                if (
                    $completionHomeHtml.Contains("V11 COGNITIVE EXECUTION") -and
                    $completionHomeHtml.Contains("JARVIS ADVANCED AUTONOMY CENTER") -and
                    $quantHealth.success -eq $true -and
                    $overview.success -eq $true -and
                    $overview.version -eq "11.0" -and
                    $overview.advanced.quant_runtime_authoritative -eq $true -and
                    $overview.safety.paper_only -eq $true -and
                    $overview.safety.live_execution -eq $false -and
                    $overview.safety.automatic_broker_order -eq $false -and
                    $overview.safety.automatic_production_strategy_rewrite -eq $false -and
                    $controller.success -eq $true -and
                    $controller.mandates.INTRADAY.profile -eq "intraday_lanes_v11" -and
                    $null -ne $tenLane -and
                    $tenLane.profile -eq "10m_only" -and
                    $tenLane.live_execution -eq $false -and
                    $scanner.success -eq $true -and
                    $scanner.routing_contract -eq "PORTFOLIO_HORIZON_CONTROLLER_ONLY" -and
                    $scanner.score_contract.execution_authority -eq $false -and
                    $execution.version -eq "11.0" -and
                    $execution.system_plane -eq $true -and
                    $execution.permanent_agent -eq $false -and
                    $execution.live_execution -eq $false -and
                    $execution.automatic_broker_order -eq $false -and
                    $decision.version -eq "11.0" -and
                    $decision.runtime_source -eq "QUANT_LOOPBACK_8787" -and
                    $decision.live_execution -eq $false -and
                    $decision.automatic_broker_order -eq $false -and
                    $derived.version -eq "11.0" -and
                    $derived.installed -eq $true -and
                    $derived.source -eq "QUANT_LOOPBACK_8787" -and
                    $derived.timeframe -eq "10m" -and
                    $derived.source_timeframe -eq "5m" -and
                    $derived.completed_bars_only -eq $true -and
                    $derived.synthetic_missing_bars -eq $false -and
                    $derived.live_execution -eq $false -and
                    $routing.version -eq "11.0" -and
                    $routing.installed -eq $true -and
                    $routing.routing_contract -eq "PORTFOLIO_HORIZON_CONTROLLER_ONLY" -and
                    $routing.live_execution -eq $false -and
                    $v11.version -eq "11.0" -and
                    $v11.service -eq "JARVIS_COGNITIVE_EXECUTION_CONVERGENCE" -and
                    $v11.permanent_agents -eq 29 -and
                    $v11.system_planes_do_not_count_as_agents -eq $true -and
                    $v11.paper_only -eq $true -and
                    $v11.live_execution -eq $false -and
                    $v11.automatic_broker_order -eq $false -and
                    $v11.automatic_production_strategy_rewrite -eq $false -and
                    $v10Autonomy.version -eq "10.0" -and
                    $v10Autonomy.live_execution -eq $false -and
                    $v10Critic.version -eq "10.0" -and
                    $v10Critic.live_execution -eq $false
                ) {
                    foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
                    Write-Host "PASS V8 protected Master identity retained" -ForegroundColor Green
                    Write-Host "PASS V11 Completion identity" -ForegroundColor Green
                    Write-Host "PASS authoritative Quant loopback source" -ForegroundColor Green
                    Write-Host "PASS portfolio-aware discovery routing" -ForegroundColor Green
                    Write-Host "PASS independent 5m/10m/15m intraday lanes" -ForegroundColor Green
                    Write-Host "PASS 10m completed-bar provenance contract" -ForegroundColor Green
                    Write-Host "PASS WHY-NOT-TRADE decision mesh" -ForegroundColor Green
                    Write-Host "PASS V10 Autonomy + Critic inheritance" -ForegroundColor Green
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
    throw "V11 runtime verification failed."
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
    throw "Working tree is not clean. Preserve unrelated work before V11 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V11 COGNITIVE EXECUTION CONVERGENCE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v11-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $ExpectedV10Base HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V11 is not descended from expected V10 checkpoint $ExpectedV10Base."
    }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "omni\governed_execution_mesh.py",
        "workstation\derived_timeframe_bridge.py",
        "workstation\discovery_routing_bridge.py",
        "workstation\candidate_horizon_router.py",
        "workstation\trading_decision_mesh.py",
        "workstation\trading_timeframe_profiles.py",
        "workstation\intraday_lane_group.py",
        "workstation\paper_portfolio_controller.py",
        "workstation\completion_console_v10.py",
        "workstation\completion_console_v11.py",
        "workstation\completion_console_static\v11_execution_mesh.js",
        "scripts\jarvis_runtime_supervisor_v11.py",
        "start_jarvis_quant_terminal.py",
        "start_jarvis_completion_console.py",
        "tests\test_v11_cognitive_execution_convergence.py",
        "tests\test_v11_runtime_and_safety.py",
        "tests\test_v11_quant_runtime_bridges.py",
        "data\roadmap\jarvis_v11_cognitive_execution.json"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V11 file is missing: $file"
        }
    }
    Write-Host "Critical V10 + V11 convergence surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\governed_execution_mesh.py" `
        "workstation\derived_timeframe_bridge.py" `
        "workstation\discovery_routing_bridge.py" `
        "workstation\candidate_horizon_router.py" `
        "workstation\trading_decision_mesh.py" `
        "workstation\trading_timeframe_profiles.py" `
        "workstation\intraday_lane_group.py" `
        "workstation\completion_console_v11.py" `
        "scripts\jarvis_runtime_supervisor_v11.py" `
        "start_jarvis_quant_terminal.py" `
        "start_jarvis_completion_console.py" `
        "tests\test_v11_cognitive_execution_convergence.py" `
        "tests\test_v11_runtime_and_safety.py" `
        "tests\test_v11_quant_runtime_bridges.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        & $Node.Source --check "workstation\completion_console_static\v11_execution_mesh.js"
        if ($LASTEXITCODE -ne 0) { throw "V11 Execution Mesh JavaScript syntax failed." }
        & $Node.Source --check "workstation\completion_console_static\v10_advanced.js"
        if ($LASTEXITCODE -ne 0) { throw "V10 Advanced Center JavaScript compatibility failed." }
        & $Node.Source --check "workstation\completion_console_static\v93_world.js"
        if ($LASTEXITCODE -ne 0) { throw "V9.3 World Model JavaScript compatibility failed." }
        & $Node.Source --check "workstation\quant_terminal_v2_static\paper_desk_runtime.js"
        if ($LASTEXITCODE -ne 0) { throw "Paper Desk JavaScript compatibility failed." }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow
    }

    Write-Host "V11 COGNITIVE EXECUTION SAFETY CONTRACT" -ForegroundColor Cyan
    & $Python -c "from omni.agent_registry import default_agent_specs; from omni.governed_execution_mesh import GOVERNED_EXECUTION_MESH; from workstation.trading_timeframe_profiles import resolve_trading_profile; from workstation.derived_timeframe_bridge import status as derived_status; from workstation.discovery_routing_bridge import status as routing_status; from scripts.jarvis_runtime_supervisor_v11 import v11_services; names={s.name for s in default_agent_specs()}; assert len(names)==29; assert 'critic' in names; assert not ({'executive','autonomy_orchestrator','critic_verifier','governed_execution_mesh','engineering_governance','trading_decision_mesh','discovery_routing_bridge'} & names); e=GOVERNED_EXECUTION_MESH.status(); p=resolve_trading_profile('10m'); d=derived_status(); r=routing_status(); assert e['system_plane'] is True and e['permanent_agent'] is False; assert e['live_execution'] is False and e['automatic_broker_order'] is False; assert p.name=='10m_only' and p.timeframes==('10m',) and p.require_confirmed_pattern is True; assert d['completed_bars_only'] is True and d['synthetic_missing_bars'] is False and d['live_execution'] is False; assert r['discovery_score_is_execution_score'] is False and r['live_execution'] is False; services={s.name:s for s in v11_services()}; assert services['completion'].health_url.endswith('/api/v11/status'); print('Permanent agent contract (29 + legacy critic): PASS'); print('V11 Governed Execution Mesh: PASS'); print('V11 10m completed-bar contract: PASS'); print('V11 discovery/execution score separation: PASS'); print('V11 runtime identity contract: PASS'); print('Real execution locked: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "V11 safety contract failed." }

    $launcherText = Get-Content (Join-Path $Root "JARVIS.bat") -Raw
    if (-not $launcherText.Contains("-m scripts.jarvis_runtime_supervisor_v11")) {
        throw "JARVIS.bat does not launch the V11 supervisor."
    }
    if (-not $launcherText.Contains("scripts.jarvis_runtime_supervisor_v8")) {
        throw "V8 runtime compatibility lineage marker is missing."
    }
    if (-not $launcherText.Contains("scripts.jarvis_runtime_supervisor_v62")) {
        throw "V6.2 ownership-safety lineage marker is missing."
    }

    Write-Host "TARGETED REGRESSION > V11 + V10 + V9.3 + V9.2 + V9R1 + V8.1/V8/V7" -ForegroundColor Cyan
    & $Python -m unittest `
        tests.test_v11_cognitive_execution_convergence `
        tests.test_v11_runtime_and_safety `
        tests.test_v11_quant_runtime_bridges `
        tests.test_v10_advanced_autonomy_convergence `
        tests.test_v10_autonomy_orchestrator `
        tests.test_v93_cognitive_redaction `
        tests.test_v93_completion_world_api `
        tests.test_v93_world_model_cognitive_bus `
        tests.test_v92_goal_task_mission_runtime `
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
    if ($LASTEXITCODE -ne 0) { throw "Targeted V11 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V11 release gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }

    Write-Host "PROTECTED CORE + V11 SAFETY" -ForegroundColor Cyan
    & $Python -c "import main; from omni.agent_registry import default_agent_specs; from omni.governed_execution_mesh import GOVERNED_EXECUTION_MESH; from omni.autonomy_orchestrator import AUTONOMY_ORCHESTRATOR; from omni.mission_worker import MISSION_WORKER; from workstation.trading_timeframe_profiles import resolve_trading_profile; names={s.name for s in default_agent_specs()}; assert len(names)==29 and 'critic' in names; assert 'governed_execution_mesh' not in names; e=GOVERNED_EXECUTION_MESH.status(); a=AUTONOMY_ORCHESTRATOR.status(); m=MISSION_WORKER.status(); p=resolve_trading_profile('10m'); assert e['live_execution'] is False and e['automatic_broker_order'] is False; assert a['live_execution'] is False and a['automatic_broker_order'] is False; assert m['bounded_concurrency']==1 and m['live_execution'] is False; assert p.require_confirmed_pattern is True; print('Protected Core import: PASS'); print('Permanent agent contract (29): PASS'); print('Legacy Critic specialist: PRESERVED'); print('V11 system-plane boundary: PASS'); print('Mission runtime: PASS'); print('Paper/live safety: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core or V11 safety validation failed." }

    Invoke-Git @("diff", "--check")
    $PostDirty = (& git status --porcelain) -join "`n"
    if ($PostDirty.Trim()) {
        throw "V11 validation unexpectedly modified the working tree.`n$PostDirty"
    }

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V11 COGNITIVE EXECUTION" -ForegroundColor Cyan
        Start-Process -FilePath (Join-Path $Root "JARVIS.bat")
        Wait-V11Runtime
    }

    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V11 COGNITIVE EXECUTION CONVERGENCE: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Branch                    : $TargetBranch"
    Write-Host "Head                      : $Head"
    Write-Host "Backup                    : $BackupBranch"
    Write-Host "Parent V10 checkpoint     : $ExpectedV10Base"
    Write-Host "V8 Master                 : PRESERVED / UNIFIED INTELLIGENCE"
    Write-Host "Completion Center         : V11 COGNITIVE EXECUTION"
    Write-Host "Governed Execution Mesh   : ENABLED / SYSTEM PLANE"
    Write-Host "Trading Decision Mesh     : ENABLED / WHY-NOT-TRADE"
    Write-Host "Discovery routing         : PORTFOLIO HORIZON CONTROLLER"
    Write-Host "Intraday execution lanes  : MTF + 5M + 10M + 15M"
    Write-Host "10m bars                  : 2x CONTIGUOUS COMPLETED 5m PROVIDER BARS"
    Write-Host "Discovery score           : NOT EXECUTION AUTHORITY"
    Write-Host "Quant source of truth     : 127.0.0.1:8787"
    Write-Host "Mission queueing          : AFTER V11 CRITIC / EXPLICIT"
    Write-Host "Permanent agents          : 29 PRESERVED"
    Write-Host "Legacy Critic specialist  : PRESERVED"
    Write-Host "External actions          : APPROVAL GATED"
    Write-Host "Production self-rewrite   : DISABLED"
    Write-Host "Real execution            : LOCKED"
}
catch {
    Write-Host ""
    Write-Host "V11 INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
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
