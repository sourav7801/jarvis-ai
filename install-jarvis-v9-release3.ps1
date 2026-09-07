param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260907-JARVIS-V9-3-world-model-cognitive-bus"
$RemoteRef = "origin/$TargetBranch"
$VerifiedV92 = "5bfaadbbcbd4bd61d21c172664b14a7331d24677"

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$GitArgs)
    & git @GitArgs
    if ($LASTEXITCODE -ne 0) { throw "git $($GitArgs -join ' ') failed with exit code $LASTEXITCODE" }
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

function Wait-V9Release3Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/intelligence.html",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/overview",
        "http://127.0.0.1:8799/api/missions",
        "http://127.0.0.1:8799/api/missions/graphs",
        "http://127.0.0.1:8799/api/world?refresh=1",
        "http://127.0.0.1:8799/api/cognitive-events",
        "http://127.0.0.1:8799/api/cognitive-bridge",
        "http://127.0.0.1:8799/v93_world.js"
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(120)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        if ($pending.Count -eq 0) {
            $home = (Invoke-WebRequest -Uri "http://127.0.0.1:8799/" -UseBasicParsing -TimeoutSec 10).Content
            $overview = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/overview" -TimeoutSec 10
            $world = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/world?refresh=1" -TimeoutSec 10
            $events = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/cognitive-events" -TimeoutSec 10
            $bridge = Invoke-RestMethod -Uri "http://127.0.0.1:8799/api/cognitive-bridge" -TimeoutSec 10
            if (
                $home.Contains("JARVIS COGNITIVE INTELLIGENCE CENTER") -and
                $overview.success -eq $true -and
                $overview.version -eq "9.3" -and
                $overview.safety.paper_only -eq $true -and
                $overview.safety.live_execution -eq $false -and
                $overview.safety.automatic_broker_order -eq $false -and
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
                $bridge.live_execution -eq $false
            ) {
                foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
                Write-Host "PASS V9.3 World Model provenance/freshness contract" -ForegroundColor Green
                Write-Host "PASS V9.3 typed cognitive event bus" -ForegroundColor Green
                Write-Host "PASS verified market-event cognitive bridge" -ForegroundColor Green
                Write-Host "PASS V9.3 Completion Center identity" -ForegroundColor Green
                return
            }
        }
        Start-Sleep -Seconds 1
    }
    foreach ($url in $required) {
        if (Test-Http200 $url) { Write-Host "200  $url" -ForegroundColor Green }
        else { Write-Host "FAIL $url" -ForegroundColor Red }
    }
    throw "V9 Release 3 runtime verification failed."
}

