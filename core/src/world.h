/* Dragon core internals: the world struct and the shared subsystems.
 *
 * One world = one scene strip + its depth field + the ambient systems that run
 * on top. Nothing here knows about a window, a clock, or a file.
 */
#ifndef DRAGON_WORLD_H
#define DRAGON_WORLD_H

#include "dragon_internal.h"

/* ---- ambient particle limits -------------------------------------------- */
#define DR_MAX_PETALS     72
#define DR_MAX_REEDS      40
#define DR_MAX_BIRDS      7
#define DR_MAX_RIPPLES    6
#define DR_MAX_SPARKLE    28

/* Life is drawn into its own layer, then depth-tested against the scene. So an
 * ambient system gets occluded by the same one comparison a dragon does, which
 * is how we find out now whether the mechanic holds for everything. */
#define DR_LIFE_NONE      255

typedef struct {
    /* wx is a WORLD column, not a screen column. Petals are carried by the wind
     * and rooted in the landscape, so they must travel with the art as the
     * camera pans; the screen position is derived at draw time. */
    float wx, y;         /* world x, screen y; sub-pixel allowed */
    float vy, drift;     /* fall speed, horizontal drift amplitude */
    float phase;         /* drift phase */
    float period;        /* drift period, seconds */
    int size;            /* 1 or 2 px */
    int frame;           /* 2-frame tumble */
    int settled;         /* resting on rock or water */
    float rest_left;     /* seconds until it vanishes */
    int on_water;        /* settled on water: may spawn a ripple */
} dr_petal;

typedef struct {
    int x, base_y, h;
    float phase;
    int variant;
} dr_reed;

typedef struct {
    float x, y, vx, vy;
    float phase;
    int leader;          /* the one that flies off the line */
} dr_bird;

typedef struct {
    float x, y;
    float age, life;
    int max_r;
} dr_ripple;

typedef struct {
    int x, y;
    float next_flash;
    float phase;
} dr_sparkle;

/* Timer state (docs/40). Lives in the core because the alarm is a *scene*
 * event: the camera stops, the mist thickens, the label fades in. None of that
 * is a platform concern, and all of it has to be testable off-device. */
typedef struct {
    int state;
    int kind;
    double total;             /* seconds originally set */
    double remaining;
    double alarm_t;           /* seconds since the alarm began */
    float pressure;           /* 0..1 mist thickening, the held breath */
    float label_alpha;        /* 0..1, dithered, not blended */
    int still;                /* non-zero => the camera must not pan */
    char label[DR_TIMER_LABEL_MAX];
} dr_timer;

typedef struct {
    /* assets, decoded once */
    uint8_t panel[DR_W * DR_H];
    uint8_t depth[DR_W * DR_H];
    uint8_t wf[DR_W * DR_H];

    /* camera */
    double pan;                 /* world-space scroll in px */
    double t;                   /* seconds since init */
    int pan_paused;
    int map[DR_W];              /* screen x -> world column, per pan step */

    /* the hush hook (docs/35 D-015). No dragons in this prototype, so it sits
     * at 1.0, but every ambient system already multiplies by it. */
    float ambience_gain;

    dr_petal petals[DR_MAX_PETALS];
    int petal_active;
    float petal_timer;

    dr_reed reeds[DR_MAX_REEDS];
    int reed_count;

    dr_bird birds[DR_MAX_BIRDS];
    int bird_active;
    int bird_frame;
    float bird_flap;
    float bird_timer;

    dr_ripple ripples[DR_MAX_RIPPLES];
    int ripple_count;

    dr_sparkle sparkle[DR_MAX_SPARKLE];

    /* waterfall */
    float wf_pulse;
    float wf_scroll;

    /* instrumentation */
    uint8_t prev[DR_W * DR_H * 4];
    int frame_delta;
    int have_prev;

    int view;
    uint64_t seed;

    dr_timer timer;

    /* host */
    dr_host host;
    unsigned caps;
    dr_rng rng;

    /* scratch */
    uint8_t scene_idx[DR_W * DR_H];
    uint8_t scene_depth[DR_W * DR_H];
    uint8_t life_idx[DR_W * DR_H];
    uint8_t life_depth[DR_W * DR_H];
} dragon_world_t_internal;

/* alias used by subsystems so signatures stay readable */
#define DRW dragon_world_t_internal

/* ---- text (font.c) ------------------------------------------------------ */

#define DR_GLYPH_W 5
#define DR_GLYPH_H 7

int dr_text_width(const char *s);
int dr_text_height(void);
int dr_text_draw(DRW *w, int x, int y, const char *s, int ink, int depth);
int dr_text_draw_centred(DRW *w, int centre_x, int y, const char *s, int ink, int depth);
int dr_text_draw_outlined(DRW *w, int x, int y, const char *s, int ink, int halo, int depth);
int dr_text_draw_centred_outlined(DRW *w, int centre_x, int y, const char *s,
                                  int ink, int halo, int depth);

/* ---- the timer (timer.c) ------------------------------------------------ */

void dr_timer_init(dr_timer *tm);
void dr_timer_start(dr_timer *tm, double seconds, const char *label, int kind);
void dr_timer_cancel(dr_timer *tm);
void dr_timer_set_label(dr_timer *tm, const char *label);
void dr_timer_step(dr_timer *tm, double dt);
int  dr_timer_phase(const dr_timer *tm);
void dr_timer_render(DRW *w);

float dr_gust(const DRW *w, float world_x, float t);

void dr_scene_decode(DRW *w);
void dr_scene_compose(DRW *w);

void dr_life_reset(DRW *w);
void dr_life_step(DRW *w, float dt);
void dr_life_render(DRW *w);
/* shared helpers implemented in scene.c / palette.c */
int  dr_idx_by_luma(int luma, int warm);
int  dr_pal_luma(int idx);
int  dr_mist_alpha(int x, int y);
void dr_life_place_reeds(DRW *w);


void dr_water_step(DRW *w, float dt);
void dr_waterfall_step(DRW *w, float dt);
void dr_petals_step(DRW *w, float dt);
void dr_birds_step(DRW *w, float dt);

#endif /* DRAGON_WORLD_H */
