# Publishes the Kinect for Xbox One (v2) colour camera to the local RTSP server as /cam.
# 1920x1080 - about seven times the pixels of the v1 (2.07M vs 0.31M).
#
# STATUS: the v2 RTSP publish path is NOT yet reliable - it still collapses to
# ~1-2 fps (see the note below and docs/CAMERAS.md). publish-kinect.ps1 (v1) is
# the reliable default publisher; use this script for stills/experiments.
#
# Prereqs: Kinect SDK 2.0, the Kinect Adapter for Windows (power brick + USB 3.0
# converter), start-mediamtx.ps1 running, and NO other publisher on /cam
# (stop publish-kinect.ps1 or the test pattern first - one publisher at a time).
# NOTE: keep this file pure ASCII - PowerShell 5.1 misparses UTF-8 punctuation.
#
#   .\publish-kinect-v2.ps1                 # 15 fps (default)
#   .\publish-kinect-v2.ps1 -Fps 30         # full sensor rate
#
# The bridge emits native YUY2 (2 bytes/pixel), not BGRA - see KinectV2Pipe.cs for
# why. 1080p15 YUY2 is ~62 MB/s through the pipe.
param(
  [int]$Fps = 15,
  [int]$Bitrate = 4
)
$bridge = "$PSScriptRoot\kinect-bridge\v2\KinectV2Pipe.exe"
$ffmpeg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue |
  Select-Object -First 1 -ExpandProperty FullName
if (-not $ffmpeg) { $ffmpeg = "ffmpeg" }
if (-not (Test-Path $bridge)) { Write-Error "KinectV2Pipe.exe not built - run kinect-bridge\build.ps1"; exit 1 }

# -threads 8 is a mitigation attempt, not a confirmed fix: left to itself x264
# spawns one thread per core (34 here), which starves ffmpeg's pipe-reader thread.
# Capping it helps in theory, but the full path still measures ~1-2 fps and the
# root cause is not yet resolved - the encoder alone benchmarks at 36x realtime
# and the pipe alone sustains 30fps, so the bottleneck is elsewhere in the RTSP
# publish path (see docs/CAMERAS.md). sliced-threads=0 avoids a known
# decoder-artifact source; keyint = 1 second so any corruption clears quickly.
# Binary pipe must go through cmd.exe.
$kf = $Fps
cmd /c "`"$bridge`" --fps $Fps | `"$ffmpeg`" -hide_banner -f rawvideo -pix_fmt yuyv422 -video_size 1920x1080 -framerate $Fps -i - -c:v libx264 -preset veryfast -threads 8 -pix_fmt yuv420p -b:v $($Bitrate)M -bf 0 -x264-params sliced-threads=0:keyint=$kf`:min-keyint=$kf`:scenecut=0 -f rtsp -rtsp_transport tcp rtsp://127.0.0.1:8554/cam"
