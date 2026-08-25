# Camera notes and tuned settings

Working settings for every camera this project has used, so a known-good starting point
survives when we come back to one. The Kinects are **prototype stand-ins**; the intended
final camera is a Raspberry Pi Camera Module 3 pressed against a window.

---

## Kinect for Windows v1 (model 1517) — tuned and working

The 2010-era sensor. Xbox 360 generation, sold in a "Kinect for Windows" variant.

| Property | Value |
|---|---|
| Colour resolution | 640 x 480 @ 30 fps (its maximum) |
| SDK | Kinect for Windows SDK **1.8** |
| Connection | Own captive cable + **AC power adapter** (USB alone is not enough) |
| Managed assembly | `C:\Program Files\Microsoft SDKs\Kinect\v1.8\Assemblies\Microsoft.Kinect.dll` |

### The settings that work

Pointed out an office window at a bright daytime skyline (Nashville, late August,
midday sun). Applied by [KinectPipe.cs](../pc/kinect-bridge/KinectPipe.cs); these are the
script defaults, so plain `.\publish-kinect.ps1` uses them.

```powershell
.\publish-kinect.ps1 -KinectArgs "--exposure 20 --gain 1.0 --wb 4700"
```

| Setting | Value | Why |
|---|---|---|
| `AutoExposure` | **false** | Auto metering averaged over a bright sky and blew the whole frame to near-white — buildings and trees were unrecoverable. |
| `ExposureTime` | **20** | SDK units of 1/10000 s, so **2 ms**. Valid range 1–4000. Correctly exposes a sunlit outdoor scene. |
| `Gain` | **1.0** | Minimum. Any more adds noise for no benefit in daylight. |
| `AutoWhiteBalance` | **false** | **This is what caused the magenta flicker.** AWB hunted under mixed office/daylight and periodically swung the whole frame toward pink. |
| `WhiteBalance` | **4700** K | Fixed, mid-daylight. Matches the plan's advice to lock WB behind tinted glazing rather than let it drift. |

Verified stable: 60 s of stream measured at `Y=182.9 U=136.8 V=116.6` with essentially
zero variance — no colour drift at all.

### Re-tuning for a different scene

Exposure is the only value likely to need changing. Lower = darker.

| Scene | Try |
|---|---|
| Bright sunlit exterior | `--exposure 20` (current) |
| Overcast / shaded exterior | `--exposure 40` to `--exposure 80` |
| Indoor room | `--exposure 150` to `--exposure 400`, possibly `--gain 2` |

Auto-exposure is still available (`--auto --brightness 0.13`) but is not recommended for
a window scene. **Auto white balance is never re-enabled** — the bridge always forces it
off, because that was the magenta bug.

### Gotchas that cost real time

- **AC power is mandatory.** Without the wall adapter the sensor either does not
  enumerate at all, or the SDK reports it as `NotPowered`. USB cannot run the cameras.
- **Core Isolation / Memory Integrity blocks the camera driver.** Windows 11 refuses to
  load the v1's 2013-era camera driver with Memory Integrity on. Symptom: the audio
  devices appear and work, but `Kinect for Windows Camera` fails to start and the SDK
  reports the sensor stuck at `Initializing` forever. Turn Memory Integrity off, then
  **reboot** — the change does nothing until you do.
- Camera settings must be applied **after** `sensor.Start()`. Setting them earlier throws
  or is silently ignored on SDK 1.8.

---

## Kinect for Xbox One (v2) — much better image, streaming still being tuned

