# Dragon Timer

> A focused timer whose alarm is a dragon crossing your landscape.

---

## The product question

A timer app is a solved problem. Nobody needs another one. So the only reason
this exists is: **the alarm moment is broken in every timer app**.

Every timer ends the same way — a notification, a beep, a modal. It interrupts
you with *noise*, and the noise is identical whether you wanted a break or
forgot a pot on the stove. It doesn't tell you *why* it's ringing, and it
certainly doesn't feel like anything.

Dragon Timer's thesis: **an alarm should be an arrival, not an interruption.**

When the timer ends, a dragon flies across your landscape, and the dragon *is*
the message. Long slow pass = "take your time, this is a break." A sharp,
direct dive = "get up now." You learn to read the dragon. That's the entire
product idea.

## Core loop

1. Pick a duration. (Or pick a *preset*: Focus 25, Break 5, Tea 3, Deep 90.)
2. Name it, optional. ("Pull the bread out.")
3. Press start. The window becomes the landscape, running.
4. Live in it or hide it. It keeps counting.
5. On end: **a dragon arrives.** Then, and only then, a quiet label.

## Choreography of the alarm

This is the craft. Six phases, ~9 seconds total:

| t | Phase | What happens |
|---|---|---|
| 0.0s | **Stillness** | The pan *stops*. This is the only time the camera ever stops. The stop itself is the alert. |
| 0.0–0.6s | **Pressure** | Mist thickens slightly, ambient sound ducks. A held breath. |
| 0.6s | **Arrival** | The dragon enters — but *from* the direction the timer's meaning implies (see below). |
| 0.6–4.0s | **Pass** | It flies a short, deliberate path. Fast, but not frantic. Never bobbing. |
| 4.0–5.2s | **Turn** | It slows near the centre, turns its head **toward the viewer**. Only time this ever happens. |
| 5.2–6.4s | **Speech** | The timer label fades in *below* the dragon, in the same paper-cream ink. It reads:  `°  Bread is done  ` |
| 6.4–9.0s | **Exit** | The dragon leaves upward into mist, camera resumes panning. |

Two decisions worth calling out:

- **The camera stopping** is the alert. We have trained the user for hours that
  this image moves. When it stops, they feel it before they see anything. Zero
  pixels needed. This is the most elegant thing in the whole design.
- **The dragon looks at you once.** In the wallpaper it never does. Here it
  does, exactly once, and that's why it lands.

### Dragon intensity = timer kind

| Timer kind | Dragon | Why |
|---|---|---|
| **Break / rest** | Slow traverse, jade, far-to-mid depth, long lazy S | "unwind, no rush" |
| **Focus end** | Direct mid-depth pass, ash, crisp | "you're done, stand up" |
| **Hard alarm** (kitchen, meds) | Fast low dive, cinnabar, near depth, mouth open | unmistakable |
| **Interval / pomodoro repeat** | Two dragons, one after the other, smaller | "again" |
| **Gentle / sleep** | Ivory, very far, barely visible, fading | "let go" |

This table is the real design. It's also why the dragon variety in
`20-dragon-design.md` isn't decoration — it's *semantics*.

## Audio

Optional, off by default for the wallpaper, on for the timer.

- No beeps. A **low stone chime** (one struck note, long decay) at t=0.6s,
  when the dragon arrives. It should sound like the landscape, not like a UI.
- A soft **air/wind swell** under the pass, ducking the ambient bed.
- The chime is the *only* sound that must cut through other audio. Use it as the
  OS notification sound too, so the brand is consistent in the notification
  centre.
- Accessibility: respect "reduce motion" (see below), and always support a
  fallback OS notification so a missed window still alerts.

## Window & presence

Three modes, one app:

1. **Full window** — the landscape, large, with a minimal timer readout in the
   corner (`23:41` in the paper-cream font, small, no boxes).
2. **Compact / floating** — a 320×180 mini-landscape pinned anywhere, always
   visible, with the countdown. This is the mode people will actually use while
   working. A dragon can fly *through* the mini window too.
3. **Menu bar** — a 1px dragon glyph and remaining time. Clicking expands to
   compact. This is the "I forgot it was running" mode, and it's fine.

Setting the timer must be possible in **under 3 seconds**: type `25` + Enter.
Also drag a dial (a circular dial rendered as a stone ring with a jade bead
marker — consistent with the art). No sliders with 1-minute increments for a
90-second timer.

### The handoff to the wallpaper

If the wallpaper is installed and running, the timer's alarm should play **in
the wallpaper**, not in the app window. The app sends the event, the wallpaper
performs it. That's the "one world" promise and it's the thing that makes the
two apps feel like one product rather than a bundle.

Implementation: local IPC (see `50-tech-architecture.md`). If the wallpaper
isn't there, the app performs the scene itself. Same renderer, so it looks
identical — only smaller.

## Respecting the user

- **No sound before it's earned.** Default: silent start, chime at the end.
  Mute is one click, always visible.
- **Never steal focus.** The alarm must not break the user's typing. A
  full-screen dragon that steals focus is a *hostile* timer.
- **Reduce Motion**: if enabled, the dragon pass is replaced by a still dragon
  and a slow mist reveal, plus the OS notification. Honestly *beautiful*, not a
  degraded fallback.
- **Do Not Disturb**: respect it, but re-send once after DND ends. Don't spam.
- **Missed while asleep**: on wake, don't replay a backlog. One dragon, and if
  more than one timer ended, one dragon per timer, spaced 2s. Cap at 3.
- **No accounts, no telemetry by default.** A timer is private. If we ever add
  focus stats, it's local-only and opt-in.

## Screensaver

A `.saver` bundle reusing the renderer, slowly panning, with a rare dragon. This
is a 30-line host around `DragonKit` and it's the best possible demo of the
art — people will install the wallpaper because they saw the screensaver.

## What v1 is not

- No task lists, no projects, no integrations, no calendar.
- No stats, streaks, or gamification.
- No custom character creation. Five dragon variants, fixed.
- No multiplayer/shared timers. (Tempting. v3 at the earliest.)

## Success test

Use it for a week.

- The alarm never startles you; it *arrives*.
- You can tell, without reading, whether it was a break or an alarm.
- You stop setting phone timers for things you're sitting at your desk for.
- You leave the compact window open even when no timer is running, because you
  like having it there. That last one is the real proof.
