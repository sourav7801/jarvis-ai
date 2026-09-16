param(
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "============================================================"
Write-Host " JARVIS V17 ROUTE + FYERS HEALTH PATCH INSTALLER"
Write-Host " Read-only market data / PAPER trading only"
Write-Host "============================================================"

$ExpectedBranch = "jarvis-dev/20260916-JARVIS-V17-autonomous-options-runtime"

if (Get-Command git -ErrorAction SilentlyContinue) {
    $CurrentBranch = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to read the current Git branch."
    }
    if ($CurrentBranch -ne $ExpectedBranch) {
        throw "Wrong branch: '$CurrentBranch'. Switch to '$ExpectedBranch' before installing this V17 patch."
    }
    Write-Host "Branch: $CurrentBranch"
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "JARVIS virtual environment not found at .venv. Run .\install_v17.ps1 first."
}

$RequiredFiles = @(
    "agents\fyers_live_stream.py",
    "workstation\v17_terminal_http.py",
    "workstation\quant_terminal_v2_static\v17_runtime.js",
    "tests\test_v17_route_fyers_health.py"
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path (Join-Path $Root $File))) {
        throw "Required V17 patch file is missing: $File. Run git pull on the V17 branch first."
    }
}

$StreamText = Get-Content "agents\fyers_live_stream.py" -Raw
$HttpText = Get-Content "workstation\v17_terminal_http.py" -Raw
$JsText = Get-Content "workstation\quant_terminal_v2_static\v17_runtime.js" -Raw

if ($StreamText -notmatch 'RECONNECTING' -or $StreamText -notmatch 'order_socket_enabled') {
    throw "FYERS bounded-reconnect patch markers are missing. Run git pull first."
}
if ($HttpText -notmatch '_route_metadata' -or $HttpText -notmatch 'market_data') {
    throw "V17 route/market-data status patch markers are missing. Run git pull first."
}
if ($JsText -notmatch 'v17FeedState' -or $JsText -notmatch 'execution_workspace') {
    throw "V17 route-aware UI patch markers are missing. Run git pull first."
}

Write-Host "Running Python compile checks..."
& $VenvPython -m py_compile `
    agents\fyers_live_stream.py `
    workstation\v17_terminal_http.py `
    workstation\v17_autonomous_options.py `
    start_jarvis_professional_terminal_v17.py
if ($LASTEXITCODE -ne 0) {
    throw "Python compile checks failed."
}

Write-Host "Running safety assertions..."
& $VenvPython -c "from workstation.v17_terminal_http import _route_metadata; r=_route_metadata('OPTIONS'); assert r['requested_workspace']=='OPTIONS' and r['execution_workspace']=='INTRADAY'; print('V17 OPTIONS route: PASS')"
if ($LASTEXITCODE -ne 0) { throw "V17 route assertion failed." }

& $VenvPython -c "from agents.fyers_live_stream import FyersLiveStream; s=FyersLiveStream(); st=s.status(); assert st['read_only'] and st['data_only'] and not st['order_socket_enabled'] and not st['live_order_execution']; print('FYERS read-only boundary: PASS')"
if ($LASTEXITCODE -ne 0) { throw "FYERS read-only assertion failed." }

if (-not $SkipTests) {
    Write-Host "Running focused V17 regression tests..."
    & $VenvPython -m unittest `
        tests.test_v17_route_fyers_health `
        tests.test_v17_terminal_identity
    if ($LASTEXITCODE -ne 0) {
        throw "Focused V17 tests failed."
    }
}

if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Host "Checking patch whitespace..."
    & git diff --check
    if ($LASTEXITCODE -ne 0) {
        throw "git diff --check reported a problem."
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host " JARVIS V17 ROUTE + FYERS PATCH: INSTALLED"
Write-Host "============================================================"
Write-Host "Route-aware terminal status: ENABLED"
Write-Host "FYERS bounded reconnect/freshness health: ENABLED"
Write-Host "FYERS order socket: DISABLED"
Write-Host "Live broker order execution: LOCKED"
Write-Host "Canonical execution mode: PAPER / RESEARCH"
Write-Host ""
Write-Host "Start JARVIS V17:"
Write-Host "  .\.venv\Scripts\python.exe -m scripts.jarvis_runtime_supervisor_v17"
Write-Host "or double-click JARVIS_V17.bat"
