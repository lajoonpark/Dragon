# The Dragon

> Long-bodied, wingless, four-legged, antlered. It must read as *air moving in
> a shape*, not as a character sprite that flies.

---

## Design language

### Silhouette first

Every dragon must be identifiable as a 1-colour silhouette at 40px wide. That
means:

- **A long, tapering S** — the body is the dragon. Not the head.
- **A clear head kink** — the neck bends at a distinct angle from the body, so
  the eye finds "front" instantly. Without the kink, a serpentine ribbon reads
  as a snake, or worse, a rope.
- **A tail flare** — the tip ends in a small fan/tuft. This is what makes it
  read as a dragon tail rather than a sliced-off sausage.
- **Antlers/horns** — 2px wide breaks in the head silhouette. These are the
  single most important identity pixels in the whole design.

### Proportion (in body-widths)

```
head      1.0 × bw      (with antlers extending 0.8 bw)
neck      2.0 bw
torso     5.0 bw
tail      4.0 bw
total    ~12 bw  →   length ≈ 12 × body_width
```

At near depth `bw = 5px` → a ~60px long dragon. At far depth `bw = 2px` →
~24px, which still reads. Keep the ratio fixed; scale everything together.

### Four legs, usually tucked

Legs are the fastest way to lose the "air current" feel. Rules:

- Legs are visible only when **the dragon is at low depth-variation** (i.e.,
  moving broadly parallel to the screen). During dives/turns, tuck them.
- Each leg is 2–3px: thigh stub + foot. Nothing more. Think of the reference
  image's tiger-ish rock formations — shape over anatomy.
- Front legs sit under the neck kink; back legs 2.5 bw behind them.
- The **whiskers** (barbels) off the snout are worth it at near depths: two 4px
  curves that trail with the head's velocity. They sell the whole thing.

### Head: quantised, not simulated

Do **not** free-rotate the head sprite. Rotate the body, but snap the head to
one of **16 pre-drawn directions** (16 × 3 frames idle/roar = 48 tiny assets per
depth variant). Rationale:

- Rotation of a 12×12 pixel head destroys the pixel grid — antlers turn into
  mush.
- Hand-drawn per-direction heads let a *human* fix the readability at each
  angle, which is where dragon charm actually lives.
- 16 dirs is enough; the body hides the seams at in-between angles.

Head animation states:
- `drift` (default, 2-frame breathing)
- `look` (turns 1–2 steps toward the camera; use sparingly, once per pass)
- `roar` (mouth opens, 3 frames — only during the Timer payoff, see `40-timer-app.md`)

## The body: procedural ribbon

The body is **generated**, not sprited. Why: a 60px serpentine dragon at 16
orientations × 8 wave phases is hundreds of assets; procedural is ~20 lines and
infinitely smooth.

### Spine

A rope of N points (N ≈ 22 for a near dragon, 14 for a far one).

```
Step 1 — leader. Advance a point along the path at speed v.
Step 2 — follow. Each subsequent point lerps toward the one ahead of it,
         constrained to a max distance of `spacing`.
```

This yields a natural, whip-like, lagging motion for free — the tail always
does what the head did, a moment later, slightly wider. This is *the* trick that
makes a dragon feel like it has mass. No sine waves driving position; sine waves
only modulate the *wave amplitude*.

### Undulation

On top of the rope, apply a travelling sine perpendicular to the local tangent:

```
offset(p_i) = normal_i × A(i) × sin(2π (i / wavelength) − ω t)
A(i) = A_max × sin(π × i / N)          // 0 at head and tail, max at mid-body
```

`A_max ≈ 0.6 × bw`, `wavelength ≈ 6–8 spine points`, `ω ≈ 1.5–2.5 rad/s`.

Amplitude fading to zero at *both* ends is essential — a uniform sine makes the
head waggle, which instantly reads as a fish.

### Cross-section

At each spine point, draw a perpendicular bar of pixels, width tapered:

```
width(i) = bw × taper(i)      // taper: 0.55 head → 1.0 torso → 0.15 tail tip
```

Then stamp, per body-width, in this order:
1. Body fill from the depth-appropriate ramp.
2. **Top highlight**: 1px of the ramp's light step along the upper edge.
3. **Belly**: 1px of a warmer cream step along the lower edge, only where
   `depth > 0.45` (belly is a near-field detail; it would turn to noise at
   distance).
4. **Scales**: sparse 1px marks every ~3 body-widths, only at `depth > 0.6`.
5. **Dorsal fin**: optional 1px ridge, only on the "elder" dragon variant.
6. **Ink outline**: 1px, near-depth only.

### Depth along the body

