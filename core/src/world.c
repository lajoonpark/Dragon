#include <math.h>
#include <stdlib.h>
#include <string.h>

#include "world.h"

/* The world driver: one scene, a fixed timestep, and one composite.
 *
 * The composite is the whole project in miniature. The scene is a rigid plane
 * with a depth field; ambient life is drawn into its own layer; every life pixel
 * is then resolved against the scene depth with the single documented
 * comparison (docs/10 after the convention fix):
 *
 *     occluded when  life_depth < scene_depth
 *
 * which is the same test a dragon will use. Getting that working for petals and
 * reeds now is what makes the dragon a later addition rather than a rewrite.
 */

extern int dr_idx_by_luma(int luma, int warm);
extern int dr_pal_luma(int idx);
extern void dr_life_place_reeds(DRW *w);

static void init_world(DRW *w)
{
    int i;
    w->pan = 0.0;
    w->t = 0.0;
    w->pan_paused = 0;
    w->ambience_gain = 1.0f;
    w->view = DR_VIEW_SCENE;
    w->frame_delta = 0;
    w->have_prev = 0;

    dr_life_reset(w);
    for (i = 0; i < DR_MAX_SPARKLE; i++) {
        dr_sparkle *s = &w->sparkle[i];
        s->x = (int)dr_rng_range(&w->rng, 8.0f, (float)DR_W - 8.0f);
        s->y = DR_WATER_TOP + 2 + dr_rng_range_i(&w->rng, 0, DR_H - DR_WATER_TOP - 5);
        s->next_flash = dr_rng_range(&w->rng, 1.0f, 20.0f);
        s->phase = 0.0f;
    }
    dr_life_place_reeds(w);
}

dragon_world_t *dragon_world_create(const dr_host *host, uint64_t seed, int preset)
{
    DRW *w = (DRW *)calloc(1, sizeof(DRW));
    if (!w) return NULL;

    if (host) w->host = *host;
    w->caps = host ? dr_host_caps(&w->host) : 0;
    w->seed = seed;
    dr_rng_seed(&w->rng, seed ^ 0xD4A60ull);

    (void)preset;   /* only DAWN_MIST ships (docs/30) */

    dr_scene_decode(w);
    init_world(w);

    /* Open a quarter of the way into the loop. The seam (where the panel fades
     * to mist and back) sits at world column 0 == 480, so booting at 0 or 240
     * both put it dead centre of the first frame -- the worst possible first
     * impression, since the mist valley reads as a hole until you have seen it
     * pass. A quarter in is clean in both directions. */
    w->pan = (double)(DR_W / 4);
    return (dragon_world_t *)w;
}

void dragon_world_destroy(dragon_world_t *world)
{
    free(world);
}

int dragon_petal_count(const dragon_world_t *world)
{
    return ((const DRW *)world)->petal_active;
}

void dragon_set_view(dragon_world_t *world, int view)
{
    DRW *w = (DRW *)world;
    w->view = view;
}

int dragon_view(const dragon_world_t *world)
{
    return ((const DRW *)world)->view;
}

void dragon_set_pan_paused(dragon_world_t *world, int paused)
{
    ((DRW *)world)->pan_paused = paused;
}

double dragon_pan_offset(const dragon_world_t *world)
{
    return ((const DRW *)world)->pan;
}

float dragon_depth_at(const dragon_world_t *world, int x, int y)
{
    const DRW *w = (const DRW *)world;
    if (x < 0 || x >= DR_W || y < 0 || y >= DR_H) return 0.0f;
    return (float)w->scene_depth[y * DR_W + x] / (float)DR_DEPTH_MAX;
}

void dragon_event(dragon_world_t *world, const dr_event *ev)
{
    DRW *w = (DRW *)world;
    if (!ev) return;
    switch (ev->type) {
    case DR_EV_PAN_NUDGE:
        w->pan += (double)ev->value * 24.0;
        break;
    case DR_EV_PAUSE_TOGGLE:
        w->pan_paused = !w->pan_paused;
        break;
    case DR_EV_TIMER_FIRED:
        /* The dragon is not in this prototype. The hook exists so the timer
         * host can be written against a stable API. */
        break;
    default:
        break;
    }
}

void dragon_step(dragon_world_t *world, double dt)
{
    DRW *w = (DRW *)world;
    float fdt = (float)dt;

    dr_timer_step(&w->timer, dt);

    /* THE ALERT (docs/40): during the alarm the camera holds still. This is not
     * a pause for the dragon's benefit -- the stop is the signal itself, and it
     * costs zero pixels. An explicit host pause still wins, so the dev toggle
     * keeps working while a timer runs. */
    if (!w->pan_paused && !w->timer.still) {
        w->pan += DR_PAN_PX_S * dt;
        if (w->pan > 1.0e9) w->pan -= 1.0e9;
    }
    w->t += dt;

    dr_life_step(w, fdt);
}

