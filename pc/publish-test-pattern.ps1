# Publishes a synthetic 1280x720@10 test pattern to the local RTSP server,
# standing in for a camera until the Kinect bridge (or the Pi) is live.
# Run while start-mediamtx.ps1 is running; Ctrl-C to stop.
$ffmpeg = Get-ChildItem "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg*" -Recurse -Filter ffmpeg.exe -ErrorAction SilentlyContinue |
  Select-Object -First 1 -ExpandProperty FullName
if (-not $ffmpeg) { $ffmpeg = "ffmpeg" }
& $ffmpeg -hide_banner -re `
  -f lavfi -i "testsrc2=size=1280x720:rate=10" `
  -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -b:v 1M -g 20 `
  -f rtsp -rtsp_transport tcp rtsp://127.0.0.1:8554/cam
