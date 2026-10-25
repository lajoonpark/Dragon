# Art Pipeline — how the background actually gets made

> Answering: can we do this in SVG? No. Here's what we do instead, and here's
> the evidence from six failed attempts at doing it procedurally.

---

## Verdict on SVG: no, not for the art

SVG is the wrong tool for pixel art, for four specific reasons:

1. **SVG is anti-aliased by definition.** Rasterising a path gives you soft
   sub-pixel edges. Pixel art is the deliberate *refusal* of that. You can turn
   AA off in some rasterisers, but then you're fighting the tool on every curve.
2. **The model is wrong.** SVG describes shapes with curves and fills. Pixel art
   is decisions about individual pixels — "this one pixel is lighter because it's
   the rim", "these four pixels dither into that". There is no SVG element for
   "make pixel (34, 91) the highlight colour".
3. **Dithering in SVG is unmaintainable.** A 4×4 Bayer patch is 16 rects. A
   mist band is thousands. You'd be generating them programmatically, at which
   point SVG is doing nothing for you.
4. **Resizing destroys it.** An SVG scales "beautifully", which is precisely
   what must never happen to a 480×270 composition. We want nearest-neighbour x4
   and nothing else ever.

**Where SVG *is* genuinely useful:** as a *layout sketch*. Drawing the depth band
boundaries, the thirds, the void, the pan width — as a vector diagram you can
move things around in. That's a planning surface, not an asset. Useful, cheap,
worth doing once.

---

## What six failures taught us (the important part)

I built six generators before writing this document, each one fixing the last
one's most obvious flaw. None of them produced acceptable rock. The failure
table is more useful than any advice I could give:

| Attempt | Approach | What it produced | What it proved |
|---|---|---|---|
| v1 | smooth taper formula, per-pixel noise | **candles** with ribbing | a formula cannot make a mountain. Any monotonic taper gives a cone. |
| v2 | stepped silhouette (authored) + noise interior | outline improved, interior read as a **scanned 3D mesh** | noise cannot make rock. Rock is a *shape*, not a texture. |
| v3 | value-compressed ramps, column profiles | **tombstones** | correct values with no facets still reads as a cardboard cut-out |
| v4 | authored facet planes + jagged outline | mist ate the image; far peaks rendered as **tablecloths** | dither used as a *fill* produces checkerboard. Dither is a *transition*. |
| v5 | fixed the above | better, still **postage stamps** — every peak the same silhouette | one archetype repeated is worse than a wrong archetype |
| v6 | **hand-authored silhouette in ASCII**, planes declared as row fractions | finally **read as karst** at 1× | the silhouette is the art. It must be a decision. |

Two conclusions, both structural:

**1. Silhouettes must be hand-authored.**
Not generated, not parameterised, not scaled from one master. The shape of a
karst spire — blunt cap, hard shoulder, narrow neck, jagged face, held width,
mist-hidden foot — is a *decision about specific pixels*. Six attempts at
automating that decision all failed in different ways, which is the signature of
a task that resists automation.

**2. Value planes must be declared, not computed.**
A cliff face is a small number of **flat** value regions meeting at hard edges.
Not a gradient. Not a noise field. In v6, the interior is: three declared planes
at row-width fractions 0.30 / 0.56 / 1.0, plus a 1px darker line at each
boundary. That's it. It looks like rock because a lit face and a shadowed face
meeting at an edge *is* what rock looks like in this style.

The generator's job is **palette, dither, compositing, depth, and the animation
systems.** Its job is *not* invention.

---

## The recommended pipeline

Three tools, each doing what it's good at.

### 1. Painting — Aseprite (or a free equivalent)

For anything that needs a human hand: the base silhouettes, head directions,
the pavilion, foreground rocks, pines, blossom branches.

- **Aseprite** — $20, the standard. Indexed palettes, tile mode (essential for
  the handscroll), onion skin for the dragon, layer groups per depth band.
  Worth the money; it's the best $20 in this project.
- Free alternatives, in order: **LibreSprite** (free Aseprite fork, identical
  feel), **Pixelorama** (free, actively developed), **Piskel** (browser, fine
  for tiny assets, poor for a 480×270 scene).
- Do **not** use Photoshop, Illustrator, Krita, Figma, or Procreate. All are
  built for smooth images and actively fight pixel art (auto-AA, brush
  interpolation, resampling).

