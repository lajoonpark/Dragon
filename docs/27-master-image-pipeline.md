# Master Image Pipeline — generate the art, then dismantle it

> **Supersedes** `25-art-pipeline.md` as the *production method* (not as an
> argument — the failure ledger there is why this document exists). Read that
> one for why procedural generation of form failed; read this one for what we do
> instead.

---

## The decision

**A generated master image is the source of truth for the landscape — including
its pixels. Code does not re-draw the mountains.**

The previous plan had the generator *invent* rock from arithmetic. Forty rounds
proved that does not work: a formula cannot make a mountain, and every attempt
produced a recognisable machine artefact (candles, tombstones, tablecloths,
sawtooth, chevron flanks). What eventually worked — hand-authored summits with
explicit prominence — is precisely *form by decision*.

An image generation model is a form-generating machine. It is the right tool for
exactly the step that resisted automation. So we invert the pipeline:

```
OLD:  code invents rock  →  code places rock  →  PNG
NEW:  model paints the scene  →  we dismantle it into layers  →  PNG
                                    ↑
                          code does palette, layers, depth, pan
```

### The amendment that decides whether this works

**Do not re-derive the image as code-drawn geometry.** That is the trap, and it
is how the previous forty rounds died. Re-deriving a generated image as polygons:

- discards the pixel decisions the model made, which are the only part worth
  having;
- re-enters the quantisation and inversion bugs that cost most of the audit loop;
- round-trips through lossy code for no gain.

The saving realisation: **the landscape is static.** It never moves. Only
dragons, mist, petals, birds are animated. So the master image can literally
*be* the shipped pixels. Code's job shrinks from "invent mountains" to:

1. **palette-lock** — reduce to one indexed palette
2. **layer-split** — cut the stack apart, with alpha
3. **depth-extract** — write the depth field from the layer order
4. **pan + composite** — scroll, and resolve dragons against the depth field

That is work code is genuinely good at, it is a fraction of the previous scope,
and it is testable on Linux with no Xcode.

---

## What the model is good for, and what it is not

| Good at | Bad at |
|---|---|
| Convincing karst silhouettes | Pixel art *discipline* (see below) |
| Natural stratification and facet structure | Exact palette adherence |
| Believable shanshui composition | Repeating an identical asset 16 times |
| Atmospheric perspective as a *look* | Alpha / layer separation |
| Rendering mist as volumetric form | Anything needing determinism |
| Variety — irreducible, hand-made-feeling rock | Being told "no anti-aliasing" and complying |

The model solves *invention*. It does not solve *discipline*. Discipline is the
reduction pass and the acceptance checklist below.

---

## Why AI "pixel art" is not pixel art

This is the single largest risk, and it is not fixable by prompting. Models
produce **pixel-styled** images: anti-aliased, thousands of colours, and
inconsistently gridded — different regions at different apparent resolutions,
because the model has never had to commit to one grid.

At 480×270 upscaled 4× for a 1080p wallpaper, that is glaring. Every soft edge
becomes a 4px gradient smear.

### The reduction pass (required, non-optional)

Workflow, in order. Each step is deterministic and testable:

1. **Generate at 1920×1080** (4× the target). Never ask the model for "480×270
   pixel art" — it will fail and you will have no detail to salvage.
2. **Downsample 4:1 with a per-block MODE filter**, not an average. Averaging
   creates new intermediate colours and destroys the grid. Mode picks the most
   common colour in each 4×4 block, which *keeps existing pixel decisions.*
   (Pillow has no mode filter at this size — write it, ~15 lines with numpy.)
3. **Palette-quantise to the locked project palette**, nearest in a perceptual
   space, with dithering OFF. If the image needs dither to survive quantisation,
   it has too many tones and the source is wrong.
4. **Hand-polish.** At 480×270 this is hours, not weeks: fix the silhouette
   edges, break any remaining aligned runs, place the one warm accent, repair
   eyes that read wrong. **This is the step that makes it pixel art.** The
   reduction gets you 85% of the way; the polish is the remaining 15% and it is
   the difference between "AI pixel art" and "pixel art".
5. **Audit.** Run the acceptance checklist (below). Fail → regenerate or
   re-polish, do not ship.

### The 85/15 rule

Assume the model gets you a composition and a silhouette structure. Assume you
must hand-fix: silhouette edges, all value boundaries that survived as soft
gradients, the focal structure, and every warm accent. Budget a real day of
polish per panel. That is still dramatically cheaper than 60 hand-painted
mountains, and it produces a better result than either approach alone.

---

## Layer extraction — cutting the master apart

The scene is cut back to front into the existing depth stack
(`10-depth-and-occlusion.md`). Six to eight layers, matching the bands:
sky wash / far peaks / mist A / mid peaks / mist B / near-mid / low mist /
near rock.

### The good news: this image is unusually easy to cut

The shared DNA of the reference style is *"stacked overlapping ridges separated
by mist."* Mist is near-flat cream. So **the separations are findable by colour
almost automatically** — the layer boundaries are exactly where the image goes
pale. Segmentation is not the hard part here; it is nearly free. This is a
straight payoff of "mist between planes": the style that creates the depth is
the same thing that makes the image dismantlable.

Practical method: threshold on luminance-with-warmth to find mist corridors,
take connected components for the ridges between them, then assign each ridge to
a band by its mean value (paler = further). Verify against the intended stack by
eye. Where the automatic split is ambiguous, cut by hand — it is a handful of
regions, not hundreds.

