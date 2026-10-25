# Technical Architecture

> One C core, two hosts, deterministic and testable on Linux.

---

## The hard constraints

1. **It must run as a macOS wallpaper**, which is the platform's most fragile
   surface (window levels, Spaces, Stage Manager, full-screen apps, multiple
   displays, lock screen).
2. **It must be developed and verified on Linux.** We have no Xcode. Anything
   that can only be checked on a Mac is a risk that will bite us late. So the
   *majority* of the product must be verifiable off-device.
3. **It's a wallpaper.** It runs for 12 hours a day on a laptop. Power draw is a
   first-class feature, not a polish item.

These three constraints, together, point at exactly one architecture.

## Shape

```
                ┌──────────────────────────────────────────┐
                │  DragonKit (C99, zero dependencies)       │
                │  ─ scene strip + depth field              │
                │  ─ palette ramps (data)                   │
                │  ─ dragon rig (rope + ribbon)             │
                │  ─ shot/path scheduler (seeded)           │
                │  ─ compositor (per-pixel depth test)      │
                │  ─ mist, water, reflections, dither        │
                │  output: RGBA framebuffer 480×270         │
                └───────────────┬──────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
 ┌──────▼──────┐        ┌───────▼────────┐      ┌───────▼────────┐
 │ Linux CLI   │        │ macOS host     │      │ Headless test  │
 │ PNG seq out │        │ Swift/AppKit   │      │ golden images  │
 │ (fast loop) │        │ wallpaper+timer│      │ (CI)           │
 └─────────────┘        └────────────────┘      └────────────────┘
```

### Why C for the core

- Compiles with `clang` on Linux *and* Mac with the same file.
- Drops straight into a Swift app as a C target — no bridging ceremony, no
  runtime, no package manager.
- Can be driven from Python via `ctypes` for instant iteration: change a
  constant, dump 300 frames, watch the video. This is the fast loop.
- No GC pauses, no allocation in the frame loop, predictable timing.
- Zero dependencies means zero build-system archaeology, which matters a lot
  when the whole point is being able to build it anywhere.

We explicitly do **not** use Swift for the core, because we couldn't run it
here. The core is where the art lives; it must be runnable and reviewable on
this machine.

### Why not a game engine

Unity/Godot means a 60MB runtime for a 129k-pixel image, plus a licensing and
packaging story, plus fighting the engine's idea of pixels. The renderer here is
a few thousand lines. We own it.

## Render pipeline

```
per frame (target 15 fps):
  1. advance world pan offset x
  2. compositor_reset()               // copy cached static strip region
  3. for layer in static_layers:      // pre-sorted, back→front
        blit_scroll(layer, x)         // + write depth where alpha
  4. for dragon in active_dragons (back→front by mean depth):
        rig_update(dragon)            // rope + sine + depth interp
        rasterise(dragon)             // per-pixel depth test vs scene_depth
  5. for mist_layer in animated_mist:
        blit_scroll(mist_layer, x, t) // mist also writes depth
  6. water_reflections()
  7. surface post: vignette, grain
  8. present
```

### The static/dynamic split (this is the power story)

Cache aggressively:

- **Fully static** — peaks, ridges, rocks, the sky wash. Composited once into a
  *scrolling strip* in memory. Per frame this is one `memcpy`-ish scanline copy
  from the strip, not a re-blit of 12 layers.
- **Pan-static** — while no dragon is on screen and mist is at a low-animation
  phase, the entire composed frame for a given pan offset can be reused. Cache
  the last N composed frames keyed by pan offset.
- **The single biggest win**: when nothing is happening, we are doing one
  full-frame copy per frame. At 480×270×15fps that's ~2M pixel-writes/second.
  A Raspberry Pi could do it.

### Frame rate: 15 fps, deliberately

- Pixel animation is *traditionally* animated on twos and threes. 15 fps is not
  a compromise; it's the correct look. 60 fps pixel art frequently feels
  "cheap CG".
- 4× less work than 60 fps.
- The dragon at 15 fps with 1-px steps will slightly "stutter" its position
  relative to the smooth pan. **Fix**: pan at 15 fps too, and move the dragon in
  whole steps. Consistent judder is invisible; mixed-rate judder is not.
- Config: `dragon.fps = 15` (default), tool supports 12/15/24/30 for taste.

### Adaptive throttling

