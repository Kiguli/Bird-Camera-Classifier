# Getting the Kinect bridges allowed under Application Control

The Kinect bridges are blocked by an **enterprise-managed WDAC (Device Guard)
policy**. This is not something to work around locally — the policy is deployed
by the organisation's management infrastructure, so local changes would need
admin rights, would be reverted at the next MDM sync, and would likely breach IT
policy. The route is a request to whoever administers the machine.

## What the diagnostics found

| Fact | Value |
|---|---|
| Usermode code-integrity enforcement | **2 (enforced)** — not audit mode |
| Virtualisation-based security | Running |
| Blocking policy ID | `{0283ac0f-fff1-49ae-ada1-8a933130cad6}` |
| Failure reason | *"did not meet the **Enterprise signing level** requirements"* |
| Management | MDM-enrolled (`Deploy Authority`, `Cloud Authority`) — centrally pushed |
| `CiTool -lp` | Access denied without elevation |
| Binaries | Unsigned |

Relevant event log: **Microsoft-Windows-CodeIntegrity/Operational**, event IDs
**3033** (signing level not met) and **3077** (policy violation).

## Option A — ask IT to allow-list (fastest)

Everything a ticket needs:

> **Request:** allow two locally built executables to run under the Application
> Control policy on this machine.
>
> **Purpose:** a personal hobby project — a bird-identification camera. The
> binaries are small C# programs that read frames from a Kinect sensor via the
> Microsoft Kinect SDK and write them to stdout for ffmpeg. They open no network
> listeners and write no files. Source is available for review.
>
> **Blocked files:**
>
> | File | SHA256 |
> |---|---|
> | `KinectPipe.exe` | `B63831131AA279EBABDDA96ECA39684AA66A142E2136F632D50E5D985ABAC1A6` |
> | `KinectV2Pipe.exe` | `62362BD9F0B08447713296DE89835524EC1F31ADC15FF3DE9ACCC3CC8E21805C` |
>
> **Blocking policy:** `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`
> **Events:** CodeIntegrity/Operational, IDs 3033 and 3077

> [!IMPORTANT]
> **Hash-based allow-listing breaks on every rebuild.** Each compile produces a
> new hash that the policy has never seen — which is exactly why these binaries
> ran at first and were blocked later. If the bridges are going to be modified
> at all, ask for a signing certificate (Option B) instead; otherwise every code
> change needs a new ticket.

## Option B — code signing (the durable fix)

If the organisation runs an internal code-signing CA, a certificate the policy
already trusts solves this permanently: sign after each build and the binary
satisfies the "Enterprise signing level" requirement regardless of its hash.

```powershell
# once a cert is issued and installed
Set-AuthenticodeSignature -FilePath .\KinectPipe.exe `
  -Certificate (Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert)[0]
```

This is worth asking about if you expect to write more local tooling on this
machine — it fixes the whole class of problem, not just these two files.

## Option C — don't need the exemption at all (recommended)

**The Raspberry Pi build sidesteps this completely**, and it is where the project
was always heading. Capture code runs on the Pi; this machine only runs Docker,
Frigate and stock ffmpeg — all signed, none of it affected by the policy.

This is worth weighing seriously before raising a ticket: the Kinects are
prototype scaffolding for a camera that is already in transit, so an exemption
buys a stand-in you plan to discard. The one thing blocking the Pi is a microSD
card reader.

`publish-test-pattern.ps1` also keeps working meanwhile — it is stock ffmpeg —
so the rest of the pipeline stays testable either way.

## Why not just turn it off

Beyond being centrally managed and reverting on sync, WDAC in enforced mode is
the control that stops unsigned code running on a managed endpoint. Disabling it
weakens that for every other process too, and on a corporate device it is not
yours to change. Ask, sign, or move the workload to the Pi.
