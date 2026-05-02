# JOBFUL // run_all.ps1
# ============================================================
# STEP 1 (manual): Run database/schema/setup.sql in Supabase
#         dashboard SQL editor BEFORE running this script.
#         https://supabase.com/dashboard/project/ytunhsgecrmkaurhcmwb
# ============================================================
# STEP 2: uv sync  (runs automatically below)
# STEP 3: uvicorn main:app --reload
# STEP 4: npm run dev
# STEP 5: Register -> verify -> onboarding -> upload CV -> tags -> dashboard
# ============================================================

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Write-Step { param([string]$Msg) Write-Host "`n[ >> ] $Msg" -ForegroundColor Cyan }
function Write-Ok   { param([string]$Msg) Write-Host "[ OK ] $Msg" -ForegroundColor Green }
function Write-Warn { param([string]$Msg) Write-Host "[ !! ] $Msg" -ForegroundColor Yellow }

# ── kill leftovers ──────────────────────────────────────────
Write-Step "Killing leftover node/python processes"
$ErrorActionPreference = "SilentlyContinue"
Get-Process -Name "node"   | Stop-Process -Force
Get-Process -Name "python" | Stop-Process -Force
$ErrorActionPreference = "Stop"
Start-Sleep -Seconds 1

# ── uv sync ─────────────────────────────────────────────────
Write-Step "uv sync (backend deps)"
Push-Location "$Root\backend"
uv sync
if ($LASTEXITCODE -ne 0) { Write-Host "uv sync failed. Abort." -ForegroundColor Red; exit 1 }
Pop-Location
Write-Ok "Backend deps synced"

# ── start backend ────────────────────────────────────────────
Write-Step "Starting backend  -> http://127.0.0.1:8000"
$backend = Start-Process -PassThru -NoNewWindow -FilePath "cmd.exe" `
    -ArgumentList "/c uv run uvicorn main:app --reload --reload-dir api --reload-dir core --reload-dir db --reload-dir services --reload-dir utils --host 0.0.0.0 --port 8000" `
    -WorkingDirectory "$Root\backend"

# give uvicorn a moment to bind
Start-Sleep -Seconds 3

# ── start frontend ───────────────────────────────────────────
Write-Step "Starting frontend -> http://localhost:3000"
$frontend = Start-Process -PassThru -NoNewWindow -FilePath "cmd.exe" `
    -ArgumentList "/c npm run dev" `
    -WorkingDirectory "$Root\frontend"

# ── ready ────────────────────────────────────────────────────
Write-Host ""
Write-Host "==========================================" -ForegroundColor DarkGray
Write-Host "  JOBFUL // SYSTEM ONLINE" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor DarkGray
Write-Host "  Backend:   http://127.0.0.1:8000"
Write-Host "  Frontend:  http://localhost:3000"
Write-Host "  API docs:  http://127.0.0.1:8000/docs"
Write-Host "------------------------------------------" -ForegroundColor DarkGray
Write-Warn "STEP 1 (if not done): run database/schema/setup.sql in Supabase SQL editor"
Write-Host "------------------------------------------" -ForegroundColor DarkGray
Write-Host "  Flow: register -> verify -> onboarding"
Write-Host "        -> upload CV -> pick tags -> dashboard"
Write-Host "==========================================" -ForegroundColor DarkGray
Write-Host "  Ctrl+C to stop both servers"
Write-Host ""

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Write-Host "`nShutting down..." -ForegroundColor Yellow
    Stop-Process -Id $backend.Id  -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
    $ErrorActionPreference = "SilentlyContinue"
    Get-Process -Name "node"   | Stop-Process -Force
    Get-Process -Name "python" | Stop-Process -Force
    Write-Host "Done." -ForegroundColor Green
}
