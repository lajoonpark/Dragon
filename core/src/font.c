/* Core text: a 5x7 ink face, drawn only into the life layer.
 *
 * docs/40 asks for the countdown and the timer label "in the paper-cream ink,
 * small, no boxes". That means the text is part of the painting, not a widget
 * pasted over it -- so it is drawn with palette indices from the warm ramp and
 * it obeys the same depth test the petals do. A label that floats above the
 * mist would be the only thing in the frame exempt from the world, and the eye
 * finds that instantly.
 *
 * There is no font engine here: no kerning, no wrapping, no antialiasing. Every
 * glyph is 5x7 with one blank column of tracking, which is what pixel art
 * wants, and at 1:1 it cannot be made softer or it stops being pixel art.
 */
#include "world.h"

/* 5x7 glyph table, rows top to bottom, bit 4 = leftmost column.
 *
 * Small caps only: lowercase input is folded to uppercase. At 480x270 a
 * 5x7 face is the difference between a caption and a smudge, and a
 * second lowercase set costs a table twice this size for a caption that
 * is one line long. */
static const unsigned char glyphs[][7] = {
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00 },   /* ' ' */
    { 0x04, 0x04, 0x04, 0x04, 0x04, 0x00, 0x04 },   /* '!' */
    { 0x04, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00 },   /* '\'' */
    { 0x02, 0x04, 0x08, 0x08, 0x08, 0x04, 0x02 },   /* '(' */
    { 0x08, 0x04, 0x02, 0x02, 0x02, 0x04, 0x08 },   /* ')' */
    { 0x00, 0x04, 0x04, 0x1f, 0x04, 0x04, 0x00 },   /* '+' */
    { 0x00, 0x00, 0x00, 0x1f, 0x00, 0x00, 0x00 },   /* '-' */
    { 0x00, 0x00, 0x00, 0x00, 0x00, 0x06, 0x06 },   /* '.' */
    { 0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x10 },   /* '/' */
    { 0x0e, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0e },   /* '0' */
    { 0x04, 0x0c, 0x04, 0x04, 0x04, 0x04, 0x0e },   /* '1' */
    { 0x0e, 0x11, 0x01, 0x02, 0x04, 0x08, 0x1f },   /* '2' */
    { 0x1f, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0e },   /* '3' */
    { 0x02, 0x06, 0x0a, 0x12, 0x1f, 0x02, 0x02 },   /* '4' */
    { 0x1f, 0x10, 0x1e, 0x01, 0x01, 0x11, 0x0e },   /* '5' */
    { 0x06, 0x08, 0x10, 0x1e, 0x11, 0x11, 0x0e },   /* '6' */
    { 0x1f, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08 },   /* '7' */
    { 0x0e, 0x11, 0x11, 0x0e, 0x11, 0x11, 0x0e },   /* '8' */
    { 0x0e, 0x11, 0x11, 0x0f, 0x01, 0x02, 0x0c },   /* '9' */
    { 0x00, 0x04, 0x04, 0x00, 0x04, 0x04, 0x00 },   /* ':' */
    { 0x0e, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04 },   /* '?' */
    { 0x06, 0x09, 0x09, 0x06, 0x00, 0x00, 0x00 },   /* '~' used as the degree mark */
    { 0x0e, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11 },   /* 'A' */
    { 0x1e, 0x11, 0x11, 0x1e, 0x11, 0x11, 0x1e },   /* 'B' */
    { 0x0e, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0e },   /* 'C' */
    { 0x1c, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1c },   /* 'D' */
    { 0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x1f },   /* 'E' */
    { 0x1f, 0x10, 0x10, 0x1e, 0x10, 0x10, 0x10 },   /* 'F' */
    { 0x0e, 0x11, 0x10, 0x13, 0x11, 0x11, 0x0f },   /* 'G' */
    { 0x11, 0x11, 0x11, 0x1f, 0x11, 0x11, 0x11 },   /* 'H' */
    { 0x0e, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0e },   /* 'I' */
    { 0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0c },   /* 'J' */
    { 0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11 },   /* 'K' */
    { 0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1f },   /* 'L' */
    { 0x11, 0x1b, 0x15, 0x15, 0x11, 0x11, 0x11 },   /* 'M' */
    { 0x11, 0x19, 0x15, 0x15, 0x13, 0x11, 0x11 },   /* 'N' */
    { 0x0e, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e },   /* 'O' */
    { 0x1e, 0x11, 0x11, 0x1e, 0x10, 0x10, 0x10 },   /* 'P' */
    { 0x0e, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0d },   /* 'Q' */
    { 0x1e, 0x11, 0x11, 0x1e, 0x14, 0x12, 0x11 },   /* 'R' */
    { 0x0f, 0x10, 0x10, 0x0e, 0x01, 0x01, 0x1e },   /* 'S' */
    { 0x1f, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04 },   /* 'T' */
    { 0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0e },   /* 'U' */
    { 0x11, 0x11, 0x11, 0x11, 0x11, 0x0a, 0x04 },   /* 'V' */
    { 0x11, 0x11, 0x11, 0x15, 0x15, 0x1b, 0x11 },   /* 'W' */
    { 0x11, 0x11, 0x0a, 0x04, 0x0a, 0x11, 0x11 },   /* 'X' */
    { 0x11, 0x11, 0x0a, 0x04, 0x04, 0x04, 0x04 },   /* 'Y' */
    { 0x1f, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1f },   /* 'Z' */
};