### 2. Storage — assets as text, in git

Two formats, both diffable:

- **Silhouettes: ASCII art.** One character = one pixel, `.` = transparent.
  Demonstrated working in v6. Reviewable in a PR, editable without opening an
  app, and `git diff` shows *exactly which pixels moved*. This is the format
  that made the good silhouette possible at all.
- **Everything else: indexed PNG (1, 4, or 8-bit) + a palette file.** Aseprite
  exports these natively. Small, lossless, and diffable enough at the binary
  level that an unexpected change is obvious.

`assets/` must be plain data. Never a `.aseprite` file in the repo as the
source of truth — it's a binary blob that produces an opaque diff.

### 3. Compositing — our own tool (already prototyped)

This is where the tool earns its place, because these are things you cannot do
by hand at scale:

- Palette assignment per depth band, and the palette audit that fails on any
  stray colour.
- Bayer dither for mist and depth blending.
- Mist bands, water, reflections, wobble, dash rows.
- Depth field generation (which pixel is at which depth) — this is
  *derived from the layer stack*, never painted.
- Placement of 10 archetypes into a 7680px world.
- All the ambient systems (gusts, petals, waterfalls, birds).

The prototype in `tools/proto/gen_bg.py` is the seed of this. It already does
palette indexing, ASCII silhouette loading, declared value planes, depth
writing, mist, water and reflection. It is ~350 lines and it produced the
image that finally read as karst.

---

## Solving the volume problem (this is the real risk)

The world is 7680×270. At the density the reference implies, that's roughly
**50–70 mountains**, plus foreground rocks, trees, and six regions.

Hand-painting 60 unique mountains is weeks of work and is not the plan. Hand-
painting **10** is a weekend. So:

### The 10-archetype × 6-variant system

