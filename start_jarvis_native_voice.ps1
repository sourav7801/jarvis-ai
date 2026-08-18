param(
    [switch]$Foreground
)

$ErrorActionPreference = "Stop"

$Root = "C:\Jarvis"
$Source = Join-Path $Root "workstation\native_voice\JarvisVoiceService.cs"
$Exe = Join-Path $Root "workstation\native_voice\JarvisVoiceService.exe"

if (-not (Test-Path $Source)) {
    Write-Host "Native voice source not found: $Source" -ForegroundColor Red
    exit 2
}

Add-Type -AssemblyName System.Speech

$SpeechDll = (
    [System.Speech.Recognition.SpeechRecognitionEngine]
).Assembly.Location

$CscCandidates = @(
    "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe",
    "$env:WINDIR\Microsoft.NET\Framework\v4.0.30319\csc.exe"
)

$Csc = $CscCandidates |
    Where-Object { Test-Path $_ } |
    Select-Object -First 1

if (-not $Csc) {
    Write-Host "C# compiler not found." -ForegroundColor Red
    exit 3
}

$NeedsBuild =
    (-not (Test-Path $Exe)) -or
    ((Get-Item $Source).LastWriteTimeUtc -gt (Get-Item $Exe).LastWriteTimeUtc)

if ($NeedsBuild) {

    & $Csc `
        /nologo `
        /target:exe `
        /optimize+ `
        "/out:$Exe" `
        "/reference:$SpeechDll" `
        $Source

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Native voice compile failed." -ForegroundColor Red
        exit $LASTEXITCODE
    }

    Write-Host "Native voice compile: PASS" -ForegroundColor Green
}

$Existing = Get-Process `
    -Name "JarvisVoiceService" `
    -ErrorAction SilentlyContinue |
    Select-Object -First 1

if ($Existing) {
    Write-Host "Native voice already running. PID=$($Existing.Id)"
    exit 0
}

if ($Foreground) {
    & $Exe
    exit $LASTEXITCODE
}

Start-Process `
    -FilePath $Exe `
    -WorkingDirectory (Split-Path $Exe) `
    -WindowStyle Hidden

Start-Sleep -Milliseconds 700

try {
    $Health = Invoke-RestMethod `
        -Uri "http://127.0.0.1:8798/health" `
        -Method Get `
        -TimeoutSec 2

    if ($Health.success) {
        Write-Host "Native voice service: READY" -ForegroundColor Green
        exit 0
    }
}
catch {
    Write-Host "Native voice health check failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 4
}

Write-Host "Native voice service did not report ready." -ForegroundColor Red
exit 5
