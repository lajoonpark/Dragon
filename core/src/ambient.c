#include <math.h>
#include <stdlib.h>

#include "world.h"

/* Ambient life.
 *
 * docs/35 is the spec: three tempos, 2-4 systems active at once, everything
 * gated by region and multiplied by ambience_gain. This file builds the four
 * systems with the best value-per-pixel and defers the rest:
 *
 *   waterfall  (D-016: required, highest value per pixel)
 *   petals     (explicitly requested; land on water -> ripple, on rock -> rest)
 *   water      (dash rows, sparkles, fish ripples)
 *   reeds      (gust-driven, susceptibility ~ height^2)
 *   birds      (rare, a scale cue rather than decoration)
 *
 * THE MEASUREMENT THAT SHAPED THIS FILE
 * The pan alone changes 29.6% of pixels per 1px step. The ambience gate in
 * docs/35 (0.30%-1.20% frame_delta) therefore cannot be applied to a composed
 * frame that is panning -- it measures the camera, not the life. So the gate is
 * measured with the pan paused (dragon_set_pan_paused), which isolates the thing
 * it was always trying to measure. Everything below is tuned against that
 * number, and tests/test_ambience.py enforces it.
 */

/* ---- shared: where the emitters are ------------------------------------- */
/* Measured by tools/pipeline/export_emitters.py from the art itself. */
#define WF_X0 360
#define WF_X1 442
#define WF_Y0  96
#define WF_Y1 200
#define BLOSSOM_X0   2
#define BLOSSOM_X1  62
#define BLOSSOM_Y0 188
#define BLOSSOM_Y1 252

static inline int idx(int x, int y) { return y * DR_W + x; }

/* ---- water -------------------------------------------------------------- */

void dr_water_step(DRW *w, float dt)
{
    int i;

    /* Sparkles: ~20 per screen, each flashing once every 8-20 s. Sparse and
     * local. They are the fast tempo over water. */
    for (i = 0; i < DR_MAX_SPARKLE; i++) {
        dr_sparkle *s = &w->sparkle[i];
        if (s->x < 0) continue;
        s->next_flash -= dt;
        if (s->next_flash <= 0.0f) {
            s->next_flash = dr_rng_range(&w->rng, 8.0f, 20.0f);
            s->phase = dr_rng_range(&w->rng, 0.0f, 0.20f);
        }
    }

    /* Fish ripples: one expanding ring every 30-90 s, never two at once. */
    for (i = 0; i < w->ripple_count; i++) {
        w->ripples[i].age += dt;
    }
    /* drop finished rings so the pool is reused */
    {
        int j, n = 0;
        for (j = 0; j < w->ripple_count; j++)
            if (w->ripples[j].age < w->ripples[j].life)
                w->ripples[n++] = w->ripples[j];
        w->ripple_count = n;
    }
}

