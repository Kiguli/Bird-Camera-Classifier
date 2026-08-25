#!/usr/bin/env bash
# Publishes a synthetic test stream so the RTSP path Pi -> PC can be proven
# before the camera arrives (the plan's week-2 network gate).
#
# On the Pi:  bash ~/pi/test-pattern.sh        (leave it running, Ctrl-C to stop)
# On the PC:  open rtsp://birdpi.local:8554/test in VLC (RTP-over-RTSP: TCP)
set -euo pipefail

exec ffmpeg -hide_banner -re \
  -f lavfi -i "testsrc2=size=640x360:rate=10" \
  -c:v libx264 -preset ultrafast -tune zerolatency -pix_fmt yuv420p -b:v 500k -g 20 \
  -f rtsp -rtsp_transport tcp rtsp://127.0.0.1:8554/test
