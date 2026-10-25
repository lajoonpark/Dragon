# Dragon — Vision

> An animated pixel-art shanshui landscape. Long-bodied dragons drift through
> layered mountains, disappearing behind ridges and reappearing in the mist.

---

## One line

**A living ink-painting wallpaper: mist, stone, and dragons, drawn at 1:1 pixel scale.**

## The feeling we're chasing

The reference image has three qualities that matter more than any specific
mountain, tree, or pavilion:

1. **Stillness with something alive in it.** The composition is quiet and
   symmetric-ish, weighted low, heavy at the edges. The dragons are the only
   thing that moves. Contrast is the whole point — if the background is busy,
   the dragons vanish; if the dragons are always on screen, the stillness dies.
2. **Depth that is painted, not built.** Nothing in that image is in
   perspective. Depth comes from three things only: **overlap**, **desaturation
   with distance**, and **mist cutting between planes**. We will reproduce
   exactly these three things, procedurally, in pixels.
3. **Silence as a texture.** Big areas of near-empty value: water, fog, sky.
   Those voids are where the eye rests and where the dragons can be seen.

## The three pillars

### 1. Depth without 3D
The scene is a stack of flat layers with known depth values. Dragons are not
"on" a layer — a dragon's body has **depth along its length**, so it can enter
behind a ridge, travel inside the mountain range, and emerge 6 seconds later on
the other side. This is the single most important mechanic in the project and
gets its own document (`10-depth-and-occlusion.md`).

### 2. Dragons that feel like weather
Not mascots. Not sprites that bob up and down. A dragon should read like a
slow-moving current of air: a serpentine ribbon that follows a curved path,
banking through turns, wings-less, legs tucked, occasionally coiling. A dragon
is on screen roughly **half the time**. The other half, the landscape carries
the piece on its own — which is why ambient life is a pillar, not polish.

### 3. The empty screen is not empty
Half the time there is no dragon. Those minutes are not a lull; they're the
baseline the dragon plays against. Wind moves through grass, petals drift and
land on water, a waterfall never stops, birds cross rarely because they're rare.
Three tempos — slow world, medium weather, fast punctuation — and everything
yields when a dragon arrives. See `35-ambient-life.md`.

### 4. One world, many hosts
`Dragon` (the wallpaper) and `Dragon Timer` (the companion) are the same world
seen at different zoom levels of attention. Dragon Timer is a small, precise,
useful tool that happens to open a window onto the same landscape and end with
a dragon flying through your screen. The aesthetic is not decoration applied to
a timer — it *is* the product.

And the world is not bound to one OS: macOS first, but the core knows nothing
about any platform, so Windows and Linux are a host each, not a rewrite. See
`55-platform-portability.md`.

## Non-goals (v1)

- No 3D, no camera perspective, no lighting engine, no shaders-as-crutch.
- No gameplay, no progression, no accounts, no network.
- No "cute" dragons. Expressive, yes. Cartoon mascots, no.
- Not a screensaver-only product, though we ship one.
- Not a general-purpose wallpaper engine. One scene, done well.

## Art direction: translating the reference to pixels

The reference is a vertical composition. A wallpaper is usually 16:9, so we
**recompose rather than crop**. The native form of this painting style is the
horizontal handscroll, and that's what we build: a long panoramic world that the
camera pans across slowly. That gives us variety for free and never loops.

### Read of the reference (what we keep)

| Element | Reference | Our translation |
|---|---|---|
| Palette | Cool blue-greys, warm paper cream, near-black ink | 5 depth ramps, each 5–6 colours, shifted hue + desaturated with distance |
| Mountain form | Vertical karst spires, cliff faces, vertical striations | Hand-pixelled silhouette libraries, stackable column archetypes |
| Edge treatment | Soft mist eats the base of every peak | Mist band layer at each depth break; hard top edge, soft bottom |
| Foreground | Dark rocks, pines, a blossoming tree, a pavilion | Dark silhouette layer with 1–2 accent details only |
| Water | Mirror reflection, low contrast, horizontal banding | Vertical flip of sky/mist ramps, broken by 3–5 darker dash rows |
| Focal point | Pavilion on a crag, slightly off-centre | One small human-scale anchor per "panel" — pavilion, bridge, lantern, boat |
| Void | Huge pale sky + fog | Same, and this is where dragons are readable |

### Pixel craft rules (non-negotiable)

- **Integer scale only.** Internal resolution 480×270 (16:9, ×4 = 1920×1080) or
  512×288 for a slightly roomier composition. Never fractional scaling, never
  bilinear filtering on the world.
- **No anti-aliasing on the world.** Hard edges. If something needs to be soft,
  it's mist, and mist is made of dither bands.
- **Dither, don't gradient.** Bayer 4×4 for mist falloff and depth blending.
  Ordered dither is the only smoothing tool we get.
- **1px ink outline** on anything meant to read as "ink drawn" (dragons,
  foreground rocks, pines). Layers read as "washed" (distant mountains) get no
  outline, only value separation.
- **Ramps, not RGB.** Every colour belongs to a named ramp. No ad-hoc colours,
  ever. This is what keeps 20 assets looking like one artist made them.
- **Restraint on detail.** A distant mountain is 3–4 values. Only the
  foreground gets dither texture, moss, and individual needles.

## Composition rules

- **Heavy at the edges, open in the middle.** The pan should always have one
  clear "valley" of near-empty value; that's the dragon stage.
- **Never centre a peak on screen.** Peaks live at thirds. The void lives in
  the centre.
- **The camera never stops moving**, but it moves at ~6–10 px/sec. Slow enough
  to feel like the world is breathing, not like a screensaver scroll.
- **Vertical camera is nearly fixed.** A tiny parallax drift (±8px) is enough
  to feel hand-held; more reads as video-game.
- **One anchor object per panel.** Keeps scale legible. Without a
  human-scale object, mountains read as abstract shapes.

## Success test

Open it on a 27" display, at 1m, for ten minutes.

- You forget it's a loop.
- When no dragon is on screen, you're still watching. Something is always
  moving — a gust running through grass, petals settling on water, a waterfall
  that never stops.
- At least once, a dragon appears somewhere you didn't expect and you go "oh".
- At least once, you do not notice a dragon at all until it's halfway across.
- The moment a dragon appears, the small life quiets down — you couldn't say
  what changed, but the dragon feels *important*.
- If you crop a random 300×300 region at 1× and put it in a gallery frame, it
  looks like a real pixel-art piece, not a crop of a desktop background.
