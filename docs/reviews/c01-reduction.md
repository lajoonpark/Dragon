# Reduction report — master-candidate-01

> First real test of the generate → reduce → dismantle pipeline
> (`27-master-image-pipeline.md`). **Verdict: the approach works.**

## Result

| | |
|---|---|
| Source | `docs/refs/master-candidate-01.png`, 1536×864, **87,492 unique colours** |
| Crop | 1440×810 (48px left/right, 27px top/bottom removed) |
| Factor | **÷3 exactly** → 480×270 |
| Palette | **24 colours**, adaptive, no dither |
| Output | `docs/review/c01-reduced-{1x,2x,4x}.png` |

The crop is the important numbers trick: 1536/480 = 3.2, not an integer, so a
straight resize would resample unevenly and blur some pixel columns. Cropping to
1440×810 gives exact ÷3, **and** 480→1920 is exact ×4, so the final asset
upscales to 1080p with no interpolation at all. The crop is centred and
costs 3% of the width, which is the least destructive option. The
`512×288` alternative is also exact ÷3 but only 3.75× at 1080p, which is blurry
at the one magnification we actually ship.

## The pipeline order that matters

**Quantise at full resolution, then mode-filter the indices.** This is the
finding, and it is not obvious.

A mode filter on the raw image is meaningless: with 87,492 unique colours every
pixel in a 3×3 block is a unique colour, so "most common" is a coin flip and the
result is noise. Quantising to 24 colours *first* turns the block into a real
majority vote over 24 candidate values, which preserves the pixel decisions the
image already made. Averaging instead would invent 87,000-blend colours that are
in neither the source nor the palette, and the result greys out.

The centre pixel is weighted ×3 so a 1px feature — a thin spire, a strata line —
survives instead of being outvoted by its surrounding rock.

## Gate results

```
automatic:  PASS no stray colours   PASS flat field 6.53%   PASS warm 24.41%
needs eyes: seam 77px at x=420,y=190   banding 23 rows, longest run 10
```

The three automatic gates pass cleanly. The two flagged numbers are **both
legitimate features**, verified by zooming to 7×:

- **x=420, y=190, 77px, Δ59** — the **waterfall**. A bright vertical ribbon down
  a karst face. It is a required scene element (`D-016`) and it is supposed to be
  a long high-contrast vertical.
- **x=381, 35px** — a **lit face against a shadowed face**. Reads as faceting at
  visual scale; there is no rock-without-facets option in this style.
- **Waterline rows** — the horizon. A single high-change row is a horizon; only a
  *run* of them would be banding. Longest run is 10, all in the water band, which
  is a separate layer anyway.

So the honest audit is: **5 of 5 pass, with two confirmed features.** But this
exposed a real flaw in the gate design, recorded below.

## Gate design flaw, and the fix

Both flagged metrics *cannot* be decided by a threshold. A karst fissure, a
waterfall ribbon, a horizon, and a genuine barcode all produce the same numbers.
Previous rounds burned effort chasing exactly this confusion — the r47 seam gate
failed on the mountain's own silhouette and the gate had to be rescoped.

The tool now refuses to pretend: it splits checks into **automatic** (palette
adherence, flat field, warm presence — all objectively decidable) and **needs
eyes** (seam, banding — printed *with coordinates* so a human zooms the exact
pixel). A threshold that cannot distinguish art from artefact should not
arbitrate; it should point.

## Palette size: 24 is the number

| Colours | Flat field | Banded rows (consecutive) | Read |
|---|---|---|---|
| 16 | 9.44% | 8 | Mist gradation collapses; the far ridges lose their separation |
| **24** | **6.53%** | **10** | **Correct** — clean separation, mist still graduated |
| 32 | 5.70% | 19 | Doubles the banding for no visible gain |
| 48 | 3.82% | — | Banding increases further; noise |

More colours made the image *worse*: the banding metric roughly doubles from 16
to 32 because extra intermediate steps start resolving the model's smooth
gradients into visible terraces. 16 flattens, 32 introduces noise, 24 sits
between. Compare `docs/review/c01-palette-comparison.png`.

## The palette it converged to

`docs/refs/palette-c01.yaml` — 24 entries, and structurally clean rather than a
jumble:

- **17-step cool blue ramp**, near-black `#141923` → pale `#dfe5e6` (75.6%)
- **7-step warm cream ramp**, `#d4d0c6` → `#fdf5e1` (24.4%)

That is exactly the two-ramp structure the plan called for, discovered rather
than imposed. No green cast (0.0% of pixels have G > R and G > B), which was a
specific worry given the mist leans warm. **This is now the locked project
palette** — future art quantises to it.

## What this image proves, and what it does not

**Proves:** the model delivers karst form, the warm/cool split, seven-plus depth
planes, and volumetric lit mist — the four things forty procedural rounds never
achieved. The reduction survives. Detail density is not the problem I feared:
pines and strata do survive at 480×270 as legible marks, not debris.

**Does not prove:** layer separation. This is a single flat image. The hole
problem (D-024) is still untested and is the next real risk.

## Remaining defects to fix by hand (polish pass)

1. **Top-corner branches** — dark branches enter both top corners; that is where
   the macOS menu bar sits. Remove them; bottom and side framing is enough.
2. **Near-symmetry** — the two framing massifs are close to mirrored. Fine
   standalone, will read as a pattern when it pans. Vary on the next batch.
3. **Corridor is partly obstructed** — mid-ground spires intrude into the
   brightest air near centre. The dragon corridor wants that clearer.
4. **Water band is shallow** — waterline at y≈236 leaves only ~34px (12.6%),
   where the plan wants 25–35%. Either extend downward or treat it as a
   separate, deeper water layer.
5. Mist is slightly more cream/yellow than the cool reference; acceptable, but a
   small palette nudge is available since we now own the palette.

## Reproduce

```bash
python3 tools/pipeline/reduce.py docs/refs/master-candidate-01.png --tag c01
```

Defaults: `--colors 24 --target 480x270 --factor 3`.
