# Kid mode in the browser for the jury: our server (keys stay here) + a free Cloudflare tunnel.
# Run from the repo root on the stage laptop:  powershell -ExecutionPolicy Bypass -File scripts\kid_web.ps1
# Needs once:  winget install --id Cloudflare.cloudflared
$ErrorActionPreference = "Stop"
if (-not ($env:P2_KID_WAD -or (Test-Path data\freedoom1.wad) -or (Select-String -Quiet -Path .env -Pattern "^P2_KID_WAD=.+" -ErrorAction SilentlyContinue))) {
    Write-Warning "no data\freedoom1.wad and no P2_KID_WAD: the game will not load"
}
$server = Start-Process -PassThru -NoNewWindow uv -ArgumentList "run", "uvicorn", "voice.kid_web:app", "--port", "8010"
try {
    Start-Sleep 3
    Write-Host "Local: http://localhost:8010   The public https://....trycloudflare.com link is printed below."
    cloudflared tunnel --url http://localhost:8010
} finally {
    Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
}
