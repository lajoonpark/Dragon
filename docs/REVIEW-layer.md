# Layer review — pass/fail criteria

You are reviewing **one background layer** of a pixel-art macOS wallpaper called
Dragon. Be a demanding art director, not a cheerleader. The author cannot see
the reference images; you can read `15-reference-notes.md` for what they look
like. Judge against that and against `25-art-pipeline.md`.

## What you are looking at

- `out/layer_<tag>_flat_1x.png` — the layer composited over paper. **This is the
  primary image. Judge at 1×.**
- `out/layer_<tag>_flat_2x.png` — nearest-neighbour 2×, for reading pixel-level
  decisions.
- `out/layer_<tag>.png` — the layer with real alpha. A ridge must genuinely
  dissolve into mist at its base, not fade behind a grey band.

The layer is **the mountain range only**. Water, foreground, pavilion, dragons
and the timer are all out of scope. Do not fail it for missing those.

## Hard pass/fail gates

Answer each PASS or FAIL, with one sentence of evidence.

1. **Reads as mountains at 1×.** Not grass, not a barcode, not a plateau, not
   noise. A viewer should say "mountains" instantly, without being told.
2. **Distinct summits.** At least 3 separate summits are legible per band, and
   they are not all the same shape. Repetition of one archetype is a fail.
3. **No vertical striping.** No per-column banding, no barcode of one stripe per
   flank, no full-height straight edges.
4. **No horizontal rulers.** Terraces must wrap the form. Full-width horizontal
   lines, or scanline-like rows, are a fail.
5. **Atmospheric perspective is visible.** Each successive band is paler and
   lower-contrast than the one in front. If you cannot tell the bands apart, fail.
6. **Warm light / cool shadow split.** Upper and lit faces are warmer; valleys
   and shadow faces are cooler. Flat monochrome is a fail.
7. **Mist pools and is not a band.** Mist should sit in valleys and wrap ridge
   bases. A flat-topped horizontal mist bar is a fail.
8. **Alpha is genuinely atmospheric.** Looking at the alpha channel alone, a
   ridge should dissolve gradually into nothing at its base. An abrupt cut, or a
   hard minimum opacity, is a fail.
9. **Pixel discipline.** No anti-aliasing, no stray colours outside the
   declared ramps, no dither used as a fill (dither is a transition only).
10. **Vegetation reads as clumps on crests**, not as even confetti. If the dark
    marks look like scattered debris or flies, fail.

## Softer judgement — score 1–5 and justify

11. **Verticality.** Does the range feel like it exceeds the frame, or does it
    sit politely inside it with dead sky above?
12. **Painterliness.** Does it feel like a painted shanshui range, or like a
    heightmap rendered by a computer? This is the one that matters most, and the
    hardest to fake.
13. **Would it survive being a wallpaper for 8 hours?** Calm enough, or tiring?

## Output format

Reply with exactly this structure:

```
VERDICT: PASS | FAIL
SCORES: reads_as_mountains=N verticality=N painterliness=N wallpaper_endurance=N
GATES:
1. ... PASS/FAIL — evidence
...
10. ... PASS/FAIL — evidence
TOP 3 PROBLEMS (ordered by how much they hurt the image):
1. <problem> -> <the specific fix, in terms of what to change>
2.
3.
WHAT ALREADY WORKS (do not change these):
- ...
ONE THING TO TRY THAT WE HAVE NOT TRIED:
- ...
```

Be specific. "Improve the shading" is useless; "the terrace quantisation is
stepping at row granularity, which is why it reads as blocky noise — quantise
in the across-the-form direction instead of by row" is useful.

Do not edit any files. Review only.
