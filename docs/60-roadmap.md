# Roadmap

> Vertical slice first. Nothing is real until a dragon slips behind a mountain.

---

## Principle

The riskiest thing in this project is not the art and it is not the timer. It is
**"does a dragon actually slip behind a mountain and look good doing it."**
Everything else can be built once that's true, and is wasted if it's not.

So: build the smallest possible thing that answers that question, in week one,
on this machine, as a GIF.

---

## Phase 0 — The Spike (2–4 days)

**Goal:** a 3-second GIF of one dragon passing behind one mountain.

- [ ] `core/include/dragon.h` API sketch (init / step / render / presets).
- [ ] `core/include/dragon_host.h` + `platform/null/` stub host. **Write this
      first**, before anything else — it's the dev loop and the portability
      canary, and retrofitting it later is the expensive mistake.
- [ ] Flat-colour framebuffer, 480×270, PPM out.
- [ ] Two hard-coded mountain silhouettes at depths 0.30 and 0.70.
- [ ] Depth buffer + per-pixel test.
- [ ] Rope spine + sine ribbon body, hard-coded straightish path.
- [ ] Two-colour palette, no mist, no dither.
- [ ] → `preview.gif`. **Look at it. Decide if the core idea works.**

This is a go/no-go. If a plain 2-colour ribbon disappearing behind a grey blob
already reads as "dragon behind mountain", everything after this is craft. If it
doesn't, the problem is the body rendering, and we find that out for cheap.

## Phase 1 — The Dragon (1–2 weeks)

**Goal:** the dragon is genuinely beautiful, alone on a neutral background.

- [ ] Rope tuning: spacing, lag, mass; the "whip" feel.
- [ ] Undulation with amplitude taper at both ends.
- [ ] Tapered cross-section bars, top highlight, belly, ink outline.
- [ ] 16-direction head sprites (hand-pixelled — this is real art time).
- [ ] Legs (tucked variants first), whiskers, tail fan.
- [ ] 5 palette ramps + depth-driven ramp selection + Bayer dither falloff.
- [ ] Depth-varying body: verify head-in-front / tail-behind works.
- [ ] Path splines in (x, y, depth) + 3 path types.
- [ ] Golden-frame tests + silhouette read test.

**Exit criteria:** a silhouette still reads as a dragon, a distant dragon
dissolves into mist, and the path from "behind a far peak" to "in front of a
near rock" is one continuous move with no popping.

## Phase 2 — The World (3 weeks) — the biggest block in the project

**Goal:** a still frame worth framing. Then make it move.

See `25-art-pipeline.md` for how. The short version: hand-author 10 karst
silhouettes in Aseprite/ASCII, 8 overlay stamps, then compose with the tool.
**Every pixel of the mountain is a decision; the tool never invents rock.**
Six procedural attempts failed — that's now evidence, not opinion.

Do not author a flat image. Author the layered stack, so the depth field comes
free and the same art serves the still and the animation.

- [ ] Peak archetype library (start with 6 of the 12).
- [ ] 5 depth ramps + the palette audit test.
- [ ] Mist layers (3), animated, with depth bands and soft/hard edges.
- [ ] Water plane + reflections + wobble + dash rows.
- [ ] Foreground silhouette layer + one anchor object (pavilion first).
- [ ] Handscroll world strip, 7680px, pan camera, no dragon yet.
- [ ] Contact-sheet tool for reviewing the whole scroll at once.
- [ ] Dragon-in-mist ghost pass.
- [ ] Dragon water reflection.

**Exit criteria:** export a single still at 4× and it holds up as a print. If it
doesn't, we keep painting. Do not proceed with an ugly landscape.

## Phase 2.5 — Ambient Life (1–2 weeks)

**Goal:** leave it running with dragons disabled for five minutes and still want
to watch.

This phase is now load-bearing: with dragons on screen only ~50% of the time,
the landscape is the product half the time.

- [ ] `gust()` field — travelling gust envelope, quiet gaps, direction opposing
      the pan. Verify objects near each other bend *together*.
- [ ] Apply gusts to: grass/reeds, pine clusters, branch tips, mist edges.
- [ ] **Waterfall**: scrolling dither core, haze, base mist pulse, spray flecks.
      One per ~2500px of world.
- [ ] **Petals**: spawn from off-screen blossom trees, sin drift + gust, 2-frame
      tumble, land on water → ripple ring, land on rock → rest 20–60s.
- [ ] Water sparkle dashes + occasional fish ripple.
- [ ] Birds: rare flock, 2-frame flap, shallow arc, scale cue at far depth.
- [ ] Lantern flame, irregular schedule.
- [ ] **The hush**: `ambience_gain` 1.0 → 0.65 on dragon spawn, slow settle after.
- [ ] **Ambient director**: 2–4 active systems, region-gated, deterministic,
      crossfading at region boundaries.
