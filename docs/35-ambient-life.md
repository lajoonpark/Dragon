# Ambient Life — making the empty screen worth watching

> If there is no dragon half the time, the landscape itself has to carry the
> piece. This document is the answer to "what is happening when nothing is
> happening."

---

## The tension we're solving

Two failure modes, and they're the same failure from opposite ends:

- **Frozen.** The scene is beautiful but static. After 20 seconds the eye has
  nothing to do and the whole thing reads as a JPEG with a slow scroll. This is
  the default failure of every "minimal" wallpaper.
- **Busy.** We add motion everywhere to fix that: petals, birds, mist, wind,
  ripples, fireflies... and now the dragon has to compete for attention and the
  stillness that made the reference image good is gone.

The resolution is not "more motion" or "less motion". It's **three tempos and a
hierarchy**, plus a rule that ambient life always *yields* to a dragon.

## The measurement that keeps us honest

"Interesting enough" is subjective until you count pixels. Let's define it:

```
frame_delta = pixels differing from the previous frame
ambience = frame_delta / (480 × 270)        // = /129,600
```

At 15 fps, with no dragon on screen:

| Ambience | Read |
|---|---|
| < 0.10% (~130 px) | **frozen.** Mist only, nothing alive. Fail. |
| 0.30% – 1.20% (~390–1550 px) | **alive.** This is the target band. |
| > 2.50% (~3240 px) | **busy.** The dragon will not read. Fail. |

We can assert this in a test, per region of the handscroll. It's a crude number
but it's *objective*, it's cheap, and given we develop on Linux and can't sit
and stare at it on a Mac, an objective tripwire beats good intentions. The
number is a smell test, not an aesthetic — but it catches "I added seven systems
and now it's a screensaver" instantly.

## Tempo hierarchy

Three independent clocks. Never let one tempo dominate the composition.

### Slow (~0.02 Hz, 20–60s periods) — the world
Things that are almost imperceptibly moving. You only notice if you look for a
while, and *that's the reward for looking*.

- Camera pan (7 px/s)
- Mist bands drifting (2–5 px/s, per-depth)
- Tall grass / reeds leaning, recovering (period 30–60s)
- Water surface dash rows (4 px/s)
- Cherry branch very slight sway (period ~45s)
- Cloud edge deformation

### Medium (~0.2 Hz, 3–8s periods) — the weather
The things that make it feel like there is air.

- **Wind gusts** sweeping across the scene (the big one — see below)
- Waterfall plume flicker + base mist pulse
- Petals and leaves falling
- Pine needle clusters shivering
- Ripples on water
- Distant waterfall haze breathing

### Fast (~1–3 Hz) — the punctuation
Small, sparse, and short-lived. These are what stop it reading as a lava lamp.

- Bird flecks crossing (2-frame wing flap)
- A fish disturbing the surface (one ring, then gone)
- Lantern flame flicker (2px, irregular, not a sine)
- A single leaf detaching and falling
- Dragonflies over the water in summer

**The rule:** fast elements must be *sparse and local*. Ten bird flocks at once
is noise. One bird flock every few minutes is a gift.

## Wind: gusts, not sway

The single biggest difference between "beautifully animated" and "clearly an
animated GIF" is whether the wind is *coherent*.

A constant sine sway, per-object with random phase, reads as a shader effect.
Real wind is a **gust envelope that travels across the scene**, and every
deformable object samples it at its screen position:

```
gust(x, t):
    // 3 overlapping travelling waves, prime-ish periods, so it never repeats
    for k in 0..2:
        phase = (x / gust_wavelength[k]) - t / gust_period[k]
        g += weight[k] * smoothstep(-1, 1, sin(phase * 2π))
    return saturate(g) * gust_strength
```

Then each deformable object (grass, branch tips, petals, mist edge, dragon
whiskers) deflects by `gust(x_object, t) * local_susceptibility`.

Properties that matter:

- **Gusts travel in a consistent direction** — and it should be *opposite* to
  the camera pan heading, so it feels like flying into the wind. Cheap and it
  reads as weather, not as noise.
- **Objects near each other bend together.** That single property is what makes
  it feel like air with a body. Random per-object phase instantly destroys it.
- **Gusts have quiet gaps.** `gust_strength` itself is modulated by a slow
  envelope so there are calm seconds between gusts. Constant wind = wallpaper
  pattern; gusty wind = weather.
