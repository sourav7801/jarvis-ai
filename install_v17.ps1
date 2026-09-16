param(
    [switch]$SkipFullDependencies
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

Write-Host "============================================================"
Write-Host " JARVIS V17 INSTALLER"
Write-Host " Autonomous Options Runtime - PAPER ONLY"
Write-Host "============================================================"

function Resolve-Python {
    try {
        & py -3.13 -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) { return @("py", "-3.13") }
    } catch {}

    try {
        & py -3.12 -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -eq 0) { return @("py", "-3.12") }
    } catch {}

    try {
        & python -c "import sys; assert (3,11) <= sys.version_info[:2] < (3,14)" *> $null
        if ($LASTEXITCODE -eq 0) { return @("python") }
    } catch {}

    throw "Python 3.11, 3.12 or 3.13 is required. Python 3.13 is recommended."
}

if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    $Python = Resolve-Python
    Write-Host "Creating C:\Jarvis compatible virtual environment..."
    if ($Python.Count -eq 2) {
        & $Python[0] $Python[1] -m venv .venv
    } else {
        & $Python[0] -m venv .venv
    }
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    throw "Virtual environment creation failed."
}

Write-Host "Using: $VenvPython"
& $VenvPython -c "import sys; print('Python', sys.version)"
& $VenvPython -m pip install --upgrade pip setuptools wheel

if ($SkipFullDependencies) {
    Write-Host "Installing JARVIS V17 package only..."
    & $VenvPython -m pip install -e .
} else {
    Write-Host "Installing JARVIS V17 with full optional runtime dependencies..."
    & $VenvPython -m pip install -e ".[full]"
}

Write-Host "Running V17 import/compile checks..."
& $VenvPython -m py_compile start_jarvis_professional_terminal_v17.py workstation\v17_autonomous_options.py
& $VenvPython -c "from workstation.v17_autonomous_options import option_execution_capability; assert option_execution_capability('NIFTY')['auto_paper'] is True; assert option_execution_capability('CRYPTO_OPTIONS')['auto_paper'] is False; print('V17 autonomy capability check: PASS')"

Write-Host ""
Write-Host "============================================================"
Write-Host " JARVIS V17 INSTALL COMPLETE"
Write-Host "============================================================"
Write-Host "Verified autonomous PAPER options: NIFTY / BANKNIFTY / SENSEX"
Write-Host "Manual strike selection is not required for qualified autonomous plans."
Write-Host "MCX/crypto can be scanned where provider data exists, but option execution"
Write-Host "stays blocked until exact option-contract providers are verified."
Write-Host "Live broker execution: LOCKED"
Write-Host ""
Write-Host "Start with:"
Write-Host "  .\.venv\Scripts\python.exe .\start_jarvis_professional_terminal_v17.py"
Write-Host "or double-click JARVIS_V17.bat"
