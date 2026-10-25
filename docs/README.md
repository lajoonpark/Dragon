# Dragon — design docs

Read in this order. Each doc stands alone, but they build.

| # | Doc | What it answers |
|---|---|---|
| 00 | [Vision](00-vision.md) | What is this, what does it feel like, what are we deliberately not making |
| 10 | [Depth & Occlusion](10-depth-and-occlusion.md) | **The core mechanic.** How a dragon slips behind a mountain, and why not with layers |
| 20 | [The Dragon](20-dragon-design.md) | Silhouette, proportion, the procedural body rig, palettes, and how it flies |
| 30 | [Scene & Composition](30-scene-composition.md) | The handscroll, depth stack, mountain archetypes, water, weather, shot list |
| 35 | [Ambient Life](35-ambient-life.md) | **The other half.** Wind gusts, petals, waterfalls, birds, the hush, and the density budget |
| 40 | [Dragon Timer](40-timer-app.md) | The companion app: why it exists, the alarm choreography, intensity = meaning |
| 50 | [Technical Architecture](50-tech-architecture.md) | C core + Swift hosts, 15 fps, power, determinism, the Linux dev loop, macOS landmines |
| 55 | [Platform Portability](55-platform-portability.md) | **The `dr_host` contract.** How Windows and Linux become a host, not a rewrite |
| 60 | [Roadmap](60-roadmap.md) | Phases, exit criteria, what's deferred and why |
| 70 | [Decisions & Questions](70-decisions-and-questions.md) | Append-only decision log, open questions, things we'll probably be wrong about |

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
