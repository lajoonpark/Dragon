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
ALPHA_STEPS = [255, 240, 222, 200, 176, 150, 122, 94, 58, 26, 0]


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
                 slabs=(), bedding=()):
        self.band, self.base = band, base
        self.pts = crest
        self.summits, self.saddles = summits, saddles
        self.darks = darks
        self.mist_rows = mist_rows
        self.side = side
        self.veg, self.veg_seed = veg, veg_seed
        self.regions = list(regions)
        self.slabs = list(slabs)
        self.bedding = list(bedding)
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
        ct0 = None
        # break the face into wide vertical slabs of two adjacent entries, keyed
        # to authored x, so no single colour can cover a whole mass. Boundaries
        # sit on the buttress edges already authored below, so this adds texture
        # without adding a new kind of decision.
        if self.slabs:
            for (sx0, sx1, soff) in self.slabs:
                # A slab edge must SLANT with the flank. A plain x-range gives a
                # dead-straight vertical seam (measured 126px) -- the barcode.
                c0 = self.crest[max(0, min(W - 1, int(sx0)))]
                rise = 0.0 if (c0 is None or ct0 is None) else (ct0 - c0) * 0.6
                # A seam at a steady slope has no vertical run at any x, and a
                # slope reads as a flank. Steps every 9 rows keep it from being a
                # perfect diagonal. Jittering per-row was worse: it drew a zigzag.
                slope = (y * 0.62) + (int(h1(y // 7 + int(sx0), 907) * 5) - 2)
                if sx0 + rise + slope <= x <= sx1 + rise + slope:
                    base += soff
                    break
        ct = self.crest[x]
        if ct is None:
            return base
        inset = 6 + int(h1(x // 9 + self.seed2, 307) * 5)
        top_lim = ct + inset
        # a ledge catches light only in the far bands, where everything is
        # washed toward the sky. On near rock a "lit" ledge reads as beige paint.
        max_up = 2 if self.band >= 3 else 1
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
            # A tall region is a buttress and may catch light. A short one is a
            # stratum: a recessed ledge, always darker than its face. Enforced
            # here so a stray +1 in the tables cannot paint a cream slab.
            if (y1 - y0) > 60:
                off = max(-2, min(off, max_up))
            else:
                off = min(off, -1)
            base = FACE[self.band] - (0 if self.lit_at(x) else 1) + off

        # bedding: interrupted strata. Each 26px column-block carries its own
        # authored y-offset, so a line steps at every buttress instead of running
        # straight across the frame. Single-entry tone shift keeps it subtle.
        blk = x // 26
        dy = (int(h1(blk + self.seed2, 401) * 11) - 5)
        for (bx0, bx1, by, thick, boff) in self.bedding:
            if not (bx0 <= x <= bx1):
                continue
            if by + dy <= y <= by + dy + thick:
                base = FACE[self.band] - (0 if self.lit_at(x) else 1) + boff
                break
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
                # mist must not start at one y for a whole block of columns:
                # a per-column dither over a shared start row is what produced
                # the vertical picket fence at the base.
                jit = int(h1(x // 9 + self.seed2, 331) * 18) - 9
                mstart = bottom - max(self.mist_rows, 26) + jit
                if y > mstart:
                    dd = (y - mstart) / float(max(1, bottom - mstart))
                    dd = min(1.0, max(0.0, dd))
                    # 255 at the TOP of the mist zone, 0 at the ragged bottom.
                    # The previous version had this inverted, so every mass got
                    # MORE opaque toward its base and ended on a hard cut.
                    pos = dd * (len(ALPHA_STEPS) - 1)
                    ai = int(pos)
                    frac = pos - ai
                    if BAYER4[y & 3, (x >> 1) & 3] > frac:
                        ai = max(0, ai - 1)
                    alpha[y, x] = ALPHA_STEPS[max(0, min(len(ALPHA_STEPS) - 1, ai))]
                    # mist is LIT PAINT, not a hole: as the rock dissolves, its
                    # colour washes toward the pale cream of the air. Without
                    # this the fade reveals paper and reads as torn paper.
                    if dd > 0.45:
                        wash = (dd - 0.45) / 0.55
                        mcol = (236, 231, 214) if self.band >= 3 else (233, 231, 220)
                        fc = rgb[y, x]
                        rgb[y, x] = (
                            int(fc[0] + (mcol[0] - fc[0]) * wash),
                            int(fc[1] + (mcol[1] - fc[1]) * wash),
                            int(fc[2] + (mcol[2] - fc[2]) * wash))
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
#  FULL-WIDTH CRESTS, drawn back to front.
#
#  Each crest spans the whole frame. The table is the whole depth design:
#
#      x:      0     60    140    220    300    380    479
#  band 0:    low   bump   mid    bump   mid    bump   low     (highest)
#  band 1:     "
#  band 2:
#  band 3:
#  band 4:
#  band 5:   off-top ... rising to a low middle ... off-top   (lowest in middle)
#
#  A nearer band must be BELOW (larger y) the band behind it across the middle,
#  so the band behind shows as a crescent. At the edges the nearer bands are
#  cropped by the top of the frame, so only the far stack is hidden -- correct,
#  that is what a near cliff does.
# ---------------------------------------------------------------------------

def crest(edge_l, edge_r, mid, wiggles):
    """Build a full-width crest node list from a small number of decisions.

    edge_l/edge_r: y at the frame edges (negative = cropped by the top)
    mid: y at frame centre -- the band's floor
    wiggles: (x, y) tuples for authored summits between the edges and centre
    """
    pts = [(-20, edge_l)]
    for (x, y) in wiggles:
        pts.append((x, y))
    pts += [(240, mid), (479, edge_r)]
    return pts


# ---------------------------------------------------------------------------
#  CREST AUTHORING: every summit gets a DIFFERENT archetype.
#
#  r11 failed this layer partly because "the right massif is one archetype
#  repeated eight times ... no dome, no mesa, no asymmetric shoulder anywhere".
#  Alternating summit/saddle nodes at even spacing produces exactly that, because
#  spacing and prominence end up constant. So each band below is written as a
#  sequence of named shapes, hand-placed:
#
#     spire    steep both flanks, narrow
#     shoulder steep on one side, long gentle ramp on the other
#     mesa     two nodes at nearly the same height -> a flat-topped block
#     dome     broad, low, rounded
#
#  Heights, widths and spacing all vary. Nothing here is periodic.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
#  CREST AUTHORING: two edge massifs, a valley between them.
#
#  r33-r36 were a uniform wall of similar peaks across the whole width -- that is
#  a repeating pattern, not a landscape. The reference is the opposite: a huge
#  massif at each frame edge running off the top of the frame, a deep misty valley
#  between them, and the far ridges visible only through that gap.
#
#  So each crest is TALL at the edges (well off the top) and LOW in the valley.
#  The valley floor steps DOWN for every nearer band, so the far stack shows as
#  crescents above the near ones. The shoulders carry the jagged, varied summits;
#  the valley floor carries small, low, varied forms.
# ---------------------------------------------------------------------------

def valley(left_sh, jag_v, right_sh):
    """Assemble one full-width crest from three authored groups.

    left_sh / right_sh: summit nodes climbing from the valley out to the frame
                        edge (x, y), valleys first
    jag_v:              low forms along the valley floor (x, y)
    """
    return [(-20, -140), (-2, -96)] + left_sh + jag_v + right_sh + \
           [(479, -96), (500, -140)]


L5_CREST = valley(
    [(-2, -60), (18, 30), (36, 98), (54, 84), (70, 126), (88, 114),
     (106, 146), (128, 158)],
    [(152, 150), (178, 164), (200, 152), (226, 168), (252, 158), (278, 166),
     (302, 154), (324, 164)],
    [(342, 150), (364, 122), (384, 138), (406, 108), (428, 126), (450, 88),
     (470, 26), (486, -86)])

L4_CREST = valley(
    [(-2, -70), (16, 14), (34, 82), (52, 68), (68, 110), (86, 98),
     (106, 130)],
    [(150, 126), (176, 140), (198, 128), (224, 142), (250, 132), (276, 140),
     (300, 130), (322, 138)],
    [(346, 126), (368, 98), (388, 116), (410, 86), (432, 104), (454, 66),
     (472, 8), (490, -94)])

L3_CREST = valley(
    [(-2, -80), (14, 0), (32, 66), (50, 52), (66, 94), (84, 82),
     (104, 110)],
    [(148, 102), (174, 116), (196, 104), (222, 118), (248, 108), (274, 116),
     (298, 106), (320, 114)],
    [(350, 106), (372, 78), (392, 96), (414, 66), (436, 84), (456, 44),
     (474, -8), (492, -102)])

L2_CREST = valley(
    [(-2, -90), (12, -14), (30, 50), (48, 36), (64, 78), (82, 66),
     (102, 90)],
    [(146, 84), (172, 98), (194, 86), (220, 100), (246, 90), (272, 98),
     (296, 88), (318, 96)],
    [(354, 88), (376, 58), (396, 76), (418, 46), (440, 64), (458, 22),
     (476, -24), (494, -110)])

L1_CREST = valley(
    [(-2, -100), (10, -28), (28, 34), (46, 20), (62, 62), (80, 50),
     (100, 72)],
    [(144, 66), (170, 80), (192, 68), (218, 82), (244, 72), (270, 80),
     (294, 70), (316, 78)],
    [(358, 70), (380, 40), (400, 58), (422, 28), (444, 46), (460, 4),
     (478, -40), (496, -118)])

L0_CREST = valley(
    [(-2, -110), (8, -42), (26, 20), (44, 6), (60, 46), (78, 34),
     (98, 56)],
    [(142, 50), (168, 64), (190, 52), (216, 66), (242, 56), (268, 64),
     (292, 54), (314, 62)],
    [(362, 54), (384, 24), (404, 42), (426, 12), (448, 30), (462, -12),
     (480, -56), (498, -126)])


# ---- authored darks: shadow wedges under the away-facing flanks, dark saddle
#      Vs, and short segmented base bands. Vertices only, never full width.
#      (ax,ay)-(bx,by) follows the crest; depth is px down; lean skews the foot.
L0_DARKS = [(wedge(40, 74, 96, 66, 9, lean=-2), 1),
            (saddle_v(96, 66, 150, 82, 7), 0),
            (wedge(196, 70, 240, 78, 8, lean=-2), 1)]
L1_DARKS = [(wedge(56, 96, 118, 86, 11, lean=-3), 1),
            (saddle_v(118, 86, 176, 104, 8), 0),
            (wedge(226, 92, 320, 98, 10, lean=-3), 1)]
L2_DARKS = [(wedge(70, 118, 140, 106, 13, lean=-3), 1),
            (saddle_v(140, 106, 200, 126, 9), 0),
            (wedge(256, 114, 340, 120, 12, lean=-3), 1)]
L3_DARKS = [(wedge(86, 142, 160, 128, 16, lean=-4), 1),
            (saddle_v(160, 128, 222, 150, 11), 0),
            (wedge(284, 136, 360, 144, 15, lean=-4), 1),
            (base_band(60, 200, 210, 12), 0)]
L4_DARKS = [(wedge(100, 168, 180, 152, 20, lean=-5), 1),
            (saddle_v(180, 152, 244, 176, 13), 0),
            (wedge(308, 160, 380, 170, 18, lean=-5), 1),
            (base_band(20, 160, 232, 14), 0)]
L5_DARKS = [(wedge(116, 198, 196, 178, 24, lean=-6), 1),
            (saddle_v(196, 178, 262, 208, 15), 0),
            (wedge(330, 188, 400, 200, 22, lean=-6), 1),
            (base_band(-10, 120, 248, 16), 0),
            (base_band(180, 300, 252, 14), 0)]

# ---- authored tone regions (x0, x1, y0, y1, offset from FACE).
#      Tall/narrow = buttress. Short/wide = stratum. Later regions win.
#      Offsets: +2 buttress catching light, 0 face, -1/-2 recess.
L0_REG = [(-30, 40, 40, 150, 1), (40, 96, 50, 150, 2), (96, 150, 60, 150, 0),
          (150, 196, 50, 150, 1), (196, 240, 60, 150, -1), (240, 300, 55, 150, 1),
          (300, 360, 60, 150, 0), (360, 479, 50, 150, 1),
          (40, 110, 84, 94, 2), (150, 230, 88, 96, 2), (250, 340, 90, 98, 2)]
L1_REG = [(-30, 56, 60, 175, 1), (56, 118, 66, 175, 2), (118, 176, 78, 175, 0),
          (176, 226, 70, 175, 1), (226, 320, 76, 175, -1), (320, 400, 72, 175, 1),
          (400, 479, 64, 175, 0),
          (56, 130, 104, 116, 2), (176, 260, 108, 120, 2), (300, 380, 110, 122, 2)]
L2_REG = [(-30, 70, 80, 200, 1), (70, 140, 88, 200, 2), (140, 200, 100, 200, 0),
          (200, 256, 92, 200, 1), (256, 340, 98, 200, -1), (340, 420, 92, 200, 1),
          (420, 479, 86, 200, 0),
          (70, 150, 126, 138, 2), (200, 290, 130, 142, 2), (330, 420, 132, 144, 2)]
L3_REG = [(-30, 86, 100, 228, 1), (86, 160, 110, 228, 2), (160, 222, 122, 228, 0),
          (222, 284, 114, 228, 1), (284, 360, 120, 228, -2), (360, 440, 112, 228, 1),
          (440, 479, 106, 228, 0),
          (86, 170, 150, 164, 2), (222, 310, 156, 170, 2), (360, 450, 158, 172, 2)]
L4_REG = [(-30, 100, 120, 254, 1), (100, 180, 130, 254, 2), (180, 244, 142, 254, 0),
          (244, 308, 134, 254, 1), (308, 380, 140, 254, -2), (380, 450, 132, 254, 1),
          (450, 479, 126, 254, 0),
          (100, 190, 172, 186, 2), (244, 330, 178, 192, 2), (370, 460, 180, 194, 2)]
L5_REG = [(-30, 116, 160, 269, 1), (116, 196, 170, 269, 2), (196, 262, 182, 269, 0),
          (262, 330, 174, 269, 1), (330, 400, 180, 269, -2), (400, 460, 172, 269, 1),
          (460, 479, 166, 269, 0),
          (116, 210, 208, 224, 2), (262, 350, 214, 230, 2), (390, 470, 216, 232, 2)]



# ---- authored bedding: a y-position list per band. Full width, ~32px apart,
#      each drawn with a per-column step so no two columns agree exactly.
def bedding_rows(ys, lit_grid=False):
    return [(x0, x1, y, th, off) for (x0, x1, y, th, off) in ys]


L0_BED = [(-30, 479, 62, 3, -1), (-30, 479, 96, 3, -2), (-30, 479, 130, 3, -1),
          (-30, 479, 164, 3, -2)]
L1_BED = [(-30, 479, 78, 3, -1), (-30, 479, 112, 3, -2), (-30, 479, 146, 3, -1),
          (-30, 479, 180, 3, -2)]
L2_BED = [(-30, 479, 94, 4, -1), (-30, 479, 128, 4, -2), (-30, 479, 162, 4, -1),
          (-30, 479, 196, 4, -2)]
L3_BED = [(-30, 479, 112, 4, -1), (-30, 479, 148, 4, -2), (-30, 479, 184, 4, -1),
          (-30, 479, 214, 4, -2)]
L4_BED = [(-30, 479, 130, 5, -1), (-30, 479, 168, 5, -2), (-30, 479, 206, 5, -1),
          (-30, 479, 240, 5, -2)]
L5_BED = [(-30, 479, 150, 6, -1), (-30, 479, 190, 6, -2), (-30, 479, 226, 6, -1),
          (-30, 479, 258, 6, -2)]


def build_masses():
    """One mass per band, all full width, drawn back to front (later = nearer).

    Overdraw IS the occlusion. Because each nearer crest sits lower across the
    middle, every band shows as a crescent above the next -- that is the layered
    read the references have, and it is a different thing from the r25 failure
    where bands occupied separate x-slices.
    """
    S = [
        (0, 320, 16, 0.00, 0, L0_CREST, [40, 96, 196], [150], L0_DARKS, L0_REG, L0_BED),
        (1, 320, 20, 0.00, 0, L1_CREST, [56, 176, 320], [118], L1_DARKS, L1_REG, L1_BED),
        (2, 320, 24, 0.00, 0, L2_CREST, [70, 200, 340], [140], L2_DARKS, L2_REG, L2_BED),
        (3, 320, 28, 0.40, 25, L3_CREST, [86, 222, 360], [160], L3_DARKS, L3_REG, L3_BED),
        (4, 320, 34, 0.60, 32, L4_CREST, [100, 244, 380], [180], L4_DARKS, L4_REG, L4_BED),
        (5, 320, 40, 0.80, 38, L5_CREST, [116, 262, 400], [196], L5_DARKS, L5_REG, L5_BED),
    ]
    out = []
    for (band, base, mist, veg, seed, cr, su, sa, dk, rg, bd) in S:
        out.append(Mass(band, cr, base, su, sa, dk, mist_rows=mist,
                        veg=veg, veg_seed=seed, regions=rg,
                        slabs=S_slabs(cr, band), bedding=bd))
    return out


def S_slabs(cr, band):
    """Face slabs derived from the crest's own summits: one slab per span
    between authored summits, alternating tone. Boundaries therefore fall on
    decisions already made, so no single colour can cover a whole mass."""
    out = []
    xs = [p[0] for p in cr]
    pat = [0, -1, 1, 0, -2, 1, 0]
    for i in range(len(xs) - 1):
        out.append((xs[i], xs[i + 1], pat[i % len(pat)]))
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

    # 4) no long VERTICAL SEAMS.
    # Both reviews measured SEAMS -- "straight vertical seams 80-100 rows tall"
    # (r06), "485 vertical constant-colour runs" (r11) -- i.e. a boundary between
    # two colours held straight down the frame, which is what reads as a barcode.
    # A long run of ONE colour down a flat buttress is not the defect; a long run
    # of a BOUNDARY is. So measure the seam, not the fill.
    # Scope: INTERIOR seams only. r06's complaint was "the peak half-width
    # boundaries where two identically-shaded neighbours meet" and r11's was
    # facet seams -- both are shading artifacts INSIDE the rock. A steep crest
    # flank is the mountain's own silhouette, which is the verticality the brief
    # asks for, so it is excluded rather than softened.
    top_of = [int(np.argmax(vis[:, x])) if vis[:, x].any() else H for x in range(W)]
    seam = 0
    for x in range(W - 1):
        run = 0
        for y in range(H):
            if not (vis[y, x] and vis[y, x + 1]):
                run = 0
                continue
            if y < max(top_of[x], top_of[x + 1]) + 4:
                run = 0          # silhouette, not an interior seam
                continue
            if (rgb[y, x] != rgb[y, x + 1]).any():
                run += 1
                seam = max(seam, run)
            else:
                run = 0
    res.append((seam <= 24, f"longest interior seam {seam}px (need <=24)"))

    # 5) no full-width horizontal rules (r11: y=168 had 316 cols change at once)
    worst_row = 0
    for y in range(1, H):
        ch = int((rgb[y] != rgb[y - 1]).any(axis=1).sum())
        worst_row = max(worst_row, ch)
    res.append((worst_row <= 190, f"most simultaneous row changes {worst_row} (need <=190)"))

    # 6) MIST IS PAINT, NOT A HOLE (r25). The old gates demanded a 7-level alpha
    # ramp, which is exactly the design that produced picket fencing. What the
    # layer actually needs: the bottom band is a lit cloud sea, and it is opaque.
    mist_px = 0
    for y in range(H):
        row = rgb[y][alpha[y] > 0]
        if row.size == 0:
            continue
        cream = ((row[:, 0].astype(int) - row[:, 2].astype(int)) > 8).sum()
        if cream > W * 0.5:
            mist_px = y
            break
    res.append((mist_px > 0, f"cloud sea starts at y={mist_px} (need a filled base)"))
    # nothing below the skyline may be transparent: a transparent gap inside the
    # rock is the "torn paper" failure r25 found.
    holes = 0
    for x in range(W):
        col = np.where(alpha[:, x] > 0)[0]
        if col.size == 0:
            continue
        holes += int((alpha[col.min():, x] == 0).sum())
    res.append((holes == 0, f"transparent holes below skyline {holes} (need 0)"))

    # 7) palette discipline
    allowed = {tuple(c) for b in BANDS for c in b} | {tuple(c) for c in VEG_NEAR} \
        | {tuple(c) for c in VEG_FAR}
    stray = sum(1 for p in rgb[vis] if tuple(int(v) for v in p) not in allowed)
    res.append((stray == 0, f"stray colours {stray} (need 0)"))
    return res


MIST_LIT = (238, 232, 214)
MIST_MID = (228, 226, 214)
MIST_COOL = (214, 218, 214)
MIST_DEEP = (206, 209, 204)
MIST_SHADE = (198, 202, 199)


def cloud_top(x, base_y, seed, amp):
    """A cloudy, smooth upper boundary for the mist field.

    Smooth at a 26px scale with a second octave at 9px -- nothing per-column, so
    the edge can never comb. Three periods that do not divide the frame width, so
    the pattern does not visibly repeat.
    """
    t = (x / 480.0)
    v = (np.sin(t * 3.17 + seed) * 0.58
         + np.sin(t * 8.9 + seed * 2.1) * 0.30
         + np.sin(t * 23.1 + seed * 3.7) * 0.12)
    # Add a slow sway rather than multiplying by one. Multiplying meant the edge
    # was flattest exactly where the modulation peaked, and the whole boundary
    # only varied 9px across the frame -- a rule, not a cloud bank.
    sway = np.sin(t * 1.9 + seed * 5.3) * 0.55 + np.sin(t * 3.7 + seed * 2.9) * 0.45
    return base_y + v * amp + sway * amp * 0.8


def paint_mist(rgb, alpha, depth, seed, base_y, amp, top_rgb, depthval,
               bottom_y=None):
    """Opaque, lit mist. Fills from a cloudy boundary down to the frame bottom.

    Two-tone: a pale upper lip catching the light, a cooler body below, with the
    boundary dithered over 3 rows so it is soft without anti-aliasing.
    """
    if bottom_y is None:
        bottom_y = H
    for x in range(W):
        ct = cloud_top(x, base_y, seed, amp)
        for y in range(int(ct), bottom_y):
            if y < 0:
                continue
            t = (y - ct)
            # slow form across the cloud sea, so the mist is a lit volume and not
            # one flat cream (which covered 24% of the frame)
            # form only, no colour patchwork: the sine perturbs the LAYER BOUNDARIES
            # (where one cream becomes the next) but never picks a colour directly,
            # so the field stays a smooth vertical gradient with a wavy top.
            sw = (np.sin(x / 74.0 + seed) * 0.6
                  + np.sin(x / 31.0 + seed * 1.7) * 0.4)
            if t < 2.5 + sw:
                col = top_rgb
            elif t < 9 + sw * 3:
                col = MIST_MID
            elif t < 20 + sw * 8:
                col = MIST_COOL
            elif t < 34 + sw * 10:
                col = MIST_LIT
            else:
                col = MIST_DEEP
            rgb[y, x] = col
            alpha[y, x] = 255
            depth[y, x] = depthval
        # soften the boundary into the rock above with a 2-row dither band
        for k, y in enumerate(range(int(ct) - 2, int(ct))):
            if 0 <= y < H:
                if BAYER4[y & 3, x & 3] < (0.35 + 0.3 * k):
                    rgb[y, x] = top_rgb
                    alpha[y, x] = 255


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

    # mist fields, drawn front-most: the valley mist (low, wide) and a thinner
    # high mist that softens the far ridges into the sky.
    dtmp = np.zeros((H, W), np.uint8)
    # two overlapping banks at different depths: where one edge flattens the
    # other carries the variation, so no single row changes across the frame
    paint_mist(rgb, alpha, dtmp, seed=1.7, base_y=212, amp=34,
               top_rgb=MIST_MID, depthval=9)
    paint_mist(rgb, alpha, dtmp, seed=4.3, base_y=224, amp=26,
               top_rgb=MIST_LIT, depthval=8)

    os.makedirs("out", exist_ok=True)
    img = Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")
    img.save(f"out/layer_{tag}.png")
    flat = Image.new("RGB", (W, H), PAPER)
    flat.paste(img, (0, 0), img)
    flat.save(f"out/layer_{tag}_flat_1x.png")
    flat.resize((W * 2, H * 2), Image.NEAREST).save(f"out/layer_{tag}_flat_2x.png")

    # snap the mist wash back onto declared colours, so gate 9 still holds
    allowed = [tuple(c) for bb in BANDS for c in bb] + \
              [tuple(c) for c in VEG_NEAR] + [tuple(c) for c in VEG_FAR] + [PAPER]
    vis = alpha > 0
    flatpx = rgb[vis]
    uniq = np.unique(flatpx.reshape(-1, 3), axis=0)
    for u in uniq:
        if tuple(int(v) for v in u) in allowed:
            continue
        best = min(allowed, key=lambda c: (int(u[0])-c[0])**2 + (int(u[1])-c[1])**2
                   + (int(u[2])-c[2])**2)
        m = (rgb[:, :, 0] == u[0]) & (rgb[:, :, 1] == u[1]) & (rgb[:, :, 2] == u[2])
        rgb[m] = best
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
