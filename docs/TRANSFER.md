# Moving this project to another machine

Everything needed to stand the stack up from a fresh clone. Written because the
original machine accumulated its setup by hand and none of it was reproducible.

## What is and is not in the repo

Committed: all source, configs, scripts and docs.

**Not** committed, and produced by [pc/setup-pc.ps1](../pc/setup-pc.ps1):

| Excluded | Why | How it comes back |
|---|---|---|
| `pc/mediamtx/mediamtx.exe` | 55 MB third-party binary | `setup-pc.ps1` downloads the pinned version |
| `*.exe`, `Microsoft.Kinect.dll` | Build artifacts / Microsoft redistributable | `pc/kinect-bridge/build.ps1` |
| `pc/storage/` | Video recordings | Regenerated at runtime |
| `pc/frigate/*.db`, `.jwt_secret` | Runtime state and a live signing secret | Frigate recreates on start |
| `auto.crt`, `auto.key` | MediaMTX TLS keypair | MediaMTX self-signs on start |

## 1. Prerequisites

Run in this order. Steps 1a and 1b are manual; everything else is scripted.

### 1a. Kinect SDKs — manual, only if using a Kinect

Not available via winget. Install only what matches your sensor; both can coexist.

| Sensor | SDK | Download |
|---|---|---|
| Kinect v1 (model 1517) | SDK **1.8** | <https://www.microsoft.com/en-us/download/details.aspx?id=40278> |
| Kinect v2 (Xbox One) | SDK **2.0** | <https://www.microsoft.com/en-us/download/details.aspx?id=44561> |

Skip entirely if the camera is a Raspberry Pi.

### 1b. Windows settings that block the Kinect v1

> **Core Isolation / Memory Integrity must be OFF, and you must reboot.**
> Windows 11 refuses to load the v1's 2013-era camera driver with Memory
> Integrity enabled. The symptom is deceptive: the Kinect's *audio* devices
> appear and work fine, while `Kinect for Windows Camera` sits at `Error` in
> Device Manager and the SDK reports the sensor stuck at `Initializing`
> forever. Windows Security > Device security > Core isolation details >
> Memory integrity > Off, then **reboot** — the change does nothing until
> you do. This cost hours the first time.

The v1 also needs its **AC power adapter**; USB alone cannot run its cameras.
The v2 needs the **Kinect Adapter for Windows** and a **USB 3.0** port.

### 1b-2. Application Control (WDAC / Device Guard) — check this early

> **A managed or corporate Windows machine may refuse to run the Kinect bridges
> at all.** They are locally compiled, unsigned executables, and an enforced
> Application Control policy blocks exactly that. This is what happened on the
> original machine partway through development:
>
> ```
> 'KinectV2Pipe.exe' was blocked by your organization's Device Guard policy.
> Program 'KinectPipe.exe' failed to run: An Application Control policy has blocked this file
> ```
>
> Check before investing time:
>
> ```powershell
> Get-CimInstance -Namespace root\Microsoft\Windows\DeviceGuard -ClassName Win32_DeviceGuard |
>   Select-Object UsermodeCodeIntegrityPolicyEnforcementStatus
> ```
>
> `0` = off, `1` = audit only, **`2` = enforced** (bridges will be blocked).
>
> Note the binaries may run once and be blocked later: each rebuild produces a
> new hash, which the policy re-evaluates. Symptoms are confusing — the
> publisher exits instantly, and Frigate shows a frozen or discoloured last
> frame rather than any error.
>
> **Do not attempt to bypass this.** It is a deliberate security control; ask
> whoever administers the machine to allow-list the binaries if you need them.
>
> **The good news: this does not affect the real build.** With a Raspberry Pi,
> capture code runs *on the Pi*, and the Windows machine only runs Docker,
> Frigate and stock ffmpeg — all signed, none of it blocked. The Kinect bridges
> are prototype scaffolding, and this is a strong argument for moving to the Pi.
> `publish-test-pattern.ps1` also keeps working, since it is stock ffmpeg.

