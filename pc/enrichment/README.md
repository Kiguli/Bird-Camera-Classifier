# Enrichment + notification service

Turns a Frigate "bird" event into an identified species and an email. It:

1. subscribes to Frigate's MQTT `frigate/events`;
2. on each finished event whose label is in `TARGET_LABELS`, fetches the
   snapshot (and clip) from Frigate's API;
3. crops the animal with **MegaDetector v6**;
4. identifies the species with **BioCLIP 2**, zero-shot against the
   [Davidson County list](species/davidson_county_birds.txt);
5. records everything to SQLite;
6. emails the recipients the clip + classification.

It runs as a container next to Frigate — see the root
[docs/INSTALL-OPTIONS.md](../../docs/INSTALL-OPTIONS.md) Option 2 and
[docs/DEPLOY-UBUNTU.md](../../docs/DEPLOY-UBUNTU.md).

## Layout

| File | Role |
|---|---|
| `main.py` | MQTT loop + worker thread orchestrating the pipeline |
| `app/frigate.py` | Frigate API client (snapshot / clip / thumbnail, with retry + content-type checks) |
| `app/detector.py` | MegaDetector v6 wrapper (crop best animal) |
| `app/classifier.py` | BioCLIP 2 zero-shot classifier |
| `app/store.py` | SQLite record (idempotent per event id) |
| `app/notify.py` | Email composition + SMTP send (dry-run by default) |
| `app/config.py` | All settings, from env (see `.env.example`) |
| `species/davidson_county_birds.txt` | Candidate species (`Common \| Scientific`) |

## Configure

```bash
cp .env.example .env
# edit .env: set SMTP_*, confirm MAIL_TO, set MAIL_DRY_RUN=false to go live
```

**Email is dry-run by default:** with `MAIL_DRY_RUN=true` (or no SMTP host set),
messages are written to `data/media/*.eml` and logged, never sent. A live send
needs `MAIL_DRY_RUN=false` **and** a configured `SMTP_HOST`. Recipients are a
comma-separated `MAIL_TO` set in `.env` (real addresses live only there, never in
the repo); add more by comma-separating.

## Graceful degradation

The service stays up through partial failure (see `detector.py`, `classifier.py`
and `main.py`): if MegaDetector can't load it classifies the full frame; if
BioCLIP can't load it still logs and emails using Frigate's own label; if a fetch
or SMTP send fails the event is still recorded. One bad event never kills the
worker.

## Run standalone (without compose)

```bash
pip install -r requirements.txt          # CPU torch; see the file's notes
export FRIGATE_URL=http://localhost:5000 MQTT_HOST=localhost SPECIES_FILE=species/davidson_county_birds.txt
export DB_PATH=./data/detections.sqlite WORK_DIR=./data/media
python main.py
```

First run downloads the MegaDetector and BioCLIP weights (a few GB) — needs
internet once, then they're cached.
