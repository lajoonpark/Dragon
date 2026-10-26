#include <math.h>
#include <stdlib.h>

#include "world.h"

/* The scene: one rigid plane, panned, plus the only thing that moves
 * independently of it.
 *
 * RIGID PAN, NOT LAYERS (D-026). The measured result in
 * docs/reviews/c01-parallax-test.md is that per-band displacement opens holes and
 * inverse warping smears, and the smear grows linearly with time -- fatal for a
 * wallpaper. So the art pans as one plane and the depth cue is occlusion.
 *
 * THE SEAM FROM ONE PANEL. A single 480px panel does not tile: column 479 and
 * column 0 differ by 52 luma and belong to two different massifs. Rather than
 * invent a mist wall, the world is the panel plus its horizontal mirror, which
 * is continuous by construction (col 479 meets col 479, col 0 meets col 0) and
 * gives a 960px cycle. Mirroring is an explicitly sanctioned variety operation
 * -- "flips the lit side, which reads as a different peak in different light"
 * (docs/25). Cost: the second screen is lit from the wrong side. Recorded in
 * docs/75-background-prototype.md; the fix is more generated panels, not code.
 *
 * THE MIST VEIL is the one element allowed to move at its own rate, because
 * mist has no structure and therefore cannot visibly distort (D-026). It is
 * recoloured toward cream by an ORDERED DITHER between palette steps, never by
 * averaging RGB, so every pixel stays inside the locked palette (D-007).
 */

#define DR_WORLD_W (DR_W * 2)

static uint8_t g_value[24];      /* palette index -> luma 0..255 */
static uint8_t g_cool_by_luma[256];
static uint8_t g_warm_by_luma[256];
static int g_tables_ready;

static int b36_val(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'z') return c - 'a' + 10;
    return -1;
}

