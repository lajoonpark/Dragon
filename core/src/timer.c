/* The Dragon Timer engine (docs/40).
 *
 * This is the app's clock and its alarm choreography, and it lives in the core
 * for the same reason everything else does: it must be verifiable off-device.
 * The host supplies wall-clock deltas; the phases, the camera stop and the
 * label are here, deterministic and testable.
 *
 * THE CENTRAL IDEA (docs/40): "The camera stopping is the alert. We have
 * trained the user for hours that this image moves. When it stops, they feel it
 * before they see anything. Zero pixels needed."
 *
 * So the alarm does not start with sound or a modal. It starts by taking the
 * one thing away that has been constant for hours. Everything after that is
 * craft on top of a signal that already landed.
 *
 * NOTE: the dragon itself is not built yet -- the core has no rig (see
 * docs/60 Phase 1). The choreography below is the full six-phase timeline with
 * the dragon's slot left explicitly empty, so the rig drops into a known shape
 * rather than requiring the timeline to be redesigned around it.
 */
#include <string.h>

#include "world.h"

/* docs/40, the phase table. Seconds from the alarm's first frame. */
#define T_PRESSURE_END   0.6
#define T_PASS_END       4.0
#define T_TURN_END       5.2
#define T_SPEECH_END     6.4
#define T_EXIT_END       9.0

/* The camera resumes during the exit, not after it: the world has to be moving
 * again before the label has finished leaving, or the alarm ends on two
 * simultaneous events and reads as a cut. */
#define T_CAMERA_RESUME  T_SPEECH_END

#define T_SPEECH_BEGIN   T_TURN_END
#define T_LABEL_FADE     1.2

void dr_timer_init(dr_timer *tm)
{
    memset(tm, 0, sizeof(*tm));
    tm->state = DR_TIMER_IDLE;
    tm->kind = DR_TIMER_FOCUS;
}

void dr_timer_start(dr_timer *tm, double seconds, const char *label, int kind)
{
    if (seconds <= 0.0) return;
    tm->state = DR_TIMER_RUNNING;
    tm->total = seconds;
    tm->remaining = seconds;
    tm->alarm_t = 0.0;
    tm->kind = (kind >= 0 && kind < DR_TIMER_KIND_COUNT) ? kind : DR_TIMER_FOCUS;
    tm->pressure = 0.0f;
    tm->label_alpha = 0.0f;
    tm->still = 0;
    tm->label[0] = '\0';
    if (label) {
        /* Truncate rather than overflow: this is a caption, and 40 characters
         * is already wider than the frame at this face. */
        strncpy(tm->label, label, sizeof(tm->label) - 1);
        tm->label[sizeof(tm->label) - 1] = '\0';
    }
}

void dr_timer_cancel(dr_timer *tm)
{
    dr_timer_init(tm);
}

void dr_timer_set_label(dr_timer *tm, const char *label)
{
    tm->label[0] = '\0';
    if (label) {
        strncpy(tm->label, label, sizeof(tm->label) - 1);
        tm->label[sizeof(tm->label) - 1] = '\0';
    }
}

/* One fixed timestep. Kept separate from the world step so the alarm timeline is
 * testable without rendering a frame. */
void dr_timer_step(dr_timer *tm, double dt)
{
    if (tm->state == DR_TIMER_RUNNING) {
        tm->remaining -= dt;
        /* Fire on a tolerance, not on > 0. Subtracting 1/15 thirty times from
         * 2.0 does not reach zero in binary floating point -- it leaves ~2e-16,
         * and a strict `<= 0.0` then fires one whole frame late on any timer
         * whose length is a whole number of seconds. That is the most common
         * case there is. The tolerance scales with the duration so a 12-hour
         * timer's accumulated drift (a few microseconds) is covered too, and it
         * is always far below one frame, so the alarm can never be visibly
         * early. */
        if (tm->remaining <= 1e-9 + 1e-9 * tm->total) {
            tm->remaining = 0.0;
            tm->state = DR_TIMER_ALARM;
            tm->alarm_t = 0.0;
            /* The stop happens on this exact frame. It is the alert. */
            tm->still = 1;
        }
        return;
    }

    if (tm->state != DR_TIMER_ALARM) return;

    tm->alarm_t += dt;

    /* Pressure: mist thickens for a held breath, then releases at arrival.
     * docs/40 puts it at 0.0-0.6s; it decays back over the pass so the world is
     * breathing again by the time the camera resumes. */
    if (tm->alarm_t < T_PRESSURE_END) {
        tm->pressure = (float)(tm->alarm_t / T_PRESSURE_END);
    } else if (tm->alarm_t < 1.2) {
        tm->pressure = 1.0f;
    } else if (tm->alarm_t < 3.0) {
        tm->pressure = (float)(1.0 - (tm->alarm_t - 1.2) / 1.8);
    } else {
        tm->pressure = 0.0f;
    }

    /* Label: absent until the speech phase, then a 1.2s fade -- the same rate
     * the mist moved at, so the two feel like one event. */
    if (tm->alarm_t < T_SPEECH_BEGIN) {
        tm->label_alpha = 0.0f;
    } else if (tm->alarm_t < T_SPEECH_BEGIN + T_LABEL_FADE) {
        tm->label_alpha = (float)((tm->alarm_t - T_SPEECH_BEGIN) / T_LABEL_FADE);
    } else {
        tm->label_alpha = 1.0f;
    }

    /* Exit: label fades out over the last second, and the camera comes back. */
    if (tm->alarm_t > T_CAMERA_RESUME) tm->still = 0;
    if (tm->alarm_t > T_EXIT_END - 1.0 && tm->alarm_t < T_EXIT_END) {
        tm->label_alpha = (float)(T_EXIT_END - tm->alarm_t);
    }

    if (tm->alarm_t >= T_EXIT_END) {
        dr_timer_init(tm);
    }
}

