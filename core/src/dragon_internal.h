/* Dragon core internals. Not a platform header, not installed. */
#ifndef DRAGON_INTERNAL_H
#define DRAGON_INTERNAL_H

#include <stdint.h>
#include <string.h>

#include "dragon.h"
#include "assets_data.h"

/* ---- limits ------------------------------------------------------------- */
#define DR_MIST_PX_S       2.5     /* docs/10: mist drift 2-5 px/s */
#define DR_FPS             15

/* Waterline and the wrap-wall geometry. Both were measured from the art by
 * tools/pipeline/export_emitters.py, not chosen; see DR_WRAP_W. */
#define DR_WATER_TOP       239
#define DR_WRAP_W          32      /* crossfade width at the scroll seam */

/* ---- depth -------------------------------------------------------------- */
#define DR_DEPTH_MAX       15      /* depth is stored 0..15, like the asset */

/* ---- fixed-point helpers ------------------------------------------------ */
static inline int dr_clampi(int v, int lo, int hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

static inline float dr_clampf(float v, float lo, float hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

static inline float dr_saturate(float v) { return dr_clampf(v, 0.0f, 1.0f); }

static inline float dr_lerp(float a, float b, float t)
{
    return a + (b - a) * t;
}

static inline int dr_lerpi(int a, int b, int t, int tmax)
{
    return a + (b - a) * t / (tmax ? tmax : 1);
}

/* Smooth 0..1 ramp, used for gust envelopes and the hush. */
static inline float dr_smoothstep(float e0, float e1, float x)
{
    float t = dr_saturate((x - e0) / (e1 - e0));
    return t * t * (3.0f - 2.0f * t);
}

/* ---- rng: splitmix64, counter-based so a shot is reproducible by index ---- */
typedef struct { uint64_t s; } dr_rng;

static inline void dr_rng_seed(dr_rng *r, uint64_t s) { r->s = s; }

static inline uint64_t dr_rng_next(dr_rng *r)
{
    uint64_t z = (r->s += 0x9E3779B97F4A7C15ull);
    z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9ull;
    z = (z ^ (z >> 27)) * 0x94D049BB133111EBull;
    return z ^ (z >> 31);
}

/* 0..n-1 */
static inline int dr_rng_int(dr_rng *r, int n)
{
    return n <= 0 ? 0 : (int)(dr_rng_next(r) % (uint64_t)n);
}

/* lo..hi inclusive */
static inline int dr_rng_range_i(dr_rng *r, int lo, int hi)
{
    return hi <= lo ? lo : lo + dr_rng_int(r, hi - lo + 1);
}

/* 0.0 .. 1.0 */
static inline float dr_rng_f(dr_rng *r)
{
    return (float)(dr_rng_next(r) >> 11) * (1.0f / 9007199254740992.0f);
}

/* lo .. hi */
static inline float dr_rng_range(dr_rng *r, float lo, float hi)
{
    return lo + (hi - lo) * dr_rng_f(r);
}

/* ---- palette ------------------------------------------------------------ */
int dr_pal_pick(float v);            /* 0..1 value -> ramp index, cool ramp */
int dr_pal_warm(float v);            /* 0..1 value -> ramp index, warm ramp */
int dr_pal_cool_index(int step);     /* clamp into the cool ramp */
int dr_pal_warm_index(int step);
int dr_pal_nearest(int r, int g, int b);  /* for audit / diagnostics only */

static inline const unsigned char *dr_pal_rgb(int i)
{
    return dr_palette_rgb[dr_clampi(i, 0, dr_palette_count - 1)];
}

/* ---- dither ------------------------------------------------------------- */
/* D-021: dither is a TRANSITION, never a fill. Below DR_DITH_LO nothing is
 * written; above DR_DITH_HI the pixel is solid. Only the band between is
 * actually dithered. v4 used dither as a fill and produced checkerboard
 * fields that ate the whole image. */
#define DR_DITH_LO 0.12f
#define DR_DITH_HI 0.78f

/* 1 = write. a_px is the sub-pixel position, a = alpha 0..1. */
int dr_dither(int x, int y, float a);
int dr_dither_noise(int x, int y, float a);

/* ---- surface ------------------------------------------------------------ */
typedef struct {
    uint8_t *px;    /* RGBA8888, DR_W * DR_H * 4 */
    int w, h;
} dr_surface;

void dr_put(dr_surface *s, int x, int y, int pal_index, int alpha_step);

/* World column -> screen x under a given pan.
 *
 * Ambient elements that are rooted in the landscape (reeds, sparkles, landed
 * petals) live in world space so they travel with the art; drawing them at a
 * literal screen x makes them slide across the cliffs, which reads instantly as
 * a particle layer pasted over a panning background. */
static inline int dr_wrap_screen(int world_x, double pan)
{
    int sx = world_x - (int)pan;
    sx %= DR_W;
    if (sx < 0) sx += DR_W;
    return sx;
}

#endif /* DRAGON_INTERNAL_H */
