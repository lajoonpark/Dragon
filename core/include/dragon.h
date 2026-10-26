/* Dragon — public core API.
 *
 * The core knows nothing about any operating system: it reads plain data in and
 * writes a 480x270 RGBA8888 framebuffer out (docs/55-platform-portability.md).
 * Every platform call is behind dr_host.
 *
 * Determinism: everything random derives from one 64-bit seed, and stepping is
 * fixed-timestep. Same seed + same dt sequence => same bytes, forever.
 */
#ifndef DRAGON_H
#define DRAGON_H

#include <stdint.h>

#include "dragon_host.h"

#define DR_W 480
#define DR_H 270
#define DR_DEFAULT_FPS 15
/* Camera speed, px/s (docs/30: the handscroll pans ~7 px/s). Public because a
 * host needs it to reason about the loop period, and because the tests assert
 * the wrap using only the public API. */
#define DR_PAN_PX_S    7.0

/* Weather / time-of-day preset. Only DAWN_MIST ships in v1 (docs/30). */
enum {
    DR_PRESET_DAWN_MIST = 0,
    DR_PRESET_COUNT
};

typedef struct dragon_world dragon_world_t;

/* Events translated by the host into core vocabulary (docs/55). The core never
 * sees a keycode or a window. */
typedef struct {
    int type;
    float x, y;
    float value;
} dr_event;

enum {
    DR_EV_NONE = 0,
    DR_EV_PAN_NUDGE,
    DR_EV_SUMMON_DRAGON,
    DR_EV_TIMER_FIRED,
    DR_EV_TIMER_TICK,
    DR_EV_PREFS_CHANGED,
    DR_EV_SURFACE_RESIZE,
    DR_EV_PAUSE_TOGGLE
};

/* Verification views. The prototype is background-only, so these are how we
 * check the parts that are invisible by design (depth, emitters). */
enum {
    DR_VIEW_SCENE = 0,   /* the composed background */
    DR_VIEW_DEPTH,       /* depth field, far blue -> near warm */
    DR_VIEW_EMITTERS,    /* waterfall mask + emitters, over the scene */
    DR_VIEW_LIFE         /* the moving layer alone, over flat paper */
};

dragon_world_t *dragon_world_create(const dr_host *host, uint64_t seed, int preset);
void dragon_world_destroy(dragon_world_t *w);

/* Advance by a fixed timestep. Hosts must accumulate and call this in whole
 * 1/15 s steps -- never variable dt (docs/50). */
void dragon_step(dragon_world_t *w, double dt);

/* Compose one frame. Writes DR_W*DR_H*4 bytes of RGBA8888 in row-major order. */
void dragon_frame(dragon_world_t *w, uint8_t *rgba);

void dragon_event(dragon_world_t *w, const dr_event *ev);
void dragon_set_view(dragon_world_t *w, int view);

/* ---- Dragon Timer (docs/40) --------------------------------------------
 *
 * The alarm is a scene event, not a notification: the camera stops (that stop
 * IS the alert), the mist thickens for a held breath, the dragon arrives, and
 * only then does the label appear. The timeline lives in the core so it stays
 * deterministic and testable; the host only supplies time and draws chrome.
 */

enum {
    DR_TIMER_IDLE = 0,
    DR_TIMER_RUNNING,
    DR_TIMER_ALARM
};

/* Timer kind picks the dragon's intensity once the rig exists (docs/40). The
 * value is stored now and surfaced through dragon_timer_kind() so the host and
 * the shot selector can be written against a stable API. */
enum {
    DR_TIMER_FOCUS = 0,     /* direct pass, "you're done, stand up" */
    DR_TIMER_BREAK,         /* slow lazy traverse, "unwind" */
    DR_TIMER_ALARM_HARD,    /* fast low dive, unmistakable */
    DR_TIMER_INTERVAL,      /* two dragons, "again" */
    DR_TIMER_GENTLE,        /* barely visible, fading, "let go" */
    DR_TIMER_KIND_COUNT
};

/* Phases of the ~9s alarm choreography (docs/40). */
enum {
    DR_ALARM_NONE = -1,
    DR_ALARM_PRESSURE = 0,  /* 0.0-0.6s the held breath */
    DR_ALARM_PASS,          /* 0.6-4.0s the dragon crosses */
    DR_ALARM_TURN,          /* 4.0-5.2s it turns to look at you */
    DR_ALARM_SPEECH,        /* 5.2-6.4s the label appears */
    DR_ALARM_EXIT           /* 6.4-9.0s it leaves, camera resumes */
};

#define DR_TIMER_LABEL_MAX 40

/* Start (or restart) a countdown. `seconds` must be > 0. `label` may be NULL.
 * `kind` is one of DR_TIMER_*KIND. */
void   dragon_timer_start(dragon_world_t *w, double seconds, const char *label, int kind);
void   dragon_timer_cancel(dragon_world_t *w);
void   dragon_timer_set_label(dragon_world_t *w, const char *label);

double dragon_timer_remaining(const dragon_world_t *w);
int    dragon_timer_state(const dragon_world_t *w);
int    dragon_timer_kind(const dragon_world_t *w);
/* Current alarm phase, or DR_ALARM_NONE when no alarm is playing. */
int    dragon_timer_phase(const dragon_world_t *w);
/* Seconds since the alarm began (0 while idle/running). */
double dragon_timer_alarm_time(const dragon_world_t *w);

/* Number of petals currently AIRBORNE (excludes those resting on rock/water).
 * Exposed for the ambience gates: docs/35 asks for 30-70 concurrent, and the
 * only way to check that is to ask. */
int  dragon_petal_count(const dragon_world_t *w);
int dragon_view(const dragon_world_t *w);

/* Ambience instrumentation: pixels that differ from the previous composed
 * frame. Used by the ship-blocking ambience test (docs/35). */
int dragon_frame_delta(const dragon_world_t *w);

/* Pan frozen, for isolating life motion from camera motion in measurements. */
void dragon_set_pan_paused(dragon_world_t *w, int paused);

/* 0.0 = infinitely far (sky), 1.0 = at the glass. Higher is nearer; a pixel at
 * depth d is occluded when d < the scene depth at that pixel (docs/10). */
float dragon_depth_at(const dragon_world_t *w, int x, int y);

/* World-space pan offset in pixels, for tests and diagnostics. */
double dragon_pan_offset(const dragon_world_t *w);

#endif /* DRAGON_H */