- **Tall things bend more than short things.** Susceptibility scales with
  height above the object's base, and quadratically — tips whip, bases don't.

This one system drives grass, reeds, branches, pine clusters, petals, mist
edges, and dragon whiskers. It's maybe 30 lines and it's the difference between
"nice" and "I can't stop looking at it."

## The ambient systems

Ranked by value per pixel. Build in this order.

### 1. Waterfall (highest value, insist on it)
Every shanshui painting has one. It is:
- A **constant gentle motion** source — solves the frozen problem permanently.
- A **colossal scale anchor** — a 200px waterfall makes the peaks legible.
- **Cheap**: static geometry, animated 1–2px dithered texture, scrolling down at
  2–3× pan speed.
- **Compositionally useful**: it's a vertical event in a horizontal scroll, so
  it breaks the pan rhythm.

Build: 2–3px wide vertical core (near-white dithered), 4–6px of falling haze
either side, a **base mist puff** that pulses at ~0.2 Hz, and a few 1px spray
flecks with parabolic arcs. Placed at a cliff face, one per ~2500px of world,
roughly.

The base mist puff also participates in the depth test, so a distant dragon
flying behind the waterfall is partially erased by it. Gorgeous.

### 2. Petals / blossoms (explicitly requested)
You asked for cherry blossoms wafting. Design:

- Spawn **only from blossom trees**, and only from off-screen ones, so petals
  *enter* the frame rather than popping into existence.
- 1px, occasionally 2×2 for near ones. 3 variants (petal / leaf / tiny cluster).
- Fall speed 6–14 px/s, with a **sinusoidal horizontal drift** whose period is
  3–6s and amplitude 4–12px, plus `gust()` deflection. This is what makes them
  "lazily waft" rather than fall.
- Rotation: 2 frames, cycling every 8–20 frames. At 1px this reads as tumbling
  and costs nothing.
- Count: 30–70 concurrent during a blossom region, 0 elsewhere. Density must
  vary — constant density looks like a particle system, which it is and mustn't.
- **On landing in water**: spawn a 1px ripple ring that expands to 5px over ~1s
  and vanishes. This is *the* detail people screenshot.
- **On landing on rock**: lie there for 20–60s, then vanish. Accumulation over
  time makes the world feel inhabited and it's 4 lines of code.
- Petals are also carried by `gust()`, so a gust visibly detaches 5–10 at once.
  That moment is worth building the whole wind system for.

### 3. Birds (rare, high impact)
- 1px each, 3–7 in a loose flock, all flapping on the same 2-frame cycle with
  ±1 frame offset per bird.
- Cross in 4–8s at far or mid depth. Never near.
- **Extremely rare** — one flock per 3–5 minutes. Their value is entirely in
  their rarity.
- They're a **scale cue**: a flock crossing behind the spires tells you the
  spires are enormous. This is doing real compositional work, not decoration.
- Flock path is a shallow arc, not a straight line, and they should be *slightly*
  sloppy — one bird off the line.

### 4. Grass / reeds
- Foreground and near-mid only. 1–2px blades.
- Bend with `gust()`, susceptibility ∝ height². A gust visibly ripples through
  a patch, 3–5 frames from one side to the other.
- In still air they have a micro-motion (~0.15 Hz, 1px) so they're never
  perfectly frozen.
- Place in clumps, never evenly. Evenly-spaced grass is the loudest tell of a
  procedural scene.

### 5. Water
- Surface dash rows scrolling at ~half pan speed (already in the scene doc).
- Sparkle dashes: ~20 per screen, each flashes once every 8–20s, 1px, then gone.
- Occasional ripple ring from a fish (1 every 30–90s per water region) — one
  expanding ring, 4px max, gone. Never two at once.
- Ripple rings from petals landing (see above).

### 6. Mist edge breathing
- Mist band edges deform with a very low-frequency noise, ~1px amplitude.
- This alone fixes 60% of the frozen problem and costs almost nothing.

### 7. Lantern flame
- 2×3px, 3 irregular frames, switching on a **random** schedule (not a loop).
- Only on the one lantern per region, if that region has one.
- Its point is to be the warmest, most saturated pixel on screen in an otherwise
  cool image. One accent, no more.

