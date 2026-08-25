# Publishes the Kinect v1's RGB camera to the local RTSP server as /cam.
# Prereqs: Kinect SDK 1.8 installed, sensor powered, start-mediamtx.ps1 running,
# and no other publisher on /cam (one publisher at a time).
# NOTE: keep this file pure ASCII - PowerShell 5.1 misparses UTF-8 punctuation.
#
# Camera tuning is passed straight to KinectPipe.exe, e.g.:
#   .\publish-kinect.ps1 -KinectArgs "--exposure 12 --gain 1 --wb 4700"
#   .\publish-kinect.ps1 -KinectArgs "--auto --brightness 0.12"
param(
  [string]$KinectArgs = "--exposure 20 --gain 1.0 --wb 4700"
)
$bridge = "$PSScriptRoot\kinect-bridge\KinectPipe.exe"
$ffmpeg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue |
  Select-Object -First 1 -ExpandProperty FullName
if (-not $ffmpeg) { $ffmpeg = "ffmpeg" }
if (-not (Test-Path $bridge)) { Write-Error "KinectPipe.exe not built - see kinect-bridge"; exit 1 }

# Binary stdout->stdin pipe must go through cmd.exe; PowerShell pipes mangle raw bytes.
# sliced-threads=0: x264's sliced threading (enabled by -tune zerolatency) is a
# known source of decoder artifacts. keyint=30 gives a keyframe every second, so
# any corruption that does occur clears in ~1s instead of persisting.
cmd /c "`"$bridge`" $KinectArgs | `"$ffmpeg`" -hide_banner -f rawvideo -pix_fmt bgra -video_size 640x480 -framerate 30 -i - -c:v libx264 -preset veryfast -pix_fmt yuv420p -b:v 2M -bf 0 -x264-params sliced-threads=0:keyint=30:min-keyint=30:scenecut=0 -f rtsp -rtsp_transport tcp rtsp://127.0.0.1:8554/cam"
