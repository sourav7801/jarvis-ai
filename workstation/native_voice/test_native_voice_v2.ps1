$ErrorActionPreference = "Stop"

$VoiceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $VoiceDir "JarvisVoiceDiagnostic.cs"
$Exe = Join-Path $VoiceDir "JarvisVoiceDiagnostic.exe"

Write-Host ""
Write-Host "============================================================"
Write-Host "JARVIS NATIVE VOICE COMPILER V2"
Write-Host "============================================================"

# ------------------------------------------------------------
# Load System.Speech normally first.
# ------------------------------------------------------------

Add-Type -AssemblyName System.Speech

# ------------------------------------------------------------
# IMPORTANT FIX:
# Ask the loaded .NET type where System.Speech.dll actually is.
# ------------------------------------------------------------

$SpeechDll = `
    [System.Speech.Recognition.SpeechRecognitionEngine] `
    .Assembly `
    .Location

Write-Host "System.Speech DLL:"
Write-Host $SpeechDll
Write-Host ""

if (
    [string]::IsNullOrWhiteSpace($SpeechDll)
) {
    throw "System.Speech assembly location could not be resolved."
}

if (
    -not (Test-Path $SpeechDll)
) {
    throw "Resolved System.Speech DLL does not exist: $SpeechDll"
}

Write-Host "SYSTEM.SPEECH PATH: PASS"

if (
    Test-Path $Exe
) {
    Remove-Item `
        $Exe `
        -Force
}

$Code = Get-Content `
    $Source `
    -Raw

Write-Host "Compiling native voice host..."

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

if (
    -not (Test-Path $Exe)
) {
    throw "JarvisVoiceDiagnostic.exe was not created."
}

Write-Host ""
Write-Host "COMPILE: PASS"
Write-Host "EXE: $Exe"
Write-Host ""

& $Exe
