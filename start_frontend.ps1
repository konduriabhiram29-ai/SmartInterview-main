# ============================================================
# start_frontend.ps1 - Run from ANYWHERE, always works
# ============================================================

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ProjectRoot "frontend"
Set-Location $FrontendDir

Write-Host ""
Write-Host "===================================" -ForegroundColor Magenta
Write-Host "  SmartInterview - Frontend Start  " -ForegroundColor Magenta
Write-Host "===================================" -ForegroundColor Magenta
Write-Host "Frontend dir: $FrontendDir" -ForegroundColor Gray
Write-Host ""

if (-not (Test-Path "$FrontendDir\package.json")) {
    Write-Host "ERROR: package.json not found in $FrontendDir" -ForegroundColor Red
    exit 1
}

Write-Host "Starting Vite frontend on http://localhost:5174" -ForegroundColor Yellow
Write-Host ""

npm run dev

