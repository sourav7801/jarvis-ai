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
& $VenvPython -m pip install --disable-pip-version-check --upgrade pip setuptools wheel
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Install the local product first, then the bounded dependency set required by
# the V17 market-data, quant-terminal and supervisor path. The large creator/
# ML extras are intentionally not pulled into this trading installer.
& $VenvPython -m pip install --disable-pip-version-check --no-deps -e $Root
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$RuntimeDependencies = @(
    "numpy",
    "pandas",
    "requests==2.31.0",
    "psutil",
    "fyers-apiv3",
    "ta",
    "openpyxl",
    "cryptography"
)
& $VenvPython -m pip install --disable-pip-version-check $RuntimeDependencies
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host ""
Write-Host "Running V17 installation preflight..." -ForegroundColor Cyan
& $VenvPython -m scripts.doctor --ci --json
if ($LASTEXITCODE -ne 0) {
    Write-Host "Doctor reported a problem. JARVIS files remain installed for diagnosis." -ForegroundColor Red
    exit $LASTEXITCODE
}

$Marker = @{
    installed_at = (Get-Date).ToUniversalTime().ToString("o")
    version = "17.0"
    runtime = "JARVIS_RUNTIME_SUPERVISOR_V17"
    paper_only = $true
    live_execution = $false
    automatic_broker_order = $false
} | ConvertTo-Json
$Marker | Set-Content -Path (Join-Path $Root "V17_INSTALLATION.json") -Encoding UTF8

Write-Host ""
Write-Host "JARVIS V17 installation complete." -ForegroundColor Green
Write-Host "Use the JARVIS V17 shortcut to start the unified workstation." -ForegroundColor Green
exit 0
