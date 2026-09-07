param(
    [switch]$SkipFullRegression,
    [switch]$NoLaunch
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = "C:\Jarvis"
$TargetBranch = "jarvis-dev/v81-trading-repair"
$RemoteRef = "origin/$TargetBranch"
$VerifiedV8 = "94be6ba06dce7154254c7edc90f43ce4e46a3678"

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
    catch { return $false }
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
    catch { return $false }
}

function Wait-V81Runtime {
    $required = @(
        "http://127.0.0.1:8797/",
        "http://127.0.0.1:8797/v8_runtime.js",
        "http://127.0.0.1:8787/api/health",
        "http://127.0.0.1:8787/intelligence.html",
        "http://127.0.0.1:8787/paper_desk_runtime.js",
        "http://127.0.0.1:8787/api/paper/portfolio-controller",
        "http://127.0.0.1:8787/api/intelligence/status",
        "http://127.0.0.1:8799/",
        "http://127.0.0.1:8799/api/health",
        "http://127.0.0.1:8799/api/completion",
        "http://127.0.0.1:8799/api/executive"
    )
    $deadline = [DateTime]::UtcNow.AddSeconds(100)
    while ([DateTime]::UtcNow -lt $deadline) {
        $pending = @($required | Where-Object { -not (Test-Http200 $_) })
        $masterV8 = Test-HttpContains "http://127.0.0.1:8797/" "V8 UNIFIED INTELLIGENCE"
        $paperV81 = Test-HttpContains "http://127.0.0.1:8787/paper_desk_runtime.js" "V8.1 INDEPENDENT HORIZONS"
        if ($pending.Count -eq 0 -and $masterV8 -and $paperV81) {
            foreach ($url in $required) { Write-Host "200  $url" -ForegroundColor Green }
            Write-Host "PASS V8 Master identity marker" -ForegroundColor Green
            Write-Host "PASS V8.1 independent horizon UI marker" -ForegroundColor Green
            return
        }
        Start-Sleep -Seconds 1
    }
    foreach ($url in $required) {
        if (Test-Http200 $url) { Write-Host "200  $url" -ForegroundColor Green }
        else { Write-Host "FAIL $url" -ForegroundColor Red }
    }
    if (-not (Test-HttpContains "http://127.0.0.1:8787/paper_desk_runtime.js" "V8.1 INDEPENDENT HORIZONS")) {
        Write-Host "FAIL V8.1 independent horizon UI marker" -ForegroundColor Red
    }
    throw "JARVIS V8.1 runtime verification failed."
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
    throw "Working tree is not clean. Commit or stash unrelated work before V8.1 installation.`n$Dirty"
}

Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "JARVIS V8.1 TRADING DECISION + EXECUTION REPAIR" -ForegroundColor Cyan
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "Previous branch : $PreviousBranch"
Write-Host "Previous HEAD   : $PreviousHead"

Invoke-Git @("fetch", "origin", "--prune")
Invoke-Git @("rev-parse", "--verify", $RemoteRef)

