# Depth test — does the core mechanic actually work?

**Verdict: yes. It works, with no layer stack, on the real master image.**

This is the answer to the question the whole project was hanging on: can a single
unbroken dragon body be partly *in front of* the scenery and partly *behind* it,
without layers, masks, or pop? Yes — with one depth test per pixel.

## What was built

| File | Role |
|---|---|
| `tools/pipeline/author_depth.py` | derives `out/depth_c01.png` from the reduced master |
| `tools/pipeline/fly_dragon.py` | renders a dragon through it and asserts the mechanic |
| `out/dragon_depth_test.png` | 10-frame contact sheet |
| `out/dragon_depth_test_zoom.png` | the straddle frame at 3× |
| `out/dragon_depth_test.gif` | the actual motion |

## The result

```
  t     x    in front  occluded   verdict
  0.00   345      351       646   straddling
  0.22   297      715       494   straddling
  0.33   273      908       359   straddling
  0.44   249      811       456   straddling
  1.00   130      610       657   straddling
```

**10 of 10 frames have one body both in front of and behind scenery.** That is
the mechanic, and it is not a mock — it is the real scene depth doing the work.

The zoom frame is the money shot: head visible in open mist, neck swallowed by a
mid spire, body re-emerging on the other side. One sprite, one depth field, no
masks.

## The convention bug this found

`docs/10-depth-and-occlusion.md` had the ASCII diagram **inverted**. It drew
`head .30` as "visible" against `.22` scenery, but with `dragon_depth <
scene_depth = occluded`, a `.30` dragon is *in front of* a `.22` ridge — the
diagram's arrows were pointing the wrong way, and its "behind rock / visible"
labels were swapped.

The numbering table and the test formula in the same doc were correct, so this
was a diagram-only error — but it is exactly the kind of error that gets copied
into code. Fixed, and `check_convention()` now asserts it:

```
  sky  0.027 (11.7% of frame)
  near 0.865 (28.2% of frame)
  spread 0.838
  dragon@0.42: in front of sky, behind near rock     OK
```

Two other bugs it caught, both mine, both in the harness:

1. **Ghost accumulation.** Frames were composited onto the *previous* frame, so
   the "ghost" pass (a faint silhouette painted onto mist so an occluded dragon
   reads as inside fog rather than erased) accumulated across all 16 frames and
   built a washed rectangular slab. The renderer is stateless per frame.
2. **Assertions against the wrong pixels.** The first convention check sampled
   `x 5..40` as "sky" — that is a tree branch. It failed for the wrong reason.
   The check now selects regions *from the depth field itself* (`< 0.10`), so a
   stray coordinate cannot fool it.

## How the depth field is built, and its one real limitation

`author_depth.py` segments rock as connected dark masses, then assigns each mass
ONE depth from its mean luminance. Sky gets 0.03, mist 0.15, rock 0.24–0.84 in
six steps, water 0.96.

Distribution is sensible: near 28.2%, near-mid 15.2%, mid 10.1%, far 0.9%, sky
11.7%, water 6.2%.

**The limitation:** because depth is per-connected-mass, the two giant framing
massifs each get a single depth for their whole extent, even though they visibly
recede from foreground to mid-background. A dragon at 0.42 passes in front of
*all* of the left massif, including its far-looking upper reaches.

This is acceptable for v1 — those massifs are continuous walls, so there is no
gap behind their upper parts for a dragon to be seen through anyway — but it is
the thing a hand-painted depth field fixes, and it is why:

## Recommendation: hand-paint the depth field, keep the auto version as a base

The auto field is a **starting point, not the final asset.** It is right in the
easy 80% (sky, mist, water, distinct spires) and wrong in the hard 20% (the big
continuous walls). Painting corrections over it at 480×270 is a couple of hours,
versus a day for a full layer split.

Crucially, this means **we do not need to split the image into layers at all.**
That was the original plan, and the split was going to need backing plates for
every hole. The depth-field approach sidesteps holes entirely: nothing is ever
removed from the image, so nothing can be exposed.

## What this does NOT yet answer

- **Panning parallax.** A single image pans as one rigid plane. Depth-correct
  parallax needs either a layer split or a per-band displacement, and we have
  not tested that. At 7px/s over a 4-screen world this may simply not matter.
- **The wrapping corridor.** The dragon flew a straight horizontal line. The real
  design needs a path that re-enters from the far side, which may need the
  depth field to be temporally consistent at the seam (D-019).
- **Dragon silhouette quality.** The test sprite is a swept tube, not art. It
  proves the composite, not the look.
