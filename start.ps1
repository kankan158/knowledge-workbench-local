param(
  [switch]$NoBrowser
)

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition

Write-Host "Starting backend..."
$backendCmd = "cd '$root\backend'; if (Test-Path '.venv\Scripts\Activate.ps1') { . '.venv\Scripts\Activate.ps1' }; uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"
Start-Process -FilePath powershell -ArgumentList "-NoExit","-Command","$backendCmd" -WindowStyle Normal

Write-Host "Starting frontend..."
$frontendCmd = "cd '$root\frontend'; npm run dev -- --host 0.0.0.0 --port 4173 --strictPort"
Start-Process -FilePath powershell -ArgumentList "-NoExit","-Command","$frontendCmd" -WindowStyle Normal

if (-not $NoBrowser) {
  Start-Process "http://localhost:4173/"
}

Write-Host "Started backend and frontend."
exit 0