$BackupBranch = "jarvis-backup/v81-prepatch-" + (Get-Date -Format "yyyyMMdd-HHmmss")
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

    & git merge-base --is-ancestor $VerifiedV8 HEAD
    if ($LASTEXITCODE -ne 0) {
        throw "V8.1 is not descended from verified V8 checkpoint $VerifiedV8."
    }

    $Python = Get-JarvisPython
    Write-Host "Python          : $Python"
    Write-Host "Target HEAD     : $((& git rev-parse --short HEAD).Trim())"

    $criticalFiles = @(
        "workstation\intraday_lane_group.py",
        "workstation\candidate_horizon_router.py",
        "workstation\paper_portfolio_controller.py",
        "workstation\paper_autonomy_engine.py",
        "workstation\trading_timeframe_profiles.py",
        "workstation\quant_terminal_v2.py",
        "workstation\quant_terminal_v2_static\paper_desk_runtime.js",
        "start_jarvis_native_voice.ps1",
        "tests\test_jarvis_v32_hybrid_voice.py",
        "tests\test_v81_trading_decision_execution_repair.py",
        "tests\test_v8_unified_intelligence_os.py"
    )
    foreach ($file in $criticalFiles) {
        if (-not (Test-Path (Join-Path $Root $file))) {
            throw "Critical V8.1 file is missing: $file"
        }
    }
    Write-Host "Critical V8.1 trading surfaces: PASS" -ForegroundColor Green

    & $Python -m py_compile `
        "workstation\intraday_lane_group.py" `
        "workstation\candidate_horizon_router.py" `
        "workstation\paper_portfolio_controller.py" `
        "workstation\paper_autonomy_engine.py" `
        "workstation\trading_timeframe_profiles.py" `
        "workstation\quant_terminal_v2.py"
    if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }
    Write-Host "Python compile: PASS" -ForegroundColor Green

    $Node = Get-Command node -ErrorAction SilentlyContinue
    if ($Node) {
        & $Node.Source --check "workstation\quant_terminal_v2_static\paper_desk_runtime.js"
        if ($LASTEXITCODE -ne 0) { throw "V8.1 paper desk JavaScript syntax validation failed." }
        & $Node.Source --check "workstation\quant_terminal_v2_static\intelligence.js"
        if ($LASTEXITCODE -ne 0) { throw "Quant Intelligence JavaScript regression failed." }
        Write-Host "JavaScript syntax: PASS" -ForegroundColor Green
    }
    else {
        Write-Host "JavaScript syntax: SKIPPED (Node.js unavailable)" -ForegroundColor DarkYellow
    }

    Write-Host "V8.1 CONTROL CONTRACT > independent horizons" -ForegroundColor Cyan
    $ControlContract = @'
from pathlib import Path
from workstation.candidate_horizon_router import candidate_horizon_router
from workstation.paper_portfolio_controller import CONTROL_PROFILE_TOKENS

