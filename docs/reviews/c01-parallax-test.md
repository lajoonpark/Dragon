# Parallax test — do we need layers after all?

**Verdict: no. Rigid pan. Decision recorded as D-026.**

This tested the last open question on the background: whether a single flat image
pans convincingly, or whether real depth parallax requires splitting it. The
answer is that splitting is not just expensive here — on a single flat image it
is **not possible without visible damage.**

## Three approaches, measured

All at the documented 7 px/s (`docs/30-scene-composition.md`), 480×270.

| Approach | Undistorted? | Result |
|---|---|---|
| Stack depth bands, shift each | No | **Tears.** Uncovered strips at every depth boundary — the hole problem (D-024), in motion |
| Inverse-warp per depth | No holes, but | **Smears**, and degrades linearly with time |
| **Rigid pan** | Yes, forever | 0.0% distorted by definition |
| Rigid + drifting mist | Yes | Contrast 67.9 vs 67.3 base; 88% detail retained |

### Smeared-pixel fraction, inverse warp

```
 span   t     stretch   smeared>1.5
 0.00  24s    1.000      0.0%     rigid
 0.15  24s    1.004      1.1%     subtle
 0.30  24s    0.996      6.1%     noticeable
 0.85  24s    0.970     11.2%     broken
```

At 24 seconds, span 0.85 already looks like the mountains are melting — see the
bottom row of `docs/review/pan_sweep.png`. And the damage grows *linearly with
time*, which is fatal for a wallpaper: it runs for hours.

## Why this is fundamental, not a bug

I tried two fixes before concluding:

1. **Smoothing the warp field** (σ=10) to stop tears. It removed the tears and
   replaced them with smearing. Both are the same underlying failure.
2. **Wrapping instead of clamping** at the edges, to remove a leftover banding
   artefact from the harness. Correct fix, but it exposed the real problem
   underneath.

The real problem is information-theoretic. **Parallax works by revealing what is
behind nearer things.** A flat image contains nothing behind its mountains — the
pixels that would be revealed were never drawn. Any method that asks for them
must invent them, and the only raw material available is stretching existing
pixels.

So there is no cleverer warp. The content simply is not there.

## The one thing that does work: mist

Structure is what smears. **Mist has no structure**, so it can be displaced
independently and the eye cannot see a shape change.

That gives a cheap, honest depth cue:

```
background   rigid pan, 7 px/s        undistorted, guaranteed
mist veil    drifts at 9.5 px/s       within the 2-5px/s already specified
dragons      depth-tested vs scene    the real depth cue
```

The depth cue that actually sells the illusion is **occlusion** — dragons
passing behind ridges — and that is already proven working
(`c01-depth-test.md`). Parallax was always going to be a subtle second-order
effect at 7 px/s, over a scene where every element is at a similar distance.

Measured on the mist version: `docs/review/pan_mist.png`. Contrast is preserved
(67.9 vs 67.3); 88% of high-frequency detail survives. The mountains stay crisp
through the whole 24 seconds. My crude auto-extracted veil washes the mist a
little bright — a production veil would be painted, not extracted — but the
technique is sound and cheap.

## What this retires

**The layer split is off the project.**

Combined with the depth-field result, both halves of the old "hole problem" are
now closed:
- nothing is ever *removed* from the image (depth field, not layers), so nothing
  can be uncovered by a dragon;
- nothing *slides* relative to anything else (rigid pan), so nothing can be
  uncovered by motion.

There are no backing plates to author. That was previously the largest unknown
piece of work in the plan.

## What we give up

A dragon cannot slip behind a near massif *while that massif moves at a different
rate*, because the massif does not move at a different rate. If the flatness ever
becomes objectionable, the remedy is not a layer split — it is **two or three
authored mist planes** at different depths, which are cheap precisely because
they are structureless.

## Files

```
tools/pipeline/pan_test.py     rigid vs banded, direct comparison
tools/pipeline/pan_sweep.py    parallax strength sweep + stretch metric
tools/pipeline/pan_mist.py     rigid pan + independently drifting mist
out/pan/pan_compare.png        rigid (top) vs banded (bottom)
out/pan/pan_sweep.png          rigid / subtle / strong
out/pan/pan_mist.png           the recommended result
out/pan/pan_rigid.gif          motion, rigid
out/pan/pan_banded.gif         motion, banded (for comparison)
out/pan/pan_mist.gif           motion, recommended
```