`depth(i)` is interpolated from 2–4 depth keys assigned to the path. Render each
spine point's bar with its *own* depth, which gives:

- Automatic partial occlusion mid-body (the money shot).
- Automatic per-segment palette shift, so a dragon diving away gets visibly
  cooler and more dithered as its tail follows.
- Automatic scale taper into the distance — a dragon flying *away* literally
  gets smaller along its length, which is subtly but powerfully correct.

## Palette by depth

Each dragon has a **hue identity** (jade, cinnabar, ash, ivory, indigo) but the
actual ramp is derived from the depth it's at:

| Depth | Ramp behaviour | Outline | Opacity feel |
|---|---|---|---|
| 0.05–0.20 | 90% toward mist colour, 3 values | none | dithered 50%, reads as shadow-in-fog |
| 0.20–0.40 | 60% toward mist, 4 values | none | dithered 25% |
| 0.40–0.60 | 25% toward mist, 5 values | 1px, 30% ink | solid |
| 0.60–0.85 | full ramp, 6 values + belly | 1px full ink | solid, dark |

**Dithering is the depth cue, not transparency.** Alpha-blending a pixel sprite
produces mud; a Bayer-dithered silhouette against mist produces *atmosphere*.

Recommended ramps (each 6 steps, dark→light):

- **Jade** `#12211d #1c3a30 #2a5546 #3f7460 #6aa088 #b9d6c2`
- **Cinnabar** `#241412 #401f1a #6b2f24 #9a4630 #c97451 #f0bda0`
- **Ash** `#141821 #232a36 #39445a #566580 #8b9bb5 #d3dbe6`
- **Ivory** `#2a2620 #4a4238 #706550 #9c8f74 #c9bd9f #f2ecd9`
- **Indigo** `#0f1420 #1a2436 #28364f #3d5075 #62789e #a8b8d2`

Ivory and Ash should be rare — they're the "elder / spirit" dragons and their
rarity is what makes them feel special.

## Motion: how it flies

### Path types

| Path | Feel | Use |
|---|---|---|
| **Traverse** | Long lazy S across the whole width, near-horizontal | the default event |
| **Dive** | Enters high/far, sweeps down through midground, exits low/near | the "hero" shot, ≤1 per hour |
| **Coil** | Circles around an off-screen pivot, briefly coils into the frame | rare, delightful |
| **Weave** | Zigzags through the valley between two peaks, changing depth | shows off occlusion |
| **Rise** | From behind a foreground rock, straight up, into cloud | short, punchy |
| **Hover** | Slow drift with a stall-and-turn | only for Dragon Timer payoff |

Paths are authored as **cubic splines in (x, y, depth) space**, then the dragon
follows them with the lagging-spine rig. Authoring 6–8 of these is enough for a
very long time.

### Timing / pacing (this is the soul of it)

- **Speed**: a traverse should take **35–70 seconds** to cross a 1920px screen.
  That's ~30–55 px/s at 1×. If you're not sure, slow it down.
- **Gap between dragons**: weighted random, `mean ≈ 30s`, `min 12s`, `max 90s`.
  Pairs overlapping ~8% of the time (two dragons sharing the range is lovely,
  as long as their paths don't collide on screen). The world should feel
  inhabited, not like a fish tank — see `35-ambient-life.md` for the pacing
  rationale and the "hush" that keeps each dragon an event.
- **Bank**: the body rolls slightly into turns — implemented as a 1px vertical
  shear of the cross-section bars, scaled by lateral acceleration. Cheap, huge.
- **No bobbing.** Ever. Vertical oscillation is the #1 thing that makes a flight
  animation look like a floating sprite.

### Idle behaviours that cost nothing

- **Mist trails from the body**, at 25% opacity, 3–4px behind, dying out in
  ~1s. Sells speed without motion blur.
- **A single falling scale** occasionally detaches and drifts down. 1px. Rare.
- **Water reflection of the dragon** — when a dragon crosses above the water
  plane, flip it vertically below the waterline at 35% contrast, offset by a
  1–2px horizontal wobble per frame, and **clip it at the water's depth** so it
  interacts with the mist correctly. This is a *huge* payoff for ~15 lines of
  code and it's the kind of detail that makes people screenshot your wallpaper.

## What we explicitly avoid

- Round eyes. Use a 1–2px angled glint only.
- Teeth in the default head. Mouth closed almost always.
- Any frame where the dragon's head is the only thing on screen.
- Dragons entering from exactly screen-left at exactly mid-height.
- Two dragons doing the same path type at the same time.
- The dragon "noticing" the viewer. Breaking the fourth wall kills the
  wallpaper's calm — with one deliberate exception (Timer payoff).
