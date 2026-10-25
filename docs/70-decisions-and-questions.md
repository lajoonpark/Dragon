# Decisions log

> Why we chose what we chose. Append-only. If we reverse one of these, we add a
> new entry saying so and why — we don't quietly edit history.

---

### D-001 — Depth by per-pixel depth test, not layer ordering
**Decision.** The scene ships an 8-bit depth field; dragons are tested against
it per pixel, with depth varying along the body.
**Why.** Layer ordering can't express "head in front, tail behind" and forces a
visible pop when the dragon changes plane. The test costs ~24k comparisons per
frame and removes an entire category of authoring work.
**Rejected.** Per-mountain masking layers (doesn't scale, no depth-varying
body); real 3D billboards (destroys the flat painted read).

### D-002 — Body is procedural, heads are hand-drawn
**Decision.** The body is generated from a lagging rope + sine ribbon. The head
is 16 hand-pixelled directions.
**Why.** A serpentine 60px body across 16 directions × 8 wave phases is
hundreds of assets and none of them would be smooth. Procedural is ~20 lines
and infinitely smooth. But heads must be hand-drawn because that's where
readability and charm live, and rotating a 12×12 head destroys the pixel grid.
**Rejected.** Fully sprited dragon (asset explosion, stiff); fully procedural
head (mushy antlers, no character).

### D-003 — 15 fps, not 60
**Decision.** Default render at 15 fps, with 12/24/30 available.
**Why.** Pixel animation is traditionally on twos and threes; 15 fps is the
correct look, not a compromise. It's 4× cheaper, which matters enormously for a
wallpaper that runs all day. Pan and dragon motion are both stepped at the same
rate so the judder is consistent and invisible.
**Rejected.** 60 fps (feels like cheap CG, 4× power); variable timestep
(unreproducible rope sim → unreproducible bugs).

### D-004 — C99 core, Swift hosts
**Decision.** All art logic in dependency-free C99; macOS hosts in Swift/AppKit.
**Why.** We develop on Linux with no Xcode. Putting the art in C means we can
compile, run, and *look at* the actual product here, and drive it from Python via
ctypes for a 10-second iterate loop. Swift hosts then only handle windowing and
chrome — the part that genuinely needs a Mac.
**Rejected.** Swift core (can't run or verify here); a game engine (60MB runtime
for a 129k-pixel image, plus fighting the engine's idea of pixels).

### D-005 — Handscroll, not a looping backdrop
**Decision.** A 7680px world strip, camera pans one direction, loops once every
~18 minutes through a mist wall.
**Why.** A 16:9 static backdrop is exhausted in 90 seconds. The horizontal
handscroll is the native form of the painting style, gives variety for free, and
makes the pan read as travel rather than a loop.
**Rejected.** Static composition with drifting clouds (gets stale fast); tiled
repeating background (the repeat is instantly legible).

### D-006 — Dither is the depth cue, not alpha
**Decision.** Distance is expressed with Bayer dithering against the mist ramp
and palette desaturation. Alpha blending of dragon pixels is avoided.
**Why.** Alpha-blending pixel art produces mud and reveals the sprite edge.
Ordered dither reads as atmosphere and stays crisp at 1×.
**Rejected.** Per-pixel alpha (mud, banding artifacts, breaks the pixel grid).

### D-007 — Everything belongs to a named ramp
**Decision.** No ad-hoc colours. Every colour is a step in a declared 5–6 step
ramp, and there's a test that fails on any pixel outside the declared ramps.
**Why.** This is the single discipline that makes 20+ assets look like one
artist made them. Palette drift is how pixel art rots.
**Rejected.** Freehand colour picking (looks amateur within a week).

### D-008 — The camera stopping is the alarm
**Decision.** In Dragon Timer, the first frame of the alarm is the pan halting.
**Why.** The user has been trained for hours that this image moves. When it
stops, they feel it before they see anything, with zero pixels spent. It's the
cheapest and most elegant notification in the design.
**Rejected.** Sound-first (hostile, unearned); a modal (interrupts, steals
focus).

### D-009 — Wallpaper and Timer are one world, two hosts
**Decision.** Shared `DragonKit` core; timer defers the alarm choreography to the
wallpaper when present, and performs it itself when absent.
**Why.** Makes the two apps feel like one product rather than a bundle. The
timer owns the clock; the wallpaper is a dumb performer, which also means the
timer works standalone.
**Rejected.** Timer rendering its own separate alarm art (two art styles, twice
the work, no cohesion).

### D-010 — Build the `.saver` and video fallbacks before shipping the wallpaper
**Decision.** Ship three delivery mechanisms in this order of fallback:
desktop-level window → screensaver bundle → exported video.
**Why.** Desktop-level windowing is the one genuinely unknown, OS-version-
dependent part of the project (Spaces, Stage Manager, notch, full-screen). Having
a zero-risk fallback means a new macOS release can't sink the product.
**Rejected.** Betting everything on one windowing technique.

### D-011 — The dragon looks at the viewer exactly once, ever
**Decision.** Never in the wallpaper. Once, at t≈4s, in the timer alarm.
**Why.** Breaking the fourth wall destroys the calm that makes the wallpaper
work. Doing it exactly once, at the moment the user is being addressed, is what
makes the alarm land.
**Rejected.** Ambient eye contact (uncanny, kills the mood).

---

## Open questions

| # | Question | Why it matters | When to resolve |
|---|---|---|---|
| Q1 | 480×270 or 512×288? | Composition room vs. exact ×4 at 1080p. 480 gives exact 4× and a slightly wider aspect feel; 512 gives more vertical room for peaks. | Phase 1 |
| Q2 | Does the desktop-level window survive Stage Manager on the current OS? | Gates the entire delivery model | Phase 3 spike, first |
| Q3 | 16 head directions enough, or do we need 32 for the slow near passes? | 32 doubles hands-on art time | Phase 1, after seeing 16 |
| Q4 | Should there be *one* elder/ivory dragon with a different body (longer, whiskers, dorsal fin) or just a recolour? | Recolour is cheap but reads as a palette swap; a unique rig is 2× work but becomes the "rare, magical" moment | Phase 2 |
| Q5 | Is a portrait/vertical composition needed for phone-as-second-screen uses? | Would need a second world strip; big scope | Post-v1 |
| Q6 | Free, paid, or donation? | Affects onboarding, updates, and whether MAS sandbox constraints matter | Phase 5 |
| Q7 | Do we want the pan to ever reverse direction, or hold a wide shot for a minute? | Holding a wide shot would let a `coil` shot breathe | Phase 2 |
| Q8 | How do we handle the user's own music (ducking vs. silence)? | Affects the audio design and possibly an audio-session permission | Phase 4 |

## Things we'll probably be wrong about

Kept honest on purpose:

- **The dragon may be too small to read at far depth.** If a 24px dragon
  dithers into the mist so much that nobody sees it, the depth range needs
  compressing. Watch for this in Phase 1, not Phase 5.
- **15 fps may judder unpleasantly at a 120 Hz display** if the host doesn't
  frame-lock cleanly. Fixable with an integer divisor, but worth measuring.
- **The 55s mean gap may be far too long** for a wallpaper people only glimpse.
  First-run should show a dragon within 20s, and we should probably bias toward
  more dragons than the stillness principle suggests.
- **Writing the core in C may feel slow to iterate on art.** If so, the answer is
  a hot-reload of `assets/` (plain-text silhouettes), not switching languages.