### The bad news: cutting leaves holes

If you lift the near massif out and pan, you expose **nothing** where it used to
be. Two fixes, and we need both:

1. **Inpaint behind each layer.** Ask the model to re-render the image with the
   near massif removed, or inpaint the exposed region. One call per layer.
   Generate the *back* of the stack first, then progressively add foreground —
   that guarantees you always have a complete image underneath.
2. **Over-extend every layer horizontally**, and cap parallax so a hole can never
   reach the frame edge. Concretely: each layer is generated/kept **wider than
   the frame by at least (pan_speed × layer_speed_delta × seconds_of_travel)**.
   Since layers scroll at different speeds, the differential — not the absolute
   speed — decides the overhang. Cheap insurance, and it makes the parallax
   legal by construction rather than by hope.

**Generate back-to-front.** Ask for the full scene first; then ask for variants
with the foreground removed. Never cut a hole you cannot fill.

---

## Consistency across the pan

Sixteen independently generated panels will not match: different palette,
different light direction, different mist density, different rock character.
Options, in descending order of preference:

1. **One very wide generation.** If the model supports wide aspect, generate
   2–3 screens in one image and cut it into panels. Best consistency by far.
2. **Chained outpainting** from a fixed first panel, with the palette locked and
   the prompt unchanged. Workable; drifts slowly.
3. **Reduce the ambition.** 4 screens instead of 16, with a long hold and a
   generous crossfade. This is the honest fallback and probably the right
   starting scope — see the roadmap change below.

Do not generate 16 panels independently and hope. That is a known failure.

---

## What this kills, and what survives

### Killed (good — it was weeks of work)

- The 10-archetype silhouette library and the ASCII silhouette authoring format
- The overlay-stamp system (ledges, cracks, tree bundles)
- The mirror × depth × overlay variety matrix
- Generative rock shading entirely: regions, trapezoids, slabs, darks, bedding

### Survives, and matters more

- **Depth and occlusion architecture** — unchanged, and easier with real layers,
  because drawing order genuinely *is* depth order.
- **The handscroll, the corridor, the notch** — composition rules are unchanged.
- **Ambient life** (wind, petals, waterfall, birds) — untouched; these were
  always going to be code.
- **The dragon** — untouched.
- **The timer app** — untouched.
- **The "mist is opaque, not alpha" correction** — still true and still load-bearing.
- **The audit harness — promoted to acceptance tests for generated art.** This
  is the most valuable residue of the forty rounds. It becomes the thing that
  catches AI tells: palette discipline, stray colours, seam detection, flat-field
  limits, warm-light presence.

### The audit gate that must be fixed first

The warm-pixel gate (`R−B ≥ 8`) counted the **cream mist**, so it reported 33%
warm while every rock face was monochrome blue — it passed a real defect. **Scope
it above the mist top.** A gate that can only pass is not a gate.

---

## Acceptance checklist (run on the reduced, polished master)

Adapted from the existing layer review gates. These are now tests for
*generated* art, which is a different job: they exist to catch the model's tells.

| # | Check | Threshold | Catches |
|---|---|---|---|
| 1 | Reads as mountains at 1× | eyeball | mush, noise, non-landscape |
| 2 | Distinct summits, no repeated archetype | ≥3 legible, no two identical | model tiling a motif |
| 3 | No vertical seams | longest interior seam ≤24px | column banding, grid artefacts |
| 4 | No horizontal rulers | no row >190 simultaneous changes | scanlines, tiering by row |
| 5 | Atmospheric perspective | monotonic pale←far | flat depth |
| 6 | Warm light above / cool below | warm pixels **above mist top** ≥8% | monochrome blue rock |
| 7 | Mist pools, is not a band | edge sweep ≥30px; pooling at crags | flat bar |
| 8 | Palette adherence | 0 colours outside the locked ramps | AA, soft gradients |
| 9 | Pixel discipline | no AA, no dither-as-fill | model's smooth edges |
| 10 | Vegetation as clumps on crests | not scattered dots | confetti |

If a check fails, the fix is regenerate-or-polish, **never** re-derive as code.

---

## Scope change to the roadmap

The 7680px / 16-screen world was justified by "we need enough content that it
never repeats". With generated panels, per-panel cost drops but *consistency*
cost rises, and the drift compounds over 16 screens. Recommendation:

- **v1: 4 screens (1920px world), one region, crossed-faded loop.** Four
  panels, one generation batch, one palette, far less drift.
- **Later: extend** to 8 and 16 screens using chained outpainting, once the first
  four are proven to match.

This trades "18 minutes before you notice" for "6 minutes and it genuinely
matches". For a wallpaper, matching beats long is the right bet, and it is
reversible — extending later is additive, whereas shipping 16 mismatched panels
is a rebuild.

---

## Risks

- **The model may not deliver karst.** It knows "Chinese mountain" well, so this
  is the lowest risk in the project.
- **The reduction may not survive.** If 4:1 mode-filtering produces mush, try
  generating at 3× and reducing 3:1, or generate at 2× and hand-polish more. The
  grid must be genuine or the whole aesthetic collapses.
- **Layer holes.** Mitigated by back-to-front generation plus over-extension.
- **Over-polish.** The polish pass is unbounded. Stop at "good"; the acceptance
  checklist defines good.
- **Legal / licensing.** Check the model's terms for redistributing generated
  art in a paid app. Resolve before Phase 5, not after.
