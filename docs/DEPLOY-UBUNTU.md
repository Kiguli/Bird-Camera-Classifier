# Deploying the full stack on Ubuntu

The Ubuntu box is where everything comes together: Frigate, the MQTT broker, and
the species-classification + email service, all in Docker. Unlike the locked
Windows machine, there's no Application Control in the way, so the whole pipeline
runs — capture (from the Pi over RTSP), detection, classification, and
notification.

## Prerequisites

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git
sudo usermod -aG docker "$USER"   # log out/in so 'docker' works without sudo
```

## Get the repo and configure

```bash
git clone https://github.com/Kiguli/Bird-Camera-Classifier.git
cd Bird-Camera-Classifier/pc

# 1. Point Frigate at the camera. On Ubuntu the capture source is the Raspberry
#    Pi over the LAN, so edit frigate/config.yml's go2rtc stream to the Pi's IP:
#        rtsp://<pi-ip>:8554/cam
#    (host.docker.internal is a Windows/Docker-Desktop thing; on Linux use the
#     Pi's real IP, or run publish-test-pattern equivalent for a dry run.)

# 2. Configure the enrichment service.
cp enrichment/.env.example enrichment/.env
nano enrichment/.env
#   - MAIL_TO: recipient address(es), comma-separated (real values only in .env)
#   - SMTP_HOST/PORT/USER/PASSWORD: your sender (Gmail = a 16-char App Password,
#     generated under Google Account > Security > App passwords; NOT the login password)
#   - Leave MAIL_DRY_RUN=true for the first run to confirm the flow, then set
#     it false to actually send.
```

## Bring it up

```bash
docker compose up -d --build
docker compose logs -f enrichment      # watch it connect to MQTT and load models
```

First start pulls Frigate + Mosquitto and **builds** the enrichment image, which
downloads the MegaDetector and BioCLIP 2 weights (a few GB) into named volumes —
so it's slow once, then fast. Frigate is at <http://localhost:5000>.

## Verify it end to end

1. **MQTT wired:** `docker compose logs frigate | grep -i mqtt` shows it
   connecting to the broker; `docker compose logs enrichment` shows
   "MQTT connected; subscribing to frigate/events".
2. **Trigger an event:** walk in front of the camera, or point it at the feeder.
   Frigate fires a `bird`/`person` event.
3. **Watch the enrichment log:** it should log `event <id>: label=... species=...
   status=ok`, write a row to `enrichment/data/detections.sqlite`, and — in
   dry-run — drop an `.eml` in `enrichment/data/media/`. Open the `.eml` to see
   exactly what would be sent.
4. **Go live:** set `MAIL_DRY_RUN=false` in `enrichment/.env`, `docker compose up
   -d enrichment`, trigger another event, and confirm the email arrives.

## Inspecting results

```bash
sqlite3 enrichment/data/detections.sqlite \
  "SELECT start_time, species_common, species_score, status FROM detections ORDER BY start_time DESC LIMIT 20;"
```

## Notes

- **CPU is fine.** One camera at 10 fps plus per-event inference (1–3 s) sits
  comfortably on a normal desktop CPU. A CUDA GPU would speed classification but
  isn't required; the images are CPU-only by design.
- **Weights offline?** If the box has no internet, uncomment the pre-cache lines
  in `enrichment/Dockerfile` and build on a connected machine, or pre-populate
  the `hf_cache` / `torch_cache` volumes.
- **Camera swap:** nothing here is Kinect-specific. Whatever publishes RTSP to
  Frigate (Pi camera, Kinect bridge on an unlocked box, or the test pattern)
  feeds the same pipeline. See [TRANSFER.md](TRANSFER.md#3-swapping-the-camera-source).