Trialled as a higher-resolution alternative, and on image quality it wins
decisively: at 1920x1080 individual cars, pedestrians, foliage detail and
readable signage are all resolved, where the v1 at 640x480 renders the same scene
as washed-out blocks. Since [pixels on target](PLAN.md#pixels-on-target-decides-everything)
is the whole game for species ID, that matters more than any other difference.

Capture is via [KinectV2Pipe.cs](../pc/kinect-bridge/KinectV2Pipe.cs), published
by [publish-kinect-v2.ps1](../pc/publish-kinect-v2.ps1).

| Property | Value |
|---|---|
| Colour resolution | 1920 x 1080 @ 30 fps — **~7x the pixels of the v1** (2.07M vs 0.31M) |
| SDK | Kinect for Windows SDK **2.0** (separate from 1.8; both can coexist) |
| Connection | Requires the **Kinect Adapter for Windows** (power brick + USB 3.0 converter) |
| USB | USB **3.0 required** — will not work on a 2.0 port |

**Exposure control:** unlike the v1, SDK 2.0 exposes no writable exposure, gain or white
balance in the managed API — `ColorCameraSettings` is read-only. The v2 is
auto-exposure-only, so the v1's manual tuning has no equivalent. This is the main
trade-off against its much higher resolution, and it matters for a window scene where
auto-metering is exactly what blew out the v1.

Device IDs, for identifying it in Device Manager:

| Interface | Hardware ID |
|---|---|
| Sensor (camera + depth) | `USB\VID_045E&PID_02C4&MI_00` |
| Sensor (audio) | `USB\VID_045E&PID_02C4&MI_02` |
| Adapter hub | `USB\VID_045E&PID_02D9` |

Without SDK 2.0 installed, `MI_00` shows **`Error`** in Device Manager — that is the
missing driver, not a broken sensor.

### Viewing the v2 feed on a WDAC-locked machine

If the custom bridge is blocked by Application Control (see
[WDAC-REQUEST.md](WDAC-REQUEST.md)), you can still **see** the live feed using the
Microsoft-signed sample viewers that ship pre-built with SDK 2.0. They pass WDAC
because they are signed by Microsoft, not locally compiled:

```
C:\Program Files\Microsoft SDKs\Kinect\v2.0_1409\bin\ColorBasics-D2D.exe   # live 1080p colour
C:\Program Files\Microsoft SDKs\Kinect\v2.0_1409\bin\DepthBasics-D2D.exe   # depth
C:\Program Files\Microsoft SDKs\Kinect\v2.0_1409\bin\InfraredBasics-D2D.exe
C:\Program Files\Microsoft SDKs\Kinect\v2.0_1409\Tools\KinectStudio\KStudio.exe  # monitor + record
```

Confirmed: `ColorBasics-D2D.exe` is Authenticode-signed `CN=Microsoft
Corporation` and launches under the enforced policy that blocks our bridge.

**What this does and does not give you.** It confirms the sensor works and lets
you view/record the streams. It does **not** feed Frigate: these viewers only
display to a window, they do not publish RTSP or expose a virtual camera. And you
cannot modify a sample to add streaming — recompiling makes it unsigned again,
and it is blocked like the bridge. Feeding the detection pipeline still requires
the signed bridge (IT allow-list / cert) or the Raspberry Pi.

The v2 emits **native YUY2** (2 bytes/pixel), not BGRA. This was not an
optimisation for its own sake: converting to BGRA in the frame callback
(`CopyConvertedFrameDataToArray` over 2 million pixels per frame) starved the
encoder down to 2.4 fps. Emitting raw YUY2 halves the bytes *and* skips the
conversion; ffmpeg reads it natively as `yuyv422`.

Measured after that change:

| Path | Result |
|---|---|
| Bridge -> ffmpeg pipe, no encode | **30 fps, 1.00x realtime** — the pipe is not a bottleneck |
| x264 1080p encode, isolated | **36x realtime** — the encoder is not a bottleneck |
| Bridge -> ffmpeg -> RTSP -> MediaMTX | **~1-2 fps** — still under investigation |

So the remaining bottleneck is in the RTSP publish path, not capture or encode.
Until that is resolved the **v1 remains the default publisher**; the v2 is
reliable for grabbing stills. This is a prototype-only concern — the Pi camera
publishes its own RTSP with a hardware encoder and does not use this path.

---

## Raspberry Pi Camera Module 3 — the intended final camera

Not yet in hand. Configuration is written and waiting in
[pi/mediamtx.yml](../pi/mediamtx.yml).

| Property | Value |
|---|---|
| Sensor | 11.9 MP IMX708, f/1.8, autofocus 10 cm–infinity |
| Planned stream | 1920 x 1080 @ 15 fps, hardware H.264, ~3 Mbps |
| White balance | `daylight`, fixed — same reasoning as the v1, tinted glass shifts colour |
| Autofocus | `continuous` — phase-detect AF locks on the feeder rather than the glass |

Planned physical setup: lens 2–3 mm off the pane behind a foam collar (never hard
contact), feeder suction-cupped to the same pane 30–50 cm away, Pi itself out of direct
sun on a longer ribbon cable.
