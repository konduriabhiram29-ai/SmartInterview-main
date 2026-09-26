# start_backend.ps1 - Always run from project root, auto-loads .env

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "SmartInterview Backend Starting..." -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

# Load .env file into environment
$EnvFile = Join-Path $ProjectRoot ".env"
if (Test-Path $EnvFile) {
    foreach ($line in Get-Content $EnvFile) {
        $line = $line.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $parts = $line.Split('=', 2)
            $key   = $parts[0].Trim()
            $val   = $parts[1].Trim()
            [System.Environment]::SetEnvironmentVariable($key, $val, 'Process')
            Write-Host "  Loaded: $key" -ForegroundColor Green
        }
    }
}

Write-Host ""
Write-Host "Backend: http://localhost:8000" -ForegroundColor Yellow
Write-Host "API docs: http://localhost:8000/docs" -ForegroundColor Gray
Write-Host ""

Set-Location "$ProjectRoot\backend"
$PythonExe = Join-Path $ProjectRoot "venv\Scripts\python.exe"
if (Test-Path $PythonExe) {
    & $PythonExe -m uvicorn app.main:app --port 8000
} else {
    python -m uvicorn app.main:app --port 8000
}


