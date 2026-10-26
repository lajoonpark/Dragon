#include <math.h>

#include "world.h"

/* The gust field.
 *
 * docs/35: "the single biggest difference between beautifully animated and
 * clearly an animated GIF is whether the wind is coherent." One field, three
 * travelling waves on prime-ish periods so it never repeats, sampled by every
 * deformable object at its screen position. Objects near each other therefore
 * bend together, which is the property that reads as air with a body.
 *
 * Two refinements from the plan, both learned by measurement:
 *   - the slow sway is ADDED, not multiplied (docs/10, r45): multiplying the
 *     fine sum by a slow sine made them cancel, and the mist edge varied 9px.
 *   - the field is evaluated in WORLD space, so the camera travelling through it
 *     is what makes a gust appear to sweep across the scene.
 */

#define GUST_WAVES 3

typedef struct {
    float wavelength;   /* px */
    float period;       /* s */
    float weight;
} gust_wave;

static const gust_wave WAVES[GUST_WAVES] = {
    {  86.0f, 6.5f, 0.50f },
    { 143.0f, 9.5f, 0.32f },
    { 233.0f, 3.7f, 0.18f },
};

float dr_gust(const DRW *w, float world_x, float t)
{
    float g = 0.0f;
    float env;
    int k;
    (void)w;
    for (k = 0; k < GUST_WAVES; k++) {
        float phase = (world_x / WAVES[k].wavelength) + t / WAVES[k].period;
        float s = 0.5f + 0.5f * (float)sin((double)phase * 6.2831853);
        g += WAVES[k].weight * dr_smoothstep(0.15f, 0.85f, s);
    }
    /* Quiet gaps: the strength itself is modulated by a slow ADDED envelope, so
     * there are calm seconds between gusts. Constant wind = wallpaper pattern. */
    env = 0.62f
        + 0.22f * (float)sin((double)t * 0.0715 + 1.7)
        + 0.16f * (float)sin((double)t * 0.0313 + 0.3);
    g = g * 0.62f * env + 0.05f;
    return dr_saturate(g);
}
