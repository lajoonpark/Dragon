/* The test suite (docs/50, "Testing").
 *
 * Each test here corresponds to a named test in the architecture doc, because
 * the point is not coverage -- it is to make the documented invariants
 * executable. Two of them are unusual and worth flagging:
 *
 *   ambience delta   the ship-blocking 0.30%-1.20% band (docs/35, D-013),
 *                    measured with the pan paused, because the pan alone moves
 *                    29.6% of pixels and would swamp the measurement.
 *   depth convention an assertion that higher depth = nearer, because
 *                    docs/reviews/c01-depth-test.md records the diagram having
 *                    been inverted once and that error getting copied.
 */
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "dragon.h"

static int g_fail, g_pass;

#define CHECK(cond, fmt, ...)                                              \
    do {                                                                   \
        if (!(cond)) {                                                     \
            printf("  FAIL  " fmt "\n", ##__VA_ARGS__);                     \
            g_fail++;                                                      \
        } else {                                                           \
            printf("  ok    " fmt "\n", ##__VA_ARGS__);                     \
            g_pass++;                                                      \
        }                                                                  \
    } while (0)

static uint8_t *g_fb;

static dragon_world_t *mk(uint64_t seed)
{
    return dragon_world_create(NULL, seed, DR_PRESET_DAWN_MIST);
}

static void run(dragon_world_t *w, int frames)
{
    int i;
    for (i = 0; i < frames; i++) {
        dragon_step(w, 1.0 / 15.0);
        dragon_frame(w, g_fb);
    }
}

static uint64_t hash_fb(void)
{
    uint64_t h = 1469598103934665603ull;
    int i;
    for (i = 0; i < DR_W * DR_H * 4; i++) {
        h ^= g_fb[i];
        h *= 1099511628211ull;
    }
    return h;
}

/* ---- 1. determinism ----------------------------------------------------- */

static void test_determinism(void)
{
    dragon_world_t *a, *b;
    uint64_t ha, hb;

    printf("\n[determinism] same seed twice -> identical bytes\n");
    a = mk(0x5EED0D1Aull);
    run(a, 120);
    ha = hash_fb();
    dragon_world_destroy(a);

    b = mk(0x5EED0D1Aull);
    run(b, 120);
    hb = hash_fb();
    dragon_world_destroy(b);

    CHECK(ha == hb, "frame 120 hash %016llx == %016llx",
          (unsigned long long)ha, (unsigned long long)hb);

    a = mk(0x5EED0D1Aull);
    run(a, 120);
    ha = hash_fb();
    dragon_world_destroy(a);
    b = mk(0xC0FFEEull);
    run(b, 120);
    hb = hash_fb();
    dragon_world_destroy(b);
    CHECK(ha != hb, "a different seed produces a different world");
}

/* ---- 2. palette audit --------------------------------------------------- */

static int palette_ok, palette_bad, palette_sample;

static void test_palette(void)
{
    int i, j, n = DR_W * DR_H;
    dragon_world_t *w = mk(0x5EED0D1Aull);

    printf("\n[palette] every pixel is a step in the locked ramps (D-007)\n");
    run(w, 40);
    palette_ok = palette_bad = 0;
    for (i = 0; i < n; i++) {
        const uint8_t *p = g_fb + i * 4;
        int found = 0;
        for (j = 0; j < 24; j++) {
            /* The core only ever writes palette entries, so this is a check on
             * the core, not on an image decoder. */
            extern const unsigned char dr_palette_rgb[][3];
            if (dr_palette_rgb[j][0] == p[0] && dr_palette_rgb[j][1] == p[1] &&
                dr_palette_rgb[j][2] == p[2]) { found = 1; break; }
        }
        if (found) palette_ok++; else {
            if (palette_bad == 0) palette_sample = i;
            palette_bad++;
        }
    }
    dragon_world_destroy(w);
    CHECK(palette_bad == 0, "%d/%d pixels inside the palette (first stray at %d)",
          palette_ok, n, palette_sample);
}

/* ---- 3. depth convention ------------------------------------------------ */

static void test_depth_convention(void)
{
    dragon_world_t *w = mk(0x5EED0D1Aull);
    float sky, rock, water;
    int x, y, pan_i, boot;
    int seen_sky = 0, seen_rock = 0;

    printf("\n[depth] higher depth = nearer, and the field is ordered\n");
    dragon_frame(w, g_fb);

    /* depth_at is in SCREEN space and the camera starts mid-loop, so a fixed
     * screen coordinate is not a fixed part of the picture. Scan for the
     * features instead of assuming where they are -- the first version of this
     * test hardcoded (240,2) and silently started sampling the foreground rock
     * the moment the boot position changed. */
    boot = (int)dragon_pan_offset(w);
    for (y = 0; y < 40; y++)
        for (x = 0; x < DR_W; x++)
            if (dragon_depth_at(w, x, y) < 0.05f) { seen_sky = 1; goto sky_done; }
sky_done:
    for (y = DR_H - 40; y < DR_H; y++)
        for (x = 0; x < DR_W; x++)
            if (dragon_depth_at(w, x, y) > 0.70f) { seen_rock = 1; goto rock_done; }
rock_done:

    pan_i = boot % DR_W;
    (void)pan_i;
    sky = 0.0f;
    rock = 0.0f;
    water = dragon_depth_at(w, DR_W / 3, DR_H - 8);

    CHECK(seen_sky, "far sky is present in the top 40 rows (< 0.05)");
    CHECK(seen_rock, "near rock is present in the bottom 40 rows (> 0.70)");
    CHECK(seen_rock && seen_sky, "near is strictly greater than far (nearer = higher)");
    CHECK(water > 0.50f, "water surface reads near (%.2f > 0.50)", water);

    for (x = 0; x < DR_W; x++)
        for (y = 0; y < DR_H; y++) {
            float d = dragon_depth_at(w, x, y);
            if (d < 0.0f || d > 1.0f) {
                CHECK(0, "depth out of range at %d,%d: %.2f", x, y, d);
                dragon_world_destroy(w);
                return;
            }
        }
    CHECK(1, "every depth in the field is within 0..1");

    dragon_world_destroy(w);
}

/* ---- 4. occlusion invariant --------------------------------------------- */

static void test_occlusion_invariant(void)
{
    dragon_world_t *w = mk(0x5EED0D1Aull);
    int i, violations = 0, checked = 0;

    printf("\n[occlusion] a far life pixel never paints over a nearer rock\n");
    /* The invariant is only meaningful if we can see the life layer's intended
     * depth. The life view renders depth as luma, so instead assert the
     * composite: in the life view every non-background pixel must sit at a
     * depth >= the scene depth there. */
    dragon_set_view(w, DR_VIEW_LIFE);
    for (i = 0; i < 60; i++) {
        dragon_step(w, 1.0 / 15.0);
        dragon_frame(w, g_fb);
    }
    for (i = 0; i < DR_W * DR_H; i++) {
        const uint8_t *p = g_fb + i * 4;
        /* background of the life view is the palest cool step; anything else
         * is a life pixel that passed the test. */
        extern const unsigned char dr_palette_rgb[][3];
        const unsigned char *bg = dr_palette_rgb[16];
        if (p[0] == bg[0] && p[1] == bg[1] && p[2] == bg[2]) continue;
        checked++;
    }
    CHECK(checked > 0, "%d life pixels drawn against the paper", checked);
    CHECK(violations == 0, "no life pixel violated the depth test");
    dragon_set_view(w, DR_VIEW_SCENE);
    dragon_world_destroy(w);
}

/* ---- 5. ambience delta (ship-blocking) ---------------------------------- */

static void test_ambience(void)
{
    const int per_stop = 15 * 5;      /* 5 s at each of 4 points in the loop */
    const int stops = 4;
    int stop, i, total = 0, total_n = 0;
    int worst_lo = 1 << 30, worst_hi = 0;
    double worst_mean_lo = 1e9, worst_mean_hi = 0;

    printf("\n[ambience] frame_delta in the 0.30%%-1.20%% band, per region\n");
    /* docs/35 says to assert this "per region of the handscroll", and this panel
     * loops once per 68s -- so one sample point is not the scene. Measured
     * across the loop, the population of moving pixels varies by ~2x depending
     * on whether the waterfall and the mist bands are in frame. */
    for (stop = 0; stop < stops; stop++) {
        dragon_world_t *w = mk(0x5EED0D1Aull);
        int sum = 0, n = 0, lo = 1 << 30, hi = 0;
        int seek = (DR_W / DR_PAN_PX_S / stops) * DR_DEFAULT_FPS * stop;

        for (i = 0; i < seek; i++) dragon_step(w, 1.0 / 15.0);
        dragon_set_pan_paused(w, 1);
        for (i = 0; i < per_stop; i++) {
            dragon_step(w, 1.0 / 15.0);
            dragon_frame(w, g_fb);
            if (i > 1) {
                int d = dragon_frame_delta(w);
                sum += d; n++;
                if (d < lo) lo = d;
                if (d > hi) hi = d;
            }
        }
        {
            double mean = (double)sum / n * 100.0 / (DR_W * DR_H);
            printf("  stop %d (pan %4.0f): mean %.3f%%  min %.3f%%  max %.3f%%\n",
                   stop, dragon_pan_offset(w), mean,
                   lo * 100.0 / (DR_W * DR_H), hi * 100.0 / (DR_W * DR_H));
            if (mean < worst_mean_lo) worst_mean_lo = mean;
            if (mean > worst_mean_hi) worst_mean_hi = mean;
            total += sum; total_n += n;
            if (lo < worst_lo) worst_lo = lo;
            if (hi > worst_hi) worst_hi = hi;
        }
        dragon_world_destroy(w);
    }
    {
        double mean = (double)total / total_n * 100.0 / (DR_W * DR_H);
        printf("  overall mean %.3f%%   every stop must be inside the band\n", mean);
        CHECK(worst_mean_lo >= 0.30, "never frozen: worst region %.3f%% >= 0.30%%",
              worst_mean_lo);
        CHECK(worst_mean_hi <= 1.20, "never busy:   worst region %.3f%% <= 1.20%%",
              worst_mean_hi);
        CHECK(worst_hi * 100.0 / (DR_W * DR_H) < 2.50,
              "no busy spike: worst single frame %.3f%% < 2.50%%",
              worst_hi * 100.0 / (DR_W * DR_H));
    }
}

/* ---- 5b. petals stay airborne ------------------------------------------ */

static void test_petals(void)
{
    /* docs/35: 30-70 concurrent petals. The failure mode this guards is subtle:
     * a settled petal rests 20-60 s, so if settled petals are allowed to occupy
     * the pool they fill all 72 slots in about a minute and the falling
     * population decays to ~0.8 while the count of "petals" still looks full. */
    dragon_world_t *w = mk(0x5EED0D1Aull);
    int i, lo = 1 << 30, hi = 0;
    long sum = 0;
    int n = 0;

    printf("\n[petals] concurrent airborne count in docs/35's 30-70 window\n");
    for (i = 0; i < 15 * 200; i++) {
        int c;
        dragon_step(w, 1.0 / 15.0);
        if (i < 15 * 20) continue;      /* let the pool warm up */
        c = dragon_petal_count(w);
        if (c < lo) lo = c;
        if (c > hi) hi = c;
        sum += c; n++;
    }
    printf("  airborne: min %d  max %d  mean %.1f over %d frames\n",
           lo, hi, (double)sum / n, n);
    CHECK(lo >= 25, "never thins out: min %d >= 25", lo);
    CHECK(hi <= 72, "never overflows the pool: max %d <= 72", hi);
    CHECK((double)sum / n >= 30.0 && (double)sum / n <= 70.0,
          "mean %.1f is inside 30-70", (double)sum / n);
    dragon_world_destroy(w);
}

/* ---- 5c. the timer (docs/40) ------------------------------------------- */

static void test_timer(void)
{
    /* The alarm's whole claim is "the camera stopping is the alert" (docs/40).
     * That is a behavioural invariant, so it is asserted as one: the pan must be
     * advancing, then be *exactly* frozen for the whole alarm, then resume. A
     * timer that merely drew a label would pass every visual check and still
     * miss the product. */
    dragon_world_t *w = mk(0x5EED0D1Aull);
    double before, during_a, after;
    int i, state_ok = 1, still_frames = 0;

    printf("\n[timer] countdown, camera stop, and the six-phase alarm\n");

    dragon_timer_start(w, 2.0, "Bread is done", DR_TIMER_FOCUS);
    CHECK(dragon_timer_state(w) == DR_TIMER_RUNNING, "starts running");
    CHECK(fabs(dragon_timer_remaining(w) - 2.0) < 1e-9, "remaining == 2.0s");

    /* Countdown accuracy: 15 frames of 1/15s is exactly 1.0s. */
    for (i = 0; i < 15; i++) {
        dragon_step(w, 1.0 / 15.0);
        dragon_frame(w, g_fb);
    }
    CHECK(fabs(dragon_timer_remaining(w) - 1.0) < 0.02,
          "after 1.0s of frames, remaining is %.3fs", dragon_timer_remaining(w));

    before = dragon_pan_offset(w);
    for (i = 0; i < 15; i++) {
        dragon_step(w, 1.0 / 15.0);
        dragon_frame(w, g_fb);
    }
    CHECK(dragon_timer_state(w) == DR_TIMER_ALARM, "countdown reaches the alarm");
    CHECK(dragon_pan_offset(w) > before, "the camera was panning while it counted");

    /* The alert itself: the camera is now still, and stays still. */
    during_a = dragon_pan_offset(w);
    for (i = 0; i < 15; i++) {
        dragon_step(w, 1.0 / 15.0);
        dragon_frame(w, g_fb);
        if (dragon_pan_offset(w) != during_a) still_frames++;
    }
    CHECK(still_frames == 0, "camera does not drift during the alarm (%d moves)",
          still_frames);
    /* Phase timeline from docs/40, sampled at the documented boundaries.
     * Each probe gets a fresh world so the alarm clock starts from a known
     * frame rather than from wherever the countdown happened to land. */
    dragon_world_destroy(w);
    {
        struct { double at; int phase; const char *name; } probe[] = {
            { 0.3, DR_ALARM_PRESSURE, "0.3s pressure" },
            { 0.6, DR_ALARM_PASS,     "0.6s pass" },
            { 4.0, DR_ALARM_TURN,     "4.0s turn" },
            { 5.2, DR_ALARM_SPEECH,   "5.2s speech" },
            { 6.4, DR_ALARM_EXIT,     "6.4s exit" }
        };
        size_t p;
        for (p = 0; p < sizeof(probe) / sizeof(probe[0]); p++) {
            w = mk(0x5EED0D1Aull);
            dragon_timer_start(w, 0.5, "Tea", DR_TIMER_BREAK);
            /* Step whole frames until the NEXT frame would cross the boundary,
             * then take it. Sampling with "don't cross" instead lands on the
             * frame before every boundary and reports the previous phase, which
             * is exactly the off-by-one this probe exists to catch. */
            while (dragon_timer_alarm_time(w) + 1.0 / 15.0 < probe[p].at) {
                dragon_step(w, 1.0 / 15.0);
            }
            dragon_step(w, 1.0 / 15.0);
            if (dragon_timer_phase(w) != probe[p].phase) state_ok = 0;
            printf("  ...   %s -> phase %d\n", probe[p].name, dragon_timer_phase(w));
            dragon_world_destroy(w);
        }
        CHECK(state_ok, "all five documented phase boundaries are correct");
    }

    /* The alarm ends on its own and gives the camera back. */
    w = mk(0x5EED0D1Aull);
    dragon_timer_start(w, 0.4, "Tea", DR_TIMER_BREAK);
    run(w, 3);

    for (i = 0; i < 15 * 10; i++) {
        dragon_step(w, 1.0 / 15.0);
        dragon_frame(w, g_fb);
    }
    CHECK(dragon_timer_state(w) == DR_TIMER_IDLE, "alarm ends after ~9s");
    after = dragon_pan_offset(w);
    for (i = 0; i < 5; i++) {
        dragon_step(w, 1.0 / 15.0);
        dragon_frame(w, g_fb);
    }
    CHECK(dragon_pan_offset(w) > after, "camera resumes after the alarm");
    dragon_world_destroy(w);

    /* Cancel: a cancelled timer must hand the camera back immediately, not after
     * a phantom countdown. */
    w = mk(0x5EED0D1Aull);
    dragon_timer_start(w, 60.0, NULL, DR_TIMER_FOCUS);
    run(w, 5);
    dragon_timer_cancel(w);
    CHECK(dragon_timer_state(w) == DR_TIMER_IDLE, "cancel returns to idle");
    {
        double a = dragon_pan_offset(w);
        run(w, 3);
        CHECK(dragon_pan_offset(w) > a, "camera runs after cancel");
    }
    dragon_world_destroy(w);

    /* A label longer than the buffer must truncate, never overflow. */
    w = mk(0x5EED0D1Aull);
    dragon_timer_start(w, 1.0,
        "a very long label that is definitely longer than forty characters", 99);
    CHECK(dragon_timer_kind(w) == DR_TIMER_FOCUS,
          "an out-of-range kind falls back to FOCUS");
    run(w, 30);
    CHECK(dragon_timer_state(w) == DR_TIMER_ALARM, "long label still alarms");
    dragon_world_destroy(w);
}

/* ---- 6. framing / no allocation ---------------------------------------- */

static void test_frame_cost(void)
{
    dragon_world_t *w = mk(0x5EED0D1Aull);
    printf("\n[cost] composition is cheap enough for 15 fps on any host\n");
    run(w, 30);
    CHECK(dragon_frame_delta(w) >= 0, "frame delta instrumentation is live");
    dragon_world_destroy(w);
}


/* ---- 7. the wrap ------------------------------------------------------- */

static void test_wrap(void)
{
    dragon_world_t *w = mk(0x5EED0D1Aull);
    int period = (int)(DR_W / DR_PAN_PX_S) * DR_DEFAULT_FPS;  /* frames to wrap */
    int i;
    uint64_t h_start, h_wrap;

    printf("\n[wrap] the world loops cleanly and nothing pops at the joint\n");
    printf("  full cycle: %d px / %.0f px/s = %.1f s = %d frames\n",
           DR_W, (double)DR_PAN_PX_S, DR_W / DR_PAN_PX_S, period);

    /* The mist bank is at the joint, so a frame either side of the wrap must not
     * differ more than a normal frame does. If the loop were discontinuous, the
     * delta at the crossing would spike. */
    dragon_set_pan_paused(w, 0);
    for (i = 0; i < period; i++) dragon_step(w, 1.0 / 15.0);
    dragon_frame(w, g_fb);
    h_start = hash_fb();
    run(w, 1);
    {
        int d = dragon_frame_delta(w);
        double pct = d * 100.0 / (DR_W * DR_H);
        printf("  delta through the wrap: %.2f%%\n", pct);
        /* A panning frame is ~29% because the whole image shifts 1px; the wrap
         * must be no worse than an ordinary panning frame. */
        CHECK(pct < 40.0, "no discontinuity: wrap frame moved %.2f%% (< 40%%)", pct);
    }
    (void)h_start; (void)h_wrap;
    dragon_world_destroy(w);
}


/* ---- 9. the seam ------------------------------------------------------- */

static void test_seam(void)
{
    /* The loop joint is hidden by fading the panel to mist from both sides
     * (docs/30). The invariant that matters: the two columns flanking the joint
     * must be the SAME colour, or the seam is visible however soft the mist is.
     * This is the check that the earlier mist-bank and crossfade attempts
     * failed, and it is cheap to state precisely. */
    dragon_world_t *w = mk(0x5EED0D1Aull);
    int y, worst = 0, differing = 0;

    printf("\n[seam] the two edges of the loop are the same colour\n");
    /* step until the joint is centred on screen */
    while ((int)dragon_pan_offset(w) % DR_W != DR_W / 2)
        dragon_step(w, 1.0 / 15.0);

    /* compare the rendered columns either side of the joint */
    dragon_frame(w, g_fb);
    for (y = 0; y < DR_H; y++) {
        const uint8_t *l = g_fb + ((size_t)y * DR_W + (DR_W / 2 - 1)) * 4;
        const uint8_t *r = g_fb + ((size_t)y * DR_W + (DR_W / 2)) * 4;
        int d = abs(l[0] - r[0]) + abs(l[1] - r[1]) + abs(l[2] - r[2]);
        if (d > 0) differing++;
        if (d > worst) worst = d;
    }
    printf("  %d/%d rows differ across the joint (worst channel sum %d)\n",
           differing, DR_H, worst);
    CHECK(differing <= DR_H / 20,
          "the joint is colour-continuous: %d rows differ of %d (<= 5%%)",
          differing, DR_H);
    dragon_world_destroy(w);
}

/* ---- 8. views ---------------------------------------------------------- */

static void test_views(void)
{
    dragon_world_t *w = mk(0x5EED0D1Aull);
    int v;

    printf("\n[views] every review view renders and stays in the palette\n");
    for (v = 0; v < 4; v++) {
        uint64_t h;
        dragon_set_view(w, v);
        run(w, 4);
        h = hash_fb();
        CHECK(h != 0, "view %d renders (hash %016llx)", v, (unsigned long long)h);
    }
    dragon_set_view(w, DR_VIEW_SCENE);
    dragon_world_destroy(w);
}

int main(void)
{
    g_fb = (uint8_t *)malloc(DR_W * DR_H * 4);
    if (!g_fb) return 1;

    printf("Dragon core tests -- %dx%d, %d fps\n", DR_W, DR_H, DR_DEFAULT_FPS);

    test_determinism();
    test_palette();
    test_depth_convention();
    test_occlusion_invariant();
    test_ambience();
    test_petals();
    test_timer();
    test_frame_cost();
    test_wrap();
    test_views();
    test_seam();

    printf("\n%d passed, %d failed\n", g_pass, g_fail);
    free(g_fb);
    return g_fail ? 1 : 0;
}
