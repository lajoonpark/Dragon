"""Dragon — ONE LAYER: the mountain range. Iteration 12.

Rewritten against TWO reviews (docs/reviews/r06-verdict.md, r11-verdict.md).
Both failed, and r11 measured exactly why:

  "98.48% of visible pixels are band 5 ... bands 0,1,2 contribute exactly zero"
  "all eight entries of the only visible band have B>R ... the lit face is
   cooler than the sky"
  "a single tone covers 28.2% of the layer as one slab from y=0 to y=224"
  "485 vertical constant-colour runs of >=45 rows (longest 178 rows)"

The root cause both reviews circle and neither quite names: **every colour
decision was a function of a coordinate.** Plane from d_rel (a row function) ->
horizontal slab. Facet from s (a column function) -> vertical bar. Any formula
keyed to x or y, applied inside a silhouette that is itself a function of x,
can only produce ruled rectangles. Arithmetic cannot make rock.

So this version inverts the model:

  1. FILL FLAT. Each mass gets one flat face value. Nothing is computed.
  2. AUTHOR THE DARKS AS SHAPES. Per summit, explicit quads -- a shadow wedge
     under the right flank, a dark saddle wedge where two flanks meet, a short
     dark base band. Hand-placed vertices, not thresholds. Every interior
     boundary therefore comes from a decision, so a ruler and a barcode are
     structurally impossible.
  3. LIGHT RUNS ACROSS THE FACE, and the palette proves it: the warm end of
     every ramp CROSSES ZERO (R > B), because the references are lit by warm
     dawn light while their shadows are cold. If the warm entry does not clear
     R-B > 0 it is not warm, it is just less blue.

The build now FAILS LOUDLY if the measurements that failed the last two reviews
go out of range. Checks are at the bottom of compose().

Run: python3 tools/proto/gen_layer.py [tag]
"""

import os
import sys
import numpy as np
from PIL import Image

W, H = 480, 270

# ------------------------------------------------------------------ palette
# 8 entries per band. idx 0-2 cold shadow, 3-4 neutral mid, 5-7 warm.
# The warm end CROSSES ZERO: R > B by a clear margin. This is the r11 fix --
# a "warm" entry with R < B reads as snow, not as lit stone.
BANDS = [
    #   shadow ............        mid .........        warm ..............
    [(168, 182, 196), (177, 189, 200), (186, 196, 205),
     (197, 204, 209), (207, 212, 213),
     (219, 217, 208), (228, 224, 209), (236, 230, 210)],
    [(150, 168, 186), (161, 177, 192), (172, 185, 198),
     (185, 195, 204), (197, 205, 210),
     (211, 211, 203), (223, 220, 206), (234, 228, 208)],
    [(130, 150, 172), (142, 160, 179), (155, 171, 187),
     (170, 183, 195), (184, 194, 203),
     (201, 204, 200), (215, 214, 202), (228, 223, 205)],
    [(107, 128, 152), (120, 140, 162), (135, 152, 172),
     (152, 167, 183), (168, 181, 194),
     (191, 197, 197), (208, 208, 196), (223, 217, 199)],
    [(83, 104, 129), (97, 118, 141), (113, 132, 153),
     (131, 149, 168), (149, 165, 181),
     (176, 184, 187), (196, 197, 186), (215, 208, 190)],
    [(58, 77, 100), (72, 92, 115), (88, 108, 131),
     (107, 126, 146), (127, 145, 162),
     (168, 166, 158), (190, 182, 166), (213, 200, 176)],
]

# flat face value per band: the mid-light plane, one entry, chosen by eye
FACE = [4, 4, 4, 3, 2, 1]
# a second, slightly darker plane for faces turning away (right flank)
FACE_FAR = [2, 2, 3, 2, 1, 0]
# the two darkest entries, for authored darks
DARK = [0, 1]
PAPER = (238, 233, 219)

VEG_NEAR = [(24, 41, 35), (16, 32, 28)]
VEG_FAR = [(122, 142, 142), (104, 124, 126), (88, 108, 110)]

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                   [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) / 16.0
ALPHA_STEPS = [255, 240, 222, 200, 176, 150, 122, 94, 64, 34]