static void draw_water(DRW *w)
{
    int y, x, i;
    /* Dash rows live where the water is: the mirror band, and only where the
     * art is actually water (pale). A dash row across rock reads as a scan bar
     * -- the exact failure recorded in docs/25 (r44, "a dotted line across the
     * entire frame"). */
    for (y = DR_WATER_TOP + 1; y < DR_H; y++) {
        int row_sh = (int)(y - DR_WATER_TOP);
        int spacing = 5 + ((y * 7) & 3);
        if (row_sh % spacing) continue;
        for (x = 0; x < DR_W; x++) {
            int i2 = idx(x, y);
            if (w->scene_idx[i2] == 0) continue;
            if (dr_pal_luma(w->scene_idx[i2]) < 150) continue;
            /* world-anchored dashes at half pan speed */
            {
                /* Dash rows scroll at ~half the pan speed AND drift on their
                 * own at the documented 4 px/s (docs/35 slow tempo), so the
                 * water keeps moving when the camera holds. */
                int wx = (int)(x + w->pan * 0.5 + (float)w->t * 4.0f) + y * 31;
                if ((wx & 15) < 3) {
                    int len = 2 + ((wx >> 4) % 5);
                    if ((wx & 15) >= len + 3) continue;
                    w->life_idx[i2] = (uint8_t)dr_idx_by_luma(
                        dr_clampi(dr_pal_luma(w->scene_idx[i2]) - 22, 0, 255), 0);
                    w->life_depth[i2] = 12;      /* just under the surface */
                }
            }
        }
    }

    /* sparkles */
    for (i = 0; i < DR_MAX_SPARKLE; i++) {
        dr_sparkle *s = &w->sparkle[i];
        if (s->x < 0) continue;
        /* Only the top of the flash window is visible: a sparkle is a 1px mark
         * that appears and is gone, not a dot held for a fifth of a second. */
        if (s->next_flash > 0.14f) continue;
        {
            /* sparkles are pinned to the water surface, so they pan with it */
            int sx = dr_wrap_screen(s->x, w->pan), sy = s->y;
            int i2;
            if (sx < 0) continue;
            i2 = idx(sx, sy);
            if (w->scene_depth[i2] >= 13) {
                w->life_idx[i2] = (uint8_t)dr_pal_warm(0.95f);
                w->life_depth[i2] = 13;
            }
        }
    }

    /* ripples: expanding ring, 4-6px max, then gone */
    for (i = 0; i < w->ripple_count; i++) {
        dr_ripple *r = &w->ripples[i];
        int rad, k;
        if (r->age >= r->life) continue;
        rad = (int)(r->max_r * (r->age / r->life));
        for (k = 0; k < 12; k++) {
            float a = (float)k * 6.2831853f / 12.0f;
            int px = (int)(r->x + cosf(a) * (float)rad);
            int py = (int)(r->y + sinf(a) * (float)rad * 0.42f);
            int i2;
            if (px < 0 || px >= DR_W || py < 0 || py >= DR_H) continue;
            i2 = idx(px, py);
            if (w->scene_depth[i2] < 12) continue;
            w->life_idx[i2] = (uint8_t)dr_idx_by_luma(
                dr_clampi(dr_pal_luma(w->scene_idx[i2]) + 26, 0, 255), 1);
            w->life_depth[i2] = 13;
        }
    }
}

/* ---- waterfall ---------------------------------------------------------- */

void dr_waterfall_step(DRW *w, float dt)
{
    /* Base mist pulse at ~0.2 Hz, plus a scroll offset for the dithered core.
     * 2-3x pan speed (docs/35): falling water is the fastest vertical thing in
     * the scene and it is what makes the peaks legible. */
    w->wf_scroll += dt * 21.0f;
    if (w->wf_scroll > 4096.0f) w->wf_scroll -= 4096.0f;
    w->wf_pulse = 0.5f + 0.5f * sinf((float)w->t * 1.2566f);
}