- [ ] **Ambience delta test**: `frame_delta / 129600` must sit in 0.30%–1.20%
      per region with no dragon. Ship-blocking.
- [ ] Region ambient identities (at minimum: one lush, one barren, one watery).

**Exit criteria:** the ambience delta test passes in every region, *and* a
five-minute dragon-free recording is worth watching. If it isn't, the answer is
not more particles — it's stronger gusts, a waterfall in view more often, and
better regional contrast (especially a genuinely empty cold-peaks region).

## Phase 3 — The Wallpaper Host (1–2 weeks)

**Goal:** it's on the desktop, and it doesn't drain the battery.

- [ ] **`dr_host` interface locked** and the null host building (should already
      be true from Phase 0 — this is the check).
- [ ] **Windowing spike first** (200 lines): desktop-level window, one screen,
      verify Spaces + Mission Control + full-screen behaviour. This is the
      risky bit; timebox it and learn early.
- [ ] Multi-display, hot-plug, notch handling.
- [ ] Occlusion/sleep detection → stop rendering.
- [ ] Menu-bar agent, prefs (fps, preset, pause, "summon a dragon").
- [ ] Launch at login.
- [ ] Sign + notarise.
- [ ] Fallback `.saver` bundle (reuses the same host code).

**Exit criteria:** 8 hours on a laptop, no fan, no meaningful battery delta,
survives sleep/wake and monitor unplug/replug.

## Phase 4 — Dragon Timer (1–2 weeks)

**Goal:** the alarm choreography, and the two apps talking.

- [ ] Timer engine (clock authority, presets, labels).
- [ ] The six-phase alarm choreography from `40-timer-app.md`.
- [ ] Dragon-intensity table → shot selection.
- [ ] Compact / floating / menu-bar modes.
- [ ] Dial + type-a-number input (under 3 seconds).
- [ ] Unix socket bus + `DistributedNotificationCenter` fallback.
- [ ] Stone-chime audio, ambient bed, ducking.
- [ ] Reduce Motion path.
- [ ] OS notification fallback so a hidden app still alerts.

**Exit criteria:** set a 5-minute timer, hide everything, get interrupted by a
dragon. That's the whole product. If it doesn't feel good at that moment, the
product doesn't work.

## Phase 5 — Polish & Ship

- [ ] Remaining peak archetypes, remaining anchor objects.
- [ ] Remaining 3 shots, plus `coil`.
- [ ] Second weather state (Ink Wash — cheapest, most striking).
- [ ] **WASM host** — the second independent host. Build it here, not later; it
      both proves the portability abstraction and doubles as the landing page.
- [ ] Onboarding: first-run shows the pavilion shot and one dragon within 8s.
- [ ] Licensing, price, DMG, update path.

---

## Phase 6 — Other platforms (post-v1, ~2 weeks total)

Only after macOS works. Each is a new `platform/` directory plus a `dr_host`
implementation; the core does not change. Order by value:

- [ ] **Web/WASM** (likely already done in Phase 5) — demo + abstraction proof.
- [ ] **Windows**: WorkerW behind desktop icons, tray, registry prefs.
- [ ] **Linux X11**: `override-redirect` desktop window.
- [ ] **Linux Wayland**: `wlr-layer-shell` where supported; honest fallback
      (borderless always-behind) elsewhere. GNOME is the known hard case.

Do this only if the concept is validated. Portability discipline from day one
makes it two weeks of work; skipping the discipline makes it two months per
platform. See `55-platform-portability.md`.

---

## Sequencing notes

**Why dragons before the world:** the dragon is the unique part; mountains are
craft we can do at any pace. Also the dragon constrains the world (how much
contrast a ridge may have before it swallows a dragon), so we need it first as a
calibration reference.

**Why the windowing spike is early and timeboxed:** it's the only thing with
genuine unknowns, and unknowns late in a project are what kill projects.

**Why the `.saver` comes before shipping:** it's the free fallback if the
wallpaper window misbehaves on a new OS, and it's the best demo we have.

## Deliberately deferred

| Idea | Why not yet |
|---|---|
| Multiple scenes / more worlds | One scene done deeply beats five done shallowly |
| Custom dragon colours | Breaks the palette discipline that makes it look authored |
| Focus stats dashboard | Turns a calm object into a productivity tool with guilt |
| iOS companion | Nice, but the wallpaper is the point; do it if v1 lands |
| Interactive (click the dragon) | Wallpapers must not demand attention |
| Shared/synced timers | Needs accounts and a server. v3 at earliest. |
| Music / generative audio | Enormous scope, easy to get wrong, not the pitch |

## Definition of done for v1

A person downloads one DMG, drags it in, sees a mountain landscape on their
desktop, and within two minutes sees a dragon slip behind a ridge. They open
Dragon Timer, set five minutes, forget about it, and get interrupted by
something beautiful instead of a beep. Then they leave the compact window open
all day even when no timer is running.