int dr_timer_phase(const dr_timer *tm)
{
    if (tm->state != DR_TIMER_ALARM) return DR_ALARM_NONE;
    if (tm->alarm_t < T_PRESSURE_END) return DR_ALARM_PRESSURE;
    if (tm->alarm_t < T_PASS_END) return DR_ALARM_PASS;
    if (tm->alarm_t < T_TURN_END) return DR_ALARM_TURN;
    if (tm->alarm_t < T_SPEECH_END) return DR_ALARM_SPEECH;
    return DR_ALARM_EXIT;
}

/* ---- rendering ---------------------------------------------------------- */

static void fmt_clock(double sec, char *out, int cap)
{
    int total = (int)(sec + 0.999);      /* count down, so 0.4s left shows 00:01 */
    int m = total / 60, s = total % 60;
    if (total > 99 * 60) { m = 99; s = 59; }
    if (cap < 6) { if (cap > 0) out[0] = '\0'; return; }
    out[0] = (char)('0' + (m / 10) % 10);
    out[1] = (char)('0' + m % 10);
    out[2] = ':';
    out[3] = (char)('0' + s / 10);
    out[4] = (char)('0' + s % 10);
    out[5] = '\0';
}

/* Drawn after the ambient layer, so it shares the one depth test everything else
 * uses. Text is an inscription on the painting, not a widget over it.
 *
 * docs/40 is literal about the colour: "paper-cream ink". Cream fill is what the
 * doc asks for and what a handscroll inscription looks like against a dark
 * ground -- but cream alone is invisible against the pale void the composition
 * deliberately keeps in the centre (measured 1.2:1, which is nothing). So the
 * glyphs get a 1px COOL-0 keyline, which is the same near-black the pines and
 * ridges use. Cream fill plus a dark keyline holds on the void, on mid-tone
 * wash, and on foreground rock, and it keeps the doc's colour rather than
 * quietly substituting a dark label. */
void dr_timer_render(DRW *w)
{
    const dr_timer *tm = &w->timer;
    const int ink = dr_pal_warm(1.0f);      /* paper cream (docs/40) */
    const int halo = dr_pal_pick(0.0f);     /* cool 0, near-black keyline */

    if (tm->state == DR_TIMER_RUNNING) {
        char buf[8];
        const int y = 12;
        fmt_clock(tm->remaining, buf, sizeof(buf));
        dr_text_draw_outlined(w, DR_W - dr_text_width(buf) - 12, y, buf,
                              ink, halo, DR_DEPTH_MAX);
    }

    if (tm->state == DR_TIMER_ALARM && tm->label_alpha > 0.02f && tm->label[0]) {
        /* docs/40 spells the line as "°  Bread is done  ": a small ring, then the
         * name. The ring is the same mark the app uses for "timer", so the
         * inscription reads as the app's voice rather than as plain body text.
         * Built here so the core owns the exact rendered line and the hosts
         * cannot drift from it. */
        char line[DR_TIMER_LABEL_MAX + 8];
        int n = 0;
        line[n++] = '~';                 /* the ring glyph, aliased to ° */
        line[n++] = ' ';
        line[n++] = ' ';
        {
            const char *p = tm->label;
            while (*p && n < (int)sizeof(line) - 1) line[n++] = *p++;
        }
        line[n] = '\0';

        /* There is no alpha channel in a 24-colour palette, so a fade has to be
         * a dither. But the decision is made for the WHOLE LINE, not per pixel:
         * a per-pixel dissolve on 5x7 glyphs destroys them, and unreadable text
         * is worse than no text. */
        if (dr_dither_noise(97, 131, tm->label_alpha)) {
            dr_text_draw_centred_outlined(w, DR_W / 2, 152, line,
                                          ink, halo, DR_DEPTH_MAX);
        }
    }
}

/* ---- public API --------------------------------------------------------- */

void dragon_timer_start(dragon_world_t *world, double seconds, const char *label, int kind)
{
    dr_timer_start(&((DRW *)world)->timer, seconds, label, kind);
}

void dragon_timer_cancel(dragon_world_t *world)
{
    dr_timer_cancel(&((DRW *)world)->timer);
}

void dragon_timer_set_label(dragon_world_t *world, const char *label)
{
    dr_timer_set_label(&((DRW *)world)->timer, label);
}

double dragon_timer_remaining(const dragon_world_t *world)
{
    return ((const DRW *)world)->timer.remaining;
}

int dragon_timer_state(const dragon_world_t *world)
{
    return ((const DRW *)world)->timer.state;
}

int dragon_timer_kind(const dragon_world_t *world)
{
    return ((const DRW *)world)->timer.kind;
}

int dragon_timer_phase(const dragon_world_t *world)
{
    return dr_timer_phase(&((const DRW *)world)->timer);
}

double dragon_timer_alarm_time(const dragon_world_t *world)
{
    return ((const DRW *)world)->timer.alarm_t;
}