static const char glyph_chars[] = " !'()+-./0123456789:?~ABCDEFGHIJKLMNOPQRSTUVWXYZ";
#define GLYPH_COUNT ((int)(sizeof(glyph_chars) - 1))


static int glyph_index(int ch)
{
    int i;
    if (ch >= 'a' && ch <= 'z') ch -= 32;      /* fold to the small-caps set */
    /* docs/40 writes the label as "°  Bread is done  ". A real degree sign needs
     * two UTF-8 bytes and this face is byte-indexed, so it is aliased to the
     * ring glyph; the host passes UTF-8 and the alias folds it in. */
    if (ch == 0xC2 || ch == 0xB0) ch = '~';
    for (i = 0; i < GLYPH_COUNT; i++) {
        if (glyph_chars[i] == (char)ch) return i;
    }
    return -1;
}

int dr_text_width(const char *s)
{
    int n = 0;
    if (!s) return 0;
    while (*s) { n++; s++; }
    /* 5 px glyph + 1 px tracking, minus the trailing gap */
    return n > 0 ? n * (DR_GLYPH_W + 1) - 1 : 0;
}

int dr_text_height(void) { return DR_GLYPH_H; }

/* Draw at (x, y) = top-left, in palette index `ink`. Returns the advance width.
 *
 * `depth` is written into the life depth buffer so the compositor can hide the
 * text behind nearer rock. Text is drawn as the nearest thing that is not
 * foreground rock -- it is an annotation on the world, like the painted
 * inscription on a real handscroll, and those sit in front of the wash. */
int dr_text_draw(DRW *w, int x, int y, const char *s, int ink, int depth)
{
    int cx = x;
    if (!s) return 0;
    while (*s) {
        int gi = glyph_index((unsigned char)*s);
        if (gi >= 0) {
            int row;
            for (row = 0; row < DR_GLYPH_H; row++) {
                int bits = glyphs[gi][row];
                int col;
                for (col = 0; col < DR_GLYPH_W; col++) {
                    int px = cx + col, py = y + row;
                    if (!(bits & (1 << (DR_GLYPH_W - 1 - col)))) continue;
                    if (px < 0 || px >= DR_W || py < 0 || py >= DR_H) continue;
                    w->life_idx[py * DR_W + px] = (uint8_t)ink;
                    w->life_depth[py * DR_W + px] = (uint8_t)depth;
                }
            }
        }
        cx += DR_GLYPH_W + 1;
        s++;
    }
    return cx - x;
}

/* Same, horizontally centred on `centre_x`. */
int dr_text_draw_centred(DRW *w, int centre_x, int y, const char *s, int ink, int depth)
{
    int x = centre_x - dr_text_width(s) / 2;
    return dr_text_draw(w, x, y, s, ink, depth);
}

/* Text with a 1px keyline, drawn in `halo`, so it survives any background.
 *
 * This is not decoration: docs/00 makes the 1px ink outline a non-negotiable of
 * the style, and here it is also a legibility requirement. The composition
 * deliberately keeps the centre of the screen a pale void -- the "dragon stage"
 * -- and paper-cream text on paper-cream mist is invisible. Dark ink with a
 * cream keyline is legible on both the void and on foreground rock, which is the
 * whole reason inscriptions on real handscrolls are dark. */
int dr_text_draw_outlined(DRW *w, int x, int y, const char *s,
                          int ink, int halo, int depth)
{
    static const int ox[4] = { -1, 1, 0, 0 };
    static const int oy[4] = { 0, 0, -1, 1 };
    int i;
    for (i = 0; i < 4; i++) dr_text_draw(w, x + ox[i], y + oy[i], s, halo, depth);
    return dr_text_draw(w, x, y, s, ink, depth);
}

int dr_text_draw_centred_outlined(DRW *w, int centre_x, int y, const char *s,
                                  int ink, int halo, int depth)
{
    return dr_text_draw_outlined(w, centre_x - dr_text_width(s) / 2, y, s, ink, halo, depth);
}
