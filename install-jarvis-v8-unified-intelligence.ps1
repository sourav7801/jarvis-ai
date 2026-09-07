param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/20260907-JARVIS-V8-unified-intelligence-os"
$RemoteRef = "origin/$TargetBranch"
$VerifiedV7 = "b0b67a67046717dca4d0b76ad68194f0001f67e7"

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
    catch {
        return $false
    }
}

function Test-HttpContains {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Marker
    )
    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 10
        return ([int]$response.StatusCode -eq 200) -and ([string]$response.Content).Contains($Marker)
    }
    catch {
        return $false
    }
}

function Wait-V8Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/v8_runtime.js",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/intelligence.html",
        "http://127.0.0.1:8787/lightweight-charts.standalone.production.js",
        "http://127.0.0.1:8787/adaptive_brain_runtime.js",
        "http://127.0.0.1:8787/api/intelligence/status",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/completion",
        "http://127.0.0.1:8799/api/executive"
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(90)
    $pending = @($required)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        $masterV8 = Test-HttpContains "http://127.0.0.1:8797/" "V8 UNIFIED INTELLIGENCE"
        $runtimeV8 = Test-HttpContains "http://127.0.0.1:8797/v8_runtime.js" "executeWorkspaceActionsV8"
        if ($pending.Count -eq 0 -and $masterV8 -and $runtimeV8) {
            foreach ($url in $required) {
                Write-Host "200  $url" -ForegroundColor Green
            }
            Write-Host "PASS V8 Master identity marker" -ForegroundColor Green
            Write-Host "PASS V8 browser runtime marker" -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 1
    }
    foreach ($url in $required) {
        if (Test-Http200 $url) { Write-Host "200  $url" -ForegroundColor Green }
        else { Write-Host "FAIL $url" -ForegroundColor Red }
    }
    if (-not (Test-HttpContains "http://127.0.0.1:8797/" "V8 UNIFIED INTELLIGENCE")) {
        Write-Host "FAIL V8 Master identity marker" -ForegroundColor Red
    }
    if (-not (Test-HttpContains "http://127.0.0.1:8797/v8_runtime.js" "executeWorkspaceActionsV8")) {
        Write-Host "FAIL V8 browser runtime marker" -ForegroundColor Red
    }
    throw "JARVIS V8 runtime verification failed."
}

if (-not (Test-Path (Join-Path $Root ".git"))) {
    throw "$Root is not the JARVIS Git working tree."
}

Set-Location $Root
$PreviousBranch = (& git branch --show-current).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read current Git branch." }
$PreviousHead = (& git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw "Unable to read current Git HEAD." }
$Dirty = (& git status --porcelain) -join "`n"
if ($LASTEXITCODE -ne 0) { throw "Unable to read Git status." }
if ($Dirty.Trim()) {
    throw "Working tree is not clean. Commit or stash unrelated work before V8 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V8 UNIFIED INTELLIGENCE OS" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)

