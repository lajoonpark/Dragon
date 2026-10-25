# Depth & Occlusion — the core mechanic

> "Dragons should be able to slip behind mountains." This document is how that
> works, and why the answer is *not* "put the dragon on a layer".

---

## The problem with layers

The obvious approach: the scene is a list of layers, the dragon is a sprite, you
insert the dragon at layer index N. Done.

It fails at the first interesting shot. A dragon starts behind a mid-ground
ridge, then flies *forward* toward the viewer and ends up in front of the
foreground rocks. With layer-index ordering you must **pop the dragon between
layers at a threshold**, and the pop is visible — it happens all at once, for
the whole dragon.

Worse: a long serpentine dragon can never *dive through* a ridge. Head in
front, body inside the mountain, tail still behind. That's the exact shot the
reference image is begging for.

## The solution: per-pixel depth, per-body-segment depth

Two ideas, both cheap:

**1. The scene has a depth field.**
Every background layer renders into an 8-bit depth buffer alongside its colour.
Static content, computed once at scene-load (or per-pan-frame for a cheap
rebuild), never per-dragon.

**2. A dragon's depth is a function of its spine parameter.**
Not one depth per dragon. Each point along the body has its own depth,
interpolated from control points along the path:

```
depth(s) where s = 0 (head) → 1 (tail tip)
```

So the head can be at depth 0.30 and the tail at 0.75. The dragon is a *ribbon
that spans depth*, which is exactly what a long snake-like creature does when it
weaves between rocks.

The render test, per dragon pixel: `dragon_depth(x, y) < scene_depth(x, y)`.
Behind: skip the pixel. In front: write it. That's the whole thing.

```
   scene:  [ foreground rocks ][ mist ][ mid mountains ][ mist ][ far peaks ][ sky ]

   dragon:      tail .75 ──── body .55 ──── head .30
                   ↑ invisible          ↑ visible       ↑ visible
                   (behind rock)     (in the mist)   (in front of mist)
```

No authoring. No masking. No pop. And "fly in from the far peaks and land in
front of the foreground" is one continuous move in depth.

## Depth numbering

Normalised `0.0` = infinitely far (sky) … `1.0` = the glass of the monitor.
Suggested assignment:

| Depth | Content | Notes |
|---|---|---|
| 0.00 | sky wash + sun/moon | flat ramp, no detail |
| 0.06 | far peaks | ~85% desaturated, 3 values, no outline |
| 0.14 | far mist band | |
| 0.22 | mid peaks (the big spires) | 4–5 values, faint outline |
| 0.30 | mid mist band | where the pavilion crag sits |
| 0.40 | near-mid ridge | 5 values, outline appears |
| 0.50 | drifting low mist | *animated*, the prime dragon-hiding layer |
| 0.58 | water plane | reflection has its own depth trick |
| 0.70 | near rocks / pines | dark, 6 values, hard outline |
| 0.82 | foreground silhouettes | near-black, the frame |
| 0.90 | blossom branch / lantern | accent, animated sway |
| 1.00 | vignette / film grain | applied last, over everything |

Dragons live in `0.05 … 0.85`. Anything above `0.86` and they're occluded by the
frame itself, which we use deliberately: a dragon can pass *behind* the
foreground branch and be teased.

## Important subtlety: depth is not linear in screen space

A dragon flying at constant world speed should not move at constant screen
speed. Depth must also drive:

- **Scale**: `scale = lerp(0.55, 1.6, depth)` roughly — but quantised to whole
  pixels, never sub-pixel scaling of the sprite art. A far dragon is a
  *smaller sprite*, not a scaled one, where possible. Acceptable cheat:
  authored at 1× and 2×, and the far variant is a separate, simplified asset.
- **Speed**: `screen_speed = world_speed * scale`
- **Palette**: a dragon at depth 0.10 uses the far ramp (cool, desaturated,
  low contrast), at 0.80 uses the near ramp (dark ink, warm cream highlights).
  This is the single highest-value trick in the project — a distant dragon
  genuinely dissolves into the mist instead of looking pasted on.
- **Dither**: at far depths, the dragon's pixels are Bayer-dithered against the
  mist colour so it reads as *semi-transparent air*, not as a sprite.

## Reference implementation: painter's algorithm with a depth test

We are not doing real z-buffering of the scene. Two-stage:

```
STAGE 1 (static, once)
  for each background layer, back to front:
      blit colour into scene_color[]
      write layer.depth into scene_depth[]  (only where alpha > 0)

STAGE 2 (per frame)
  memcpy(working_color, scene_color)
  for each active dragon, sorted by mean depth (back to front):
      for each body segment, sorted along the spine:
          for each sprite pixel:
              if dragon_px_depth < scene_depth[screen_xy]:
                  blend/write into working_color
  then: low mist passes (animated, using a depth band)
  then: foreground layers that must always be in front (vignette, grain)
```

The dragon sort matters for *dragon vs dragon* only. Dragon vs scene is always
resolved by the test, so two dragons can interweave without any special casing.

## Cost

At 480×270 = 129,600 pixels:

- Stage 1 is one-time (or once per pan step if we rebuild rather than scroll).
- Stage 2: a dragon covering ~4,000 px does ~4,000 depth tests. Even with 6
  dragons that's ~24k comparisons/frame. At 30 fps: 720k/s. Nothing.
- Full-scene redraw without a depth test would be a single 129k-pixel blit.

**Conclusion: software rendering is completely viable.** This is deliberately
important — it means the entire renderer runs and is testable on Linux, in
Python/JS, no Xcode required, and we can dump PNG sequences to review animation
in a video editor. See `50-tech-architecture.md`.

## Alternative considered and rejected

**Per-dragon masking layers.** Author a mask for each mountain, hide the dragon
inside it. Rejected: doesn't scale to new paths, doesn't allow depth-varying
dragon bodies, and every new scene region is manual labour.

**True 3D (billboard quads in a 3D scene).** Rejected: it's 3D. The moment we
have a camera and perspective, the painting flattens into a diorama and we lose
the shanshui read. Also: affine texture-mapping wobble on pixel art is a
nightmare.

**Occlusion sprites / "roof" tiles over the dragon.** Cheaper than a depth
test, but equivalent work to author, and loses the free depth-varying body.

## The mist, specifically

Mist is not a vignette. Mist is a **depth band with movement**, and it must be
able to hide a dragon:

- 3 mist layers at depths 0.14 / 0.30 / 0.50.
- Each is a wide, tiling, low-contrast dither texture scrolling at
  `speed = parallax(depth)`.
- Each has a **soft top and hard bottom** (mist pools in valleys) or the
  reverse, depending on the band.
- Mist bands are also *draws* in the depth test: mist at 0.50 occludes a dragon
  at 0.45, and the dragon's silhouette faintly darkens the mist behind it via a
  one-pixel "ghost" pass — cheap AO that sells the volume.

That ghost pass is worth calling out: place a very low-alpha copy of the
dragon's silhouette *behind* the mist band it's passing through. The dragon
reads as being inside the fog rather than erased by it. This is the single
cheapest "wow" in the whole renderer.