p = Path('workstation/quant_terminal_v2_static/paper_desk_runtime.js').read_text(encoding='utf-8')
required = [
    'INTRADAY', 'SWING', 'INVESTMENT',
    'intraday_only', 'swing_only', 'investment_only',
    'stop_intraday', 'stop_swing', 'stop_investment',
    'WHY / WHY NOT TRADE', 'mandateStart${key}', 'mandateStop${key}',
    'config.startToken', 'config.stopToken', 'controlMandate'
]
missing = [item for item in required if item not in p]
assert not missing, 'missing independent-horizon markers: ' + ', '.join(missing)
assert ('DISCOVERY SCORE ' + chr(0x2260) + ' EXECUTION SCORE') in p, 'score-separation marker missing'
assert CONTROL_PROFILE_TOKENS['intraday_only'] == ('START', 'INTRADAY')
assert CONTROL_PROFILE_TOKENS['swing_only'] == ('START', 'SWING')
assert CONTROL_PROFILE_TOKENS['investment_only'] == ('START', 'INVESTMENT')
assert CONTROL_PROFILE_TOKENS['stop_intraday'] == ('STOP', 'INTRADAY')
assert CONTROL_PROFILE_TOKENS['stop_swing'] == ('STOP', 'SWING')
assert CONTROL_PROFILE_TOKENS['stop_investment'] == ('STOP', 'INVESTMENT')
assert candidate_horizon_router.live_execution is False
print('Independent horizon controls: PASS')
print('Independent start/stop token routing: PASS')
print('Discovery/execution score separation: PASS')
print('Candidate horizon router safety: PASS')
'@
    & $Python -c $ControlContract
    if ($LASTEXITCODE -ne 0) { throw "V8.1 independent horizon contract failed." }

    Write-Host "NATIVE VOICE COMPILE REGRESSION > deterministic Windows compiler invocation" -ForegroundColor Cyan
    & $Python -m unittest `
        tests.test_jarvis_v32_hybrid_voice.VoiceV32HybridTests.test_native_service_compiles `
        -q
    if ($LASTEXITCODE -ne 0) { throw "Native voice compile regression failed." }
    Write-Host "Native voice compile regression: PASS" -ForegroundColor Green

    Write-Host "TARGETED REGRESSION > V8.1 trading repair + V8 baseline" -ForegroundColor Cyan
    & $Python -m unittest `
        tests.test_v81_trading_decision_execution_repair `
        tests.test_paper_portfolio_controller `
        tests.test_paper_trading_desk `
        tests.test_quant_terminal_v2 `
        tests.test_quant_v63_full_advanced `
        tests.test_quant_v6_adaptive_integration `
        tests.test_quant_v6_chart_runtime `
        tests.test_v8_unified_intelligence_os `
        tests.test_v7_project_completion `
        tests.test_agent_registry `
        tests.test_brain `
        tests.test_meta_agents `
        tests.test_universal_learning_v5 `
        tests.test_jarvis_runtime_supervisor `
        tests.test_runtime_supervisor_v62 `
        tests.test_jarvis_v32_hybrid_voice `
        -q
    if ($LASTEXITCODE -ne 0) { throw "Targeted V8.1 regression failed." }
    Write-Host "Targeted regression: PASS" -ForegroundColor Green

    if (-not $SkipFullRegression) {
        Write-Host "FULL JARVIS REGRESSION > V8.1 release gate" -ForegroundColor Cyan
        & $Python -m unittest discover -s tests -q
        if ($LASTEXITCODE -ne 0) { throw "Full JARVIS regression failed." }
        Write-Host "Full regression: PASS" -ForegroundColor Green
    }

    Write-Host "PROTECTED CORE + V8.1 SAFETY" -ForegroundColor Cyan
    & $Python -c "import main; from omni.agent_registry import default_agent_specs; from workstation.paper_portfolio_controller import paper_portfolio_controller; from workstation.candidate_horizon_router import candidate_horizon_router; s=paper_portfolio_controller.status(); assert len(default_agent_specs()) == 29; assert s['paper_only'] is True; assert s['live_execution'] is False; assert candidate_horizon_router.live_execution is False; assert set(s['mandates']) == {'INTRADAY','SWING','INVESTMENT'}; print('Protected Core import: PASS'); print('Permanent agent contract (29): PASS'); print('Three horizon contract: PASS'); print('Paper-only safety: PASS')"
    if ($LASTEXITCODE -ne 0) { throw "Protected Core or V8.1 safety validation failed." }

    Invoke-Git @("diff", "--check")
    $PostDirty = (& git status --porcelain) -join "`n"
    if ($PostDirty.Trim()) {
        throw "V8.1 validation unexpectedly modified the working tree.`n$PostDirty"
    }

    if (-not $NoLaunch) {
        Write-Host "LAUNCH > JARVIS V8.1" -ForegroundColor Cyan
        Start-Process -FilePath (Join-Path $Root "JARVIS.bat")
        Wait-V81Runtime
    }

    Write-Host ""
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "JARVIS V8.1 TRADING DECISION + EXECUTION REPAIR: SUCCESS" -ForegroundColor Green
    Write-Host "================================================================================" -ForegroundColor Green
    Write-Host "Branch              : $TargetBranch"
    Write-Host "Backup              : $BackupBranch"
    Write-Host "V8 verified baseline : PRESERVED"
    Write-Host "Intraday             : SEPARATE START/STOP · 5m + 15m + MTF PAPER LANES"
    Write-Host "Swing                : SEPARATE START/STOP · 1h + 4h + 1d"
    Write-Host "Investment           : SEPARATE START/STOP · 1d+ LONG ONLY"
    Write-Host "Candidate routing    : INTRADAY + SWING + INVESTMENT"
    Write-Host "Score contract       : DISCOVERY != EXECUTION"
    Write-Host "Why-not-trade board  : ENABLED"
    Write-Host "Native voice compile : DETERMINISTIC ARGUMENT VECTOR"
    Write-Host "Real execution       : LOCKED"
}
catch {
    Write-Host ""
    Write-Host "V8.1 PATCH FAILED: $($_.Exception.Message)" -ForegroundColor Red
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
