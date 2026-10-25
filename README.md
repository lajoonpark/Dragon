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
- [`docs/40-timer-app.md`](docs/40-timer-app.md) — the companion app
- [`docs/60-roadmap.md`](docs/60-roadmap.md) — what gets built, in what order

## Shape of the thing

| | |
|---|---|
| Internal resolution | 480x270, integer-scaled (x4 -> 1920x1080) |
| Frame rate | 15 fps (pixel-authentic, and 4x cheaper than 60) |
| World | 7680px handscroll, camera pans ~7px/s |
| Depth | per-pixel depth buffer; per-segment depth along each dragon |
| Core | dependency-free C99, testable on Linux, drives Swift hosts |
| Hosts | macOS wallpaper agent, Dragon Timer, `.saver`, (WASM demo) |

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
