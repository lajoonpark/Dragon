/* WASM host externs.
 *
 * The web host is the second independent host, and per docs/55 that makes it
 * the strongest possible evidence the core is really platform-blind: it shares
 * nothing with the null host except the 10-function vtable.
 */
#include <emscripten.h>
#include <stdlib.h>

#include "dragon.h"

static uint8_t g_fb[DR_W * DR_H * 4];

EMSCRIPTEN_KEEPALIVE
dragon_world_t *dragon_boot(uint64_t seed)
{
    /* No host is passed: the web host presents by reading the framebuffer
     * directly, so the vtable is not needed yet. Passing NULL keeps the core's
     * capability checks honest rather than faking a platform. */
    return dragon_world_create(NULL, seed, DR_PRESET_DAWN_MIST);
}

EMSCRIPTEN_KEEPALIVE
uint8_t *dragon_frame_ptr(dragon_world_t *w)
{
    dragon_frame(w, g_fb);
    return g_fb;
}

/* Timer control. The web host is the timer's UI, but the clock, the phase
 * timeline and the camera stop all live in the core (docs/40 + docs/55), so
 * these are thin forwards and nothing more. */

EMSCRIPTEN_KEEPALIVE
void dragon_timer_begin(dragon_world_t *w, double seconds, const char *label, int kind)
{
    dragon_timer_start(w, seconds, label, kind);
}

EMSCRIPTEN_KEEPALIVE
double dragon_timer_left(dragon_world_t *w)
{
    return dragon_timer_remaining(w);
}

EMSCRIPTEN_KEEPALIVE
int dragon_timer_st(dragon_world_t *w)
{
    return dragon_timer_state(w);
}

EMSCRIPTEN_KEEPALIVE
int dragon_timer_ph(dragon_world_t *w)
{
    return dragon_timer_phase(w);
}

EMSCRIPTEN_KEEPALIVE
void dragon_free(dragon_world_t *w)
{
    dragon_world_destroy(w);
}
