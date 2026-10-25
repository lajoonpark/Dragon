# Scene & Composition

> One scene, deep enough to last. Handscroll, not backdrop.

---

## Why a handscroll

A 16:9 static backdrop runs out of content in about 90 seconds — you've seen
every pixel, and the pan becomes an obvious loop. The shanshui solution, used
for a thousand years, is the **handscroll**: a very wide image unrolled a little
at a time.

- World width: **7680 px** at 480 internal width = 16 screens of content.
- Pan speed ~7 px/s → **18 minutes** before anything repeats.
- Because it never reverses, we can vary composition left-to-right and it reads
  as travel, not as a loop.
- We can also vary **elevation** slightly across the scroll (steeper peaks in
  one region, water-dominant in another), so the world has "regions" without
  ever announcing them.

### Loop handling

At the very end, crossfade over 6 seconds back to the start through a heavy mist
wall — diegetically, the camera enters a cloud and emerges somewhere else.
This is the only honest way to loop a handscroll without a hard cut. Practically
it means the last 200px and first 200px are both pure mist, so no seams.

## Layout: the depth stack

```
depth 0.00  ── sky wash, sun/moon disc, few high wisps
depth 0.06  ── FAR PEAKS      (parallel mountain silhouettes, 3 values)
depth 0.14  ── mist band A
depth 0.22  ── MID PEAKS      (the karst spires — main visual identity)
depth 0.30  ── mist band B    (pavilion crags sit in this band)
depth 0.40  ── NEAR-MID RIDGE (closer rock forms, trees start)
depth 0.50  ── DRIFTING LOW MIST  (animated, wide)
depth 0.58  ── WATER PLANE    (+ reflections composited upward)
depth 0.70  ── NEAR ROCKS / PINES / BLOSSOM
depth 0.82  ── FOREGROUND SILHOUETTE (near-black, frames the view)
depth 0.90  ── ACCENT (lantern, branch that sways)
depth 1.00  ── vignette + grain
```

The **dragons fly between 0.05 and 0.85**, most often in 0.20–0.55 — the
valley. The foreground band exists to be flown behind.

## Mountain archetypes

Build a library of ~12 vertical rock forms; compose the world by placing and
mirroring them. Each archetype has:

- **Silhouette**: 1-bit mask, hand-pixelled. This is 90% of the work.
- **Value plan**: 3–6 flat bands assigned per depth ramp.
- **Striation detail**: 1–3 vertical dither/texture strips, only for near-mid
  and closer.
- **Base treatment**: bottom 20% fades into mist (hard alpha cut + dither),
  never a soft gradient.

Recommended archetypes (named, so we can talk about them):

| Name | Shape | Used for |
|---|---|---|
| `spire` | tall vertical needle, slight lean | far & mid peaks |
| `twin-spire` | two needles, one short one tall | far background rhythm |
| `cliff` | broad flat-topped mesa with vertical faces | near-mid, holds the pavilion |
| `crag` | lumpy, narrow-based island rock | in water / mist |
| `fold` | overlapping rounded ridges | far background, fills gaps |
| `pinnacle` | tapered tower with a distinct cap | focal peaks |
| `shelf` | horizontal ledge stack | near foreground |
| `arch` | natural stone arch | 1× per world, landmark |
| `islet` | tiny rock poking from water | water region |
| `wall` | tall near-vertical face filling an edge | framing |

### Rules for placement

- **Peaks at thirds.** Never centred. A peak dead-centre stops the pan.
- **Overlap at 2–3 planes minimum.** Every mid peak should have at least one
  far peak visible *behind* it and one near form *in front of* it. That triple
  overlap is what "depth without 3D" actually is.
- **Height variance**: keep at least one peak per screen in the top 15% of the
  frame and one that only reaches the middle. Constant height = wallpaper.
- **Never show a mountain base.** Everything is cut by mist or water. Showing
  a base reveals the ground plane and kills the floating-world illusion.

## Water

The water occupies the lower 25–35% of the composition, and it's the cheapest
grandeur in the project:

- Take the sky + far mist ramps, flip vertically, reduce contrast by 40%.
- Break it with **5–9 horizontal dash rows** of 2–6px dark marks, unevenly
  spaced, scrolling at ~half the camera speed.
- Add 1px near-white sparkle dashes, extremely sparse (~20 per screen), on a
  slow independent drift.
- Reflections must be **offset horizontally** by a per-frame wobble of ±1–2px,
  and the offset grows with distance below the waterline (shear).
- Reflections are clipped by any nearer foreground rock.

Dragon reflections are handled in `20-dragon-design.md` — worth repeating: this
one feature does more for the wallpaper than any other single effect.

## The human-scale anchor

Each ~1000px of the scroll should contain exactly one small human-made object.
Without it, the mountains have no scale and the whole thing reads as abstract
texture. Candidates:

- **Pavilion** on a crag (the reference image's icon — include exactly once,
  early, so viewers recognise the reference)
- **Stone bridge** between two near rocks
- **Small boat** with a single figure, on the water
- **Lantern** on a post, swaying 1px
- **Torii-like gate** — careful, may read as Japanese rather than Chinese; use
  a simple paifang-style gate if at all
- **Stairway** cut into a cliff face

Rules: 40px wide at most. Never lit. Never the focal point of a dragon's path
(the dragon should pass *near* it, not *to* it — otherwise it's a cutscene).

## Weather / time-of-day states

Ship v1 with **one** state, fully polished: *dawn mist, cool, calm*.
But architect for variants, because they're the obvious future content and
they're nearly free once ramps are data:

| State | Change | Feel |
|---|---|---|
| Dawn mist (v1) | cool blue-grey + warm cream | serene |
| Ink wash | 3 values only, near-monochrome, harsher | austere, striking |
| Dusk ember | shift mid-distance to warm haze, sky to amber | melancholy |
| Snow | desaturate 80%, add slow falling 1px flecks | quiet |
| Night storm | near-black foreground, lantern glow, rain dashes | dramatic |
| Storm | high wind, mist streaks horizontal, fast clouds | restless |

Each state is a palette table + a couple of particle toggles. No new art
required, which is exactly why we built on ramps.

## Shot list (v1)

The six dragon shots we ship first, in order of implementation value:

1. **`traverse-far`** — small, desaturated dragon crosses behind the mid peaks.
   Proves depth + palette. Easiest win.
2. **`weave-mid`** — dragon zigzags a valley, depth varying 0.25→0.55. Proves
   per-segment occlusion. This is the tech demo.
3. **`dive-hero`** — enters high far, dives through a mist band, exits low near.
   Proves depth-driven scale + palette shift + the mist ghost pass.
4. **`rise-behind`** — from behind a foreground rock, up into cloud. Proves
   foreground occlusion and gives a short, punchy moment.
5. **`traverse-reflect`** — crosses above the water, reflection below. Proves
   the reflection system.
6. **`coil`** — rare, circles a crag and coils. The "oh" shot.

Plus the Timer payoff shots (`40-timer-app.md`), which are a separate, more
explicit choreography.

## Density budget

To keep stillness: at any moment, the screen should contain
**0 dragons ~70% of the time**, 1 dragon ~27%, 2+ ~3%.
If it ever feels busy, the answer is always *fewer dragons, longer gaps*.
