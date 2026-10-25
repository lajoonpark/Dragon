# Layer r47 — SELF-review (not independent)

> **Provenance warning.** This is my own review of my own output. The independent
> reviewer could not be launched for r47 (three attempts; no child conversation
> was created). r06, r11 and r25 were genuinely independent and their verdicts are
> in this folder unchanged. This document is *not* equivalent to those, and should
> be replaced by a real review before r47 is considered accepted. It is kept
> because the findings are specific and testable, and because throwing away a
> known-defective verdict is worse than labelling it.

Image: `docs/review/layer_r47_flat_1x.png` (primary), `-2x`, and the RGBA layer.

## VERDICT: FAIL

## SCORES
`reads_as_mountains=4 verticality=4 painterliness=2 wallpaper_endurance=3`

## GATES

1. **Reads as mountains at 1x — PASS.** Unambiguously a layered rock range; no
   barcode, no plateau, no noise read.
2. **Distinct summits, not one repeated archetype — FAIL.** The centre valley has
   genuine variety (dome, shoulder, mesa, spire are all legible). But the **left
   and right flanks are a string of identical chevrons** — eight or so evenly
   sized, evenly spaced triangles marching up each edge. That is the r11 sawtooth,
   relocated to the flanks rather than eliminated. The valley was authored; the
   flanks were not.
3. **No vertical striping — FAIL (mild).** Interior slab boundaries are visible in
   the near dark mass as soft vertical divisions, roughly 20–30px apart. They no
   longer read as a barcode because they are slanted, but they are still legible
   as columns rather than as facets of one form.
4. **No horizontal rulers — FAIL.** The middle third reads as horizontal tiers:
   three or four near-parallel pale-to-dark bands stacked across most of the frame
   width. The mist boundaries at the bottom reinforce it. The rock is divided by
   *row*, not by *form*.
5. **Atmospheric perspective — PASS.** Far ridges are clearly paler and flatter in
   contrast than the near mass; the recession is legible without explanation.
6. **Warm lit faces / cool shadow faces — FAIL.** The rock is a single cool blue
   ramp from pale grey-blue to dark slate. There is no warm light anywhere on the
   stone. The 33% "warm pixel" figure is almost entirely the **cream mist**, not
   the mountains — so the audit metric is measuring the wrong thing and passing a
   real defect. The reference's defining quality is cream light against cool
   shadow; this image does not have it.
7. **Mist pools and is not a band — FAIL.** The mist is a full-width cream sea with
   a wavy top edge. It is better than a flat bar (it has 40px of sweep), but it is
   still a *horizontal band across the whole frame*. It does not visibly pool
   against specific crags or collect in the valley floor only.
8. **Alpha is genuinely atmospheric — N/A by design.** The mist is opaque painted
   colour; the rock is covered, not faded. See the correction section at the end of
   `10-depth-and-occlusion.md`. Gate 8 as written contradicts the art and should be
   rewritten, not satisfied.
9. **Pixel discipline — PASS.** No AA, no stray colours, no dither-as-fill.
10. **Vegetation reads as clumps — FAIL.** The handful of dark marks on the left
    flank (around x=40–60) read as **scattered flies or debris**, not as trees on a
    crest. Fewer, larger, and attached to a crest line, or remove them.

## TOP 3 PROBLEMS

1. **The flanks are an unauthored chevron run — the r11 defect, unfixed, moved to
   the edges.** This is the most damaging problem because the flanks are the
   largest area of near-dark rock and the eye goes there first.
   *Fix:* author the left and right flanks with the same archetype discipline used
   in the valley — explicitly vary peak width, saddle depth and flank asymmetry
   per summit, and let at least two flank masses be **cropped by the top of the
   frame** so the run is broken by the frame edge rather than by another triangle.
   A chevron run happens because every summit is (a) the same height, (b) the same
   width, (c) fully inside the frame. Break all three.

2. **No warm light on any rock face.** The image is monochrome blue, so it reads as
   a heightmap with a blue ramp rather than as a painting. The audit gate
   (`R-B >= 8`) is satisfied by the mist and therefore cannot catch this.
   *Fix:* pick a light direction (upper-left, consistent with the reference) and
   give every lit face an authored warm entry — cream/ochre at the crest line,
   falling to the cool mid within 10–20px. Then **change the audit gate** so warm
   pixels are counted *above the mist top only*, which makes it able to fail.

3. **Horizontal tiering through the middle third.** The rock is divided by rows.
   *Fix:* the tier boundaries are currently functions of `y` alone. Derive them
   from the crest instead — offset each boundary by the local crest height, as was
   already done successfully for the strata — so a tier follows the form and no two
   tiers stay parallel across the frame.

## WHAT ALREADY WORKS (do not change)

- The two-massif valley composition. It reads as a place, not a pattern, and the
  corridor right of centre is doing its job.
- Bands stacking front-to-back with occlusion by overdraw. Depth reads correctly
  and the structure is right; this was the r25 fix and it holds.
- Opaque painted mist with a swept top edge. Far better than the alpha dissolve.
- Authored summit archetypes *in the valley*. The variety is visible and correct;
  the problem is that the discipline was not applied to the flanks.
- The dark-near / pale-far value direction.

## ONE THING TO TRY THAT WE HAVE NOT TRIED

**Author the whole crest as one silhouette path with an explicit per-summit
"prominence" number, instead of as node lists.** Every failure so far — sawtooth,
chevron run, uniform wall — is the same root cause: the crest is specified as
(summit height, saddle height) pairs, which makes prominence and spacing fall out
of the *pairing* rather than being chosen. A path with a named prominence per
summit, plus permission for a summit to exit the top of the frame, makes
repetition structurally impossible rather than something to tune away. This is the
same lesson as v6 ("the silhouette is the art, it must be a decision") applied one
level up: **the prominence of every summit is a decision too.**
