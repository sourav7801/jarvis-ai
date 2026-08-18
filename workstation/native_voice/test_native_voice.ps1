$ErrorActionPreference = "Stop"

$VoiceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $VoiceDir "JarvisVoiceDiagnostic.cs"
$Exe = Join-Path $VoiceDir "JarvisVoiceDiagnostic.exe"

Write-Host ""
Write-Host "=============================================="
Write-Host "JARVIS NATIVE VOICE COMPILER"
Write-Host "=============================================="

Add-Type -AssemblyName System.Speech

if (Test-Path $Exe) {
    Remove-Item $Exe -Force
}

$Code = Get-Content $Source -Raw

Add-Type `
    -TypeDefinition $Code `
    -Language CSharp `
    -ReferencedAssemblies @(
        "System.dll",
        "System.Core.dll",
        "System.Speech.dll"
    ) `
    -OutputAssembly $Exe `
    -OutputType ConsoleApplication

if (-not (Test-Path $Exe)) {
    throw "Native voice executable was not created."
}

Write-Host "COMPILE: PASS"
Write-Host "EXE: $Exe"
Write-Host ""
Write-Host "Starting microphone diagnostic..."
Write-Host ""

& $Exe
