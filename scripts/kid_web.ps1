# Kid mode in the browser for the jury: our server (keys stay here) + a free Cloudflare tunnel.
# Run from the repo root on the stage laptop:  powershell -ExecutionPolicy Bypass -File scripts\kid_web.ps1
# Needs once:  winget install --id Cloudflare.cloudflared
$ErrorActionPreference = "Stop"
if (-not (Test-Path data\freedoom1.wad)) { throw "data\freedoom1.wad is missing" }
$server = Start-Process -PassThru -NoNewWindow uv -ArgumentList "run", "uvicorn", "voice.kid_web:app", "--port", "8010"
try {
    Start-Sleep 3
    Write-Host "Local: http://localhost:8010   The public https://....trycloudflare.com link is printed below."
    cloudflared tunnel --url http://localhost:8010
} finally {
    Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
}
