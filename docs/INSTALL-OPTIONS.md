# Installation options

There are two ways to run this, and which one fits depends on the machine you're
on and whether you need object detection or just want to see the camera.

## Which one do I want?

| If you... | Use | Detection? | Runs on the locked work PC? |
|---|---|---|---|
| Just want to see or record the Kinect right now | **Option 1** | No | Yes, today |
| Want the full dashboard — detection boxes, event clips, review UI, species later | **Option 2** | Yes | Only with a signed bridge or via the Pi |
| Have a Raspberry Pi (or any unlocked machine) | **Option 2** | Yes | N/A — runs cleanly there |

The short version: Option 1 is the "works on this machine right now" path;
Option 2 is the full experience the project is actually built around. They're not
mutually exclusive — Option 1 is a good way to confirm the sensor works before
committing to Option 2.

---

## Option 1 — Signed SDK viewer

Microsoft-signed sample tools that ship pre-built with the Kinect for Windows SDK
2.0. Nothing to compile, no ports opened, no configuration. They run even under an
enforced WDAC / Device Guard policy **because Microsoft signs them** — the same
policy that blocks our own locally-compiled bridge (see
[WDAC-REQUEST.md](WDAC-REQUEST.md) for why).

```powershell
cd pc
.\view-kinect.ps1            # ColorBasics: a quick live 1080p colour window
.\view-kinect.ps1 -Studio    # Kinect Studio: monitor colour/depth/IR/body, and record
```

- **ColorBasics** is the minimal viewer — one window, the live colour feed.
- **Kinect Studio** (`-Studio`) is the richer interface: it monitors every stream
  at once (colour, depth, infrared, body) and records/plays back `.xef` clips.
  Reach for it when you want more than a bare picture.

**What this gives you:** confirmation the sensor works, a live view, and
recording. Good for aiming the camera and sanity-checking exposure.

**What it does not give you:** object detection, event clips, the web dashboard,
or species ID. These viewers only display. And you can't bolt those on — editing
and recompiling a sample makes it unsigned, so WDAC blocks it exactly like the
bridge. For anything beyond viewing, use Option 2.

> Exposure note: the v2 is auto-exposure only (SDK 2.0 exposes no manual control),
> so pointed straight at a bright window it may wash out. Aim it at the feeder
> rather than the sky. Full per-camera detail in [CAMERAS.md](CAMERAS.md).

---

## Option 2 — Localhost RTSP + Frigate pipeline

The real target. A capture source publishes an RTSP stream to MediaMTX on
localhost; [Frigate](https://frigate.video) (in Docker) consumes it, runs object
detection, records event clips, and serves the dashboard at
<http://localhost:5000> — detection boxes, an event timeline, the review UI, and
species classification later. This is where "the interesting interface parts"
live.

```powershell
cd pc
.\setup-pc.ps1                # once: ffmpeg, Docker, MediaMTX, build bridges
.\start-mediamtx.ps1          # RTSP server; allow it through the firewall
.\publish-kinect.ps1          # a capture publisher - pick exactly ONE
docker compose up -d          # Frigate
```

Then open <http://localhost:5000>. Full detail, prerequisites, and the
camera-swap procedure are in [TRANSFER.md](TRANSFER.md).

`publish-kinect.ps1` (v1) is the reliable default publisher. `publish-kinect-v2.ps1`
is much sharper (1080p) but its RTSP throughput is still being tuned (~1-2 fps —
[CAMERAS.md](CAMERAS.md)); `publish-test-pattern.ps1` needs no camera at all.

**The catch on a locked machine.** The capture bridge is locally-compiled,
unsigned code, and that is exactly what an enforced WDAC policy blocks. So on a
machine like the current work PC, Option 2 needs one of:

1. **The bridge allow-listed or code-signed by IT** — the request is prepared,
   with hashes and event IDs, in [WDAC-REQUEST.md](WDAC-REQUEST.md); or
2. **The Raspberry Pi** — capture runs on the Pi, this PC only runs Docker,
   Frigate and stock (signed) ffmpeg, and WDAC stops being relevant at all. This
   is the intended production setup; see [TRANSFER.md](TRANSFER.md#3-swapping-the-camera-source).

The synthetic test pattern (`publish-test-pattern.ps1`) is stock ffmpeg and runs
regardless, so the pipeline itself stays testable even while capture is blocked.

---

## Why the split exists

The Kinect can only be read through the Kinect SDK, which means running SDK code.
Microsoft's signed sample code runs anywhere; our own bridge does not, on a
machine locked to enterprise-signed binaries. Rather than fight that, Option 1
uses the signed tools for what they're good at (viewing), and Option 2 carries
the full detection pipeline for the environments where it can run — chiefly the
Raspberry Pi, which is where this project is headed regardless.