/* ---- the composite ------------------------------------------------------ */

static void clear_to(dr_surface *s, int pal_index)
{
    const unsigned char *c = dr_pal_rgb(pal_index);
    uint8_t *p = s->px;
    int i, n = s->w * s->h;
    for (i = 0; i < n; i++) {
        p[i * 4 + 0] = c[0];
        p[i * 4 + 1] = c[1];
        p[i * 4 + 2] = c[2];
        p[i * 4 + 3] = 255;
    }
}

static void put_index(dr_surface *s, int x, int y, int pal_index)
{
    const unsigned char *c;
    uint8_t *p;
    if (x < 0 || y < 0 || x >= s->w || y >= s->h) return;
    c = dr_pal_rgb(pal_index);
    p = s->px + ((size_t)y * s->w + x) * 4;
    p[0] = c[0]; p[1] = c[1]; p[2] = c[2]; p[3] = 255;
}

static void render_scene(DRW *w, dr_surface *s)
{
    int x, y;

    dr_scene_compose(w);

    for (y = 0; y < DR_H; y++) {
        for (x = 0; x < DR_W; x++) {
            put_index(s, x, y, w->scene_idx[y * DR_W + x]);
        }
    }
}

static void render_life(DRW *w, dr_surface *s)
{
    int x, y;
    dr_life_render(w);
    dr_timer_render(w);   /* ink goes into the same layer, so it depth-tests too */

    /* THE DEPTH TEST. One comparison per life pixel, against the scene depth of
     * the same pixel. This is the mechanic (D-001), and it is why a dragon will
     * be able to straddle a ridge: nothing here knows what a ridge is. */
    for (y = 0; y < DR_H; y++) {
        for (x = 0; x < DR_W; x++) {
            int i = y * DR_W + x;
            int idx = w->life_idx[i];
            if (idx == DR_LIFE_NONE) continue;
            if (w->life_depth[i] < w->scene_depth[i]) continue;   /* behind: skip */
            put_index(s, x, y, idx);
        }
    }
}

static void render_depth_view(DRW *w, dr_surface *s, int life_only)
{
    int x, y;
    for (y = 0; y < DR_H; y++) {
        for (x = 0; x < DR_W; x++) {
            int i = y * DR_W + x;
            int d = life_only ? w->life_depth[i] : w->scene_depth[i];
            int l = 20 + d * 232 / DR_DEPTH_MAX;
            put_index(s, x, y, dr_idx_by_luma(l, d >= 9));
        }
    }
}

static void render_emitters_view(DRW *w, dr_surface *s)
{
    int x, y;
    for (y = 0; y < DR_H; y++) {
        for (x = 0; x < DR_W; x++) {
            put_index(s, x, y, w->scene_idx[y * DR_W + x]);
        }
    }
    for (y = 0; y < DR_H; y++) {
        for (x = 0; x < DR_W; x++) {
            int m = w->wf[y * DR_W + x];
            if (!m) continue;
            put_index(s, x, y, m == 1 ? dr_pal_warm(0.99f) : dr_pal_warm(0.55f));
        }
    }
}

void dragon_frame(dragon_world_t *world, uint8_t *rgba)
{
    DRW *w = (DRW *)world;
    dr_surface s;
    s.px = rgba;
    s.w = DR_W;
    s.h = DR_H;

    switch (w->view) {
    case DR_VIEW_DEPTH:
        dr_scene_compose(w);
        render_depth_view(w, &s, 0);
        break;
    case DR_VIEW_EMITTERS:
        dr_scene_compose(w);
        render_emitters_view(w, &s);
        break;
    case DR_VIEW_LIFE:
        clear_to(&s, dr_pal_cool_index(dr_cool_count - 1));
        dr_scene_compose(w);
        render_life(w, &s);
        break;
    default:
        render_scene(w, &s);
        render_life(w, &s);
        break;
    }

    /* instrumentation: pixels differing from the previous composed frame */
    if (w->have_prev) {
        int i, n = DR_W * DR_H * 4, d = 0;
        for (i = 0; i < n; i += 4) {
            if (rgba[i] != w->prev[i] || rgba[i + 1] != w->prev[i + 1] ||
                rgba[i + 2] != w->prev[i + 2]) d++;
        }
        w->frame_delta = d;
    } else {
        w->frame_delta = DR_W * DR_H;
        w->have_prev = 1;
    }
    memcpy(w->prev, rgba, (size_t)DR_W * DR_H * 4);
}

int dragon_frame_delta(const dragon_world_t *world)
{
    return ((const DRW *)world)->frame_delta;
}
