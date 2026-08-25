# The design brief

Condensed from the original build brief so this repo stands alone — the source
artifact is private and a clone cannot open it.

## The core architectural decision

**Don't classify the video. Classify a still.**

Run a cheap, dumb detector on every frame; run an expensive, smart classifier on
a handful of frames. A generic "is there an animal here?" detector costs ~10 ms
and runs continuously. When it fires, pull one sharp full-resolution still, crop
to the bounding box, and hand that crop to a fine-grained species model taking
1–2 seconds.

Two reasons this wins. Fine-grained bird models need a big, sharp, centred crop —
a compressed video frame with a 40-pixel blurry bird in the corner defeats every
classifier there is. And it cuts compute by ~99%, so an ordinary desktop is
enough. End-to-end latency stays 1–3 s, so it still reads as live.

The capture device stays deliberately dumb: it captures, encodes, and publishes a
stream. All intelligence lives on the PC, so models can be swapped without
touching the hardware on the windowsill.

## The three-layer model stack

| Layer | Model | Job |
|---|---|---|
| 1. Detection | MegaDetector v6 (MIT) | "Is anything there?" Trained on camera-trap conditions: occlusion, odd poses, motion blur |
| 2. Classification | BioCLIP 2 (MIT) | Species ID, zero-shot against a candidate list *you* supply |
| 2b. Easy start | Frigate's built-in bird classifier | MobileNet iNaturalist; one config flag, common names as `sub_label` |
| 2c. Mammals | SpeciesNet (Apache 2.0) | Google's camera-trap classifier, geofenceable to `USA/TN` |

**The trick that makes BioCLIP 2 right for this:** it classifies against a label
list you provide. Take the ~120 species eBird actually records for Davidson
County and use that as the candidate set — deleting every possible confusion with
a bird that doesn't live in Tennessee, which is precisely where fine-grained
classifiers normally lose accuracy.

General-purpose VLMs are *not* the classifier: they are confidently wrong between
a Carolina and a Black-capped Chickadee, exactly the distinction that matters
here. Use one for descriptions and search, not for the label.

## Shooting through glass

Moving indoors deletes weatherproofing, cable runs, outdoor power, ladders and
theft risk, at the cost of shooting through two panes of coated glazing.

- **Lens flush to the pane, with a soft collar sealing the gap.** Reflections
  need room light hitting glass at an angle the lens can see; close the gap and
  there is nothing left to reflect. No polarising filter needed.
- **Leave 2–3 mm — don't hard-contact.** A rigid lens on glass transmits building
  vibration into the frame, and trapped grit scratches the front element. Foam
  absorbs both.
- **Free bonus:** at 3 mm from a lens focused a metre away, dust and rain streaks
  on the outer pane are so far out of focus they vanish.
- **Night vision is gone.** Low-E coatings reflect infrared, so IR illuminators
  fight the window. Plan a daylight-only station; that makes it a bird-first
  problem, which is simpler than the general camera-trap one.
- **Fix white balance.** Tinted glazing shifts colour, and drift makes crops
  inconsistent. (This project also found auto *white balance* causes magenta
  flicker — see [CAMERAS.md](CAMERAS.md).)

## Pixels on target decides everything

A Carolina Chickadee is ~12 cm long. **Target >=150 px on the bird** for reliable
species-level ID. No model recovers information the lens never captured.

```
px on bird = (sensor px across / sensor width mm) x 0.12 m x focal length / distance
```

For a Camera Module 3 that reduces to **406 / distance-in-metres**:

| Distance | 0.3 m | 0.5 m | 1 m | 2 m | 3 m | 5 m | 10 m |
|---|---|---|---|---|---|---|---|
| px on a chickadee | 1354 | 813 | 406 | 203 | 135 | 81 | 41 |

Pixels-on-target is a ratio of focal length to distance, so you can buy reach
with an expensive telephoto — or get the same result free by bringing the bird
closer. **A feeder stuck to the window is the highest-leverage move available**,
and the reason a $25 camera suffices: it puts the subject at 30–50 cm, landing a
chickadee on 800–1350 px, five to nine times the threshold.

This is also why the Kinect v1 (640x480) is a poor final camera and the v2
(1920x1080) is much better — though neither can be pressed against glass as
neatly as the Pi module.

## Siting

- **Pick the window before the camera.** North-facing is ideal; an east-facing
  pane is blown out every morning and a silhouetted bird is unclassifiable.
- **Mind the strike zone.** Feeders belong either under 1 m from the glass or
  over 10 m away, never in between — birds leaving a mid-distance feeder build up
  enough speed to injure themselves on the window. Stuck to the pane is both
  safest and best for pixels.
- **Keep the capture device out of direct sun.** Behind glass it is a greenhouse;
  a throttled board drops frames and a hot sensor gets noisy.

## What to expect

- **New feeders take one to two weeks to be found.** Empty footage in week one is
  expected, not a bug. Hang the feeder before writing any code.
- **Squirrels will be a large share of detections.** Build for it.
- Year-round Nashville regulars: Northern Cardinal, Carolina Chickadee, Tufted
  Titmouse, Carolina Wren, Blue Jay, Mourning Dove, Northern Mockingbird,
  American Robin, House Finch, American Goldfinch, Downy and Red-bellied
  Woodpecker, European Starling, House Sparrow.
- Nocturnal mammals (raccoon, opossum) are out of reach through glass.

## Build order

Each phase is independently useful and demoable.

| Phase | Goal |
|---|---|
| 0 | Prove the sight line free: tape a phone to the window, shoot morning/midday/dusk |
| 1 | Feeder on the glass (long lead time), camera on the sill |
| 2 | Stream to the PC, get detections in Frigate |
| 3 | Turn on Frigate's built-in bird classifier — a working species camera, no code |
| 4 | Enrichment service: subscribe to `frigate/events`, crop with MegaDetector, classify with BioCLIP 2, write to SQLite |
| Later | A second camera on the tree; train a linear probe on your own crops; push confirmed sightings to eBird/iNaturalist |

Acoustics (BirdNET) was cut: a microphone behind sealed glazing records HVAC, and
the pane attenuates exactly the frequencies bird song occupies. It only revives
with a mic physically outside the glass.
