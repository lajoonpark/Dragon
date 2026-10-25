# Master Generation Prompt — the landscape

> Copy the block in **The prompt** into the image model. Everything outside that
> block is guidance for us, not for the model.
>
> Target model behaviour: a text-to-image model with strong landscape and
> aspect-ratio control (Midjourney, Flux, SDXL-class, or equivalent). The prompt
> is written for a general-purpose model and assumes **no** pixel-art
> specialisation — that is deliberate, because pixel-art-specialised models
> produce 480px mush with no detail to salvage (`27-master-image-pipeline.md`).

---

## Before you generate: four settings that matter more than the prompt

1. **Resolution: 1920×1080 exactly** (16:9). Not square, not portrait. If the
   model only does 1:1 or 4:3, generate wide then outpainte to 16:9 — do not
   crop a square, you will lose the composition.
2. **Aspect: 16:9.** If there is a `--ar 16:9` style flag, use it.
3. **Batch 4–8 candidates** in the same call with the same prompt. Consistency
   between candidates matters: this image is the master for the whole world.
4. **Seed: record it.** Everything downstream (extra panels, the layer
   back-to-front variants) should reuse the seed where the model allows it.

**Do not** ask for "pixel art" as a style word in the main prompt. Ask for a
*painting* and reduce it ourselves. Requesting pixel art gets you soft, muddy,
inconsistently-gridded images that cannot be reduced cleanly.

---

## The prompt

```
A traditional Chinese shanshui ink-and-wash landscape painting of a karst
mountain range, horizontal 16:9 composition, rendered as flat poster-like
colour with NO brush texture, NO gradients, NO soft shading — every form is a
flat field of a single colour meeting the next at a hard edge.

COMPOSITION (most important): TWO ENORMOUS LIMESTONE MASSIFS, one cropped by the
left edge and one cropped by the right edge, both rising past the top of the
frame so their summits are cut off. They frame a DEEP CENTRAL VALLEY. The valley
is filled with layered pale mist, and behind it, far distant ridges are visible
as pale overlapping silhouettes, each one fainter than the last. Between the two
massifs, slightly RIGHT OF CENTRE, leave a clear vertical corridor of open
bright misty air — an empty gap where the far ridges show through, wide enough
for a dragon to fly through. This gap is the brightest area in the image.

THE ROCK: steep, thin, vertical karst spires with blunt tops and hard shoulders,
in the manner of Guilin peaks — NOT alpine, NOT snow-capped, NOT triangular
cones. Vary the summits constantly: some are narrow needles, some are flat-
topped mesas, some have a long gentle slope on one side and a sheer drop on the
other, some are broad rounded domes. No two summits the same shape. No repeating
pattern. Rock faces show horizontal stratification as a few flat bands of
slightly different value, and strong vertical fissures.

DEPTH: six clear planes, back to front, each separated by a band of mist. The
furthest ridges are barely distinguishable from the sky — very pale blue-grey,
almost white. Each plane forward of that is darker, higher-contrast and more
saturated. The nearest rock is very dark blue-grey, almost charcoal, and is
cropped by the bottom and side edges of the frame.

LIGHT: soft warm light from the UPPER LEFT. Upper and left-facing rock surfaces
catch a pale warm CREAM highlight. Faces turned away and the deep valleys are
cool BLUE-GREY. This warm-light, cool-shadow split must be clearly visible on
every near massif — the stone must not be uniformly blue.

MIST: thick, volumetric, and LIT FROM WITHIN — a warm cream glow deep inside the
mist, not flat white paint. The mist fills the valleys, pools at the base of
every cliff, and wraps around the feet of every ridge. Its upper edge is soft
and billowing, never a straight horizontal line. The rock dissolves into it —
no mountain shows a base or a ground line anywhere.

COLOUR: restrained and cool-dominant. Pale blue-grey, slate blue, deep
blue-charcoal, warm cream, and off-white mist. Desaturated, calm, restful —
this is an image to look at for eight hours. One single small warm accent
(soft muted pink blossom) entering from the LOWER LEFT corner only. No other
saturation anywhere.

FOREGROUND: dark near-black pine trees and rocks entering from the lower left
and upper corners, cut off by the frame edge, framing the view. A very small,
simply-drawn pavilion with upturned eaves on a crag at about one third up from
the bottom, near centre — tiny, for scale only, not the subject. Still dark
water with soft vertical reflections across the bottom eighth.

STYLE: flat colour planes, hard edges, no anti-aliasing, no photorealism, no 3D
rendering, no ambient occlusion, no lens flare, no text, no signature, no
watermark, no border or frame. Limited palette, high value contrast between
near and far, in the spirit of a woodblock print or a screen print of a Song
dynasty landscape.

Nobody in the image. No people, no boats, no birds, no animals.
```

---

## Short version — for models that truncate

Midjourney clips at roughly 60 words, and some SDXL front-ends weight the first
sentence heavily and ignore the rest. If the model cannot take the full prompt,
use this instead — it keeps the clauses that actually change the output, in
priority order. If forced to cut further, cut from the bottom.