- Drop to 10 fps when on battery below 40%, or when the display is asleep/off.
- Full stop when the wallpaper is fully occluded (another app's window covers
  it) or when the screen is locked. Listen for `NSWorkspace` + window occlusion
  notifications in the host, and simply stop calling `dragon_frame()`.
- Never busy-wait. `CVDisplayLink` or a `CADisplayLink`-style timer at the
  target interval, and let the OS coalesce.

## Determinism

Everything random is seeded from a **single 64-bit world seed**:

```c
dragon_world_t world;
dragon_world_init(&world, /*seed=*/0x5EED_0D1A, /*preset=*/PRESET_DAWN_MIST);
```

Per-shot randomness uses a counter-based PRNG (`splitmix64`) keyed by
`(seed, shot_index)` so that:
- The same seed always produces the same sequence of dragons.
- The test suite can assert exact output.
- A user in 2031 sees the same beautiful shot at minute 40 that we saw during
  development, if we want to curate it.

`dragon_frame(world, framebuffer, framebuffer_w, framebuffer_h)` is pure with
respect to a fixed timestep: `dragon_step(world, dt)` then render. Fixed `dt`
(`1/15`) with an accumulator loop in the host — never variable timestep, because
variable timestep makes the rope sim non-reproducible and makes bugs
unreproducible.

## The headless harness (the fast loop)

```
tools/
  render_seq.c        -> writes frames 0000.ppm ... N.ppm
  ppm2png.py          -> PIL conversion (or make a GIF/mp4 with ffmpeg)
  preview.html        -> plays a sequence of PNGs in a canvas at 1x, 2x, 3x
```

Workflow that we'll actually use dozens of times a day:

```sh
make render FRAMES=0..450 SHOT=weave-mid     # ~10s
python3 tools/ppm2png.py out/                  # → out/*.png
python3 tools/make_gif.py out/ preview.gif     # or open preview.html
```

Then look at the GIF. If the dragon reads, ship it. If not, change a constant,
re-run. **No Mac involved.** This loop is the reason the project can be built
here at all.

For the scene art, add a **still export** at any pan offset, plus a **contact
sheet** that tiles 16 stills across the world so we can review the whole
handscroll composition at once — composition problems are invisible at 1× in
one 480px window and obvious at 16 screens wide.

## Testing

| Test | What it catches |
|---|---|
| **Golden frames** — render frame 120 of `weave-mid`, compare hash | Any accidental visual change. The workhorse. |
| **Determinism** — same seed twice → identical hash | PRNG bugs, uninitialised memory, float drift |
| **Depth test unit test** — synthetic 3-px layers at known depths | The core mechanic, in isolation |
| **Occlusion invariants** — dragon pixel at depth d must be absent if a nearer opaque pixel exists at that screen xy | Catches sort/test regressions without eyeballing |
| **Coverage stats** — % of screen covered by dragon over a shot | Tuning aid: too much coverage = busy scene |
| **Palette audit** — every pixel in a frame must belong to a declared ramp | Catches ad-hoc colours, which is how pixel art rots |
| **Silhouette read test** — reduce a dragon frame to 1-bit, assert ≥1 body-length of connected pixels | "Does it still read as a dragon" |
| **Memory** — no allocation inside `dragon_frame` | Power and latency |
| **Mac typecheck gate** — `xcodebuild`/`swiftc -typecheck` in CI on a Mac runner | The thing `swiftc -parse` will *not* catch |

That last one is not optional. Custom shapes/views and macOS-26 SDK symbol
removals are exactly the class of error that only a real typecheck surfaces.
Budget for a cheap macOS CI runner, or accept a "works on my machine" risk on
every release.

## macOS host

### Wallpaper window

```swift
window.level = NSWindow.Level(rawValue: Int(CGWindowLevelForKey(.desktopWindow)))
window.collectionBehavior = [.canJoinAllSpaces, .stationary, .ignoresCycle]
window.ignoresMouseEvents = true
window.isOpaque = true
window.hasShadow = false
window.makeKeyAndOrderFront(nil)   // never makeKey if avoidable!
```

Known landmines to plan for, in order of how likely they are to hurt:

