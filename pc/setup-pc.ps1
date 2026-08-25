# Bootstraps the Windows "lab PC" side of the Office Tree Field Station.
# Safe to re-run: every step is idempotent.
#
#   1. Installs ffmpeg and Docker Desktop via winget
#   2. Downloads the pinned MediaMTX build (gitignored, so a fresh clone lacks it)
#   3. Rebuilds the Kinect bridges if a Kinect SDK is present
#
# Kinect SDKs are NOT installable via winget and must be done by hand first -
# see docs/TRANSFER.md. This script still succeeds without them; it just skips
# the bridge build.
#
# NOTE: keep this file pure ASCII - PowerShell 5.1 misparses UTF-8 punctuation.
$ErrorActionPreference = "Stop"

Write-Host "== 1/3  Package installs =="
$winget = Get-Command winget -ErrorAction SilentlyContinue
if (-not $winget) {
  $candidate = "$env:LOCALAPPDATA\Microsoft\WindowsApps\winget.exe"
  if (Test-Path $candidate) { $winget = $candidate } else {
    Write-Warning "winget not found. Install ffmpeg and Docker Desktop manually, then re-run."
  }
}
if ($winget) {
  # winget exits non-zero when a package is already current. Native exit codes do
  # not trip $ErrorActionPreference, so re-runs stay safe.
  & $winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  & $winget install --id Docker.DockerDesktop -e --accept-source-agreements --accept-package-agreements
  & $winget install --id VideoLAN.VLC -e --accept-source-agreements --accept-package-agreements
}

Write-Host "== 2/3  MediaMTX =="
# Pinned to the version this project was built and tested against. Do not pin
# lower: mediamtx-win.yml uses `rtspTransports:`, which replaced the older
# `protocols:` key, and MediaMTX rejects unknown config keys outright.
$mtxVersion = "v1.20.1"
$dest = "$PSScriptRoot\mediamtx"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
if (Test-Path "$dest\mediamtx.exe") {
  Write-Host "  mediamtx.exe already present - skipping download."
} else {
  $url = "https://github.com/bluenviron/mediamtx/releases/download/$mtxVersion/mediamtx_${mtxVersion}_windows_amd64.zip"
  $zip = Join-Path $env:TEMP "mediamtx-$mtxVersion.zip"
  Write-Host "  downloading $mtxVersion"
  Invoke-WebRequest -Uri $url -OutFile $zip
  Expand-Archive $zip -DestinationPath $dest -Force
  Remove-Item $zip -Force
  Write-Host "  installed to $dest"
}

Write-Host "== 3/3  Kinect bridges =="
# Bridge binaries are gitignored, so a fresh clone has none. Build whichever
# SDK is available; a missing SDK is a warning, not a failure.
try {
  & "$PSScriptRoot\kinect-bridge\build.ps1"
} catch {
  Write-Warning "Kinect bridge not built: $_"
  Write-Host "  Install Kinect for Windows SDK 1.8 (v1 sensor) and/or 2.0 (v2 sensor),"
  Write-Host "  then re-run this script. See docs/TRANSFER.md."
}

Write-Host ""
Write-Host "Done. Next:"
Write-Host "  1. .\start-mediamtx.ps1        (leave running - allow it through the firewall)"
Write-Host "  2. .\publish-kinect.ps1        (or publish-kinect-v2.ps1 / publish-test-pattern.ps1)"
Write-Host "  3. docker compose up -d        (from this pc\ directory)"
Write-Host "  4. open http://localhost:5000"
