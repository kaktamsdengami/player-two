# PLAYER TWO jury site: build, start the server and open a public Cloudflare tunnel (Windows laptop).
#   powershell -ExecutionPolicy Bypass -File scripts\jury_up.ps1
# Needs: .venv (uv sync), node (web/), cloudflared (winget install Cloudflare.cloudflared), .env with HAI_API_KEY.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Test-Path ".venv")) { uv sync }
if (-not (Test-Path "data\freedoom1.wad")) { Write-Host "data\freedoom1.wad missing: download Freedoom 0.13 (freedoom1.wad) into data\ first"; exit 1 }
Push-Location web; npm install --silent; npm run build | Out-Null; Pop-Location
.\.venv\bin\python -c "import playwright" 2>$null; if ($LASTEXITCODE -ne 0) { .\.venv\Scripts\pip install playwright; .\.venv\Scripts\playwright install chromium }
$env:P2_LIVE_BROADCAST = "1"
$server = Start-Process -PassThru -NoNewWindow .\.venv\Scripts\python -ArgumentList "-m","uvicorn","app.main:create_app","--factory","--host","0.0.0.0","--port","8000"
Start-Sleep -Seconds 3
$log = Join-Path $env:TEMP "p2-tunnel.log"
$tunnel = Start-Process -PassThru -NoNewWindow cloudflared -ArgumentList "tunnel","--url","http://127.0.0.1:8000","--no-autoupdate" -RedirectStandardError $log
$url = $null
for ($i = 0; $i -lt 40 -and -not $url; $i++) { Start-Sleep -Seconds 1; $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1; if ($m) { $url = $m.Matches[0].Value } }
if (-not $url) { Write-Host "no tunnel URL yet, see $log"; $url = "http://127.0.0.1:8000" }
Write-Host ""
Write-Host "PLAYER TWO jury links (share these):"
foreach ($p in "/", "/arcade/", "/live/", "/lab/", "/story/", "/kid/", "/dashboard/") { Write-Host ("  {0}{1}" -f $url, $p) }
Write-Host ""
Write-Host "server pid $($server.Id), tunnel pid $($tunnel.Id). Ctrl+C here does not stop them: Stop-Process -Id $($server.Id),$($tunnel.Id)"
