# Platform Portability

> macOS now. Windows and Linux later, by adding a host — not by rewriting
> anything.

---

## The rule

**The core knows nothing about any operating system.** It can't see a window, a
clock, a file, a socket, or a screen. It reads plain data in, writes a plain
framebuffer out.

If that rule holds, porting is a ~600-line host per platform. If it breaks, every
platform is a rewrite. That's the entire risk, and it's decided by discipline in
about five places, not by architecture diagrams.

## The contract

Everything a host provides, and nothing more:

```c
/* core/include/dragon_host.h  — implement once per platform */

typedef struct dr_host {
    void *user;

    /* REQUIRED ------------------------------------------------------- */

    /* Monotonic seconds. Must never go backwards. Used only to compute dt. */
    double (*now)(void *user);

    /* Present an RGBA8888 buffer. Core owns the memory; host must not
       retain it past return. Called once per rendered frame. */
    void (*present)(void *user, const uint8_t *rgba, int w, int h,
                    int scale_hint);

    /* Persisted prefs as a flat key/value blob. Host decides where
       (NSUserDefaults / registry / XDG config). */
    int  (*prefs_read)(void *user, const char *key, char *out, int cap);
    int  (*prefs_write)(void *user, const char *key, const char *val);

    /* OPTIONAL — each has a documented no-op default ------------------ */

    void (*log)(void *user, int level, const char *msg);

    /* Ambient audio: core asks for a bed and one-shots by name.
       Host may ignore entirely; scene stays silent. */
    void (*audio_bed)(void *user, const char *name, float gain);
    void (*audio_one)(void *user, const char *name);

    /* True when the surface is fully occluded / display asleep / on battery
       saver. Core skips rendering entirely rather than wasting power. */
    int  (*should_idle)(void *user);

    /* Inter-app bus for Dragon Timer <-> wallpaper (see 50-tech). */
    void (*bus_send)(void *user, const char *json_line);
    int  (*bus_poll)(void *user, char *out, int cap);

    /* Accessibility: motion reduction, high contrast, dynamic type-ish. */
    int  (*user_pref)(void *user, const char *name);
} dr_host;
```

That's ten functions, four required. **If a proposed feature needs an eleventh,
that's a design smell** — it almost certainly belongs in core.

### Inbound events, also plain data

```c
/* Keyboard / pointer / system events, translated by the host into core
   vocabulary. The core never sees a keycode, a window, or a button. */
typedef struct { int type; float x, y; float value; } dr_event;
enum {
    DR_EV_NONE = 0,
    DR_EV_PAN_NUDGE,     /* value = direction */
    DR_EV_SUMMON_DRAGON, /* the "give me one now" affordance */
    DR_EV_TIMER_FIRED,   /* value = intensity 0..3 */
    DR_EV_TIMER_TICK,    /* value = seconds remaining */
    DR_EV_PREFS_CHANGED,
    DR_EV_SURFACE_RESIZE /* x, y = new logical size */
};
```

So: the macOS host translates a menu item into `DR_EV_SUMMON_DRAGON`; the
Windows host translates a tray menu item into the same thing. The core has no
idea either exists.

## How the code is split

```
core/                     ~95% of the code, ZERO platform #ifdefs
  scene.c  rig.c  mist.c  water.c  ambient.c  wind.c
  palette.c dither.c paths.c clock.c bus.c font.c
  include/dragon.h        /* public API: init, step, render, event */
  include/dragon_host.h   /* the contract above */
platform/
  macos/                  Swift: NSWindow wallpaper + Timer UI + .saver
  linux/                  C: X11 override-redirect  (later)
  windows/                C++: Win32 layered window (later)
  web/                    C + emscripten, canvas present  (later, cheap)
```

**`#ifdef _WIN32` must never appear in `core/`.** Enforce it with a CI grep that
fails the build. This is a one-line rule that saves the project.

The only `#ifdef`s allowed in core are `<stdint.h>`-level portability shims and
a `DR_LITTLE_ENDIAN` check in the framebuffer write path.

## What actually differs per platform

Honest assessment of the hard parts, so there are no surprises later:

### The wallpaper surface (the genuinely hard bit, on every OS)

| OS | Technique | Reality check |
|---|---|---|
| **macOS** | `NSWindow` at `desktopWindow` level, `.canJoinAllSpaces`, `.stationary` | Our v1 target. Must not appear in Mission Control or the app switcher. |
| **Windows** | `SetParent(hwnd, WorkerW)` behind desktop icons — the classic Wallpaper Engine technique — with fallback to a borderless `HWND_BOTTOM` window | Well-trodden. The `Progman`/`WorkerW` enumeration is fussy across Windows builds, and the fallback path effectively *is* the fallback for Explorer restarts. |
| **Linux / X11** | `override-redirect` window at the bottom of the stack, or paint into the root pixmap (`_XROOTPMAP_ID`) | Works but interacts badly with compositors and with other wallpaper tools. `override-redirect` + `_NET_WM_WINDOW_TYPE_DESKTOP` is the pragmatic route. |
| **Linux / Wayland** | `wlr-layer-shell` on the `background` layer | **Not supported on GNOME.** GNOME users get the "borderless always-behind window" fallback or the `.saver` equivalent. Be honest about this on the site. |
| **Web** | `<canvas>` in a page | Trivially easy. Not a wallpaper, but a perfect demo and the proof that the core is decoupled. |

