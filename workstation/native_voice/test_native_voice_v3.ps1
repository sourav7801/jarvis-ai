$ErrorActionPreference = "Stop"

$VoiceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $VoiceDir "JarvisVoiceDiagnostic.cs"
$Exe = Join-Path $VoiceDir "JarvisVoiceDiagnostic.exe"

Write-Host ""
Write-Host "============================================================"
Write-Host "JARVIS NATIVE VOICE COMPILER V3"
Write-Host "============================================================"

# Load the Windows speech assembly.
Add-Type -AssemblyName System.Speech

# IMPORTANT:
# Keep the complete property expression on one logical line.
$SpeechDll = ([System.Speech.Recognition.SpeechRecognitionEngine]).Assembly.Location

Write-Host ""
Write-Host "System.Speech DLL:"
Write-Host $SpeechDll
Write-Host ""

if ([string]::IsNullOrWhiteSpace($SpeechDll)) {
    throw "System.Speech assembly path could not be resolved."
}

if (-not (Test-Path $SpeechDll)) {
    throw "System.Speech DLL does not exist: $SpeechDll"
}

Write-Host "SYSTEM.SPEECH PATH: PASS"

if (-not (Test-Path $Source)) {
    throw "Diagnostic source missing: $Source"
}

if (Test-Path $Exe) {
    Remove-Item $Exe -Force
}

$Code = Get-Content $Source -Raw

Write-Host ""
Write-Host "Compiling native voice diagnostic..."

Add-Type `
    -TypeDefinition $Code `
    -Language CSharp `
    -ReferencedAssemblies @(
        "System.dll",
        "System.Core.dll",
        $SpeechDll
    ) `
    -OutputAssembly $Exe `
    -OutputType ConsoleApplication

if (-not (Test-Path $Exe)) {
    throw "JarvisVoiceDiagnostic.exe was not created."
}

Write-Host ""
Write-Host "COMPILE: PASS"
Write-Host "EXE: $Exe"
Write-Host ""

Write-Host "============================================================"
Write-Host "STARTING MICROPHONE DIAGNOSTIC"
Write-Host "============================================================"
Write-Host ""

& $Exe