```
Flat-colour Chinese shanshui karst landscape, 16:9. Warm cream light on
upper-left rock faces, cool blue-grey shadow. Two enormous limestone massifs
cropped by the left and right frame edges, rising past the top of the frame,
framing a deep misty valley; a clear open corridor of bright mist right of
centre. Six overlapping layers of thin vertical karst spires receding into
lit cream mist, each layer paler than the last. Dark pine trees and a tiny
pavilion in the near foreground, still dark water at the bottom. Flat colour
planes, hard edges, no gradients, no brush texture, screen print. Empty.
--ar 16:9
```

The three clauses that must survive any shortening: **massifs cropped by the
frame edges** (verticality), **warm cream light on upper-left faces** (the
warm/cool split), and **six layers each paler than the last** (depth).

---

## Negative prompt

If the model supports negative prompts, use these. If it does not, the phrases
above ("no brush texture", "no gradients", "no anti-aliasing") are carrying the
load.

```
photorealistic, 3D render, CGI, octane, unreal engine, blurry, soft focus,
depth of field, bokeh, lens flare, sunset, orange sky, purple sky, clouds in
sky, snow, snow caps, alps, fjord, cliffs of dover, triangular cone mountains,
symmetrical composition, centred peak, repeated shapes, tiling, pattern,
texture, brush strokes, canvas texture, film grain, noise, gradients, dithered,
anti-aliased, glowing edges, neon, oversaturated, HDR, busy, cluttered, cartoon,
anime, vector art, low-poly, isometric, text, letters, signature, watermark,
frame, border, vignette, people, boats, birds, animals, dragons
```

Note `dragons` in the negative: **this image must contain no dragons.** They are
sprites, added later, and must never be baked into the master.

---

## What to check before you accept a candidate

Look at it and reject anything that fails these, in this order. Most generations
fail 1–3, and it is faster to regenerate than to fix.

| # | Check | Reject if |
|---|---|---|
| 1 | **Composition** | Peaks sit politely inside the frame with sky above. We need massifs **cropped by the top edge**. Reject any image where you can see where both big mountains end. |
| 2 | **The corridor** | Dead-centre symmetric valley, or no clear open gap. The gap must be right of centre and genuinely empty. |
| 3 | **Rock character** | Alpine cones, snow, cliffs, or mesa/desert. We need thin vertical karst spires. |
| 4 | **Warm light** | The stone is uniformly blue/grey with no cream highlight anywhere. This is the most common failure and the one that most cheapens the image. |
| 5 | **Mist has a top edge, not a line** | A straight horizontal mist boundary anywhere. Also reject mist painted flat white with no warm glow. |
| 6 | **No visible ground** | Any mountain showing a base, or a horizontal ground plane. |
| 7 | **Depth count** | Fewer than five distinguishable planes. Look for the faintest far ridge — if you cannot count layers, regenerate. |
| 8 | **Palette restraint** | Green foliage dominating, orange sunset, or more than one saturated accent. |
| 9 | **Empty** | Any figure, boat, bird. |

Also reject: any image where a large area is one flat colour with no structure
(it will read as empty sky and fail the flat-field test), and any image with
visible painterly brush texture (it will not reduce to flat planes).

---

## If you can, generate the backing plates in the same session

Per `27-master-image-pipeline.md` (D-024), cutting layers leaves holes. The fix
is to generate back-to-front **now**, while the seed and style are hot:

1. **The master** — the prompt above. Full scene.
2. **Backing plate A** — same prompt, plus:
   `Remove the two large foreground massifs at the left and right edges
   completely. Show only the far and mid ridges and the mist between them,
   filling the whole frame edge to edge, continuing where the foreground rock
   was.`
3. **Backing plate B** — same prompt, plus:
   `Remove all foreground elements — the pines, the rocks, the pavilion and the
   water. Show only the distant layered ridges and mist filling the entire frame
   edge to edge.`

Keep the seed identical if the model allows it. These two plates mean every
layer has real painted rock behind it, so parallax can never expose a hole.

---

## After generation — the reduction is not optional

The output is **not** the asset. Feed it through, in order:

1. mode-filter downsample 4:1 → 480×270
2. quantise to the locked palette, dithering **off**
3. hand-polish the silhouette edges and every soft boundary that survived
4. run the acceptance checklist in `27-master-image-pipeline.md`

Expect step 3 to be a real day of work on the first panel. That is the step that
converts an AI image into pixel art, and skipping it is why most "AI pixel art"
wallpapers look wrong at 4×.

---

## If the first batch is bad

In order of what to change:

- **All cones / alpine:** strengthen "Guilin karst, thin vertical spires, blunt
  tops" and add "not alpine, no snow" to the negative.
- **No depth:** the model is flattening. Add "many overlapping ridges receding
  into mist, each one paler than the last, at least six distinct layers".
- **Uniformly blue:** the warm-light clause is being ignored. Move "warm cream
  highlight on upper-left faces" to the **very front** of the prompt — models
  weight the beginning most heavily.
- **Painterly texture:** add "flat colour planes, screen print, woodblock, no
  brush strokes" and drop any word resembling "painting" from the style clause.
- **Too busy:** add "minimal, sparse, much empty misty air, large calm areas".
- **Symmetric and static:** add "asymmetric composition, off-centre, strong
  diagonal from lower left to upper right".