static void draw_waterfall(DRW *w)
{
    int y, x;
    int scroll = (int)w->wf_scroll;
    /* The fall is PART OF THE PANEL: w->wf, the mask and WF_X0..X1 are all in
     * panel space, because they were measured off the art. Drawing it at literal
     * screen coordinates was a bug -- the mask stayed put while the art slid
     * under it, so the fall's texture wandered onto the cliffs and off the
     * ribbon. Everything here is converted panel -> screen via w->pan. */
    for (y = WF_Y0; y < WF_Y1; y++) {
        for (x = WF_X0; x < WF_X1; x++) {
            int m = w->wf[idx(x, y)];
            int base, band, sx;
            if (m != 1) continue;   /* haze is painted; never re-render it */
            sx = dr_wrap_screen(x, w->pan);
            base = dr_pal_luma(w->scene_idx[idx(sx, y)]);

            /* SCROLLING DITHERED TEXTURE (docs/35 #1: "static geometry,
             * animated 1-2px dithered texture, scrolling down at 2-3x pan
             * speed"). The art has already painted the ribbons, so this adds
             * motion INSIDE them and never repaints their edges.
             *
             * It darkens rather than brightens: these ribbons are the palest
             * cream in the palette, so a highlight clips to white and the fall
             * vanishes (measured: 1002 px of ribbon speckled away). A dithered
             * shadow band cannot clip and reads as water passing.
             *
             * The threshold travels with wf_scroll at 21 px/s, so roughly half
             * the ribbon is one step darker at any moment and the band marches
             * down the fall. */
            /* Short period: at 21 px/s the pattern advances ~1.4 px per frame,
             * so roughly half of the ribbon changes every frame. That churn is
             * what makes it read as water rather than as a stripe being slid. */
            band = (int)((y + scroll + x * 2) % 5) < 2;
            if (!band) continue;
            /* A whole ribbon is a large soft area, so scatter rather than screen:
             * a Bayer lattice over 80x100px of fall reads as a printed dot grid. */
            if (!dr_dither_noise(x, y, 0.85f)) continue;
            w->life_idx[idx(sx, y)] = (uint8_t)dr_idx_by_luma(
                dr_clampi(base - 11, 0, 255), 0);
            w->life_depth[idx(sx, y)] = 7;  /* mid-depth: dragons pass behind */
        }
    }

    /* Spray flecks on short parabolic arcs -- the fast tempo on the fall, and
     * the thing that stops the ribbon reading as a static texture. */
    {
        int k;
        for (k = 0; k < 9; k++) {
            float life = 0.55f + (float)(k % 3) * 0.18f;
            float u = fmodf((float)w->t * 1.7f + (float)k * 0.37f, life) / life;
            int sx = dr_wrap_screen(421 + (k % 5) * 4 - 8
                                    + (int)(u * (float)((k % 3) - 1) * 7.0f), w->pan);
            int sy = 196 - (int)(22.0f * u * (1.0f - u) * 3.0f);
            int d;
            if (sy < 0 || sy >= DR_H) continue;
            d = w->scene_depth[idx(sx, sy)];
            if (d < 5) continue;
            w->life_idx[idx(sx, sy)] = (uint8_t)dr_pal_warm(0.97f);
            w->life_depth[idx(sx, sy)] = 8;
        }
    }

    /* The base puff, pulsing, where the fall meets the mist. It participates in
     * the depth test, so a dragon behind it is partly erased -- "gorgeous", per
     * docs/35. */
    {
        int cy = 200;
        int r = 9 + (int)(w->wf_pulse * 3.0f);
        int dy, cxs = dr_wrap_screen(421, w->pan);
        for (dy = -r; dy <= r; dy++) {
            int dx;
            for (dx = -r; dx <= r; dx++) {
                int d2 = dx * dx + dy * dy;
                int px = cxs + dx, py = cy + dy;
                float a;
                if (d2 > r * r) continue;
                if (px < 0 || px >= DR_W || py < 0 || py >= DR_H) continue;
                a = 0.42f * (1.0f - sqrtf((float)d2) / (float)r);
                if (a < DR_DITH_LO) continue;
                if (!dr_dither(px, py + ((int)w->wf_pulse), a)) continue;
                w->life_idx[idx(px, py)] = (uint8_t)dr_pal_warm(0.72f);
                w->life_depth[idx(px, py)] = 8;
            }
        }
    }
}

/* ---- petals ------------------------------------------------------------- */

void dr_life_reset(DRW *w)
{
    int i;
    for (i = 0; i < DR_MAX_PETALS; i++) w->petals[i].settled = 0, w->petals[i].size = 0;
    w->petal_active = 0;
    w->petal_timer = 0.0f;
    for (i = 0; i < DR_MAX_SPARKLE; i++) {
        w->sparkle[i].x = -1;
    }
    w->ripple_count = 0;
    w->bird_active = 0;
    w->bird_timer = 14.0f;
}

