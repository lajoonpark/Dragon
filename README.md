# Dragon

An animated pixel-art wallpaper: layered shanshui mountains, drifting mist, and
long-bodied wingless dragons that slip *behind* the ridges and out the other
side. Paired with **Dragon Timer**, a focused timer whose alarm is a dragon
arriving in your landscape instead of a beep.

> Status: **design phase.** No code yet — the plan lives in [`docs/`](docs/).

## Read the plan

Start at [`docs/README.md`](docs/README.md), or jump straight to the core idea:

- [`docs/10-depth-and-occlusion.md`](docs/10-depth-and-occlusion.md) — how
  "depth without 3D" actually works
- [`docs/20-dragon-design.md`](docs/20-dragon-design.md) — the dragon
- [`docs/35-ambient-life.md`](docs/35-ambient-life.md) — what happens when no
  dragon is on screen (half the time)
- [`docs/40-timer-app.md`](docs/40-timer-app.md) — the companion app
- [`docs/55-platform-portability.md`](docs/55-platform-portability.md) — why
  Windows/Linux are a host, not a rewrite
- [`docs/60-roadmap.md`](docs/60-roadmap.md) — what gets built, in what order

## Shape of the thing

| | |
|---|---|
| Internal resolution | 480x270, integer-scaled (x4 -> 1920x1080) |
| Frame rate | 15 fps (pixel-authentic, and 4x cheaper than 60) |
| World | 7680px handscroll, camera pans ~7px/s |
| Depth | per-pixel depth buffer; per-segment depth along each dragon |
| Core | dependency-free C99, testable on Linux, drives Swift hosts |
| Dragons on screen | ~50% of the time, ~30s mean gap |
| Hosts | macOS wallpaper agent, Dragon Timer, `.saver`, (WASM demo) |
| Portability | 10-function `dr_host` vtable; core has zero platform `#ifdef`s |

## Quick sanity check of the core idea

The scene has a depth field. A dragon's depth varies from head to tail. A dragon
pixel is drawn only if it's nearer than the scene pixel behind it:

```
head depth 0.30 -------- body 0.55 -------- tail 0.75
      |                      |                    |
   in front of           inside the           behind the
   far peaks             mid mountains        foreground rock
```

That's it. That's the whole trick, and it's why a dragon can dive through a
mountain range in one continuous move with no popping.

## What happens when no dragon is on screen

Half the time, nothing but landscape — so the landscape has to carry it. Three
tempos of motion, all driven by one coherent gust field:

- **slow** (~20-60s) — mist drift, grass leaning, water dash rows
- **medium** (3-8s) — wind gusts sweeping through, petals falling, waterfall
- **fast** (1-3s) — a bird flock every few minutes, a ripple, a lantern flicker

And when a dragon appears, all of it quiets down for a moment. The scene holds
still for the dragon, then settles back. Users can't say what changed, but they
feel that the dragon matters.
