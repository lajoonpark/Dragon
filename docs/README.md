# Dragon — design docs

Read in this order. Each doc stands alone, but they build.

| # | Doc | What it answers |
|---|---|---|
| 00 | [Vision](00-vision.md) | What is this, what does it feel like, what are we deliberately not making |
| 10 | [Depth & Occlusion](10-depth-and-occlusion.md) | **The core mechanic.** How a dragon slips behind a mountain, and why not with layers |
| 20 | [The Dragon](20-dragon-design.md) | Silhouette, proportion, the procedural body rig, palettes, and how it flies |
| 25 | [Art Pipeline — superseded](25-art-pipeline.md) | Why procedural rock generation failed. The failure ledger (v1–v6, r12–r47). **Historical — read for the argument, not the method** |
| 27 | [**Master Image Pipeline**](27-master-image-pipeline.md) | **How the background actually gets made now.** Generate a master image, reduce it to a true pixel grid, extract a depth field. Code does not re-draw the rock, and the image is **not** split into layers (D-026) |
| 28 | [**Master Generation Prompt**](28-master-generation-prompt.md) | The literal prompt to paste into the image model, the negative prompt, the pre-acceptance checklist, and the backing plates |
| 30 | [Scene & Composition](30-scene-composition.md) | The handscroll, depth stack, mountain archetypes, water, weather, shot list |
| 35 | [Ambient Life](35-ambient-life.md) | **The other half.** Wind gusts, petals, waterfalls, birds, the hush, and the density budget |
| 40 | [Dragon Timer](40-timer-app.md) | The companion app: why it exists, the alarm choreography, intensity = meaning |
| 50 | [Technical Architecture](50-tech-architecture.md) | C core + Swift hosts, 15 fps, power, determinism, the Linux dev loop, macOS landmines |
| 55 | [Platform Portability](55-platform-portability.md) | **The `dr_host` contract.** How Windows and Linux become a host, not a rewrite |
| 60 | [Roadmap](60-roadmap.md) | Phases, exit criteria, what's deferred and why |
| 70 | [Decisions & Questions](70-decisions-and-questions.md) | Append-only decision log, open questions, things we'll probably be wrong about |

## Where the prototype stands

`tools/proto/gen_layer.py` was **instrumentation, not product code** — it existed
to answer "can this art direction be built procedurally". **Answer: no.** Forty
rounds reached 12 of 13 audit gates and still failed on the things that matter
(repeated chevron flanks, no warm light, tiering by row). The method is now
`27-master-image-pipeline.md`: generate, reduce, dismantle. The generator is kept
for its audit harness, which becomes the acceptance tests for generated art.
Images in `docs/review/`; verdicts in `docs/reviews/`.

| Round | Verdict |
|---|---|
| r06 | FAIL — `docs/reviews/r06-verdict.md` |
| r11 | FAIL — `docs/reviews/r11-verdict.md` |
| r25 | FAIL — `docs/reviews/r25-verdict.md`; the decisive one, found that the bands sat side by side instead of one behind another |
| r47 | **FAIL, self-reviewed** — `docs/reviews/r47-self-review.md`. The independent reviewer could not be launched; this verdict is mine, not independent. Composition and structure now hold, but the flanks are still a repeated chevron run and there is no warm light on any rock face |

The audit loop and what each round's failure taught is tabulated in
`25-art-pipeline.md` — that ledger is the argument for the pipeline change. The two corrections it forced on the *plan* are recorded at
the end of `10-depth-and-occlusion.md` (mist is opaque, not alpha) and
`30-scene-composition.md` (bands stack front-to-back, not side by side).

## Where it stands now — the background is proven

Two questions were open at the start of this phase. Both are now answered with
working code on the real master image:

| Question | Answer | Report |
|---|---|---|
| Can a dragon pass behind a ridge without layers? | **Yes.** One depth test per pixel; 10/10 test frames had one unbroken body both in front of and behind scenery | [`reviews/c01-depth-test.md`](reviews/c01-depth-test.md) |
| Does a flat image need splitting for parallax? | **No — and it cannot be.** Per-depth warping smears irreversibly; the content behind nearer objects does not exist. Rigid pan + drifting mist (D-026) | [`reviews/c01-parallax-test.md`](reviews/c01-parallax-test.md) |

The reduction itself is also settled: 24 colours, 1440×810 crop, exact ÷3 to
480×270 — [`reviews/c01-reduction.md`](reviews/c01-reduction.md).

**Consequence: the layer split and its backing plates are off the project.**
The "hole problem" (D-024) is closed on both halves — nothing is removed, and
nothing slides relative to anything else.

## The four sentences

1. It's a pixel-art shanshui handscroll that pans slowly forever, and dragons
   fly through it with **real depth** — a dragon's body has depth along its
   length, so it genuinely slips behind a ridge and out the other side.
2. Depth without 3D comes from exactly three things: **overlap, desaturation
   with distance, and mist between planes.** Nothing else.
3. Dragons are on screen about **half** the time, so the landscape has to carry
   the other half — that's **wind, petals, waterfalls and birds**, which all
   quiet down the moment a dragon arrives.
4. Dragon Timer is the same world at a smaller scale, and its alarm is a dragon
   **arriving** instead of a beep interrupting you.

## If you only read two things

Read `10-depth-and-occlusion.md` and `35-ambient-life.md`. One is the idea;
the other is what makes the idea bearable to look at all day.