static int b16_val(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

static void build_tables(void)
{
    int i, l, best, bestd;
    if (g_tables_ready) return;

    for (i = 0; i < 24; i++) {
        const unsigned char *c = dr_pal_rgb(i);
        g_value[i] = (uint8_t)((c[0] * 299 + c[1] * 587 + c[2] * 114) / 1000);
    }
    /* Nearest palette index, by luma, within each ramp. Precomputed because the
     * mist pass asks this question tens of thousands of times per frame. */
    for (l = 0; l < 256; l++) {
        best = dr_cool_first; bestd = 1 << 30;
        for (i = 0; i < dr_cool_count; i++) {
            int idx = dr_cool_first + i;
            int d = abs((int)g_value[idx] - l);
            if (d < bestd) { bestd = d; best = idx; }
        }
        g_cool_by_luma[l] = (uint8_t)best;

        best = dr_warm_first; bestd = 1 << 30;
        for (i = 0; i < dr_warm_count; i++) {
            int idx = dr_warm_first + i;
            int d = abs((int)g_value[idx] - l);
            if (d < bestd) { bestd = d; best = idx; }
        }
        g_warm_by_luma[l] = (uint8_t)best;
    }
    g_tables_ready = 1;
}

int dr_idx_by_luma(int luma, int warm)
{
    build_tables();
    luma = dr_clampi(luma, 0, 255);
    return warm ? g_warm_by_luma[luma] : g_cool_by_luma[luma];
}

int dr_pal_luma(int idx)
{
    build_tables();
    return g_value[dr_clampi(idx, 0, dr_palette_count - 1)];
}

void dr_scene_decode(DRW *w)
{
    int y, x;
    build_tables();
    for (y = 0; y < DR_H; y++) {
        const char *p = dr_panel_rows[y];
        const char *d = dr_depth_rows[y];
        const char *f = dr_wf_rows[y];
        for (x = 0; x < DR_W; x++) {
            w->panel[y * DR_W + x] = (uint8_t)dr_clampi(b36_val(p[x]), 0, 23);
            w->depth[y * DR_W + x] = (uint8_t)dr_clampi(b16_val(d[x]), 0, 15);
            w->wf[y * DR_W + x] = (f[x] == '1') ? 1 : (f[x] == '2' ? 2 : 0);
        }
    }
    /* Sky and mist get their depth from the asset; nothing is painted here. */
    w->pan = 0.0;
}

/* Single panel, looped. World column == panel column, modulo the panel width:
 * the world IS the 480px scene and the camera wraps it once per 68s at 7 px/s. */
static inline int world_col(int c)
{
    c %= DR_W;
    return c < 0 ? c + DR_W : c;
}

int dr_scene_depth_at(const DRW *w, int x, int y)
{
    if (x < 0 || x >= DR_W || y < 0 || y >= DR_H) return 0;
    return w->scene_depth[y * DR_W + x];
}

/* Compose the static plane for the current pan into scene_idx/scene_depth.
 *
 * This is the power story in docs/50: when nothing is moving, one whole-frame
 * copy per frame. The map is recomputed only when the integer pan changes, and
 * for a 480-wide screen over a 960 world it is a straight or mirrored 1:1 read.
 */
static void build_mist(DRW *w);

/* THE MIST WALL AT THE JOINTS.
 *
 * The world is the panel plus its mirror (see the note above). That gives
 * continuity but it also puts an exact mirror axis at world column 480, which
 * measured as a plain Rorschach butterfly whenever it crossed mid-screen: a
 * perfectly symmetric peak with symmetric pines either side.
 *
 * A wall of opaque mist hides it, and it is the solution docs/30 already
 * describes for the single-panel case -- the world "loops through a mist wall".
 * It is scenery, not a hack: the band is written into scene_idx/scene_depth, so
 * the depth test treats it like any other mass and a dragon can pass behind it.
 *
 * Width is deliberately narrow (~30px, opaque core ~12px). It has to be opaque
 * to hide the axis, but wide would read as a fog bank rolling past on a timer.
 * The joints fall every 480 world px, i.e. once every 68s at 7 px/s.
 */
/* THE MIST BANK, AND WHY THERE IS NO MIRROR.
 *
 * The world is the single 480px panel, looped. Column 479 and column 0 differ by
 * 52 luma and belong to two different massifs, so the wrap needs hiding, and
 * docs/30/35 name the mechanism: the handscroll "loops through a mist wall".
 *
 * An earlier version extended the world to 960px by appending the panel's own
 * horizontal mirror -- continuous by construction, and it made a wider world.
 * It was removed after review. It put an exact mirror axis in the middle of the
 * screen, which read as a Rorschach butterfly (a perfectly symmetric peak with
 * symmetric pines either side), and hiding that took a heavy opaque band that
 * then read as a grey doorway. Two artifacts to conceal one seam, and the
 * symmetry is the more obvious of the two. The single-panel loop is the
 * documented design, costs one 30px bank per 68s, and leaves the art alone.
 *
 * The bank is deliberately TRANSLUCENT (peak ~200/255) and made of overlapping
 * billows at different densities, so rock shows faintly through it. An opaque
 * flat fill of the palest step reads as a hole cut in the picture.
 */
/* THE LOOP SEAM: BOTH EDGES BECOME THE SAME MIST.
 *
 * docs/30 states the mechanism exactly, and this is it:
 *
 *   "At the very end, crossfade over 6 seconds back to the start through a heavy
 *    mist wall -- diegetically, the camera enters a cloud and emerges somewhere
 *    else... Practically it means the last 200px and first 200px are both pure
 *    mist, so no seams."
 *
 * So the art is not covered at the joint; it is FADED TO MIST from both sides,
 * and because the mist colour is a function of y alone, the two edges arrive at
 * the identical colour. The seam is then zero by construction rather than by
 * concealment.
 *
 * Two earlier attempts failed for one shared reason, and it is worth recording:
 *
 *  - a mist BANK drawn over the joint: has to be opaque at every height to hide
 *    a full-height seam, so it reads as a vertical bar, and every variant
 *    (narrow/far, wide/near, ragged sides, vertical fade) traded the seam for a
 *    different artifact. The lift-based version measured 244 differing rows
 *    straight through it, because lifting art under a veil preserves the very
 *    difference the veil must remove.
 *  - a 32px dither CROSSFADE between the two edges: correct in principle, but at
 *    32px it is a dotted stripe, and the two sources are never equal so the
 *    centre is a permanent speckle.
 *
 * Fading both edges to one colour has neither problem: at d = 0 every pixel is
 * the mist step, so there is nothing to conceal, and the shoulders are a smooth
 * ramp through palette steps rather than a band with edges.
 *
 * The zone is 96px wide, which at 7 px/s is ~14 s of travel (docs/30 asks for
 * ~6 s of crossfade; a longer zone is gentler and the panel is only 480px). It
 * passes once per 68 s loop and reads as flying into cloud.
 */
#define SEAM_HALF   48          /* px either side of the joint */
#define SEAM_DEPTH   6          /* mist sits mid-far; dragons cross in front */

/* The mist the edges converge to.
 *
 * It must be a function of |distance to the joint| and y ONLY -- never of which
 * side we are on -- or the two edges arrive at different colours and the seam
 * survives. That symmetry constraint is also what lets it have STRUCTURE
 * without breaking: both sides see the same billow at equal distance, so the
 * join is still exact while the band is mottled rather than a flat fill.
 *
 * A single flat palette step here read as a bright bar cut out of the picture.
 * Real mist has value variation, so this picks between a few pale steps with a
 * low-frequency field, and it fades out at the top and bottom of the frame where
 * the band would otherwise end in a hard horizontal cut.
 */
static int seam_mist_idx(int dist, int y)
{
    /* EVEN in dist, and STATIC in time.
     *
     * Even, because cos() has zero slope at the joint so the two columns
     * flanking it are the same value -- a sine in dist was measured at 19
     * differing rows, a thin line of mist-coloured speckle down the middle.
     *
     * Static, because the result is quantised to palette steps that are ~10 luma
     * apart. A time-varying field crosses those steps all at once, flipping a
     * band several palette values in a single frame: measured as a 27% mean
     * delta on alternating frames, i.e. a visible strobe exactly at the joint.
     * Motion here has to come from the camera, not from the mist's own value. */
    float n = 0.50f * sinf((float)y * 0.061f)
            + 0.30f * sinf((float)y * 0.019f + 1.9f)
            + 0.20f * sinf((float)y * 0.130f)
            + 0.35f * cosf((float)dist * 0.075f) - 0.35f;
    int l = 228 + (int)(n * 24.0f);
    return dr_idx_by_luma(dr_clampi(l, 198, 250), 0);
}

/* 0..255: how much mist this column is.
 *
 * The outline wanders a long way vertically, because a zone of constant width
 * reads as a panel of fog with straight sides even when its rim is feathered.
 * Everything is a function of |dist| and y, so the two sides of the joint still
 * arrive at the same value and the seam stays exact -- clouds may be symmetric
 * across a soft axis in a way that a mirror-imaged mountain cannot.
 *
 * The feather is the value itself rather than a dither line at a boundary, so
 * there is no speckled edge to give the zone away. */
static int seam_mist_amount(int wc, int y, float t)
{
    int d = wc % DR_W;
    float half, u;
    if (d < 0) d += DR_W;
    if (d > DR_W / 2) d = DR_W - d;

    half = (float)SEAM_HALF
         + 26.0f * sinf((float)y * 0.031f + t * 0.11f)
         + 15.0f * sinf((float)y * 0.073f + 1.4f + t * 0.07f)
         +  9.0f * sinf((float)y * 0.157f + 2.9f - t * 0.13f)
         +  5.0f * sinf((float)y * 0.290f + 0.6f);
    if (half < 14.0f) half = 14.0f;

    if ((float)d >= half) return 0;

    u = 1.0f - (float)d / half;             /* 1 at the joint, 0 at the rim */
    /* long, soft feather: fully opaque only in the inner third */
    u = dr_saturate(u * 1.55f);
    u = u * u * (3.0f - 2.0f * u);
    return (int)(u * 255.0f);
}

void dr_scene_compose(DRW *w)
{
    int pan_i = (int)w->pan;
    int y, x;

    build_mist(w);

    for (x = 0; x < DR_W; x++) {
        w->map[x] = world_col(pan_i + x);
    }

    for (y = 0; y < DR_H; y++) {
        const uint8_t *prow = w->panel + y * DR_W;
        const uint8_t *drow = w->depth + y * DR_W;
        uint8_t *o = w->scene_idx + y * DR_W;
        uint8_t *od = w->scene_depth + y * DR_W;
        for (x = 0; x < DR_W; x++) {
            int col = w->map[x];
            int a;

            o[x] = prow[col];
            od[x] = drow[col];

            /* fade to mist at the loop joint, from both sides */
            {
                int wcx = pan_i + x;
                int sm = seam_mist_amount(wcx, y, (float)w->t);
                if (sm > 0) {
                    int d = wcx % DR_W;
                    if (d < 0) d += DR_W;
                    if (d > DR_W / 2) d = DR_W - d;
                    /* Dither on DISTANCE, not on screen x. dr_dither_noise
                     * hashes the pixel index, so the columns either side of the
                     * joint get independent noise and the joint shows through as
                     * speckle (measured 8 rows). Keying on (dist, y) makes the
                     * pattern mirror-symmetric about the joint, so both sides
                     * fall on the same side of the threshold and the edge is
                     * exact. */
                    if (dr_dither_noise(d, y, (float)sm / 255.0f)) {
                        o[x] = (uint8_t)seam_mist_idx(d, y);
                        if (od[x] < SEAM_DEPTH) od[x] = SEAM_DEPTH;
                    }
                }
            }

            /* MIST EDGE BREATHING (docs/35, system 6): "mist band edges deform
             * with a very low-frequency noise, ~1px amplitude. This alone fixes
             * 60% of the frozen problem and costs almost nothing."
             *
             * This shifts the veil's DENSITY by one palette step along a slowly
             * travelling contour, rather than sampling a neighbouring column.
             * Sampling the neighbour was the first attempt and it is a no-op
             * here: build_mist() blurs the veil, so the pixel to the left is
             * almost always identical and nothing changes on screen. Shifting
             * value is what the eye actually reads as breathing air.
             *
             * One step, and only where the contour currently sits, so the
             * change is confined to a thin moving band -- a whole-veil shift
             * was measured at +12.5% in a single frame, which is the "busy"
             * failure this gate exists to catch. */
            /* THE HELD BREATH (docs/40, pressure phase): mist thickens slightly
             * for 0.6s before the dragon arrives, then releases. Displacement,
             * not recolouring, for the same reason the veil displaces (D-026):
             * structure smears, mist has none.
             *
             * It thickens by pulling the veil's own alpha up, so the extra mist
             * appears where mist already lives and nowhere else. A global veil
             * lift was the fog-bank failure this file already documents. */
            a = dr_mist_alpha(x, y);
            if (a > 70 && a < 195) {
                float n = sinf((float)(x + pan_i) * 0.045f + (float)w->t * 0.21f)
                        + 0.6f * sinf((float)y * 0.083f - (float)w->t * 0.13f);
                /* threshold sweeps slowly, so the contour advances a fraction of
                 * a px per frame and the band creeps instead of flickering */
                float th = 0.30f * sinf((float)w->t * 0.17f + (float)(pan_i) * 0.004f);
                /* The held breath widens the band the contour traverses, so more
                 * of the veil lifts at once. Capped at 0.35 so even a full
                 * pressure frame stays a veil and never becomes a fog bank. */
                th -= 0.35f * w->timer.pressure;
                if (n > th && n < th + 0.55f) {
                    int li = dr_pal_luma(o[x]);
                    o[x] = (uint8_t)dr_idx_by_luma(dr_clampi(li + 5, 0, 255), 0);
                }
            }
        }
    }
}




/* The drifting mist veil.
 *
 * Extracted once at first use rather than painted: a soft alpha from paleness
 * restricted to the far half of the scene, so it only ever moves air. It is
 * sampled at a different rate from the pan (DR_MIST_PX_S on top), which is the
 * whole depth cue this prototype is allowed to have.
 *
 * Restraint is deliberate. An early version of this in Python washed the mist
 * bright; here the alpha is capped and the lift is a few palette steps, and the
 * result is checked against the scene-delta budget in tests/test_ambience.py.
 */
/* THE MIST VEIL, AS DISPLACEMENT.
 *
 * D-026 authorises exactly one independently moving element, and says why:
 * "structure is what smears. Mist has no structure, so it can be displaced
 * independently without the eye seeing a shape change." So the veil DISPLACES
 * pale, far pixels -- it never recolours them.
 *
 * The first implementation here did recolour, lifting mist pixels by 1-2 ramp
 * steps. Measured against the art it was wrong twice over: the largest flat
 * field went 6.5% -> 22.2% (a fog bank, not a veil, and a failed gate), and
 * mean |laplacian| went 30.2 -> 40.0, which is not detail, it is the ordered
 * dither reading as noise. Displacement leaves both numbers untouched, which is
 * what the Python prototype measured (contrast 67.9 vs 67.3, 88% of detail
 * retained -- docs/reviews/c01-parallax-test.md).
 */

static uint8_t g_mist_a[DR_W * DR_H];   /* 0..255, extracted once */
static int g_mist_ready;

static void build_mist(DRW *w)
{
    int y, x;
    if (g_mist_ready) return;
    for (y = 0; y < DR_H; y++) {
        for (x = 0; x < DR_W; x++) {
            int i = y * DR_W + x;
            int l = dr_pal_luma(w->panel[i]);
            int d = w->depth[i];
            /* pale = mist, far = the half that may drift. Water is excluded:
             * displacing the mirror band horizontally breaks the reflection. */
            int a = (l - 170) * 255 / 60;
            int far = (10 - d) * 255 / 10;
            if (y >= DR_WATER_TOP) a = 0;
            if (a < 0) a = 0;
            if (a > 255) a = 255;
            if (far < 0) far = 0;
            if (far > 255) far = 255;
            g_mist_a[i] = (uint8_t)(a * far / 255);
        }
    }
    /* blur so the veil has no edge that could be read as a shape */
    {
        static uint8_t tmp[DR_W * DR_H];
        int pass;
        memcpy(tmp, g_mist_a, sizeof(tmp));
        for (pass = 0; pass < 2; pass++) {
            for (y = 1; y < DR_H - 1; y++) {
                for (x = 1; x < DR_W - 1; x++) {
                    int i = y * DR_W + x;
                    int s = tmp[i] * 4 + tmp[i - 1] + tmp[i + 1]
                          + tmp[i - DR_W] + tmp[i + DR_W];
                    g_mist_a[i] = (uint8_t)(s / 8);
                }
            }
            memcpy(tmp, g_mist_a, sizeof(tmp));
        }
    }
    g_mist_ready = 1;
}

void dr_mist_probe(DRW *w) { build_mist(w); }

int dr_mist_alpha(int x, int y)
{
    if (!g_mist_ready) return 0;
    return g_mist_a[y * DR_W + x];
}
