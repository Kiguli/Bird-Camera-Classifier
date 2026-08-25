# Option 1 launcher: open a Microsoft-SIGNED Kinect v2 viewer from the SDK.
# Works on a WDAC/Device-Guard-locked machine because these binaries are signed
# by Microsoft - unlike our own bridge, which the policy blocks. View/record only;
# for detection use Option 2 (see docs/INSTALL-OPTIONS.md).
# NOTE: keep this file pure ASCII - PowerShell 5.1 misparses UTF-8 punctuation.
#
#   .\view-kinect.ps1            # ColorBasics: quick live 1080p colour window
#   .\view-kinect.ps1 -Studio    # Kinect Studio: monitor colour/depth/IR/body, record
param(
  [switch]$Studio
)
$sdk = "$env:ProgramFiles\Microsoft SDKs\Kinect\v2.0_1409"
if ($Studio) {
  $exe = "$sdk\Tools\KinectStudio\KStudio.exe"
} else {
  $exe = "$sdk\bin\ColorBasics-D2D.exe"
}
if (-not (Test-Path $exe)) {
  Write-Error "Not found: $exe`nInstall Kinect for Windows SDK 2.0 - see docs/TRANSFER.md"
  exit 1
}
Write-Host "Launching $(Split-Path $exe -Leaf) (Microsoft-signed)..."
Start-Process $exe