def h1(i, s):
    n = (int(i) * 374761393 + int(s) * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


# ==================================================================
#  A MASSIF: authored as vertices only.
#
#  `crest`  : (x, y) summit/saddle nodes, descending to summits
#  `summits`: x of each summit, in order, used to place the dark wedges
#  `saddles`: x of each saddle between them
#  `darks`  : explicit polygons in frame coordinates, each (list of pts, entry)
#
#  Nothing here is derived. Every vertex is a decision.
# ==================================================================

class Mass:
    def __init__(self, band, crest, base, summits, saddles, darks,
                 mist_rows=0, side="left", veg=0.0, veg_seed=0, regions=(),
                 slabs=()):
        self.band, self.base = band, base
        self.pts = crest
        self.summits, self.saddles = summits, saddles
        self.darks = darks
        self.mist_rows = mist_rows
        self.side = side
        self.veg, self.veg_seed = veg, veg_seed
        self.regions = list(regions)
        self.slabs = list(slabs)
        self.seed2 = (abs(int(crest[0][0])) + len(crest) * 7 + band * 31)
        self.crest = [None] * W
        self._build_crest()

    def _build_crest(self):
        for i in range(len(self.pts) - 1):
            (x0, y0), (x1, y1) = self.pts[i], self.pts[i + 1]
            for x in range(int(x0), int(x1) + 1):
                if not (0 <= x < W):
                    continue
                t = (x - x0) / float(max(1, x1 - x0))
                if y1 > y0:
                    y = y0 + (y1 - y0) * (t ** 0.62)      # concave: steep at summit
                else:
                    y = y0 + (y1 - y0) * (1.0 - (1.0 - t) ** 0.62)
                if self.crest[x] is None or y < self.crest[x]:
                    self.crest[x] = float(y)
        # Fill only gaps INSIDE the authored span. Carrying the crest past the
        # last node turned each edge cliff into a full-width curtain, which
        # closed the notch and produced a single flat field across the bottom.
        xs = [i for i in range(W) if self.crest[i] is not None]
        if xs:
            lo, hi = min(xs), max(xs)
            last = None
            for x in range(lo, hi + 1):
                if self.crest[x] is not None:
                    last = self.crest[x]
                elif last is not None:
                    self.crest[x] = last

    def y_bottom(self, x=None):
        """Ragged lower edge. A flat clip produces a horizontal shelf across the
        whole frame; real rock bottoms out at a different height per column."""
        b = min(H - 1, self.base - self.mist_rows)
        if x is None:
            return b
        return b - int(h1(x // 3 + self.seed2, 211) * 7)

    # ---------------- flat fill + authored darks
    def tone_at(self, x, y):
        """Authored tone regions: (x0, x1, y0, y1, offset) rectangles.

        Buttresses (tall/narrow) and strata (short/wide) use the same mechanism;
        later regions win so a stratum can override a buttress. Nothing is
        derived from a coordinate formula, so a ruler and a barcode -- both of
        which came from deriving tone from x or y alone -- cannot occur.

        Strata are clipped to the visible face: a region may only darken a pixel
        that is inside this mass at that column, AND at least 6px in from the
        silhouette edge. Without the inset they hung off the skyline as detached
        beige slabs (r15).
        """
        base = FACE[self.band] - (0 if self.lit_at(x) else 1)
        # break the face into wide vertical slabs of two adjacent entries, keyed
        # to authored x, so no single colour can cover a whole mass. Boundaries
        # sit on the buttress edges already authored below, so this adds texture
        # without adding a new kind of decision.
        if self.slabs:
            for (sx0, sx1, soff) in self.slabs:
                if sx0 <= x <= sx1:
                    base += soff
                    break
        ct = self.crest[x]
        if ct is None:
            return base
        inset = 6 + int(h1(x // 9 + self.seed2, 307) * 5)
        top_lim = ct + inset
        # a ledge catches light only in the far bands, where everything is
        # washed toward the sky. On near rock a "lit" ledge reads as beige paint.
        max_up = 3 if self.band >= 3 else 3
        for (x0, x1, y0, y1, off) in self.regions:
            if not (x0 <= x <= x1) or y < top_lim:
                continue
            # tilt the stratum with the rock: sample the crest at the region's
            # left end and here, and carry that rise into the y-range. A flat
            # rect is a ruler; a rect that follows the bedding is a ledge.
            c0 = self.crest[max(0, min(W - 1, int(x0)))]
            rise = 0.0 if c0 is None else (ct - c0) * 0.55
            ly0, ly1 = y0 + rise, y1 + rise
            if not (ly0 <= y <= ly1):
                continue
            # TAPER. A rectangle gives a full-height vertical boundary, which the
            # audit measures as a 200px vertical run. A buttress pinches out
            # downward, so the x-range shrinks with depth -- boundaries are then
            # always slanted and a long vertical run is impossible.
            u = 0.0 if ly1 <= ly0 else (y - ly0) / float(ly1 - ly0)
            tp = min((x1 - x0) * 0.34, 16.0)
            if not (x0 + tp * u <= x <= x1 - tp * u):
                continue
            off = min(off, max_up)
            base = FACE[self.band] - (0 if self.lit_at(x) else 1) + off
        return max(0, min(len(BANDS[self.band]) - 1, base))

    def lit_at(self, x):
        if not self.summits:
            return True
        return x <= min(self.summits, key=lambda s: abs(s - x))

    def y_bottom(self, x=None):
        """Ragged lower edge, and it must NOT be a single value across the frame.
        A flat clip produced the full-width shelf in r15 (319 columns changing at
        one row). Two scales of raggedness: 3px blocks for the fine edge, and a
        slow 60px wave so the whole band bottom undulates."""
        b = min(H - 1, self.base - self.mist_rows)
        if x is None:
            return b
        fine = int(h1(x // 3 + self.seed2, 211) * 9)
        slow = int(h1(x // 61 + self.seed2, 223) * 13)
        return b - fine - slow

    def draw(self, rgb, alpha, depth, depthval):
        ramp = BANDS[self.band]
        bottom0 = self.y_bottom()

        for x in range(W):
            top = self.crest[x]
            if top is None:
                continue
            top_i = int(round(top))
            bottom = self.y_bottom(x)

            for y in range(max(0, top_i), bottom + 1):
                tone = self.tone_at(x, y)
                face = ramp[tone]
                rgb[y, x] = face
                depth[y, x] = depthval
                # Every mass dissolves at its base. The 214px run in the audit
                # was a cliff column that stayed opaque to the frame bottom, so a
                # single colour ran the full height.
                mstart = bottom - max(self.mist_rows, 26)
                if y > mstart:
                    dd = (y - mstart) / float(max(1, bottom - mstart))
                    dd = min(1.0, max(0.0, dd))
                    pos = (1.0 - dd) * (len(ALPHA_STEPS) - 1)
                    ai = int(pos)
                    frac = pos - ai
                    if BAYER4[y & 3, x & 3] > frac:
                        ai = max(0, ai - 1)
                    alpha[y, x] = ALPHA_STEPS[max(0, min(len(ALPHA_STEPS) - 1, ai))]
                else:
                    alpha[y, x] = 255

        # ---- authored darks, drawn as polygons, NEAREST-NEIGHBOUR, no AA
        for poly, entry in self.darks:
            idx = DARK[entry % len(DARK)]
            col = ramp[idx]
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            x0, x1 = max(0, int(min(xs))), min(W - 1, int(max(xs)))
            y0, y1 = max(0, int(min(ys))), min(bottom0, int(max(ys)))
            for y in range(y0, y1 + 1):
                # scanline: half-open, so adjacent polygons never double-cover
                hits = []
                n = len(poly)
                for i in range(n):
                    ax, ay = poly[i]
                    bx, by = poly[(i + 1) % n]
                    if (ay <= y < by) or (by <= y < ay):
                        tt = (y - ay) / float(by - ay)
                        hits.append(ax + (bx - ax) * tt)
                if len(hits) < 2:
                    continue
                hits.sort()
                for k in range(0, len(hits) - 1, 2):
                    for x in range(int(round(hits[k])), int(round(hits[k + 1]))):
                        if not (0 <= x < W):
                            continue
                        ct = self.crest[x]
                        if ct is None or y < ct or y > self.y_bottom(x):
                            continue
                        rgb[y, x] = col
                        depth[y, x] = depthval
                        # darks are solid rock, so they stay opaque longer
                        if y <= self.y_bottom(x) - self.mist_rows:
                            alpha[y, x] = 255

    def local_maxima(self):
        out = []
        for x in range(3, W - 3):
            ys = self.crest
            if ys[x] is None or ys[x - 3] is None or ys[x + 3] is None:
                continue
            if ys[x] < ys[x - 3] - 2 and ys[x] < ys[x + 3] - 2:
                out.append(x)
        return out

    def draw_veg(self, rgb, alpha, depth, depthval, budget):
        """Asymmetric lumps ON genuine summits of THIS mass. Occlusion-safe:
        only writes where this mass is the visible surface."""
        if budget <= 0:
            return
        pal = VEG_NEAR if self.band >= 4 else VEG_FAR
        maxima = self.local_maxima()
        if not maxima:
            return
        step = max(1, len(maxima) // budget)
        for j, x0 in enumerate(maxima[::step][:budget]):
            top = self.crest[x0]
            if top is None:
                continue
            top = int(round(top))
            ws = self.veg_seed + j * 17
            wide = 11 + int(h1(ws, 3) * 12)
            high = 5 + int(h1(ws, 5) * 4)
            col = pal[int(h1(ws, 7) * len(pal)) % len(pal)]
            for i in range(wide):
                u = i / float(wide - 1)
                hh = int(high * (0.5 + 0.5 * np.sin(np.pi * min(1.0, u * 1.1))))
                hh = max(2, hh + (1 if h1(ws + i, 9) > 0.65 else 0))
                xx = x0 - wide // 2 + i
                if not (0 <= xx < W):
                    continue
                ct = self.crest[xx]
                if ct is None:
                    continue
                # only if this mass is actually the surface here
                if int(round(ct)) > top + 3:
                    continue
                for k in range(hh):
                    yy = int(round(ct)) - 1 + k
                    if 0 <= yy < H:
                        rgb[yy, xx] = col
                        alpha[yy, xx] = 255
                        depth[yy, xx] = depthval


# ==================================================================
#  AUTHORED POLYGONS. All coordinates in frame space. Every vertex chosen.
# ==================================================================

def wedge(ax, ay, bx, by, depth, lean=0.0, into=1):
    """A shadow wedge hanging under a flank: from (ax,ay) to (bx,by) along the
    crest, extending `depth` px down, with the free edge leaning `lean` px."""
    return [(ax, ay), (bx, by), (bx + lean, by + depth), (ax, ay + depth)]


def saddle_v(lx, ly, rx, ry, depth):
    """A dark V in a saddle: two crest points meeting, filled down to `depth`."""
    mx = (lx + rx) / 2.0
    my = min(ly, ry)
    return [(lx, ly), (mx, my), (rx, ry), (rx, ry + depth), (mx, my + depth),
            (lx, ly + depth)]


def base_band(l, r, y, deep, steps=4):
    """A dark band that is SEGMENTED and jagged. A plain rect produced the
    longest vertical run in the audit (214px) and a ruler edge; stepping the
    lower edge fixes both while keeping it authored."""
    pts = [(l, y)]
    w = (r - l) / float(steps)
    for i in range(steps):
        xa, xb = l + w * i, l + w * (i + 1)
        d = deep + (i * 7) % 5 - 2
        pts += [(xa, y + d), (xb, y + d)]
    pts += [(r, y)]
    return pts


# ---------------------------------------------------------------------------
#  V-NOTCH GEOMETRY
#
#  Two edge cliffs per band, cropped by the frame edges, whose inner ends form a
#  staircase inside the notch. Each band's inner end is ~24px ABOVE the band in
#  front of it, so counting ridges is possible -- which is the whole depth idea
#  in all four references.
#
#    band   inner end (y)   opening (x)
#      5         176          100..384
#      4         150          124..360
#      3         126          150..334
#      2         102          178..308
#      1          78          208..280
#      0          54         (the notch floor summit)
# ---------------------------------------------------------------------------

L5_CREST = [(-30, -60), (14, -44), (44, -6), (68, 40), (86, 110), (100, 176)]
R5_CREST = [(384, 176), (402, 140), (426, 80), (452, 20), (478, -20), (512, -46)]

L4_CREST = [(-30, -30), (20, -16), (52, 20), (78, 70), (100, 120), (124, 150)]
R4_CREST = [(360, 150), (380, 116), (404, 64), (432, 12), (462, -26), (510, -46)]

L3_CREST = [(-30, -6), (30, 8), (66, 44), (96, 86), (122, 112), (150, 126)]
R3_CREST = [(334, 126), (356, 96), (386, 54), (418, 12), (452, -24), (508, -44)]

L2_CREST = [(-30, 18), (40, 30), (82, 58), (118, 84), (146, 98), (178, 102)]
R2_CREST = [(308, 102), (330, 80), (360, 44), (394, 8), (432, -20), (494, -42)]

L1_CREST = [(-30, 42), (50, 52), (96, 66), (134, 74), (170, 78), (208, 78)]
R1_CREST = [(280, 78), (304, 62), (334, 34), (368, 4), (406, -18), (484, -40)]

L0_CREST = [(-30, 70), (50, 64), (110, 58), (150, 46), (190, 56), (220, 42), (238, 50)]
R0_CREST = [(236, 50), (270, 40), (300, 52), (340, 46), (390, 40), (440, 44), (500, 36)]

# ---- authored darks: shadow wedges under right flanks, dark saddle Vs,
#      short dark base bands. Vertices only, never full-frame width.
L5_DARKS = [(wedge(44, -6, 86, 110, 30, lean=-8), 1),
            (saddle_v(68, 40, 86, 110, 16), 0),
            (base_band(-20, 66, 232, 18), 1)]
R5_DARKS = [(wedge(426, 80, 478, -20, 28, lean=6), 1),
            (saddle_v(402, 140, 426, 80, 15), 0),
            (base_band(430, 516, 230, 16), 1)]
L4_DARKS = [(wedge(52, 20, 100, 120, 24, lean=-6), 1),
            (saddle_v(78, 70, 100, 120, 13), 0)]
R4_DARKS = [(wedge(404, 64, 462, -26, 22, lean=5), 1),
            (saddle_v(380, 116, 404, 64, 13), 0)]
L3_DARKS = [(wedge(66, 44, 122, 112, 20, lean=-5), 1),
            (saddle_v(96, 86, 122, 112, 11), 0)]
R3_DARKS = [(wedge(386, 54, 452, -24, 19, lean=4), 1),
            (saddle_v(356, 96, 386, 54, 11), 0)]
L2_DARKS = [(wedge(82, 58, 146, 98, 17, lean=-4), 1)]
R2_DARKS = [(wedge(360, 44, 432, -20, 16, lean=3), 1)]
L1_DARKS = [(wedge(96, 66, 170, 78, 14, lean=-3), 1)]
R1_DARKS = [(wedge(334, 34, 406, -18, 13, lean=3), 1)]
L0_DARKS = [(wedge(110, 58, 190, 56, 10, lean=-2), 1)]
R0_DARKS = [(wedge(300, 52, 390, 40, 9, lean=2), 1)]

# ---- authored tone regions: (x0, x1, y0, y1, offset).
#
#  Offsets are relative to the band's FACE entry and are the actual light model:
#    +4/+5  a buttress catching the dawn light   (reaches the warm entries)
#    +2     a buttress turned slightly toward it
#     0     the face
#    -1/-2  a recess / the away-turning flank
#
#  Narrow-and-tall = buttress. Short-and-wide = stratum / ledge.
#  Every number is chosen. Later regions win, so strata override buttresses.

# band 5 (nearest, darkest rock) -- 2 buttresses catch light, rest are recesses
L5_REG = [(-30, -4, -60, 269, 0), (-4, 22, -60, 269, 4), (22, 46, -60, 269, 2),
          (46, 66, -60, 269, -1), (66, 84, -60, 269, -2), (84, 100, -60, 269, -1),
          (-4, 22, 34, 52, 5), (14, 46, 84, 100, 3), (-30, 20, 138, 152, -2),
          (28, 70, 186, 198, -2), (50, 96, 222, 234, -1)]
R5_REG = [(384, 404, -60, 269, -1), (404, 424, -60, 269, 4), (424, 446, -60, 269, 2),
          (446, 468, -60, 269, -1), (468, 512, -60, 269, -2),
          (404, 424, 40, 58, 5), (418, 452, 92, 108, 3), (446, 490, 150, 164, -2),
          (430, 470, 196, 208, -1)]
# band 4
L4_REG = [(-30, 0, -30, 260, 0), (0, 26, -30, 260, 4), (26, 50, -30, 260, 2),
          (50, 74, -30, 260, -1), (74, 100, -30, 260, -2), (100, 124, -30, 260, -1),
          (0, 26, 24, 40, 5), (10, 48, 66, 80, 3), (-30, 24, 112, 124, -2),
          (36, 80, 152, 164, -2)]
R4_REG = [(360, 382, -30, 260, -1), (382, 406, -30, 260, 4), (406, 428, -30, 260, 2),
          (428, 452, -30, 260, -1), (452, 510, -30, 260, -2),
          (382, 406, 32, 48, 5), (400, 438, 84, 98, 3), (428, 472, 136, 148, -2)]
# band 3
L3_REG = [(-30, 4, -6, 218, 0), (4, 30, -6, 218, 4), (30, 54, -6, 218, 2),
          (54, 80, -6, 218, -1), (80, 104, -6, -0 + 218, -2), (104, 150, -6, 218, -1),
          (4, 30, 20, 34, 5), (14, 54, 58, 70, 3), (-30, 28, 100, 112, -2),
          (40, 88, 136, 148, -2)]
R3_REG = [(334, 356, -6, 218, -1), (356, 380, -6, 218, 4), (380, 402, -6, 218, 2),
          (402, 426, -6, 218, -1), (426, 508, -6, 218, -2),
          (356, 380, 26, 40, 5), (374, 412, 68, 80, 3), (402, 448, 116, 128, -2)]
# band 2
L2_REG = [(-30, 8, 18, 186, 0), (8, 34, 18, 186, 4), (34, 58, 18, 186, 2),
          (58, 84, 18, 186, -1), (84, 108, 18, 186, -2), (108, 178, 18, 186, -1),
          (8, 34, 34, 46, 5), (18, 58, 66, 78, 3), (-30, 30, 100, 110, -2),
          (44, 92, 130, 140, -2)]
R2_REG = [(308, 330, 18, 186, -1), (330, 354, 18, 186, 4), (354, 376, 18, 186, 2),
          (376, 400, 18, 186, -1), (400, 494, 18, 186, -2),
          (330, 354, 30, 42, 5), (348, 386, 64, 74, 3), (376, 420, 104, 114, -2)]
# band 1
L1_REG = [(-30, 14, 42, 160, 0), (14, 40, 42, 160, 4), (40, 64, 42, 160, 2),
          (64, 90, 42, 160, -1), (90, 114, 42, 160, -2), (114, 208, 42, 160, -1),
          (14, 40, 48, 58, 5), (24, 64, 72, 82, 3), (50, 100, 96, 106, -2)]
R1_REG = [(280, 302, 42, 160, -1), (302, 326, 42, 160, 4), (326, 348, 42, 160, 2),
          (348, 372, 42, 160, -1), (372, 484, 42, 160, -2),
          (302, 326, 44, 54, 5), (320, 358, 68, 78, 3), (348, 394, 94, 104, -2)]
# band 0 (furthest, palest -- lightest offsets, because fog eats contrast)
L0_REG = [(-30, 20, 20, 146, 0), (20, 46, 20, 146, 3), (46, 70, 20, 146, 1),
          (70, 96, 20, 146, -1), (96, 120, 20, 146, -2), (120, 238, 20, 146, -1),
          (20, 46, 26, 36, 4), (30, 70, 48, 58, 2), (56, 106, 72, 82, -2)]
R0_REG = [(236, 258, 20, 146, -1), (258, 282, 20, 146, 3), (282, 304, 20, 146, 1),
          (304, 328, 20, 146, -1), (328, 500, 20, 146, -2),
          (258, 282, 24, 34, 4), (276, 314, 46, 56, 2), (304, 350, 70, 80, -2)]



def S(*xs):
    """Face slabs: wide vertical bands, each with its own offset from FACE.

    Band 5 is the dominant mass (57% of the frame), so it needs the most spread
    here -- with only 0/-1 the whole cliff collapsed onto two neighbouring
    entries and one colour still covered 32% of the layer."""
    pat = [0, -1, 1, 0, -2, 1]
    return [(xs[i], xs[i + 1], pat[i % len(pat)]) for i in range(len(xs) - 1)]

L5_SL = S(-30, 6, 30, 52, 72, 100)
R5_SL = S(384, 408, 430, 452, 476, 512)
L4_SL = S(-30, 8, 40, 72, 100, 124)
R4_SL = S(360, 388, 414, 440, 466, 510)
L3_SL = S(-30, 16, 52, 88, 120, 150)
R3_SL = S(334, 364, 394, 424, 456, 508)
L2_SL = S(-30, 24, 64, 104, 142, 178)
R2_SL = S(308, 340, 372, 404, 436, 494)
L1_SL = S(-30, 40, 90, 208)
R1_SL = S(280, 326, 372, 484)
L0_SL = S(-30, 46, 96, 238)
R0_SL = S(236, 282, 328, 500)


def build_masses():
    """Back to front. Bases below the frame for near bands; each band's crest
    must clear the band in front, which the checks below verify."""
    S = [
        # band, base, mist, veg, seed, left(crest,summits,saddles,darks), right(...)
        (0, 152, 12, 0.00, 0, L0_CREST, [150], [190], L0_DARKS, L0_REG, L0_SL,
         R0_CREST, [270], [300], R0_DARKS, R0_REG, R0_SL),
        (1, 178, 14, 0.00, 0, L1_CREST, [96], [170], L1_DARKS, L1_REG, L1_SL,
         R1_CREST, [334], [406], R1_DARKS, R1_REG, R1_SL),
        (2, 206, 16, 0.00, 0, L2_CREST, [82], [146], L2_DARKS, L2_REG, L2_SL,
         R2_CREST, [360], [432], R2_DARKS, R2_REG, R2_SL),
        (3, 244, 20, 0.30, 25, L3_CREST, [66], [122], L3_DARKS, L3_REG, L3_SL,
         R3_CREST, [386], [452], R3_DARKS, R3_REG, R3_SL),
        (4, 288, 24, 0.50, 32, L4_CREST, [52], [100], L4_DARKS, L4_REG, L4_SL,
         R4_CREST, [404], [462], R4_DARKS, R4_REG, R4_SL),
        (5, 340, 28, 0.75, 38, L5_CREST, [44], [86], L5_DARKS, L5_REG, L5_SL,
         R5_CREST, [426], [478], R5_DARKS, R5_REG, R5_SL),
    ]
    out = []
    for (band, base, mist, veg, seed, lc, ls, ld, ldk, lreg, lsl,
         rc, rs, rdx, rdk, rreg, rsl) in S:
        out.append(Mass(band, lc, base, ls, ld, ldk, mist_rows=mist,
                        side="left", veg=veg, veg_seed=seed, regions=lreg,
                        slabs=lsl))
        out.append(Mass(band, rc, base, rs, rdx, rdk, mist_rows=mist,
                        side="right", veg=veg, veg_seed=seed + 9, regions=rreg,
                        slabs=rsl))
    return out


# ==================================================================
#  MEASUREMENTS. These are the numbers the last two reviews failed, so they are
#  now gates. A build that trips one prints a FAIL line.
# ==================================================================
def audit(rgb, alpha, masses):
    res = []
    vis = alpha > 0
    nvis = max(1, vis.sum())

    # 1) every band must be visible (r11: bands 0-2 contributed zero)
    depth = np.zeros((H, W), dtype=np.int32)
    for m in masses:
        pass
    # recompute band coverage from colour membership
    band_of = {}
    for bi, ramp in enumerate(BANDS):
        for ci, c in enumerate(ramp):
            band_of.setdefault(tuple(c), bi)
    cov = {b: 0 for b in range(6)}
    for p in rgb[vis]:
        b = band_of.get(tuple(int(v) for v in p))
        if b is not None:
            cov[b] += 1
    for b in range(6):
        pct = 100.0 * cov[b] / nvis
        ok = pct >= 2.0
        res.append((ok, f"band {b} coverage {pct:5.2f}% (need >=2%)"))

    # 2) warm must actually be warm (r11: R-B never crossed zero)
    rb = rgb[vis][:, 0].astype(int) - rgb[vis][:, 2].astype(int)
    warm_pct = 100.0 * (rb >= 8).mean()
    res.append((warm_pct >= 12.0,
                f"warm pixels (R-B>=8) {warm_pct:5.2f}% (need >=12%)"))

    # 3) no single colour may dominate (r11: one tone covered 28.2%)
    uniq, counts = np.unique(rgb[vis].reshape(-1, 3), axis=0, return_counts=True)
    big = 100.0 * counts.max() / nvis
    res.append((big <= 22.0, f"largest flat field {big:5.2f}% (need <=22%)"))

    # 4) no long vertical constant runs (r11: 485 runs >=45 rows, max 178)
    worst = 0
    for x in range(W):
        run, prev = 0, None
        for y in range(H):
            if not vis[y, x]:
                run, prev = 0, None
                continue
            c = tuple(rgb[y, x])
            if c == prev:
                run += 1
            else:
                run, prev = 1, c
            worst = max(worst, run)
    res.append((worst <= 46, f"longest vertical run {worst}px (need <=46)"))

    # 5) no full-width horizontal rules (r11: y=168 had 316 cols change at once)
    worst_row = 0
    for y in range(1, H):
        ch = int((rgb[y] != rgb[y - 1]).any(axis=1).sum())
        worst_row = max(worst_row, ch)
    res.append((worst_row <= 190, f"most simultaneous row changes {worst_row} (need <=190)"))

    # 6) alpha must ramp (r11: 240 fully opaque rows then a 255->52 cliff)
    levels = len(np.unique(alpha))
    res.append((levels >= 7, f"alpha levels {levels} (need >=7)"))
    mid = alpha[(alpha > 0) & (alpha < 255)]
    res.append((mid.size > 2000, f"partially transparent px {mid.size} (need >2000)"))

    # 7) palette discipline
    allowed = {tuple(c) for b in BANDS for c in b} | {tuple(c) for c in VEG_NEAR} \
        | {tuple(c) for c in VEG_FAR}
    stray = sum(1 for p in rgb[vis] if tuple(int(v) for v in p) not in allowed)
    res.append((stray == 0, f"stray colours {stray} (need 0)"))
    return res


def compose(tag):
    rgb = np.zeros((H, W, 3), dtype=np.uint8)
    rgb[:, :] = PAPER
    alpha = np.zeros((H, W), dtype=np.uint8)

    masses = build_masses()
    for m in masses:
        m.draw(rgb, alpha, np.zeros((H, W), np.uint8), 0)
        if m.veg > 0:
            m.draw_veg(rgb, alpha, np.zeros((H, W), np.uint8), 0,
                       budget=2 if m.band >= 4 else 1)

    os.makedirs("out", exist_ok=True)
    img = Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")
    img.save(f"out/layer_{tag}.png")
    flat = Image.new("RGB", (W, H), PAPER)
    flat.paste(img, (0, 0), img)
    flat.save(f"out/layer_{tag}_flat_1x.png")
    flat.resize((W * 2, H * 2), Image.NEAREST).save(f"out/layer_{tag}_flat_2x.png")

    print(f"wrote out/layer_{tag}.png")
    results = audit(rgb, alpha, masses)
    fails = 0
    for ok, msg in results:
        print(f"  [{'PASS' if ok else 'FAIL'}] {msg}")
        fails += 0 if ok else 1
    print(f"  --- {len(results) - fails}/{len(results)} checks pass")
    return fails


if __name__ == "__main__":
    compose(sys.argv[1] if len(sys.argv) > 1 else "r12")