static void spawn_petal(DRW *w)
{
    int i, free_slot = -1, oldest = -1;
    float oldest_rest = 1e9f;
    for (i = 0; i < DR_MAX_PETALS; i++) {
        dr_petal *p = &w->petals[i];
        if (!p->size) { if (free_slot < 0) free_slot = i; continue; }
        /* A settled petal lies still for 20-60s, and there are far more of those
         * than there are falling ones. Without this, settled petals fill every
         * slot within a minute and no petal ever falls again: measured 72/72
         * slots settled and a mean of 0.8 petals airborne against docs/35's
         * 30-70. Evicting the one closest to vanishing recycles the pool into
         * the falling population, which is the thing you actually see. */
        if (p->settled && p->rest_left < oldest_rest) {
            oldest_rest = p->rest_left;
            oldest = i;
        }
    }
    if (free_slot < 0) {
        if (oldest < 0) return;         /* genuinely full of falling petals */
        free_slot = oldest;
    }
    if (free_slot >= 0) {
        dr_petal *p = &w->petals[free_slot];
        p->wx = dr_rng_range(&w->rng, (float)BLOSSOM_X0 - 4.0f,
                             (float)BLOSSOM_X1 + 10.0f);
        p->y = dr_rng_range(&w->rng, BLOSSOM_Y0 - 14.0f, BLOSSOM_Y0 + 10.0f);
        p->vy = dr_rng_range(&w->rng, 6.0f, 13.0f);
        p->drift = dr_rng_range(&w->rng, 4.0f, 11.0f);
        p->period = dr_rng_range(&w->rng, 3.0f, 6.0f);
        p->phase = dr_rng_range(&w->rng, 0.0f, 6.2831853f);
        p->size = (p->y > 200.0f && dr_rng_f(&w->rng) < 0.4f) ? 2 : 1;
        p->frame = 0;
        p->settled = 0;
        p->rest_left = 0.0f;
        p->on_water = 0;
    }
}

void dr_petals_step(DRW *w, float dt)
{
    int i;
    int alive = 0;
    /* Micro-motion in still air, and gusts visibly detach a burst. Base rate is
     * low so a gust is felt as an event. */
    w->petal_timer -= dt * w->ambience_gain;
    if (w->petal_timer <= 0.0f) {
        w->petal_timer = dr_rng_range(&w->rng, 0.10f, 0.26f);
        spawn_petal(w);
    }

    for (i = 0; i < DR_MAX_PETALS; i++) {
        dr_petal *p = &w->petals[i];
        float gust;
        if (!p->size) continue;

        if (p->settled) {
            p->rest_left -= dt;
            if (p->rest_left <= 0.0f) p->size = 0;
            continue;
        }
        alive++;

        /* gust() is a function of WORLD x, so it must be sampled at the petal's
         * world position -- feeding it a screen x made the wind pattern slide
         * under the petals as the camera moved. */
        gust = dr_gust(w, p->wx, (float)w->t);
        p->phase += dt * 6.2831853f / p->period;
        p->y += p->vy * dt;
        p->wx += (sinf(p->phase) * p->drift + gust * 9.0f) * dt;
        if (p->wx < 0.0f) p->wx += (float)DR_W;
        if (p->wx >= (float)DR_W) p->wx -= (float)DR_W;

        /* 2-frame tumble, cycling every 8-20 frames: at 1-2px this reads as
         * rotation and costs nothing. */
        if (((int)(p->y * 0.7f + p->phase) & 15) < 3) p->frame = 1 - p->frame;

        if (p->y >= (float)DR_H + 4.0f) { p->size = 0; continue; }

        /* Landing. On water -> ripple ring; on rock -> lie there 20-60 s.
         *
         * Sampled through the pan map, so "what is under the petal" is the art
         * that is actually under it. Reading the panel at the petal's world
         * column would be the same thing, but going through map[] keeps the
         * question ("is this rock or water?") identical to the one the renderer
         * answers. */
        {
            int px = dr_wrap_screen((int)p->wx, w->pan), py = (int)p->y;
            int i2, d, l;
            if (py >= DR_H) { p->size = 0; continue; }
            i2 = idx(px, py);
            d = w->scene_depth[i2];
            l = dr_pal_luma(w->scene_idx[i2]);
            if (py >= DR_WATER_TOP && l > 150 && d <= 12) {
                p->settled = 1; p->on_water = 1;
                p->rest_left = dr_rng_range(&w->rng, 0.6f, 1.2f);
                if (w->ripple_count < DR_MAX_RIPPLES) {
                    w->ripples[w->ripple_count].x = p->wx;
                    w->ripples[w->ripple_count].y = p->y;
                    w->ripples[w->ripple_count].age = 0.0f;
                    w->ripples[w->ripple_count].life = 1.0f;
                    w->ripples[w->ripple_count].max_r = 5;
                    w->ripple_count++;
                }
            } else if (d >= 11 && l < 120) {
                /* rock: land anywhere on it, not only below the waterline --
                 * the near rock climbs well above DR_WATER_TOP, and petals were
                 * falling straight through the upper half of it */
                if (dr_rng_f(&w->rng) < 0.5f) {
                    p->settled = 1;
                    p->rest_left = dr_rng_range(&w->rng, 20.0f, 60.0f);
                }
            }
        }
    }
    w->petal_active = alive;
}

