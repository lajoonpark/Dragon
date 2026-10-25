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

### D-012 — Dragons ~50% of the time, ~30s mean gap
**Decision.** Revised from ~70% empty / 55s mean. New: 0 dragons ~50%, mean gap
~30s, min 12s, max 90s, pairs ~8%. First dragon 8s after launch.
**Why.** User direction: 55s felt too sparse — the wallpaper risked being a
pretty picture you glance at and see nothing. More presence makes it feel
inhabited.
**Consequence, and it's the important part.** Half the time the landscape is on
screen alone, so *ambient life becomes load-bearing*, not decoration. This forced
D-013.
**Rejected.** Keeping 55s and fixing it with more ambient motion only — that
makes a busy screensaver with rare dragons, which is the worse failure.

### D-013 — Ambient life is a system with a measured budget
**Decision.** Three tempo tiers (slow world / medium weather / fast
punctuation). 2–4 systems active at once, region-gated, deterministic. Ambient
density is asserted by a test: `frame_delta / 129600` must sit in **0.30%–1.20%**
with no dragon, per region.
**Why.** "Interesting enough" is subjective and we can't eyeball it on a Mac.
An objective band catches both failure modes — frozen (<0.10%) and busy
(>2.50%) — mechanically. Crude, but it's a tripwire, and it beats good
intentions.
**Rejected.** Piling on effects until it feels alive (becomes a screensaver and
kills the dragon's read).

### D-014 — Wind is a travelling gust field, not per-object sway
**Decision.** One global `gust(x, t)` — three overlapping travelling waves plus
a slow strength envelope — sampled by every deformable thing at its screen x.
**Why.** Per-object random-phase sine sway is the single loudest tell of an
animated GIF. Objects bending *together*, with quiet gaps between gusts and a
consistent direction (opposing the pan, so it feels like a headwind), is what
turns motion into weather. It's ~30 lines and it drives grass, reeds, branches,
petals, mist edges, and dragon whiskers.
**Rejected.** Per-object independent oscillation (reads as a shader effect).

### D-015 — Ambient life yields to dragons (the hush)
**Decision.** On dragon spawn, `ambience_gain` 1.0 → 0.65 over 2s; slow settle
back over 4s. Petal spawn halves, birds suspend, gusts weaken, sparkle thins.
Mist and waterfalls keep going.
**Why.** It resolves the busy/frozen tension *structurally* instead of by
endless tuning. It also makes the dragon feel like a physical presence
displacing air rather than a sprite on top of an animation — users can't say
what changed, but they feel the dragon matter.
**Rejected.** Constant ambient level (dragon has to compete); full stop (scene
looks dead when a dragon appears).

### D-016 — Waterfall is a required v1 element
**Decision.** At least one waterfall per ~2500px of world, with a scrolling
dithered core, side haze, a pulsing base mist, and spray flecks.
**Why.** Highest value-per-pixel in the project: permanent gentle motion (kills
the frozen failure outright), a colossal scale anchor that makes the peaks
legible, a vertical compositional event in a horizontal scroll, and it's static
geometry with an animated texture. It also participates in the depth test, so
dragons can be half-erased by its spray.
**Rejected.** Treating it as optional polish.

### D-017 — macOS first, but the core is platform-blind from day one
**Decision.** All OS contact goes through a 10-function `dr_host` vtable (4
required: `now`, `present`, `prefs_read`, `prefs_write`). `core/` contains zero
platform `#ifdef`s, enforced by a CI grep. A `platform/null` stub host exists
from Phase 0 and is always in the test suite.
**Why.** User requirement: Windows and Linux must not need a rewrite. The risk
isn't architectural, it's five small discipline failures (a direct `NSLog`, a
CoreGraphics type leaking upward, an absolute path). A grep test and a null host
catch all of them cheaply. Getting this right on day one costs nothing; getting
it wrong costs a rewrite per platform.
**Estimated port cost with discipline:** ~2 weeks for web + Windows + Linux X11.
Without it: ~2 months each.
**Rejected.** "We'll extract the core later" — extraction after the fact means
untangling rendering from the platform surface, which is exactly the painful
part.

### D-018 — The core never touches a platform surface
**Decision.** Core writes to its own RGBA buffer; the host presents it. No
CoreGraphics/Metal/GDI/X11 drawable ever reaches core. Same for assets (plain
text, compiled in), the clock (host provides `now()`, core does fixed-timestep
math), and IPC (JSON lines through `bus_send`/`bus_poll`).
**Why.** These four leaks are what actually make ports expensive. Named
explicitly so we can refuse them at 1am.

### D-019 — Silhouettes are hand-authored; the tool never invents rock
**Decision.** Karst silhouettes are drawn by hand (Aseprite, stored as ASCII in
git). Value planes are *declared* as row-width fractions. The compositor owns
palette, dither, depth, mist, water, placement and animation — never shape.
**Why.** Six procedural generators were built and all six failed, each
differently: candles (taper formula), 3D-mesh noise, tombstones (values without
facets), tablecloths (dither-as-fill), postage stamps (one archetype repeated).
Only the hand-authored ASCII silhouette read as karst. Shape is a decision, and
decisions resist automation.
**Rejected.** Procedural generation (six attempts, no); SVG (anti-aliased by
definition, wrong model — see `25-art-pipeline.md`).

### D-020 — Variety via mirror + depth + authored overlays, not new silhouettes
**Decision.** 10 hand-drawn archetypes × 2 mirrors × 3 depth/palette
assignments × authored overlay stamps (ledges, cracks, tree bundles) to fill a
7680px world with 50–70 distinct-looking peaks.
**Why.** Hand-painting 60 unique mountains is weeks; hand-painting 10 is a
weekend. Overlays are the underrated piece — a 16×24 "ledge with three pines"
stamp at different heights makes a peak read as a different location. Free
rotation is banned; it destroys the pixel grid.
**Rejected.** One archetype scaled and repeated (v5 — legible as wallpaper
within seconds).

### D-021 — Dither is a transition, never a fill
**Decision.** `dith()` writes nothing below alpha 0.12 and writes solid above
0.78. Only the band between is actually dithered.
**Why.** v4 used dither as a fill and produced checkerboard fields that ate the
entire image. This is a one-line rule that cost a full iteration to learn.
**Rejected.** Unconditional `bayer < alpha` writes (looked correct in isolation,
destroyed the composition).

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
| Q9 | Are 30s-mean dragons too frequent — do they become furniture, like a fish tank? | If yes, the fix is lengthening *hero* shot rarity, not lowering the common traverse rate | Phase 3, from real all-day use |
| Q10 | Does the ambience delta band (0.30–1.20%) actually correlate with feeling alive? | The whole ambient budget rests on this proxy | Phase 2.5 |
| Q11 | Wayland/GNOME desktop-window support — attempt or scope out? | GNOME fundamentally disallows background-layer clients | Phase 6 |

## Things we'll probably be wrong about

Kept honest on purpose:

- **The dragon may be too small to read at far depth.** If a 24px dragon
  dithers into the mist so much that nobody sees it, the depth range needs
  compressing. Watch for this in Phase 1, not Phase 5.
- **15 fps may judder unpleasantly at a 120 Hz display** if the host doesn't
  frame-lock cleanly. Fixable with an integer divisor, but worth measuring.
- **30s mean may be too frequent.** Now that dragons are on screen half the
  time, the risk inverts: they stop being an event and become furniture. The
  mitigation we're betting on is *variety* (6 shot types, 5 palettes, wide depth
  range) plus a strong hush — not a lower rate. If that bet fails, lengthen only
  the hero shots' rarity and leave common traverses alone.
- **The ambience delta band may be the wrong proxy.** 0.3–1.2% pixel change is
  measurable, but "alive" might be about *coherence* (a gust travelling) rather
  than volume. If the number passes and it still feels dead, trust the eye over
  the test and change what's moving, not how much.
- **`gust()` may fight the dragon.** Whiskers and mist driven by the same field
  as the grass could make dragons look wind-blown rather than self-propelled.
  Likely fix: dragons sample gust at reduced weight, with a phase lag.
- **Writing the core in C may feel slow to iterate on art.** If so, the answer is
  a hot-reload of `assets/` (plain-text silhouettes), not switching languages.
- **The `dr_host` abstraction may be slightly wrong on first contact with
  Windows.** Expect one interface change at the first port; that's cheap and
  expected. Two or three would mean the abstraction is bad, not unlucky.