$BackupBranch = "jarvis-backup/v8-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $VerifiedV7 HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V8 is not descended from verified V7 checkpoint $VerifiedV7."
    }

    $Python = Get-JarvisPython
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $((& git rev-parse --short HEAD).Trim())"

    $criticalFiles = @(
        "omni\unified_intent_router.py",
        "omni\context_fabric.py",
        "omni\executive_control_plane.py",
        "omni\workspace_command_center.py",
        "omni\project_completion.py",
        "omni\code_intelligence.py",
        "omni\mission_queue.py",
        "omni\model_router_telemetry.py",
        "workstation\jarvis_os_v8.py",
        "workstation\jarvis_os_v8_assets\runtime.js",
        "workstation\completion_console.py",
        "workstation\completion_console_static\index.html",
        "workstation\completion_console_static\app.js",
        "workstation\quant_terminal_v2_static\intelligence.html",
        "workstation\quant_terminal_v2_static\adaptive_brain_runtime.js",
        "scripts\jarvis_runtime_supervisor_v62.py",
        "scripts\jarvis_runtime_supervisor_v7.py",
        "scripts\jarvis_runtime_supervisor_v8.py",
        "start_jarvis_v3.py",
        "data\roadmap\jarvis_master_gap_map.json",
        "docs\JARVIS_MASTER_BLUEPRINT_STATUS.md",
        "tests\test_v8_unified_intelligence_os.py"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V8 file is missing: $file"
        }
    }
    Write-Host "Critical unified-intelligence surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "omni\unified_intent_router.py" `
        "omni\context_fabric.py" `
        "omni\executive_control_plane.py" `
        "omni\project_completion.py" `
        "omni\meta_agent_specs.py" `
        "workstation\jarvis_os_v8.py" `
        "workstation\completion_console.py" `
        "scripts\jarvis_runtime_supervisor_v8.py" `
        "start_jarvis_v3.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        & $Node.Source --check "workstation\jarvis_os_v8_assets\runtime.js"
        if ($LASTEXITCODE -ne 0) { throw "V8 Master runtime JavaScript syntax validation failed." }
        & $Node.Source --check "workstation\completion_console_static\app.js"
        if ($LASTEXITCODE -ne 0) { throw "Completion/Executive Center JavaScript syntax validation failed." }
        & $Node.Source --check "workstation\quant_terminal_v2_static\intelligence.js"
        if ($LASTEXITCODE -ne 0) { throw "Quant Intelligence JavaScript regression failed." }
        & $Node.Source --check "workstation\quant_terminal_v2_static\adaptive_brain_runtime.js"
        if ($LASTEXITCODE -ne 0) { throw "Adaptive Brain JavaScript regression failed." }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow
    }

    Write-Host "EXACT COMMAND CONTRACT > open apps workspace" -ForegroundColor Cyan
    $ExactApps = "from omni.unified_intent_router import route_intent; d=route_intent('open apps workspace'); assert d.deterministic is True; assert d.kind == 'WORKSPACE_CONTROL'; assert {'type':'open_window','window':'apps'} in list(d.workspace_actions); assert 'Computer & Apps' in d.response; assert 'understand' not in d.response.lower(); print('open apps workspace: PASS ->', d.response)"
    & $Python -c $ExactApps
    if ($LASTEXITCODE -ne 0) { throw "Exact Apps workspace command contract failed." }

    Write-Host "TARGETED REGRESSION > V8 unified intelligence + cross-generation compatibility" -ForegroundColor Cyan
    & $Python -m unittest `
        tests.test_v8_unified_intelligence_os `
        tests.test_v7_project_completion `
        tests.test_agent_registry `
        tests.test_brain `
        tests.test_meta_agents `
        tests.test_universal_learning_v5 `
        tests.test_jarvis_conversation_research_startup_v1 `
        tests.test_quant_v5_nautilus_integration `
        tests.test_quant_v63_full_advanced `
        tests.test_quant_v6_adaptive_integration `
        tests.test_quant_v6_chart_runtime `
        tests.test_self_improvement_v6 `
        tests.test_workspace_command_center `
        tests.test_workspace_command_center_health `
        tests.test_company_terminal `
        tests.test_quant_terminal_v2 `
        tests.test_options_chain_analytics `
        tests.test_paper_trading_desk `
        tests.test_jarvis_runtime_supervisor `
        tests.test_runtime_supervisor_v62 `
        tests.test_quant_trading_intelligence_phase1_integration `
        -q
    if ($LASTEXITCODE -ne 0) { throw "Targeted V8 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V8 release gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }

    Write-Host "PROTECTED CORE + V8 SAFETY" -ForegroundColor Cyan
    & $Python -c "import main; from omni.agent_registry import default_agent_specs; from omni.executive_control_plane import EXECUTIVE_CONTROL_PLANE; from omni.project_completion import snapshot; from omni.unified_intent_router import route_intent; s=snapshot(); d=route_intent('open apps workspace'); p=EXECUTIVE_CONTROL_PLANE.plan('open apps workspace', include_context=False); assert len(default_agent_specs()) == 29; assert s['paper_only'] is True; assert s['live_execution'] is False; assert s['automatic_broker_order'] is False; assert d.deterministic is True; assert p['safety']['live_execution'] is False; assert p['safety']['automatic_broker_order'] is False; print('Protected Core import: PASS'); print('Permanent agent contract (29): PASS'); print('V8 deterministic intent: PASS'); print('V8 safety contract: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core or V8 safety validation failed." }

    Invoke-Git @("diff", "--check")
    $PostDirty = (& git status --porcelain) -join "`n"
    if ($PostDirty.Trim()) {
        throw "V8 validation unexpectedly modified the working tree.`n$PostDirty"
    }

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V8" -ForegroundColor Cyan
        Start-Process -FilePath (Join-Path $Root "JARVIS.bat")
        Wait-V8Runtime
    }

    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V8 UNIFIED INTELLIGENCE OS: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Branch              : $TargetBranch"
    Write-Host "Backup              : $BackupBranch"
    Write-Host "V7 verified baseline : PRESERVED"
    Write-Host "Permanent agents     : 29 PRESERVED"
    Write-Host "Apps workspace       : DETERMINISTIC ROUTING FIXED"
    Write-Host "Unified Intent Router: ENABLED"
    Write-Host "Context Fabric       : ENABLED / READ-ONLY SYNTHESIS"
    Write-Host "Executive Control    : SYSTEM PLANE / ENABLED"
    Write-Host "Master V8            : http://127.0.0.1:8797"
    Write-Host "Quant Advanced       : PRESERVED"
    Write-Host "Completion Executive : http://127.0.0.1:8799/?section=executive"
    Write-Host "Mission/Code/Memory   : PRESERVED + EXECUTIVE CONTEXT"
    Write-Host "External actions      : APPROVAL GATED"
    Write-Host "Live execution        : LOCKED"
}
catch {
    Write-Host ""
    Write-Host "V8 PATCH FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Stop-TrustedJarvisProcesses
    try {
        if ($PreviousBranch) {
            Invoke-Git @("switch", $PreviousBranch)
            Invoke-Git @("reset", "--hard", $PreviousHead)
        }
        else {
            Invoke-Git @("switch", "--detach", $PreviousHead)
        }
        Write-Host "Rolled back to previous JARVIS checkpoint: $PreviousHead" -ForegroundColor Yellow
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