### 1c. .NET Framework

`build.ps1` compiles with `csc.exe` from
`%WINDIR%\Microsoft.NET\Framework64\v4.0.30319`. Present on any current Windows;
no action needed normally.

### 1d. Everything else — scripted

```powershell
cd pc
.\setup-pc.ps1
```

Installs ffmpeg, Docker Desktop and VLC via winget, downloads MediaMTX v1.20.1,
and builds whichever Kinect bridges have their SDK present.

### 1e. If PowerShell refuses to run the scripts

A fresh machine may block them, either by execution policy or by
Mark-of-the-Web on a downloaded zip:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned      # once per machine
Get-ChildItem -Recurse *.ps1 | Unblock-File              # if cloned from a zip
```

Cloning with `git` rather than downloading a zip avoids the second problem.

## 2. Start the stack

Three components, in this order. Each stays running.

```powershell
cd pc
.\start-mediamtx.ps1          # 1. RTSP server. Allow it through the firewall
                              #    when Windows asks - the Frigate container
                              #    reaches it across the WSL2 network.
.\publish-kinect.ps1          # 2. A camera publisher (pick ONE - see below)
docker compose up -d          # 3. Frigate
```

Then open <http://localhost:5000>.

### Choosing a publisher

Exactly one may publish to `/cam` at a time.

| Script | Source | Notes |
|---|---|---|
| `publish-kinect.ps1` | Kinect v1 | 640x480. Manual exposure — see [CAMERAS.md](CAMERAS.md) |
| `publish-kinect-v2.ps1` | Kinect v2 | 1920x1080, far better image. Auto-exposure only |
| `publish-test-pattern.ps1` | Synthetic | No camera needed — use to prove the plumbing |

### What success looks like

- MediaMTX logs `[path cam] stream is available and online, 1 track (H264)`
- `http://localhost:5000` shows live video, correct colours, no magenta
- `curl -s localhost:5000/api/stats` shows `camera_fps` near the publisher's rate
  and `detection_enabled: true`
- Walking in front of the camera produces a `person` event in the review UI
  within a couple of seconds — the quickest end-to-end proof

## 3. Swapping the camera source

The whole point of the RTSP indirection: Frigate never talks to a camera, only
to a stream. To change cameras, change who publishes.

**To the Raspberry Pi** (the intended final setup): run `pi/setup.sh` on the Pi,
then point go2rtc at it in [pc/frigate/config.yml](../pc/frigate/config.yml):

```yaml
go2rtc:
  streams:
    office_tree:
      - rtsp://<pi-ip>:8554/cam     # was host.docker.internal
```

Stop the local publisher and MediaMTX; the Pi runs its own. Nothing else changes
— detect resolution is auto-detected, so a different frame size needs no edit.

## 4. Platform caveats

**`host.docker.internal`** resolves on Docker Desktop (Windows/macOS) but *not*
on native Linux Docker. On Linux, either add to `docker-compose.yml`:

```yaml
    extra_hosts:
      - "host.docker.internal:host-gateway"
```

or use the host's LAN IP in the go2rtc stream URL.

**Hardware acceleration.** Docker Desktop on WSL2 cannot reach the Intel iGPU, so
the config uses the CPU detector — fine for one camera at 10 fps. On native Linux
with an Intel CPU, switch to OpenVINO for a significant speedup; see
[Frigate's detector docs](https://docs.frigate.video/configuration/object_detectors/).

## 5. Conventions worth keeping

- **PowerShell scripts must be pure ASCII.** Windows PowerShell 5.1 misparses
  UTF-8 punctuation (curly quotes, em dashes) and fails with confusing
  "string is missing the terminator" errors. This has bitten the project twice.
- **Shell scripts stay LF.** [.gitattributes](../.gitattributes) enforces it;
  without it a Windows clone checks out CRLF and the Pi fails on the shebang.
- **One publisher at a time** on the `/cam` path.
