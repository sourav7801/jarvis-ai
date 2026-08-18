param(
    [Parameter(Position=0)]
    [string]$Command = "status",

    [Parameter(Position=1)]
    [string]$Patch = "",

    [string]$Message = "",

    [switch]$Full,

    [switch]$Push
)

$Python = "C:\Jarvis\.venv\Scripts\python.exe"
$Agent  = "C:\Jarvis\tools\jarvis_dev_agent.py"

if (-not (Test-Path $Python)) {
    Write-Host "JARVIS Python not found: $Python" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path $Agent)) {
    Write-Host "Dev Agent not found: $Agent" -ForegroundColor Red
    exit 1
}

if ($Command -eq "status") {
    & $Python $Agent status
    exit $LASTEXITCODE
}

if ($Command -eq "verify") {

    $ArgsList = @(
        $Agent,
        "verify"
    )

    if ($Full) {
        $ArgsList += "--full"
    }

    & $Python @ArgsList

    exit $LASTEXITCODE
}

if ($Command -eq "apply") {

    if (-not $Patch) {
        Write-Host "Patch path required." -ForegroundColor Red
        exit 1
    }

    $ArgsList = @(
        $Agent,
        "apply",
        $Patch
    )

    if ($Message) {
        $ArgsList += "--message"
        $ArgsList += $Message
    }

    if ($Full) {
        $ArgsList += "--full"
    }

    if ($Push) {
        $ArgsList += "--push"
    }

    & $Python @ArgsList

    exit $LASTEXITCODE
}

Write-Host "Unknown command: $Command" -ForegroundColor Red
exit 2