Author ten silhouettes by hand (that's the irreducible work):

`spire`, `twin-spire`, `needle`, `tower`, `cliff`, `crag`, `fold`, `shelf`,
`arch`, `islet`.

Then generate variety with operations that **preserve the hand-made quality**:

| Operation | Preserves craft? | Notes |
|---|---|---|
| Horizontal mirror | Yes | Cheapest, most effective. Flips the lit side, which reads as a different peak in different light. |
| Depth + palette reassignment | Yes | The same silhouette at depth 0.22 vs 0.62 reads as a different object entirely. |
| **Authored overlay** | Yes | Stamp a hand-drawn ledge, crack, cave, or tree bundle onto the base. This is the big one — it changes the read without changing the outline. |
| Vertical crop at the top | Yes | Chop the summit → a different peak. Chop the bottom → a different peak in mist. |
| Scale (integer only) | Mostly | 1× and 2× only. Never fractional. |
| Non-uniform squash | Sometimes | Careful — it destroys the pixel grid's implied density. |
| Free rotation | **No** | Destroys the pixel grid. Never. |

Target: 10 archetypes × (2 mirrors) × (3 depth/palette assignments) ×
(authored overlays) = the 50–70 distinct reads we need, at maybe 4× the work of
10 assets instead of 6×. That's the whole trick, and it's how every 2D game with
a big world does it.

### Authored overlays are the underrated piece

A single 16×24 hand-drawn "ledge with three pines" stamp, placed at different
heights on different peaks, makes those peaks read as different locations. Ten
overlays + ten silhouettes is 20 hand-made things that compose into a world.
Budget real time for the overlays; they're what stops the tiling being legible.

---

## What "base background first" should actually mean

Agreed that the still is the priority — with one clarification that will save a
rewrite:

**Don't author a flat image; author the layered stack.** The base background
*is* the depth layers. If we paint one flat 480×270 image, we have to throw it
away when dragons need a depth field. If we paint it as six layers with declared
depths from minute one, the same art serves the still and the animation.

So the deliverable for this phase is:

1. **Palette file** — 5 ramps × 6 steps, plus FG/blossom. Locked early.
2. **Ten silhouette assets** — ASCII, hand-authored, reviewed.
3. **Six-to-eight overlay stamps** — ledges, cracks, trees.
4. **One panel** — a single 480×270 composition, assembled from the above,
   reviewed at 1× and 4×, worth framing.
5. **The depth field** — generated from the stack, verified by a test that
   asserts no pixel is unpainted and every layer's depth is monotonic.
6. **The world strip** — the panel repeated/extended to 7680px with the
   archetype system, then reviewed as a contact sheet.

Only then does anything animate.

### Honest time estimate

| Task | Time |
|---|---|
| Palette lock + 10 silhouettes | 3–5 days (real drawing) |
| 8 overlay stamps | 2 days |
| First panel composition | 2–3 days |
| Compositor tool (this prototype, finished) | 2 days |
| World strip from archetypes + contact sheet | 3–4 days |
| Polish pass on the panel until it's framable | 3–5 days (unbounded; stop at "good") |
| **Total** | **~3 weeks** |

That's the honest number. It's the biggest single block of work in the project,
and it's the one that decides whether the product is beautiful. Which is exactly
why it goes first.

---

## The one rule that keeps it beautiful

**Every pixel of the landscape is a decision.** The tool may decide *where* an
authored thing goes, what palette band it uses, and how mist eats its base. It
may never decide what a mountain looks like. Six attempts is enough evidence
that it cannot.

---

## Panel 01 — what the first real panel established

`docs/panel-01-1x.png` (and `-2x`) is the first composed panel. Reviewed at 1×
and 2×, because that is the only honest way to judge it.

### The composition is a gorge, not a frontal range

The reference is a tall portrait: a wall of spires, mist, water at the bottom.
Copying it into 16:9 would have given a postcard. Instead:

- **Two massifs cropped by the frame edges** (left cropped by top *and* left).
  The range exceeds the frame vertically instead of politely fitting inside it
  with sky above. This is how the portrait's verticality survives a wide frame.
- **A notch right of centre** — pale, layered, near-empty. That void is the
  dragon corridor and the brightest air in the frame. The reference has no room
  for it; a wallpaper must have one, because something has to fly through.
- **A waterfall** off the right crag. Not in the reference. A vertical event in a
  horizontal frame, a scale anchor that makes the peaks legible, and permanent
  gentle motion — the highest value-per-pixel element in the scene.
- **One warm accent** (blossom, bottom-left) against an entirely cool image.
- **Asymmetric foreground**: rocky at the left, open at the right.

### Edge language, learned the hard way

Three attempts at cliff edges, in order:

1. **Per-row authored numbers** → 8–12px staircase steps. Reads as Minecraft.
2. **Continuous noise on the edge** → a caterpillar. Reads as a snake.
3. **Held runs + one jump** → correct. Rock holds an offset for 4–6 rows, then
   steps. The eye reads "faceted cliff", not "wobbling line".

The rule: *edges step in runs, never continuously*. Continuous variation is
organic (worms, cloth); quantised runs are geological (rock, brick).

Similarly, **facet edge lines must be broken into segments**. A 1px darker line
running the full height of a plane becomes a serpentine contour that the eye
follows like a river. Segments that start and stop read as folds. Same for rock
strata: short authored ledges, never full-width scanlines.

### Mist must pool, not band

A mist band with a flat top edge is a scan bar. Mist is given:
- a **per-column vertical offset**, so its ceiling undulates;
- **local pooling at specific x-positions** near the base of crags, so it looks
  like it settled where the rock is;
- **no band across the waterline at all** — that produced a dotted line across
  the entire frame. Low mist now exists only where there is rock to pool against.

### What still needs work

- The notch spires are still too uniform in spacing and all lean vertical. They
  need clustering and two or three distinct archetypes, not one repeated.
- The left massif's faceting is only three planes; it wants a fourth and a
  shadow plane at the silhouette edge.
- Perspective: the water reflection is a mirror. It should compress toward the
  horizon and darken with distance.
- No dragons yet. The notch is sized for them: roughly 170px of clear air
  horizontally at the mouth, which comfortably takes a body 140px long.

---

## Attempts 12–47: what a measured audit loop actually found

v1–v6 above were judged by eye. From v12 onward the generator ran a **numeric
audit** on every render, with hard gates, and the loop became: generate → audit →
look at 2× → fix the *measured* defect → archive an independent review verdict
(`docs/reviews/`). Four reviews, three FAILs. This table is the useful part, and
it is longer than v1–v6 because the failures got subtler, not rarer.

| Iter | Measured symptom | Actual cause | Fix |
|---|---|---|---|
| r12 | band 5 covered 95.6% of frame | near bands were drawn taller *and* wider than far ones | rebuilt as a V-notch: near massifs are narrow edge cliffs cropped by the frame, far ridges show *inside* the notch |
| r15 | flat shelf across the valley | every mass shared one flat base row | ragged per-column dissolving base |
| r18 | strata spilled into the notch as floating beige slabs | region clipping was to the band, not the face | clip regions to the face, inset 6px from skyline; strata forced `offset <= 0` |
| r18 | near cliffs were *pale*, far ridges dark | `FACE = [3,3,4,4,5,5]` inverted the ramp direction | `FACE` dark→near, pale→far. Atmospheric perspective is a property of the *fill*, not the outline |
| r20 | warm pixels 0.15% | coat-of-paint ramp was never actually reached by any region | rewrote region offsets against the real ramp → 10.9% |
| r23 | hard vertical edges inside every mass | rectangles have vertical sides | tapered trapezoids (`tp` px/side) |
| r23 | slabs collapsed to one tone | `FACE[5]=1` mapped to `ramp[1]` while `DARK[0]=ramp[0]` — one entry apart | separate the two tables so a slab can be 2+ entries from its neighbour |
| r24 | **every band filled the notch — one giant flat box** | `_build_crest` carried `last` across every column, so each edge cliff's crest ran to the opposite frame edge | reset the carried value at each authored node |
| r25 | cream slabs as full panels | buttress regions used +4/+5, painting the warm end as a field | cap lit offset at +2; warm only as narrow accents |
| **r25 verdict** | **reviewer FAIL: bands sat side by side in x-slices, not one behind another** | composition, not shading | — |
| r26 | — | — | **architectural fix**: full-width crests, drawn strictly back to front, one mass per band. Occlusion became plain overdraw |
| r26 | base was an alpha fade → visible picket fence | per-column alpha ramp quantised into stripes | mist repainted as an **opaque painted field** with a cloudy top edge |
| r30 | 200px vertical runs inside faces | no horizontal structure at all | authored bedding lines |
| r31 | full-frame opacity gate failing on the *sky* | the gate was wrong, not the art | rescoped: nothing *below the skyline* may be transparent |
| r32 | uniform sawtooth — every summit one triangle | alternating summit/saddle nodes at even spacing ⇒ constant prominence | authored summit archetypes (spire / shoulder / mesa / dome), hand-placed |
| r33–r36 | plaid | vertical slabs + horizontal bedding = two orthogonal families of flat rects | deleted bedding entirely; strata come from authored darks |
| r36–r37 | a uniform wall of peaks | evenly distributed peaks read as pattern | valley composition: two edge massifs, deep centre, corridor right of centre |
| r40 | 126px vertical seams | a slab is an x-range at every y ⇒ dead-vertical edge | slant each slab edge with the crest's own rise |
| r41 | visible zigzag on cliffs | per-row seam jitter | *jittering is worse than slanting* — steady slope, stepping every 7–9 rows |
| r44 | rock ended in mid-air above the mist | far band bases terminated at y=152/174/198, above the mist top | every mass runs past the frame bottom; only the front mist ends rock |
| r45 | 260 columns changing colour on one row | cloud-top sine sum was *multiplied* by a slow sine, so edge variation collapsed to 9px | *add* the slow sway instead of multiplying; two overlapping banks |

### The five transferable lessons

1. **A recalled bug is usually a structural inversion, not a tuning error.**
   Three separate failures — alpha inverted, ramp direction inverted, `last`
   carried across columns — all presented as "the picture is wrong in a vague
   way" and all were fixed by finding the one line where a value ran backwards.
   Reach for structure before parameters.
2. **Two orthogonal families of flat regions always read as plaid.** Vertical
   slabs plus horizontal bedding is a grid no matter how you tune it. Pick one
   direction per surface.
3. **Jittering an edge is worse than slanting it.** A per-row random offset
   reads as digital noise; a steady slope reads as a flank. Rock edges want to be
   *slanted and stepped*, never wobbled.
4. **A gate can be wrong.** Two audit gates had to be rewritten (full-frame
   opacity; flat-run vs seam). When a gate fails but the image looks right, check
   the gate — but only after assuming the art is wrong first, because it usually
   is.
5. **When a metric and a review disagree, believe the review.** The reviewer's
   one-line diagnosis at r25 ("side by side instead of one behind another")
   invalidated six rounds of shading work in a single sentence. Numeric gates
   catch regressions; they cannot catch a wrong composition.