/* ---- reeds -------------------------------------------------------------- */

void dr_life_place_reeds(DRW *w)
{
    int i, x;
    /* On the bottom-left foreground crest, in clumps, never evenly spaced
     * ("evenly-spaced grass is the loudest tell of a procedural scene"). */
    i = 0;
    for (x = 4; x < 118 && i < DR_MAX_REEDS; x += dr_rng_range_i(&w->rng, 2, 7)) {
        int y;
        for (y = 150; y < DR_H; y++) {
            int li = dr_pal_luma(w->panel[idx(x, y)]);
            int d = w->depth[idx(x, y)];
            if (li < 70 && d >= 11) {
                w->reeds[i].x = x;   /* world column: reeds belong to the rock */
                w->reeds[i].base_y = y;
                w->reeds[i].h = 4 + dr_rng_range_i(&w->rng, 0, 7);
                w->reeds[i].phase = dr_rng_range(&w->rng, 0.0f, 6.2831853f);
                w->reeds[i].variant = dr_rng_range_i(&w->rng, 0, 2);
                i++;
                break;
            }
        }
    }
    w->reed_count = i;
}


static void draw_reeds(DRW *w)
{
    int i;
    for (i = 0; i < w->reed_count; i++) {
        dr_reed *r = &w->reeds[i];
        int k;
        float bend;
        /* Susceptibility ~ height^2: tips whip, bases do not. In still air a
         * ~0.15 Hz 1px micro-motion so they are never perfectly frozen. */
        bend = dr_gust(w, (float)r->x, (float)w->t) * (float)(r->h * r->h) * 0.30f
             + sinf((float)w->t * 0.94f + r->phase) * 0.8f;
        for (k = 0; k < r->h; k++) {
            float u = (float)(k + 1) / (float)r->h;
            /* World column -> screen. Reeds are rooted in the rock, so they must
             * travel WITH the art; drawn at a literal screen x they slid across
             * the cliffs as the camera moved, which is the classic tell of a
             * particle layer pasted over a panning background. */
            int pxs = dr_wrap_screen(r->x + (int)(bend * u * u), w->pan);
            int py = r->base_y - k;
            int li, px;
            if (pxs < 0 || py < 0) continue;
            px = pxs;
            li = dr_pal_luma(w->scene_idx[idx(px, py)]);
            w->life_idx[idx(px, py)] = (uint8_t)dr_idx_by_luma(
                dr_clampi(li - 8, 0, 255), 0);
            w->life_depth[idx(px, py)] = 14;    /* in front of the rock they grow on */
        }
    }
}

/* ---- birds -------------------------------------------------------------- */

static void spawn_flock(DRW *w)
{
    int n = 3 + dr_rng_range_i(&w->rng, 0, 5);
    int i;
    if (n > DR_MAX_BIRDS) n = DR_MAX_BIRDS;   /* bird_active drives iteration */
    float y0 = dr_rng_range(&w->rng, 62.0f, 120.0f);
    int from_left = dr_rng_f(&w->rng) < 0.5f;
    for (i = 0; i < n && i < DR_MAX_BIRDS; i++) {
        dr_bird *b = &w->birds[i];
        b->x = (from_left ? -8.0f : (float)DR_W + 8.0f)
             - (from_left ? 1.0f : -1.0f) * dr_rng_range(&w->rng, 0.0f, 26.0f);
        b->y = y0 + dr_rng_range(&w->rng, -7.0f, 7.0f);
        b->vx = (from_left ? 1.0f : -1.0f) * dr_rng_range(&w->rng, 34.0f, 46.0f);
        b->vy = dr_rng_range(&w->rng, -2.0f, 2.0f);
        b->phase = dr_rng_range(&w->rng, 0.0f, 6.2831853f);
        b->leader = (i == 0);
    }
    w->bird_active = n;
    w->bird_frame = 0;
    w->bird_flap = 0.0f;
}

