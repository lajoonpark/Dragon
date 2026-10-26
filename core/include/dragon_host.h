/* Dragon — the platform contract. Ten functions, four required.
 *
 * If a feature needs an eleventh, that is a design smell: it almost certainly
 * belongs in the core (docs/55-platform-portability.md). Optional members may
 * be NULL; the core checks capabilities before asking.
 */
#ifndef DRAGON_HOST_H
#define DRAGON_HOST_H

#include <stdint.h>

typedef struct dr_host {
    void *user;

    /* REQUIRED ------------------------------------------------------------ */

    /* Monotonic seconds, never backwards. Used only to compute dt. */
    double (*now)(void *user);

    /* Present an RGBA8888 buffer, 480x270. `scale_hint` is the integer factor
     * the host should use, or 0 to choose. The core owns the memory; the host
     * must not retain it past return. */
    void (*present)(void *user, const uint8_t *rgba, int w, int h, int scale_hint);

    /* Persisted preferences as a flat key/value blob. */
    int (*prefs_read)(void *user, const char *key, char *out, int cap);
    int (*prefs_write)(void *user, const char *key, const char *val);

    /* OPTIONAL ------------------------------------------------------------ */

    void (*log)(void *user, int level, const char *msg);

    void (*audio_bed)(void *user, const char *name, float gain);
    void (*audio_one)(void *user, const char *name);

    /* Non-zero when the surface is occluded, the display is asleep, or the
     * machine is in power saver: the core skips composition entirely. */
    int (*should_idle)(void *user);

    void (*bus_send)(void *user, const char *json_line);
    int (*bus_poll)(void *user, char *out, int cap);

    int (*user_pref)(void *user, const char *name);
} dr_host;

#define DR_CAP_PREFS   (1u << 0)
#define DR_CAP_AUDIO   (1u << 1)
#define DR_CAP_BUS     (1u << 2)
#define DR_CAP_IDLE    (1u << 3)

static inline unsigned dr_host_caps(const dr_host *h)
{
    unsigned c = 0;
    if (h->prefs_read && h->prefs_write) c |= DR_CAP_PREFS;
    if (h->audio_bed || h->audio_one)    c |= DR_CAP_AUDIO;
    if (h->bus_send && h->bus_poll)      c |= DR_CAP_BUS;
    if (h->should_idle)                  c |= DR_CAP_IDLE;
    return c;
}

#endif /* DRAGON_HOST_H */
