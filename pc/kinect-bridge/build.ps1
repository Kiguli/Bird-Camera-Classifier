# Builds the Kinect capture bridges from source.
# Builds whichever bridge has its SDK installed; skips the other with a note.
#   v1 (model 1517)   needs Kinect for Windows SDK 1.8
#   v2 (Xbox One)     needs Kinect for Windows SDK 2.0
# Both SDKs can be installed side by side. See docs/TRANSFER.md for install links.
#
# Usage:  .\build.ps1
$ErrorActionPreference = "Stop"

$csc = "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
if (-not (Test-Path $csc)) { throw "C# compiler not found at $csc (.NET Framework 4.x is required)" }

function Find-KinectDll([string]$versionGlob) {
  Get-ChildItem "$env:ProgramFiles\Microsoft SDKs\Kinect\$versionGlob" -Recurse -Filter "Microsoft.Kinect.dll" -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty FullName
}

$built = 0

# --- Kinect v1 (SDK 1.8) -----------------------------------------------------
$v1 = Find-KinectDll "v1.8"
if ($v1) {
  Write-Host "Building KinectPipe (v1) against $v1"
  & $csc /nologo /platform:x86 /out:"$PSScriptRoot\KinectPipe.exe" /r:"$v1" "$PSScriptRoot\KinectPipe.cs"
  if ($LASTEXITCODE -ne 0) { throw "KinectPipe build failed" }
  Copy-Item $v1 "$PSScriptRoot\Microsoft.Kinect.dll" -Force
  Write-Host "  -> KinectPipe.exe"
  $built++
} else {
  Write-Host "Kinect SDK 1.8 not found - skipping v1 bridge."
}

# --- Kinect v2 (SDK 2.0) -----------------------------------------------------
# The v2 assembly is x64-only and shares the filename Microsoft.Kinect.dll with
# the v1 one, so it is kept in its own subdirectory alongside its executable.
$v2 = Find-KinectDll "v2.0*"
if ($v2) {
  Write-Host "Building KinectV2Pipe (v2) against $v2"
  $outDir = "$PSScriptRoot\v2"
  New-Item -ItemType Directory -Force $outDir | Out-Null
  & $csc /nologo /platform:x64 /out:"$outDir\KinectV2Pipe.exe" /r:"$v2" "$PSScriptRoot\KinectV2Pipe.cs"
  if ($LASTEXITCODE -ne 0) { throw "KinectV2Pipe build failed" }
  Copy-Item $v2 "$outDir\Microsoft.Kinect.dll" -Force
  Write-Host "  -> v2\KinectV2Pipe.exe"
  $built++
} else {
  Write-Host "Kinect SDK 2.0 not found - skipping v2 bridge."
}

if ($built -eq 0) { throw "No Kinect SDK found. Install SDK 1.8 and/or 2.0 - see docs/TRANSFER.md" }
Write-Host "Built $built bridge(s)."
