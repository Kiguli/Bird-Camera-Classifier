# Office Tree Field Station

A live wildlife-identification camera pointed at the tree outside an office
window. A camera publishes RTSP; [Frigate](https://frigate.video) consumes that
stream for motion and object detection; species classification
(BioCLIP 2 / MegaDetector) comes later.

The design brief this follows is summarised in [docs/PLAN.md](docs/PLAN.md).

## Status

**Working today:** an end-to-end prototype on one Windows PC. A Kinect stands in
as the camera while the real one is in transit.

```
Kinect  ->  bridge (C#)  ->  ffmpeg  ->  MediaMTX  ->  Frigate (Docker)
                                          RTSP         detection + clips
```

**The intended final build:** a Raspberry Pi with a Camera Module 3 pressed
against the window glass, publishing the same RTSP stream over WiFi to this same
Frigate instance. Because Frigate only ever talks to a *stream*, swapping the
camera is a one-line config change — see
[docs/TRANSFER.md](docs/TRANSFER.md#3-swapping-the-camera-source).

| Piece | State |
|---|---|
| Kinect v1 (model 1517) | Code works (640x480, manually tuned exposure). Currently **blocked by this machine's Application Control policy** |
| Kinect v2 (Xbox One) | Code works, and its 1920x1080 image is dramatically better. Same **Application Control block**; RTSP throughput also needs tuning |
| Frigate + MediaMTX | Working. Detection on, event-only retention. Running on the synthetic test pattern |
| Raspberry Pi 2 | Blocked: needs a microSD *card reader* to flash. Scripts ready in [pi/](pi/) |
| Camera Module 3 | In transit |

## Two ways to run it

Full side-by-side detail and a decision guide are in
[docs/INSTALL-OPTIONS.md](docs/INSTALL-OPTIONS.md).

### Option 1 — Signed SDK viewer (works on a locked machine today)

Microsoft-signed Kinect viewers that run even under enforced Application Control,
where our own bridge is blocked. View and record only — no detection.

```powershell
cd pc
.\view-kinect.ps1            # ColorBasics: quick live 1080p colour window
.\view-kinect.ps1 -Studio    # Kinect Studio: monitor all streams, record
```

### Option 2 — Localhost RTSP + Frigate (the full detection dashboard)

The real target: detection boxes, event clips, the review UI, species later — at
<http://localhost:5000>. Needs the capture bridge, which on a locked machine
requires an IT allow-list/signing ([docs/WDAC-REQUEST.md](docs/WDAC-REQUEST.md))
or the Raspberry Pi ([docs/TRANSFER.md](docs/TRANSFER.md)).

```powershell
cd pc
.\setup-pc.ps1                # once: ffmpeg, Docker, MediaMTX, build bridges
.\start-mediamtx.ps1          # leave running; allow through the firewall
.\publish-kinect.ps1          # a camera publisher - pick exactly ONE
docker compose up -d          # Frigate
```

`publish-kinect.ps1` (v1) is the reliable default. `publish-kinect-v2.ps1` gives a
much sharper 1080p image, but its RTSP throughput is still being tuned (~1-2 fps —
see [docs/CAMERAS.md](docs/CAMERAS.md)). No camera to hand? `.\publish-test-pattern.ps1`
proves the whole pipeline with a synthetic feed. **Quickest end-to-end proof:** walk in front of the camera —
`person` is tracked, so an event with a bounding box appears in the review UI
within a couple of seconds.

## Layout

| Path | What |
|---|---|
| [pc/](pc/) | The Windows machine: capture bridges, publishers, Frigate |
| [pc/view-kinect.ps1](pc/view-kinect.ps1) | Option 1 launcher: open a signed SDK viewer |
| [pc/kinect-bridge/](pc/kinect-bridge/) | C# sources that pull frames from a Kinect and pipe raw video to ffmpeg |
| [pi/](pi/) | Raspberry Pi capture node: one-shot `setup.sh` installs MediaMTX + systemd |
| [docs/INSTALL-OPTIONS.md](docs/INSTALL-OPTIONS.md) | The two ways to run it, compared |
| [docs/CAMERAS.md](docs/CAMERAS.md) | Per-camera tuned settings, and why each value is what it is |
| [docs/TRANSFER.md](docs/TRANSFER.md) | Standing this up on another machine |
| [docs/WDAC-REQUEST.md](docs/WDAC-REQUEST.md) | Getting the bridge allowed under Application Control |

## Hard-won gotchas

Each of these cost real time. Detail in [docs/TRANSFER.md](docs/TRANSFER.md) and
[docs/CAMERAS.md](docs/CAMERAS.md).

- **Frigate's `detect.enabled` defaults to `false`.** Everything looks healthy —
  video plays, recordings tick over — and nothing is ever detected. It must be
  set explicitly.
- **A detect resolution that doesn't match the stream turns the picture magenta**
  (misaligned YUV planes), which reads as a camera fault. Leave it unset.
- **Kinect v1 needs AC power**, and Windows 11's Core Isolation / Memory
  Integrity blocks its camera driver — with a reboot required after changing it.
- **Auto white balance caused the magenta flicker** on the v1; auto exposure blew
  out a bright window scene. Both are forced manual.
- **PowerShell 5.1 misparses non-ASCII punctuation.** Keep `.ps1` files pure
  ASCII; a stray em dash produces a baffling "missing terminator" error.
- **A managed Windows machine may block the locally-compiled Kinect bridges**
  via WDAC / Device Guard, with no error surfaced beyond the publisher exiting
  instantly. Check before investing time — see
  [TRANSFER.md](docs/TRANSFER.md#1b-2-application-control-wdac--device-guard--check-this-early),
  and [WDAC-REQUEST.md](docs/WDAC-REQUEST.md) for how to get it allowed.
  The Raspberry Pi build sidesteps it entirely.

## Storage

Recording is **event-only**: continuous retention is off, and only footage
belonging to an alert or detection is kept (30 days), plus snapshots. Continuous
recording filled 728 MB in three hours, which is why it is off. Nothing under
[pc/storage/](pc/storage/) is committed.
