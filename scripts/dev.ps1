param(
  [switch]$Frontend,
  [switch]$Backend
)

if (-not ($Frontend -or $Backend)) {
  $Frontend = $true
  $Backend = $true
}

if ($Frontend) {
  Start-Job -ScriptBlock {
    cd "$PSScriptRoot/../frontend"
    if (Test-Path pnpm-lock.yaml) { pnpm dev } elseif (Test-Path package-lock.json) { npm run dev } else { npm run dev }
  } | Out-Null
}

if ($Backend) {
  Start-Job -ScriptBlock {
    cd "$PSScriptRoot/../backend"
    if (Get-Command poetry -ErrorAction SilentlyContinue) {
      poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    } else {
      python -m pip install -q -r requirements.txt 2>$null
      uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
    }
  } | Out-Null
}

Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend:  http://localhost:8000"
Wait-Job * | Receive-Job


