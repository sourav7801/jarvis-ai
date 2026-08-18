param(
    [ValidateSet("diagnose", "repair", "improve")]
    [string]$Mode = "diagnose"
)

$Python = "C:\Jarvis\.venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Host "JARVIS Python not found: $Python" -ForegroundColor Red
    exit 1
}

$Code = @'
from agents.reliability_agent import reliability
import sys
mode = sys.argv[1]
request = {
    "diagnose": "Jarvis diagnose yourself",
    "repair": "Jarvis repair yourself",
    "improve": "Jarvis improve yourself",
}[mode]
result = reliability(request)
print(result.get("message", result))
'@

$Code | & $Python - $Mode
exit $LASTEXITCODE