if (-not (Test-Path (Join-Path $Root ".git"))) { throw "$Root is not the JARVIS Git working tree." }
Set-Location $Root
$PreviousBranch = (& git branch --show-current).Trim()
$PreviousHead = (& git rev-parse HEAD).Trim()
$Dirty = (& git status --porcelain) -join "`n"
if ($LASTEXITCODE -ne 0) { throw "Unable to inspect Git state." }
if ($Dirty.Trim()) { throw "Working tree is not clean. Preserve unrelated work before V9 Release 3 installation.`n$Dirty" }

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V9 RELEASE 3 - WORLD MODEL + COGNITIVE EVENT BUS" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)
$BackupBranch = "jarvis-backup/v9r3-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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
    if ($LASTEXITCODE -ne 0) { throw "V9 Release 3 is not descended from V9 Release 2 checkpoint $VerifiedV92." }

    $Python = Get-JarvisPython
    $Head = (& git rev-parse HEAD).Trim()
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $Head"

    $criticalFiles = @(
        "omni\cognitive_event_bus.py",
        "omni\world_model.py",
        "omni\cognitive_bridges.py",
        "omni\context_fabric.py",
        "workstation\completion_console_v93.py",
        "workstation\completion_console_static\v93_world.js",
        "workstation\completion_console_static\index.html",
        "start_jarvis_completion_console.py",
        "tests\test_v93_world_model_cognitive_bus.py",
        "tests\test_v93_cognitive_redaction.py",
        "tests\test_v93_completion_world_api.py"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) { throw "Critical V9 Release 3 file is missing: $file" }
    }
    Write-Host "Critical V9 Release 3 surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\cognitive_event_bus.py" `
        "omni\world_model.py" `
        "omni\cognitive_bridges.py" `
        "omni\context_fabric.py" `
        "workstation\completion_console_v93.py" `
        "start_jarvis_completion_console.py" `
        "tests\test_v93_world_model_cognitive_bus.py" `
        "tests\test_v93_cognitive_redaction.py" `
        "tests\test_v93_completion_world_api.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        & $Node.Source --check "workstation\completion_console_static\v93_world.js"
        if ($LASTEXITCODE -ne 0) { throw "V9.3 World Model JavaScript syntax validation failed." }
        & $Node.Source --check "workstation\completion_console_static\app.js"
        if ($LASTEXITCODE -ne 0) { throw "Completion Center JavaScript regression failed." }
        & $Node.Source --check "workstation\quant_terminal_v2_static\paper_desk_runtime.js"
        if ($LASTEXITCODE -ne 0) { throw "Paper Desk JavaScript regression failed." }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else { Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow }

    Write-Host "V9.3 COGNITIVE SAFETY CONTRACT" -ForegroundColor Cyan
    & $Python -c "from omni.agent_registry import default_agent_specs; from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS; from omni.world_model import WORLD_MODEL; from omni.cognitive_bridges import install_cognitive_bridges; b=COGNITIVE_EVENT_BUS.snapshot(); w=WORLD_MODEL.snapshot(); bridge=install_cognitive_bridges(); assert len(default_agent_specs()) == 29; assert b['persistent'] is True; assert b['redacts_sensitive_fields'] is True; assert b['live_execution'] is False; assert b['automatic_broker_order'] is False; assert w['persistent'] is True; assert w['provenance_required'] is True; assert w['freshness_explicit'] is True; assert w['live_execution'] is False; assert bridge['installed'] is True; assert bridge['live_execution'] is False; print('Permanent agent contract (29): PASS'); print('Typed cognitive bus: PASS'); print('Sensitive-field redaction: PASS'); print('World Model provenance/freshness: PASS'); print('Market cognitive bridge: PASS'); print('Live execution locked: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "V9.3 cognitive safety contract failed." }

    Write-Host "TARGETED REGRESSION > V9.3 + V9.2 + V9R1 + V8.1/V8 compatibility" -ForegroundColor Cyan
    & $Python -m unittest `
        tests.test_v93_world_model_cognitive_bus `
        tests.test_v93_cognitive_redaction `
        tests.test_v93_completion_world_api `
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
    if ($LASTEXITCODE -ne 0) { throw "Targeted V9 Release 3 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V9 Release 3 gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }

    Write-Host "PROTECTED CORE + V9.3 SAFETY" -ForegroundColor Cyan
    & $Python -c "import main; from omni.agent_registry import default_agent_specs; from workstation.completion_console_v93 import overview_payload; from omni.world_model import WORLD_MODEL; from omni.cognitive_event_bus import COGNITIVE_EVENT_BUS; o=overview_payload(); w=WORLD_MODEL.snapshot(); e=COGNITIVE_EVENT_BUS.snapshot(); assert len(default_agent_specs()) == 29; assert o['success'] is True; assert o['safety']['paper_only'] is True; assert o['safety']['live_execution'] is False; assert o['safety']['automatic_broker_order'] is False; assert w['live_execution'] is False; assert e['live_execution'] is False; print('Protected Core import: PASS'); print('Permanent agent contract (29): PASS'); print('V9.3 overview: PASS'); print('World Model safety: PASS'); print('Cognitive bus safety: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core or V9.3 safety validation failed." }

    Invoke-Git @("diff", "--check")
    $PostDirty = (& git status --porcelain) -join "`n"
    if ($PostDirty.Trim()) { throw "V9 Release 3 validation unexpectedly modified the working tree.`n$PostDirty" }

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V9 RELEASE 3" -ForegroundColor Cyan
        Start-Process -FilePath (Join-Path $Root "JARVIS.bat")
        Wait-V9Release3Runtime
    }

    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V9 RELEASE 3: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Branch               : $TargetBranch"
    Write-Host "Head                 : $Head"
    Write-Host "Backup               : $BackupBranch"
    Write-Host "V9 Release 2 base    : PRESERVED"
    Write-Host "World Model          : PERSISTENT / PROVENANCE + FRESHNESS EXPLICIT"
    Write-Host "Cognitive Event Bus  : TYPED / BOUNDED / PERSISTENT"
    Write-Host "Market Event Bridge  : VERIFIED EVENTS ONLY / NO TICK DUPLICATION"
    Write-Host "Executive Context    : WORLD STATE + COGNITIVE EVENTS"
    Write-Host "World UI             : ENABLED IN COMPLETION CENTER"
    Write-Host "Sensitive fields     : REDACTED"
    Write-Host "External actions     : APPROVAL GATED"
    Write-Host "Permanent agents     : 29 PRESERVED"
    Write-Host "Real execution       : LOCKED"
}
catch {
    Write-Host ""
    Write-Host "V9 RELEASE 3 FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Stop-TrustedJarvisProcesses
    try {
        if ($PreviousBranch) {
            Invoke-Git @("switch", $PreviousBranch)
            Invoke-Git @("reset", "--hard", $PreviousHead)
        }
        else { Invoke-Git @("switch", "--detach", $PreviousHead) }
        Write-Host "Rolled back to previous checkpoint: $PreviousHead" -ForegroundColor Yellow
        Write-Host "Backup retained: $BackupBranch" -ForegroundColor Yellow
        if (-not $NoLaunch) { Start-Process -FilePath (Join-Path $Root "JARVIS.bat") }
    }
    catch {
        Write-Host "Automatic rollback encountered an additional error: $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "Backup branch remains available: $BackupBranch" -ForegroundColor Yellow
    }
    throw
}