| Landmine | Behaviour | Mitigation |
|---|---|---|
| **Spaces / Mission Control** | Window must not reappear in the switcher | `.stationary`, `.ignoresCycle`; verify per-OS |
| **Stage Manager** | Desktop-level windows may be unmounted | Detect, fall back to a normal borderless window |
| **Full-screen app** | Our window is behind everything — fine | Don't fight it; pause rendering (saves power) |
| **Multiple displays** | Need one window per `NSScreen`, hot-plug | Observe `NSApplication.didChangeScreenParametersNotification` |
| **Lock screen / sleep** | Should stop rendering | `NSWorkspace.willSleepNotification`, screen-lock distributed notifications |
| **Notch / menu bar** | Window should span full frame incl. under-notch | `screen.frame`, not `visibleFrame` |
| **Native macOS wallpapers** | Setting a wallpaper may un-hide the desktop icons above us | We sit *below* icons, so icons stay clickable |
| **Aerial/dynamic wallpaper** | macOS may animate its own wallpaper behind us | Make our window opaque so we don't composite over it |
| **App Sandbox / MAS** | Desktop-level windows are restricted | If we ever want the Mac App Store, plan a separate build |
| **Code signing / notarisation** | Users must be able to run it | Sign + notarise, or ship unsigned with clear instructions |

**Contingency plan, decided up front:** if the desktop-level window proves
unreliable on a given macOS version, we fall back in this order:
1. A `.saver` bundle (very reliable, and we want it anyway).
2. A borderless window on a dedicated Space ("the Dragon Space"), user-initiated.
3. Export a long looping **video** (HEVC, or a ProRes-ish master) and let the
   user set it with a third-party tool. Least elegant, zero risk, and honestly a
   fine v0.1 for people who just want the art.

Each of these uses the same `DragonKit` core, so the fallback costs a host, not
a rewrite.

### Event bus (wallpaper ↔ timer)

Local, no network, no permissions:

- **Primary**: Unix domain socket at `~/Library/Application Support/Dragon/bus.sock`.
  Newline-delimited JSON. Works on Linux for testing.
- **Fallback**: `DistributedNotificationCenter` for zero-config delivery.

Events (~12 total):

```
{"v":1,"ev":"presence","role":"wallpaper","pid":412}
{"v":1,"ev":"timer.started","id":"a3","label":"Tea","endsAt":1761390000,"kind":"break"}
{"v":1,"ev":"timer.fired","id":"a3","label":"Tea is ready","kind":"break"}
{"v":1,"ev":"timer.cancelled","id":"a3"}
{"v":1,"ev":"scene.request","shot":"dive-hero"}     // manual "give me a dragon"
{"v":1,"ev":"prefs.changed","reducedMotion":true}
```

The wallpaper is a *dumb* performer: it receives `timer.fired` and plays the
choreography from `40-timer-app.md`. The timer app owns the clock. This split
means the timer works with the wallpaper absent, and the wallpaper never needs
to know about time.

## Pets, not processes

The wallpaper host must be a **menu-bar agent** (`LSUIElement = true`) with no
Dock icon, plus a proper menu-bar item for quit/pause/preferences. Wallpaper
apps that can't be quit are the ones users uninstall angrily.

## Build

```
Dragon/
  core/            # C99, zero deps — the whole art
    dragon.h       # public API (init, step, frame, presets, events)
    world.c scene.c river.c mist.c water.c palette.c
    rig.c          # rope + ribbon + head stamping
    paths.c        # shot table, seeded scheduler
    dither.c font.c
  tools/           # Linux iteration loop
  tests/           # golden frames, invariants
  assets/          # peak silhouettes, head directions, ramps (data, not code)
  platforms/macos/ # Swift host: wallpaper agent + timer app + .saver
  platforms/web/   # optional: WASM host for the landing page (huge demo value)
  docs/
```

`assets/` as **data** (plain text/PGM, not a binary format) matters: we want to
be able to diff an art change in git and see exactly which pixels moved.

## The one thing that could sink this

Not the art. The **wallpaper window on macOS**. Everything above is comfortable;
desktop-level windowing across Spaces/Stage Manager/notch is the part with real
unknowns and a moving target every OS release. Which is why:

- The core is built and reviewed first, entirely off-Mac.
- The `.saver` and video fallbacks exist before the wallpaper host is finished.
- We validate the windowing with a 200-line spike before writing the rest of
  the host.

## Optional: the web build is a superpower

`DragonKit` compiles to WASM with `emcc` almost for free (no deps, C99, one
framebuffer). That gives us:
- A landing page that *is* the product demo, at full speed, no install.
- A way to share shots with non-technical people.
- A second independent host, which is the best possible stress test of whether
  the core is really decoupled from macOS.

Worth 2 days, returns a lot more.