void dr_birds_step(DRW *w, float dt)
{
    int i;

    if (w->bird_active == 0) {
        w->bird_timer -= dt;
        if (w->bird_timer <= 0.0f) {
            /* One flock per 3-5 minutes: their value is entirely in their
             * rarity, and they are a scale cue, not decoration. */
            spawn_flock(w);
            w->bird_timer = dr_rng_range(&w->rng, 180.0f, 300.0f);
        }
        return;
    }

    /* 2-frame flap on a shared cycle, with a small per-bird offset. */
    w->bird_flap += dt;
    if (w->bird_flap > 0.13f) { w->bird_flap = 0.0f; w->bird_frame = 1 - w->bird_frame; }

    {
        int any = 0;
        for (i = 0; i < w->bird_active; i++) {
            dr_bird *b = &w->birds[i];
            b->phase += dt * 2.1f;
            /* shallow arc, not a straight line, and slightly sloppy */
            b->x += b->vx * dt;
            b->y += (b->vy + sinf(b->phase) * 2.4f) * dt;
            if (b->x > -24.0f && b->x < (float)DR_W + 24.0f) any = 1;
        }
        if (!any) w->bird_active = 0;
    }
}

static void draw_birds(DRW *w)
{
    int i;
    for (i = 0; i < w->bird_active; i++) {
        dr_bird *b = &w->birds[i];
        int px = (int)b->x, py = (int)b->y;
        int wing = w->bird_frame ? 1 : -1;
        int off = b->leader ? 1 : 0;      /* one bird slightly off the line */
        int k;
        if (px < -1 || px > DR_W || py < 0 || py >= DR_H) continue;
        /* 1px each, a 2-frame wing flap. At far depth, and rare. */
        for (k = 0; k < 2; k++) {
            int qx = px + (k ? 1 : -1);
            int qy = py + (k ? wing : -wing) + off;
            if (qx < 0 || qx >= DR_W || qy < 0 || qy >= DR_H) continue;
            w->life_idx[idx(qx, qy)] = (uint8_t)dr_idx_by_luma(48, 0);
            w->life_depth[idx(qx, qy)] = 5;    /* far: behind the mid peaks */
        }
    }
}

/* ---- the director ------------------------------------------------------- */

void dr_life_step(DRW *w, float dt)
{
    dr_water_step(w, dt);
    dr_waterfall_step(w, dt);
    dr_petals_step(w, dt);
    dr_birds_step(w, dt);
}

void dr_life_render(DRW *w)
{
    memset(w->life_idx, DR_LIFE_NONE, sizeof(w->life_idx));
    memset(w->life_depth, 0, sizeof(w->life_depth));
    draw_water(w);
    draw_waterfall(w);
    draw_birds(w);
    draw_reeds(w);
    {
        int i;
        for (i = 0; i < DR_MAX_PETALS; i++) {
            dr_petal *p = &w->petals[i];
            int px, py;
            if (!p->size) continue;
            /* near petals are warm cream against the cool scene: one accent,
             * used once (docs/15). Far ones are just a pale speck. */
            px = dr_wrap_screen((int)p->wx, w->pan);
            py = (int)p->y;
            if (py < 0 || py >= DR_H) continue;
            w->life_idx[idx(px, py)] = (uint8_t)(p->settled
                ? dr_pal_warm(0.62f) : dr_pal_warm(0.90f));
            w->life_depth[idx(px, py)] = p->size == 2 ? 13 : 10;
            if (p->size == 2) {
                int ox = p->frame ? 1 : 0;
                if (px + ox < DR_W) {
                    w->life_idx[idx(px + ox, py)] = (uint8_t)dr_pal_warm(0.78f);
                    w->life_depth[idx(px + ox, py)] = 13;
                }
            }
        }
    }
}