### Deliberately rejected
- **Fireflies / glowing particles.** Read as "magic" not "nature"; they also
  compete with dragons for the eye.
- **Full cloud systems with shadows.** Way too much motion, and shadows imply a
  sun direction and a ground plane, which breaks the floating-world read.
- **Rain (for v1).** Whole separate system; a weather state, not an ambient layer.
- **Constant particle snow.** Becomes texture within a minute. If we do snow, it
  must be sparse and gusty.

## The hush rule (the most important rule here)

**When a dragon enters, ambient life yields.**

- On dragon spawn, `ambience_gain` ramps from 1.0 → 0.65 over ~2s. Petal spawn
  rate halves, bird spawns suspend, gust strength drops ~25%, water sparkle
  thins.
- On dragon exit, it ramps back over ~4s (slower than it dropped — the world
  *settles*).
- Exception: mist and waterfall keep going. They're the landscape, not the life.

Why this matters: it makes the dragon feel like a *physical presence displacing
the air*, not a sprite pasted on top of an animation. And it solves the busy/
frozen tension structurally instead of by tuning numbers forever. The scene
breathes: full of small life, then it holds still for the dragon, then it
resumes.

The hush is also perceptible. Users won't be able to say what changed, but they
will feel that the dragon is *important*. That's the whole goal.

## Regions: variety through travel

The other half of "the background must be interesting" is **not** piling up
effects — it's that the handscroll *changes* as you travel through it. Solve
novelty with composition, not with motion.

Suggested ambient character per ~1500px region:

| Region | Signature life | Dragon feel |
|---|---|---|
| **Mist harbour** | still water, boat, few petals, gulls | far traverses |
| **Blossom valley** | heavy petals, blossom trees, birds | mid weaves |
| **Waterfall gorge** | waterfall, spray, roaring mist, no petals | dives through spray |
| **Reed marsh** | reeds, dragonflies, ripples, low haze | low fast passes |
| **High cold peaks** | snow flecks, no life, huge silence | the `coil` shot |
| **Pavilion terrace** | lantern, one tree, very quiet | reflective, slow |

Six regions ≈ 9000px, close enough to the 7680px world; we can drop one in v1.

The key property: **each region has a different *absence*.** The cold peaks are
interesting because nothing lives there. That contrast is worth more than any
particle effect, and it's free.

## Scheduling (the ambience director)

Don't run every system everywhere. A tiny director with the same seeded-PRNG
determinism as the dragon scheduler:

- Each region declares which ambient systems are *eligible*.
- At any moment, **2–4 systems are active**, weighted, crossfading over ~10s at
  region boundaries.
- The director also schedules the rare beats (bird flock, fish ripple, leaf
  detach) on its own weighted-random gaps, so they never coincide with a dragon
  spawn by accident.
- Deterministic from `(world_seed, region_index)` so the golden-frame tests hold.

## Pacing, revised

Per your direction — dragons more present, ~50% of time with none:

| Parameter | Old | **New** |
|---|---|---|
| Time with no dragon on screen | ~70% | **~50%** |
| Mean gap between dragons | 55s | **~30s** |
| Min gap | 20s | **12s** |
| Max gap | 240s | **90s** |
| P(2 dragons overlapping) | 3% | **8%** (pairs are lovely, and now affordable) |
| First dragon after launch | 55s | **8s** (first impressions) |

Two consequences to accept:

1. **Dragons now sometimes share the screen.** That's good (it's a *range* of
   mountains, not a pet), but it means the dragon-vs-dragon sort in the
   compositor actually matters, and shots should be authored to not overlap in
   the same screen region. The 8% figure is where pairs still feel like an event
   rather than a crowd.
2. **The scene will get more scrutiny**, because it's on screen alone half the
   time. Hence this whole document. The ambience delta test is now a
   ship-blocking test, not a nice-to-have.

Worth flagging: I think 30s mean might still be slightly *too frequent* to keep
dragons feeling special — the risk is they become furniture, like a fish tank.
The mitigation isn't to lower the rate, it's to keep **variety** high (6 shot
types, 5 palettes, huge depth ranges) and keep the **hush** strong so each one
still stops you. If by Phase 3 it feels like furniture, the fix is lengthening
only the *hero* shots' rarity, not the common traverses.
