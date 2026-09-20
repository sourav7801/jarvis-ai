$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Venv = Join-Path $Root ".venv"
$PythonExe = $null

function Resolve-CompatiblePython {
    $candidates = @(
        @{ Cmd = "py"; Args = @("-3.13") },
        @{ Cmd = "py"; Args = @("-3.12") },
        @{ Cmd = "py"; Args = @("-3.11") },
        @{ Cmd = "python"; Args = @() }
    )

    foreach ($candidate in $candidates) {
        try {
            $cmd = Get-Command $candidate.Cmd -ErrorAction Stop
            $args = @($candidate.Args) + @("-c", "import sys; print(sys.executable) if (3,11) <= sys.version_info[:2] < (3,14) else sys.exit(7)")
            $resolved = & $cmd.Source @args 2>$null
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                return ($resolved | Select-Object -First 1).Trim()
            }
        } catch {
            continue
        }
    }
    return $null
}

Write-Host ""
Write-Host "JARVIS V17 setup - preparing isolated runtime" -ForegroundColor Cyan
Write-Host "Live broker execution remains LOCKED. This installer is PAPER-only." -ForegroundColor Yellow

$PythonExe = Resolve-CompatiblePython
if (-not $PythonExe) {
    Write-Host ""
    Write-Host "Python 3.11, 3.12, or 3.13 is required." -ForegroundColor Red
    Write-Host "Install 64-bit Python and rerun JARVIS V17 Setup." -ForegroundColor Red
    exit 31
}

Write-Host "Using Python: $PythonExe"

if (-not (Test-Path (Join-Path $Venv "Scripts\python.exe"))) {
    & $PythonExe -m venv $Venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

$VenvPython = Join-Path $Venv "Scripts\python.exe"

# NautilusTrader is intentionally isolated from the main FYERS/Quant Python
# environment. V17's supervisor prefers this interpreter when present.
$NautilusVenv = Join-Path $Root ".venv-nautilus-new"
$NautilusPython = Join-Path $NautilusVenv "Scripts\python.exe"
if (-not (Test-Path $NautilusPython)) {
    Write-Host "Preparing isolated NautilusTrader environment..." -ForegroundColor Cyan
    & $PythonExe -m venv $NautilusVenv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $NautilusPython -m pip install --disable-pip-version-check --upgrade pip wheel
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
if (Test-Path (Join-Path $Root "requirements-nautilus.txt")) {
    Write-Host "Ensuring NautilusTrader dependency contract..." -ForegroundColor Cyan
    & $NautilusPython -m pip install --disable-pip-version-check -r (Join-Path $Root "requirements-nautilus.txt")
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# FYERS API v3 3.1.18 requires setuptools==68.0.0. Keep the installer
# deterministic and do not let a generic tooling upgrade replace that pin.
& $VenvPython -m pip install --disable-pip-version-check --upgrade pip wheel
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
& $VenvPython -m pip install --disable-pip-version-check "setuptools==68.0.0"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Install the local product without PEP-517 build isolation. The isolated build
# environment would otherwise download a second setuptools version and can sit
# at "Installing build dependencies..." even though the runtime tooling is
# already present in this dedicated V17 virtual environment.
& $VenvPython -m pip install --disable-pip-version-check --no-build-isolation --no-deps -e $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Bounded dependency set required by the V17 market-data, quant-terminal and
# supervisor path. Large creator/ML extras are intentionally excluded.
$RuntimeDependencies = @(
    "numpy",
    "pandas",
    "requests==2.31.0",
    "psutil",
    "fyers-apiv3==3.1.18",
    "ta",
    "openpyxl",
    "cryptography"
)
& $VenvPython -m pip install --disable-pip-version-check $RuntimeDependencies
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Assert the exact FYERS/setuptools compatibility contract after dependency
# resolution so a future package change fails installation loudly instead of
# leaving a subtly broken market-data runtime.
& $VenvPython -c "import importlib.metadata as m; s=m.version('setuptools'); f=m.version('fyers-apiv3'); print('setuptools='+s+'; fyers-apiv3='+f); raise SystemExit(0 if s=='68.0.0' and f=='3.1.18' else 42)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "Dependency compatibility verification failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "Running V17 installation preflight..." -ForegroundColor Cyan
& $VenvPython -m scripts.doctor --ci --json
if ($LASTEXITCODE -ne 0) {
    Write-Host "Doctor reported a problem. JARVIS files remain installed for diagnosis." -ForegroundColor Red
    exit $LASTEXITCODE
}

$Marker = @{
    installed_at = (Get-Date).ToUniversalTime().ToString("o")
    version = "17.0.2"
    runtime = "JARVIS_RUNTIME_SUPERVISOR_V17"
    paper_only = $true
    live_execution = $false
    automatic_broker_order = $false
    setuptools = "68.0.0"
    fyers_apiv3 = "3.1.18"
} | ConvertTo-Json
$Marker | Set-Content -Path (Join-Path $Root "V17_INSTALLATION.json") -Encoding UTF8

Write-Host ""
Write-Host "JARVIS V17 installation complete." -ForegroundColor Green
Write-Host "Use the JARVIS V17 shortcut to start the unified workstation." -ForegroundColor Green
exit 0