Consequence, and it's fine: **the wallpaper surface is the only genuinely
platform-specific, hard, uncertain part.** Everything above it is shared. That's
the design working as intended.

### The clock
`now()` is one function per platform. Core does the accumulator/fixed-timestep
math itself, so no platform can introduce variable-timestep bugs.

### Audio
Per-platform output backends, but the *core* owns the sound design decisions
(what plays when, gains, ducking) and just asks the host for named one-shots.
A Linux host with no audio backend at all is a valid build.

### File paths / config
The host owns them. Core only ever calls `prefs_read` / `prefs_write`.

### Multiprocess IPC
`bus_send` / `bus_poll` — Unix socket on macOS/Linux, named pipe on Windows,
`localStorage`+`BroadcastChannel` on web. Core just moves JSON lines.

## Build system

**CMake**, once, for the core and every non-macOS host:

```
cmake -B build                      # core + Linux host
cmake -B build -DDRAGON_HOST=win32  # core + Windows host
```

For macOS, the Xcode project (or `Package.swift` with the C target) consumes
`core/` as a plain C target. CMake can also generate the Xcode project, but a
hand-rolled Swift Package is less friction since the Swift side is small.

**No third-party dependencies.** Not one. That's what makes five hosts
affordable — there's nothing to port, vendor, or version. Every dependency we
add is a tax paid five times.

## Feature negotiation

Hosts differ, so the core must degrade gracefully rather than assume:

- `DR_CAP_AUDIO`, `DR_CAP_BUS`, `DR_CAP_PREFS`, `DR_CAP_IDLE` — declared by the
  host at init. Core checks before asking. Missing bus = timer-only mode.
- `DR_CAP_SCALE` — some hosts can present at native resolution, some can't. Core
  renders at 480×270 either way; the *host* does the integer scale. If a host
  can't integer-scale (some Wayland compositors fight it), core has a built-in
  nearest-neighbour upscaler as a last resort.

## Keeping it honest (the tests that protect portability)

1. **The grep test** — `core/` contains no `#ifdef` on a platform macro. CI fails
   otherwise.
2. **The stub-host test** — a `platform/null/` host (~80 lines, writes PPM,
   fake clock) is always in the test suite. If the core ever depends on a real
   platform, this stops compiling and we find out immediately.
3. **The WASM build** — once it exists, it's the second independent host. Two
   hosts that disagree about nothing is the strongest possible evidence the
   abstraction is real. Build it during Phase 3, not "someday".
4. **No absolute paths, no `#include <windows.h>` or `<AppKit/AppKit.h>` in core.**
   Obvious, and it's the one that actually gets violated at 1am.

## What we do for macOS now that pays off later

Cheap things, done at the start, that make ports easy:

- Put **every** platform call behind `dr_host`, immediately, even when there's
  only one implementation. Never call `NSLog` or `gettimeofday` from core "just
  this once".
- Write the **null host** in Phase 0, before the macOS host exists. We're
  developing headless on Linux anyway — the null host *is* the dev loop.
- Keep the present path dumb: `present(rgba, w, h, scale_hint)`. Don't let
  CoreGraphics or Metal types leak upward.
- Use integer, not float, for anything that crosses into platform code.
- Don't let the Timer UI own domain logic. The countdown engine lives in
  `core/clock.c` and knows nothing about AppKit; the SwiftUI view is a renderer
  for a struct.

## What would actually require a rewrite

Named explicitly so we can avoid them:

- Rendering directly into a platform surface (CoreGraphics, Metal, GDI, X11
  drawables). **Never do this.** Core writes to its own buffer, always.
- Threading model that assumes a platform run loop. Core is single-threaded and
  stepped by whoever calls it.
- Loading assets through platform APIs (`NSImage`, `StbImage`-less PNG). Assets
  are plain-text silhouettes and palette tables compiled into the binary.
- Assuming a display refresh rate, a scale factor, or a colour space.
- Assuming one window. Core renders a surface; it doesn't know how many exist.
  (Multi-display macOS = many surfaces, many `present` calls, one world.)

## Effort estimate for the ports

Once the core is stable, from the macOS v1 codebase:

| Port | Effort | Notes |
|---|---|---|
| WASM / web demo | 1–2 days | Highest value: doubles as marketing and as the abstraction test |
| Linux X11 | 3–5 days | X11 desktop window + compositor quirks |
| Windows | 3–5 days | WorkerW technique is documented, tray + prefs are routine |
| Linux Wayland (good) | weeks | GNOME fundamentally doesn't allow it; scope carefully or skip |
| Timer UI per platform | 2–3 days each | It's a small view over `core/clock.c` |

Total non-macOS, all in: about two weeks. That's the payoff for the discipline.
A rewrite would be two months per platform, which is why the discipline is
cheaper than it feels on day one.
