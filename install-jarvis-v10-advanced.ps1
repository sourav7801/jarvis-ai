param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260907-JARVIS-V10-advanced-autonomy-convergence"
$RemoteRef = "origin/$TargetBranch"
$VerifiedV92 = "5bfaadbbcbd4bd61d21c172664b14a7331d24677"

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
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 12
        return [int]$response.StatusCode -eq 200
    }
    catch { return $false }
}

function Wait-V10Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/intelligence.html",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/v93_world.js",
        "http://127.0.0.1:8799/v10_advanced.js",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/overview",
        "http://127.0.0.1:8799/api/missions",
        "http://127.0.0.1:8799/api/missions/graphs",
        "http://127.0.0.1:8799/api/world?refresh=1",
        "http://127.0.0.1:8799/api/cognitive-events",
        "http://127.0.0.1:8799/api/cognitive-bridge",
        "http://127.0.0.1:8799/api/autonomy",
        "http://127.0.0.1:8799/api/critic",
        "http://127.0.0.1:8799/api/evidence",
        "http://127.0.0.1:8799/api/engineering",
        "http://127.0.0.1:8799/api/system-diagnostics",
        "http://127.0.0.1:8799/api/trading-governance",
        "http://127.0.0.1:8799/api/v10/status"
    )

    $deadline = [DateTime]::UtcNow.AddSeconds(160)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            # Do not use $home: PowerShell variable names are case-insensitive and
            # $HOME is read-only on Windows PowerShell.
            $completionHomeHtml = (Invoke-WebRequest -Uri "http://127.0.0.1:8799/" -UseBasicParsing -TimeoutSec 12).Content
            $overview = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/overview" -TimeoutSec 12
            $world = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/world?refresh=1" -TimeoutSec 12
            $events = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/cognitive-events" -TimeoutSec 12
            $bridge = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/cognitive-bridge" -TimeoutSec 12
            $autonomy = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/autonomy" -TimeoutSec 12
            $critic = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/critic" -TimeoutSec 12
            $evidence = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/evidence" -TimeoutSec 12
            $engineering = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/engineering" -TimeoutSec 12
            $diagnostics = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/system-diagnostics" -TimeoutSec 12
            $tradingGov = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/trading-governance" -TimeoutSec 20
            $v10 = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/v10/status" -TimeoutSec 12

            if (
                $completionHomeHtml.Contains("JARVIS ADVANCED AUTONOMY CENTER") -and
                $completionHomeHtml.Contains("AUTONOMY CONTROL") -and
                $overview.success -eq $true -and
                $overview.version -eq "10.0" -and
                $overview.safety.paper_only -eq $true -and
                $overview.safety.live_execution -eq $false -and
                $overview.safety.automatic_broker_order -eq $false -and
                $overview.safety.automatic_production_strategy_rewrite -eq $false -and
                $world.version -eq "9.3" -and
                $world.world.persistent -eq $true -and
                $world.world.provenance_required -eq $true -and
                $world.world.freshness_explicit -eq $true -and
                $world.live_execution -eq $false -and
                $events.version -eq "9.3" -and
                $events.persistent -eq $true -and
                $events.redacts_sensitive_fields -eq $true -and
                $events.live_execution -eq $false -and
                $bridge.installed -eq $true -and
                $bridge.live_execution -eq $false -and
                $autonomy.version -eq "10.0" -and
                $autonomy.system_plane -eq $true -and
                $autonomy.permanent_agent -eq $false -and
                $autonomy.live_execution -eq $false -and
                $critic.version -eq "10.0" -and
                $critic.system_plane -eq $true -and
                $critic.permanent_agent -eq $false -and
                $critic.live_execution -eq $false -and
                $evidence.version -eq "10.0" -and
                $evidence.redacts_sensitive_fields -eq $true -and
                $evidence.live_execution -eq $false -and
                $engineering.status.version -eq "10.0" -and
                $engineering.status.capabilities.automatic_editing -eq $false -and
                $engineering.status.capabilities.automatic_merge -eq $false -and
                $engineering.status.live_execution -eq $false -and
                $diagnostics.unknown_process_termination -eq $false -and
                $diagnostics.live_execution -eq $false -and
                $tradingGov.version -eq "10.0" -and
                $tradingGov.paper_only -eq $true -and
                $tradingGov.live_execution -eq $false -and
                $tradingGov.automatic_broker_order -eq $false -and
                $v10.version -eq "10.0" -and
                $v10.permanent_agents -eq 29 -and
                $v10.paper_only -eq $true -and
                $v10.live_execution -eq $false -and
                $v10.automatic_broker_order -eq $false -and
                $v10.automatic_production_strategy_rewrite -eq $false
            ) {
                foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
                Write-Host "PASS V9.3 World Model + Cognitive Bus included in V10" -ForegroundColor Green
                Write-Host "PASS V10 Autonomy Orchestrator" -ForegroundColor Green
                Write-Host "PASS V10 System Critic + Evidence Ledger" -ForegroundColor Green
                Write-Host "PASS V10 Governed Engineering" -ForegroundColor Green
                Write-Host "PASS V10 System Diagnostics" -ForegroundColor Green
                Write-Host "PASS V10 Paper Trading Governance" -ForegroundColor Green
                Write-Host "PASS V10 Advanced Autonomy Center identity" -ForegroundColor Green
                return
            }
        }
        Start-Sleep -Seconds 1
    }

    foreach ($url in $required) {
        if (Test-Http200 $url) { Write-Host "200  $url" -ForegroundColor Green }
        else { Write-Host "FAIL $url" -ForegroundColor Red }
    }
    throw "V10 runtime verification failed."
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
    throw "Working tree is not clean. Preserve unrelated work before V10 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V10 ADVANCED AUTONOMY CONVERGENCE" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v10-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $VerifiedV92 HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V10 is not descended from verified V9 Release 2 checkpoint $VerifiedV92."
    }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "omni\goal_task_graph.py",
        "omni\mission_worker.py",
        "omni\cognitive_event_bus.py",
        "omni\world_model.py",
        "omni\cognitive_bridges.py",
        "omni\evidence_ledger.py",
        "omni\critic_verifier.py",
        "omni\engineering_governance.py",
        "omni\system_diagnostics.py",
        "omni\autonomy_orchestrator.py",
        "omni\trading_intelligence\trading_governance_center.py",
        "workstation\completion_console_v93.py",
        "workstation\completion_console_v10.py",
        "workstation\completion_console_static\v93_world.js",
        "workstation\completion_console_static\v10_advanced.js",
        "tests\test_v93_world_model_cognitive_bus.py",
        "tests\test_v10_advanced_autonomy_convergence.py",
        "tests\test_v10_autonomy_orchestrator.py"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V10 file is missing: $file"
        }
    }
    Write-Host "Critical V9.3 + V10 surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\cognitive_event_bus.py" `
        "omni\world_model.py" `
        "omni\cognitive_bridges.py" `
        "omni\context_fabric.py" `
        "omni\executive_control_plane.py" `
        "omni\evidence_ledger.py" `
        "omni\critic_verifier.py" `
        "omni\engineering_governance.py" `
        "omni\system_diagnostics.py" `
        "omni\autonomy_orchestrator.py" `
        "omni\trading_intelligence\trading_governance_center.py" `
        "workstation\completion_console_v93.py" `
        "workstation\completion_console_v10.py" `
        "start_jarvis_completion_console.py" `
        "tests\test_v10_advanced_autonomy_convergence.py" `
        "tests\test_v10_autonomy_orchestrator.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        & $Node.Source --check "workstation\completion_console_static\v93_world.js"
        if ($LASTEXITCODE -ne 0) { throw "V9.3 World Model JavaScript syntax failed." }
        & $Node.Source --check "workstation\completion_console_static\v10_advanced.js"
        if ($LASTEXITCODE -ne 0) { throw "V10 Advanced Center JavaScript syntax failed." }
        & $Node.Source --check "workstation\quant_terminal_v2_static\paper_desk_runtime.js"
        if ($LASTEXITCODE -ne 0) { throw "Paper Desk JavaScript compatibility regression failed." }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow
    }

    Write-Host "V10 ADVANCED SAFETY CONTRACT" -ForegroundColor Cyan
    & $Python -c "from omni.agent_registry import default_agent_specs; from omni.autonomy_orchestrator import AUTONOMY_ORCHESTRATOR; from omni.critic_verifier import CRITIC_VERIFIER; from omni.engineering_governance import ENGINEERING_GOVERNANCE; from omni.evidence_ledger import EVIDENCE_LEDGER; from omni.system_diagnostics import SYSTEM_DIAGNOSTICS; from omni.world_model import WORLD_MODEL; from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS; assert len(default_agent_specs()) == 29; a=AUTONOMY_ORCHESTRATOR.status(); c=CRITIC_VERIFIER.status(); e=ENGINEERING_GOVERNANCE.status(); w=WORLD_MODEL.snapshot(limit=5); b=COGNITIVE_EVENT_BUS.snapshot(limit=5); assert a['system_plane'] is True and a['permanent_agent'] is False; assert c['system_plane'] is True and c['permanent_agent'] is False; assert e['capabilities']['automatic_editing'] is False; assert e['capabilities']['automatic_merge'] is False; assert e['capabilities']['automatic_push'] is False; assert a['live_execution'] is False and c['live_execution'] is False and w['live_execution'] is False and b['live_execution'] is False; assert a['automatic_broker_order'] is False and c['automatic_broker_order'] is False; assert EVIDENCE_LEDGER.snapshot(limit=1)['redacts_sensitive_fields'] is True; assert SYSTEM_DIAGNOSTICS.status()['unknown_process_termination'] is False; print('Permanent agent contract (29): PASS'); print('V9.3 World Model/Cognitive Bus: PASS'); print('V10 Autonomy Orchestrator: PASS'); print('V10 Critic/Evidence: PASS'); print('V10 Engineering Governance: PASS'); print('V10 System Diagnostics: PASS'); print('Real execution locked: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "V10 advanced safety contract failed." }

    Write-Host "TARGETED REGRESSION > V10 + V9.3 + V9.2 + V9R1 + V8.1/V8" -ForegroundColor Cyan
    & $Python -m unittest `
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
    if ($LASTEXITCODE -ne 0) { throw "Targeted V10 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V10 release gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }

    Write-Host "PROTECTED CORE + V10 SAFETY" -ForegroundColor Cyan
    & $Python -c "import main; from omni.agent_registry import default_agent_specs; from workstation.completion_console_v10 import overview_payload; from omni.autonomy_orchestrator import AUTONOMY_ORCHESTRATOR; from omni.mission_worker import MISSION_WORKER; o=overview_payload(); a=AUTONOMY_ORCHESTRATOR.status(); m=MISSION_WORKER.status(); assert len(default_agent_specs()) == 29; assert o['success'] is True; assert o['version'] == '10.0'; assert o['safety']['paper_only'] is True; assert o['safety']['live_execution'] is False; assert o['safety']['automatic_broker_order'] is False; assert o['safety']['automatic_production_strategy_rewrite'] is False; assert a['live_execution'] is False; assert m['bounded_concurrency'] == 1; assert m['live_execution'] is False; print('Protected Core import: PASS'); print('Permanent agent contract (29): PASS'); print('V10 overview: PASS'); print('Mission runtime: PASS'); print('Paper/live safety: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core or V10 safety validation failed." }

    Invoke-Git @("diff", "--check")
    $PostDirty = (& git status --porcelain) -join "`n"
    if ($PostDirty.Trim()) {
        throw "V10 validation unexpectedly modified the working tree.`n$PostDirty"
    }

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V10 ADVANCED AUTONOMY" -ForegroundColor Cyan
        Start-Process -FilePath (Join-Path $Root "JARVIS.bat")
        Wait-V10Runtime
    }

    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V10 ADVANCED AUTONOMY CONVERGENCE: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Branch                    : $TargetBranch"
    Write-Host "Head                      : $Head"
    Write-Host "Backup                    : $BackupBranch"
    Write-Host "V9.2 rollback floor       : PRESERVED"
    Write-Host "V9.3 World Model/Bus      : INCLUDED + VERIFIED"
    Write-Host "Goal/Task Mission Runtime : PERSISTENT / RESUMABLE"
    Write-Host "Autonomy Orchestrator     : ENABLED / GOVERNED"
    Write-Host "System Critic             : ENABLED"
    Write-Host "Evidence Ledger           : ENABLED / SENSITIVE FIELDS REDACTED"
    Write-Host "Engineering Governance    : INSPECT / PLAN / CHECK / REVIEW PACKET"
    Write-Host "System Diagnostics        : OBSERVE + SAFE RECOVERY PROPOSALS"
    Write-Host "Trading Governance        : LEARNING + CHAMPION/CHALLENGER"
    Write-Host "Permanent agents          : 29 PRESERVED"
    Write-Host "External actions          : APPROVAL GATED"
    Write-Host "Production self-rewrite   : DISABLED"
    Write-Host "Real execution            : LOCKED"
}
catch {
    Write-Host ""
    Write-Host "V10 INSTALL FAILED: $($_.Exception.Message)" -ForegroundColor Red
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
