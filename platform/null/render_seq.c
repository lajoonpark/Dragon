/* The null host: ~80 lines, always builds, writes PPM.
 *
 * Not a toy. This is the Linux dev loop and the portability canary
 * (docs/55): if the core ever starts depending on a real platform, this stops
 * compiling and we find out immediately.
 *
 *   render_seq --frames 240 --out /tmp/seq --seed 0x5EED
 *
 * Writes 0000.ppm ... and prints the ambience delta per frame, so the
 * ship-blocking 0.30%-1.20% band (docs/35) can be checked from a terminal.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <math.h>

#include "dragon.h"

typedef struct {
    double t0;
    int frame;
    int pan_paused;
    const char *dir;
    int quiet;
} null_state;

static double null_now(void *user)
{
    null_state *st = (null_state *)user;
    return (double)st->frame / (double)DR_DEFAULT_FPS;
}

static void ppm_write(const char *dir, int n, const uint8_t *rgba, int w, int h)
{
    char path[512];
    FILE *f;
    int x, y;
    snprintf(path, sizeof(path), "%s/%04d.ppm", dir, n);
    f = fopen(path, "wb");
    if (!f) return;
    fprintf(f, "P6\n%d %d\n255\n", w, h);
    for (y = 0; y < h; y++) {
        for (x = 0; x < w; x++) {
            const uint8_t *p = rgba + ((size_t)y * w + x) * 4;
            fwrite(p, 1, 3, f);
        }
    }
    fclose(f);
}

static void null_present(void *user, const uint8_t *rgba, int w, int h, int scale)
{
    null_state *st = (null_state *)user;
    (void)scale;
    if (st->dir) ppm_write(st->dir, st->frame, rgba, w, h);
}

static int null_prefs_read(void *user, const char *key, char *out, int cap)
{
    (void)user; (void)key; (void)out; (void)cap;
    return 0;
}

static int null_prefs_write(void *user, const char *key, const char *val)
{
    (void)user; (void)key; (void)val;
    return 0;
}

static void null_log(void *user, int level, const char *msg)
{
    (void)user;
    fprintf(stderr, "[%d] %s\n", level, msg);
}

static void usage(void)
{
    fprintf(stderr,
        "render_seq --frames N [--out DIR] [--seed HEX] [--fps N]\n"
        "           [--pan-paused] [--quiet] [--seek N] [--pan PX]\n"
        "           [--dump-frame N --png FILE]\n");
}

int main(int argc, char **argv)
{
    int frames = 120, i, fps = DR_DEFAULT_FPS, dump = -1, quiet = 0, seek = 0;
    double pan = -1.0;
    const char *out = "/tmp/dragonseq";
    const char *png = NULL;
    uint64_t seed = 0x5EED0D1Aull;
    int pan_paused = 0;
    null_state st;
    dr_host host;
    dragon_world_t *w;
    uint8_t *fb = (uint8_t *)malloc(DR_W * DR_H * 4);
    long long delta_sum = 0;
    int delta_n = 0, delta_min = 1 << 30, delta_max = 0;

    for (i = 1; i < argc; i++) {
        if (!strcmp(argv[i], "--frames") && i + 1 < argc) frames = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--out") && i + 1 < argc) out = argv[++i];
        else if (!strcmp(argv[i], "--seed") && i + 1 < argc) seed = strtoull(argv[++i], NULL, 0);
        else if (!strcmp(argv[i], "--fps") && i + 1 < argc) fps = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--pan-paused")) pan_paused = 1;
        else if (!strcmp(argv[i], "--seek") && i + 1 < argc) seek = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--pan") && i + 1 < argc) pan = atof(argv[++i]);
        else if (!strcmp(argv[i], "--quiet")) quiet = 1;
        else if (!strcmp(argv[i], "--dump-frame") && i + 1 < argc) dump = atoi(argv[++i]);
        else if (!strcmp(argv[i], "--png") && i + 1 < argc) png = argv[++i];
        else { usage(); return 2; }
    }

    memset(&st, 0, sizeof(st));
    st.dir = out;
    st.quiet = quiet;

    memset(&host, 0, sizeof(host));
    host.user = &st;
    host.now = null_now;
    host.present = null_present;
    host.prefs_read = null_prefs_read;
    host.prefs_write = null_prefs_write;
    host.log = null_log;

    w = dragon_world_create(&host, seed, DR_PRESET_DAWN_MIST);
    if (!w) { fprintf(stderr, "world create failed\n"); return 1; }
    dragon_set_pan_paused(w, pan_paused);

    /* --pan jumps straight to a world offset, for reviewing a specific part of
     * the 960px cycle (the mirror joints fall at 480 and 960). */
    if (pan >= 0.0) {
        int k;
        for (k = 0; k < 40000 && dragon_pan_offset(w) < pan; k++)
            dragon_step(w, 1.0 / (double)fps);
    }

    /* --seek advances time without rendering: lets a still be taken at any
     * point in the 960px world cycle without writing every intermediate frame. */
    for (i = 0; i < seek; i++) dragon_step(w, 1.0 / (double)fps);

    for (i = 0; i < frames; i++) {
        st.frame = i;
        dragon_step(w, 1.0 / (double)fps);
        dragon_frame(w, fb);

        if (i > 0) {
            int d = dragon_frame_delta(w);
            double pct = d * 100.0 / (DR_W * DR_H);
            delta_sum += d;
            delta_n++;
            if (d < delta_min) delta_min = d;
            if (d > delta_max) delta_max = d;
            if (getenv("DRAGON_TRACE"))
                printf("frame %4d  delta %6d  %5.2f%%\n", i, d, pct);
        }
        if (i == dump && png) {
            FILE *f = fopen(png, "wb");
            if (!f) fprintf(stderr, "cannot write %s\n", png);
            else {
                fwrite(fb, 1, (size_t)DR_W * DR_H * 4, f);
                fclose(f);
            }
        }
        st.frame = i;
        if (host.present) host.present(&st, fb, DR_W, DR_H, 0);
    }

    if (delta_n) {
        double mean = (double)delta_sum / delta_n;
        printf("frames %d  mean delta %.2f%%  min %.2f%%  max %.2f%%  (band 0.30-1.20, pan %s)\n",
               frames, mean * 100.0 / (DR_W * DR_H),
               delta_min * 100.0 / (DR_W * DR_H),
               delta_max * 100.0 / (DR_W * DR_H),
               pan_paused ? "PAUSED" : "RUNNING");
    }
    dragon_world_destroy(w);
    free(fb);
    return 0;
}
