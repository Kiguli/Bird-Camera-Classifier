#!/usr/bin/env bash
# One-shot provisioning for the Office Tree Field Station capture node.
# Target: Raspberry Pi 2, Raspberry Pi OS Bookworm Lite (32-bit). Safe to re-run.
#
# From the PC:  scp -r pi <user>@birdpi.local:~/
# On the Pi:    bash ~/pi/setup.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "==> Updating package lists"
sudo apt-get update

echo "==> Installing packages (camera apps, ffmpeg for the no-camera test stream)"
sudo apt-get install -y --no-install-recommends rpicam-apps-lite ffmpeg curl ca-certificates

echo "==> Detecting architecture"
ARCH="$(dpkg --print-architecture)"
case "$ARCH" in
  armhf) MTX_ARCH="linux_armv7" ;;   # Pi 2 / 32-bit OS
  arm64) MTX_ARCH="linux_arm64" ;;
  *) echo "Unexpected architecture: $ARCH" >&2; exit 1 ;;
esac

echo "==> Fetching latest MediaMTX release for ${MTX_ARCH}"
URL="$(curl -fsSL https://api.github.com/repos/bluenviron/mediamtx/releases/latest \
  | grep -o "https://[^\"]*${MTX_ARCH}\.tar\.gz" | head -n1)"
if [ -z "$URL" ]; then
  echo "Could not find a MediaMTX release asset for ${MTX_ARCH}" >&2
  exit 1
fi
echo "    $URL"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
curl -fsSL "$URL" -o "$TMP/mediamtx.tar.gz"
tar -xzf "$TMP/mediamtx.tar.gz" -C "$TMP"
sudo install -m 755 "$TMP/mediamtx" /usr/local/bin/mediamtx
echo "    installed: $(/usr/local/bin/mediamtx --version 2>/dev/null || echo mediamtx)"

echo "==> Installing config to /etc/mediamtx/mediamtx.yml"
sudo mkdir -p /etc/mediamtx
sudo cp "$SCRIPT_DIR/mediamtx.yml" /etc/mediamtx/mediamtx.yml

echo "==> Installing systemd service"
sudo tee /etc/systemd/system/mediamtx.service >/dev/null <<'EOF'
[Unit]
Description=MediaMTX RTSP server (bird camera)
After=network-online.target
Wants=network-online.target

[Service]
ExecStart=/usr/local/bin/mediamtx /etc/mediamtx/mediamtx.yml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now mediamtx
sudo systemctl restart mediamtx

echo "==> Camera check"
if rpicam-hello --list-cameras 2>/dev/null | grep -qi imx; then
  echo "    Camera detected - the cam path is live."
else
  echo "    No camera detected (expected until it's delivered)."
  echo "    MediaMTX keeps retrying the 'cam' path automatically; the 'test' path works regardless."
fi

IP="$(hostname -I | awk '{print $1}')"
echo
echo "Done. Stream endpoints (force TCP in the player):"
echo "  camera (once attached): rtsp://${IP}:8554/cam"
echo "  test pattern:           rtsp://${IP}:8554/test   (publish it with: bash ~/pi/test-pattern.sh)"
