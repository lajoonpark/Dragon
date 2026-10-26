#include "dragon_internal.h"

/* Palette access.
 *
 * Two ramps, each sorted dark -> light, exported from the reduced master rather
 * than picked by hand (docs/reviews/c01-reduction.md). Object colour is chosen
 * by *value* into a ramp, which is what keeps 20 assets looking like one artist
 * made them (D-007).
 */

int dr_pal_cool_index(int step)
{
    return dr_clampi(dr_cool_first + step, dr_cool_first,
                     dr_cool_first + dr_cool_count - 1);
}

int dr_pal_warm_index(int step)
{
    return dr_clampi(dr_warm_first + step, dr_warm_first,
                     dr_warm_first + dr_warm_count - 1);
}

int dr_pal_pick(float v)
{
    return dr_pal_cool_index((int)(dr_saturate(v) * (dr_cool_count - 1) + 0.5f));
}

int dr_pal_warm(float v)
{
    return dr_pal_warm_index((int)(dr_saturate(v) * (dr_warm_count - 1) + 0.5f));
}

int dr_pal_nearest(int r, int g, int b)
{
    int best = 0, bestd = 1 << 30;
    int i;
    for (i = 0; i < dr_palette_count; i++) {
        int dr = r - dr_palette_rgb[i][0];
        int dg = g - dr_palette_rgb[i][1];
        int db = b - dr_palette_rgb[i][2];
        /* Weighted to approximate luma perception: the audit only needs a
         * defensible nearest, not a perceptual colour space. */
        int d = dr * dr * 3 + dg * dg * 6 + db * db;
        if (d < bestd) { bestd = d; best = i; }
    }
    return best;
}

/* ---- dither ------------------------------------------------------------- */

static const unsigned char BAYER4[4][4] = {
    {  0,  8,  2, 10 },
    { 12,  4, 14,  6 },
    {  3, 11,  1,  9 },
    { 15,  7, 13,  5 },
};

/* Hash-noise dither, for LARGE soft areas.
 *
 * BAYER4 is right for a 1-2px edge: the grid is too fine to resolve and it
 * behaves like a clean threshold. Over a 40px mist bank the same grid is
 * plainly visible as a lattice, which reads as a screened halftone rather than
 * as mist. This variant hashes the pixel index, so it scatters at any scale.
 *
 * Both dithers respect the same rule (D-021): below DR_DITH_LO nothing is
 * written, above DR_DITH_HI the pixel is solid, only the band between is mixed.
 * Neither ever averages RGB, so both stay inside the locked palette (D-007). */
int dr_dither_noise(int x, int y, float a)
{
    unsigned h;
    if (a <= DR_DITH_LO) return 0;
    if (a >= DR_DITH_HI) return 1;
    {
        float t = (a - DR_DITH_LO) / (DR_DITH_HI - DR_DITH_LO);
        h = (unsigned)(x * 374761393u + y * 668265263u);
        h = (h ^ (h >> 13)) * 1274126177u;
        h ^= h >> 16;
        return (float)(h & 1023u) * (1.0f / 1024.0f) < t;
    }
}

int dr_dither(int x, int y, float a)
{
    if (a <= DR_DITH_LO) return 0;
    if (a >= DR_DITH_HI) return 1;
    {
        /* map the transition band onto 0..1 so the threshold is met gradually,
         * and the raw Bayer value (0..15) is compared in sixteenths. */
        float t = (a - DR_DITH_LO) / (DR_DITH_HI - DR_DITH_LO);
        int thr = BAYER4[y & 3][x & 3];
        return (thr * (1.0f / 16.0f)) < t;
    }
}

/* ---- surface ------------------------------------------------------------ */

void dr_put(dr_surface *s, int x, int y, int pal_index, int alpha_step)
{
    if (x < 0 || y < 0 || x >= s->w || y >= s->h) return;
    if (!dr_dither(x, y, (float)alpha_step / 255.0f)) return;
    {
        const unsigned char *c = dr_pal_rgb(pal_index);
        uint8_t *p = s->px + ((size_t)y * s->w + x) * 4;
        p[0] = c[0];
        p[1] = c[1];
        p[2] = c[2];
        p[3] = 255;
    }
}
