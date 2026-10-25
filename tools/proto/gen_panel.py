"""Dragon — base panel generator (panel 01, "gorge").

v7 failed by making two huge flat cliffs -> grey slabs. A wide surface needs
detail, and a painted landscape never actually shows you a wide flat rock face:
it shows you MANY RECEDING PLANES, each cropping the one behind it.

That is also exactly what the reference image does: spires layered at different
depths, each paler than the one in front, bases eaten by mist. That is the
structure we copy. The composition we do NOT copy, because the reference is
portrait and this is 16:9:

  - The tallest peaks are CROPPED BY THE TOP OF FRAME, so the range exceeds the
    frame vertically instead of politely fitting inside it with sky above.
  - Slightly right of centre there is a V-notch: the gorge mouth, a deep pale
    void. That's the dragon corridor, and it's the composition the reference
    has no room for.
  - A waterfall falls from a shelf high in the notch -- vertical event in a
    horizontal frame, and permanent gentle motion.
  - One warm accent (blossom, bottom-left) against an entirely cool image.

Depth bands: 0.06 far / 0.15 mist / 0.26 mid / 0.34 mist / 0.48 near-mid /
0.60 near / 0.78 water / 0.92 foreground.

Authoring rules (docs/25-art-pipeline.md): silhouettes are numbers a human
chose; value planes are flat; dither is a transition, never a fill.

Run: python3 tools/proto/gen_bg.py
"""

import os
import numpy as np
from PIL import Image

W, H = 480, 270

PAL = {
    ".": (239, 234, 220),
    "1": (232, 229, 219),
    "2": (223, 223, 217),
    "3": (213, 216, 214),
    "4": (203, 208, 210),

    "5": (190, 199, 205),
    "6": (178, 189, 197),
    "7": (166, 179, 189),
    "8": (154, 169, 181),

    "a": (162, 177, 190),
    "b": (149, 166, 181),
    "c": (136, 155, 172),
    "d": (123, 144, 163),

    "e": (134, 153, 170),
    "f": (120, 140, 159),
    "g": (106, 127, 147),
    "h": (92, 114, 135),

    "i": (88, 107, 126),
    "j": (73, 91, 110),
    "k": (58, 75, 93),
    "l": (45, 60, 76),
    "m": (34, 47, 61),

    "-": (26, 34, 44),
    "=": (17, 23, 31),
    "#": (9, 13, 19),

    "p": (223, 191, 193),
    "P": (199, 159, 164),
}

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                   [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) / 16.0


class Canvas:
    def __init__(self):
        self.rgb = np.zeros((H, W, 3), dtype=np.uint8)
        self.rgb[:, :] = PAL["."]
        self.depth = np.zeros((H, W), dtype=np.uint8)
        self.own = np.full((H, W), -1, dtype=np.int16)

    def px(self, x, y, c, d=None, o=None):
        if 0 <= x < W and 0 <= y < H:
            self.rgb[y, x] = c
            if d is not None:
                self.depth[y, x] = d
            if o is not None:
                self.own[y, x] = o

    def b(self, x, y):
        return BAYER4[y & 3, x & 3]

    def dith(self, x, y, c, a):
        if not (0 <= x < W and 0 <= y < H):
            return
        if a >= 0.78:
            self.rgb[y, x] = c
        elif a > 0.12 and self.b(x, y) < a:
            self.rgb[y, x] = c


def h1(i, s):
    n = (int(i) * 374761393 + int(s) * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def vn(x, s):
    i = int(np.floor(x))
    f = x - i
    f = f * f * (3 - 2 * f)
    return h1(i, s) * (1 - f) + h1(i + 1, s) * f


# ==================================================================
#  RIDGE: a hand-authored left and right edge, row by row.
#  (left_x, right_x, plane_cuts) per row band. Numbers chosen, not derived.
# ==================================================================

class Ridge:
    """A cliff silhouette from authored CONTROL POINTS + authored EVENTS.

    Why not per-row numbers: authoring 200 rows by hand produced 8-12px
    staircase steps, which reads as Minecraft. Why not a formula: v1 proved a
    formula gives candles.

    The middle ground is what an artist actually does -- place a handful of
    control points for the overall gesture, then add deliberate features:
      * control points (row, x):  the gesture, interpolated 1px per row
      * buttresses (row, depth):  a ledge that juts out and returns
      * notches (row, depth):     a slice cut inward
      * jag:                      1-2px irregularity, so no edge is ruler-straight
    """

    def __init__(self, ctrl, cuts, keys, jag=1, seed=0, buttresses=(),
                 notches=()):
        self.cuts = cuts
        self.keys = keys
        r0, r1 = ctrl[0][0], ctrl[-1][0]
        self.rows = []
        for r in range(r0, r1 + 1):
            # piecewise-linear interpolation through the control points
            for i in range(len(ctrl) - 1):
                (ra, xa), (rb, xb) = ctrl[i], ctrl[i + 1]
                if ra <= r <= rb:
                    t = 0.0 if rb == ra else (r - ra) / float(rb - ra)
                    x = xa + (xb - xa) * t
                    break
            else:
                x = ctrl[-1][1]
            # authored events
            for (br, bd, bw) in buttresses:
                d = r - br
                if 0 <= d < bw:
                    x += bd * (1.0 - abs(d - bw / 2.0) / (bw / 2.0 + 1e-6))
            for (nr, nd, nw) in notches:
                d = r - nr
                if 0 <= d < nw:
                    x -= nd * (1.0 - abs(d - nw / 2.0) / (nw / 2.0 + 1e-6))
            # Angular jag: hold an offset for a run of rows, then jump.
            # Continuous noise reads as a caterpillar; held runs read as rock.
            if jag:
                RUN = 5
                block = r // RUN
                step = (h1(block, seed + 17) - 0.5) * 2.0 * jag
                x += step
                # one 1px kick mid-block so long runs don't look machined
                if (r % RUN) == 2 and h1(block, seed + 29) > 0.6:
                    x += 1 if h1(block, seed + 31) > 0.5 else -1
            self.rows.append((r, int(round(x))))

    def draw(self, c, depth, own, left_edge=None, right_edge=None):
        for (r, edge) in self.rows:
            y = r
            if not (0 <= y < H):
                continue
            l = left_edge if left_edge is not None else edge
            rr = right_edge if right_edge is not None else edge
            l, rr = min(l, rr), max(l, rr)
            if left_edge is not None and right_edge is None:
                l, rr = left_edge, edge
            if right_edge is not None and left_edge is None:
                l, rr = edge, right_edge
            span = max(1, rr - l)
            for x in range(max(0, l), min(W, rr + 1)):
                u = (x - l) / float(span)
                k = len(self.keys) - 1
                for j, cut in enumerate(self.cuts):
                    if u < cut:
                        k = j
                        break
                col = PAL[self.keys[min(k, len(self.keys) - 1)]]
                for cut in self.cuts[:-1]:
                    if abs(u - cut) < 1.4 / (span + 2.0):
                        col = PAL[self.keys[max(0, k - 1)]]
                c.px(x, y, col, depth, own)
            if 0 <= min(W - 1, rr) < W:
                c.px(min(W - 1, rr), y, PAL[self.keys[-1]], depth, own)


# ---- LEFT massif: cropped by the left edge and the top of frame. Its right
# edge descends toward the notch with two buttresses and one deep notch.
LEFT = Ridge(
    ctrl=[(0, 118), (30, 138), (60, 130), (90, 148), (120, 140),
          (150, 160), (180, 152), (210, 168), (240, 162), (270, 176)],
    cuts=[0.26, 0.52, 0.76, 1.01],
    keys=["m", "l", "j", "i"],
    jag=2.2, seed=3,
    buttresses=[(52, 9, 9), (128, 11, 11), (196, 8, 8)],
    notches=[(96, 12, 7), (168, 9, 6)],
)

# ---- RIGHT massif: lower, further back, its left edge stepping into the notch.
RIGHT = Ridge(
    ctrl=[(0, 396), (30, 384), (60, 390), (90, 372), (120, 378),
          (150, 362), (180, 368), (210, 350), (240, 356), (270, 344)],
    cuts=[0.16, 0.44, 0.72, 1.01],
    keys=["i", "h", "g", "f"],
    jag=2.2, seed=5,
    buttresses=[(44, -9, 10), (120, -11, 12), (188, -8, 9)],
    notches=[(80, 9, 7), (156, 7, 6)],
)

# ---- the two massifs are drawn edge-to-edge: LEFT fills leftwards from its
# right edge, RIGHT fills rightwards from its left edge.

# ---- mid-distance spires standing in the notch mouth, palest = furthest
def spire(rows, x_centre, half_w0, half_w1, cuts, keys, seed=0, jag=1.4):
    """A narrow karst spire: authored half-widths, 1-2px jag, flat planes."""
    out = []
    for r in range(rows):
        t = r / float(rows - 1)
        hw = half_w0 + (half_w1 - half_w0) * (t ** 1.35)
        hw += (vn(r * 0.9 + seed, seed) - 0.5) * 2.0 * jag
        out.append((r, int(round(x_centre - hw)), int(round(x_centre + hw))))
    return out


MID_SPIRES = [
    # (x_centre, top_row, half_w0, half_w1, cuts, keys)
    (178, 60, 3.0, 22.0, [0.40, 1.01], ["d", "c"]),
    (206, 34, 2.0, 26.0, [0.46, 1.01], ["c", "b"]),
    (238, 74, 3.5, 20.0, [0.42, 1.01], ["b", "a"]),
    (268, 96, 4.0, 18.0, [0.50, 1.01], ["a", "8"]),
    (150, 108, 4.5, 16.0, [0.38, 1.01], ["c", "b"]),
]

FAR_SPIRES = [
    (166, 76, 4.0, 26.0, [0.45, 1.01], ["7", "6"]),
    (222, 88, 3.0, 22.0, [0.40, 1.01], ["6", "5"]),
    (292, 100, 5.0, 24.0, [0.48, 1.01], ["7", "6"]),
    (128, 118, 5.0, 20.0, [0.42, 1.01], ["6", "5"]),
]


def mist_band(c, y0, y1, key, density=0.5, seed=1, wisp=0.7, soft=1.4):
    """Mist pools in valleys. Its ceiling must be patchy -- a mist band with a
    flat top edge reads as a scan bar, not as weather."""
    col = PAL[key]
    for x in range(W):
        # per-column band offset, so the top edge undulates
        off = int((vn(x * 0.020 + 3.0, seed + 55) - 0.5) * 16)
        top = y0 + off
        bot = y1 + off // 2
        for y in range(max(0, top), min(H, bot)):
            mid = (top + bot) * 0.5
            halfp = max(1.0, (bot - top) * 0.5)
            prof = max(0.0, 1.0 - abs(y - mid) / halfp) ** soft
            n = vn(x * 0.030 + y * 0.10, seed)
            n2 = vn(x * 0.0072 + 51.0, seed + 7)
            a = prof * density * (n * wisp + n2 * 0.95)
            c.dith(x, y, col, min(1.0, a))


def draw_sky(c):
    for y in range(H):
        f = min(1.0, y / 130.0) * 3.0
        i = min(int(f), 2)
        frac = f - i
        keys = ["1", "2", "3", "4"]
        for x in range(W):
            nz = vn(x * 0.075 + y * 0.42, 11)
            a = frac * 0.38 + (nz - 0.5) * 0.11
            c.px(x, y, PAL[keys[i + 1]] if c.b(x, y) < a else PAL[keys[i]])
        c.depth[y, :] = 2


def draw_water(c, wy, seed=5):
    h = H - wy
    for y in range(wy, H):
        src = max(0, wy - (y - wy + 1))
        if src >= wy:
            src = wy - 1
        wob = int(round((vn(y * 0.5, seed) - 0.5) * 5))
        for x in range(W):
            sx = min(W - 1, max(0, x + wob))
            r, g, b = c.rgb[src, sx]
            a = 0.55
            c.rgb[y, x] = (int(r * (1 - a) + 197 * a),
                           int(g * (1 - a) + 207 * a),
                           int(b * (1 - a) + 215 * a))
            c.depth[y, x] = 7
    for k in range(14):
        yy = wy + int((k + 1) * h / 15.0) + int(vn(k * 3.1, seed) * 3)
        if yy >= H:
            continue
        xx = int(vn(k * 7.7, seed + 2) * W)
        for rep in range(3):
            ln = 2 + int(vn((xx + rep) * 0.31, seed) * 9)
            for i in range(ln):
                c.px((xx + i) % W, yy, PAL["g" if k % 3 else "f"], 7)


def draw_waterfall(c, x, y0, y1, depth):
    for y in range(y0, y1):
        t = (y - y0) / float(max(1, y1 - y0))
        for dx in (-1, 0, 1):
            key = "2" if dx == 0 else "3"
            if c.b(x + dx, y) < 0.5 + t * 0.5:
                c.px(x + dx, y, PAL[key], depth)
    for y in range(y1 - 2, min(H, y1 + 5)):
        r = 2 + (y - (y1 - 2))
        for dx in range(-r, r + 1):
            a = 0.75 - abs(dx) / float(r + 1)
            c.dith(x + dx, y, PAL["1"], a)


PINE = [
    "......#......",
    "......#......",
    ".....###.....",
    "....#####....",
    ".....###.....",
    "...#######...",
    "....#####....",
    "...#######...",
    "..#########..",
    "...#######...",
    "..#########..",
    ".###########.",
    "..#########..",
    "#############",
]

BAMBOO_STEM = ["##", "##", ".#", "##", "##", ".#"]


def stamp(c, rows, ox, oy, key, depth, own):
    for ry, row in enumerate(rows):
        for rx, ch in enumerate(row):
            if ch != ".":
                c.px(ox + rx, oy + ry, PAL[key], depth, own)


FOREGROUND = [
    "........................",
    ".............###........",
    "...........#######......",
    ".........##########.....",
    "........############....",
    "......##############....",
    ".....################...",
    "....#################...",
    "...##################...",
    "...###################..",
    "..####################..",
    "..#####################.",
    ".######################.",
    ".######################.",
    "#######################.",
    "#######################.",
]


def draw_pavilion(c, x, y, depth):
    ink, dark, mid = PAL["-"], PAL["="], PAL["e"]
    for i in range(17):
        c.px(x - 8 + i, y + 5, dark, depth)
        c.px(x - 8 + i, y + 6, mid, depth)
    for j in range(1, 6):
        c.px(x - 6, y + j, dark, depth)
        c.px(x + 6, y + j, dark, depth)
        c.px(x - 3, y + j, mid, depth)
        c.px(x + 2, y + j, mid, depth)
    for i, dy in ((-11, 3), (-10, 2), (-9, 1), (-8, 1), (-7, 0), (-6, 0)):
        c.px(x + i, y + dy, ink, depth)
    for i in range(-6, 7):
        c.px(x + i, y, ink, depth)
    for i, dy in ((6, 0), (7, 0), (8, 1), (9, 1), (10, 2), (11, 3)):
        c.px(x + i, y + dy, ink, depth)
    for i in range(-4, 5):
        c.px(x + i, y - 3, ink, depth)
    for i in range(-2, 3):
        c.px(x + i, y - 4, ink, depth)
    c.px(x, y - 5, ink, depth)


def compose():
    c = Canvas()
    draw_sky(c)

    # ---------- far band: pale spires only, no massif yet
    for (xc, tr, w0, w1, cuts, keys) in FAR_SPIRES:
        for (r, l, rr) in spire(270 - tr, xc, w0, w1, cuts, keys, seed=tr):
            y = tr + r
            if not (0 <= y < H):
                continue
            span = max(1, rr - l)
            for x in range(max(0, l), min(W, rr + 1)):
                u = (x - l) / float(span)
                k = 0 if u < cuts[0] else 1
                c.px(x, y, PAL[keys[k]], 3, 1)
    mist_band(c, 150, 196, "2", density=0.66, seed=41, wisp=0.8, soft=1.3)

    # ---------- mid spires in the notch
    for (xc, tr, w0, w1, cuts, keys) in MID_SPIRES:
        for (r, l, rr) in spire(244 - tr, xc, w0, w1, cuts, keys, seed=tr + 7):
            y = tr + r
            if not (0 <= y < H):
                continue
            span = max(1, rr - l)
            for x in range(max(0, l), min(W, rr + 1)):
                u = (x - l) / float(span)
                k = 0 if u < cuts[0] else 1
                c.px(x, y, PAL[keys[k]], 4, 1)
            if 0 <= rr < W:
                c.px(rr, y, PAL[keys[1]], 4, 1)
    mist_band(c, 190, 232, "2", density=0.56, seed=43, wisp=0.9, soft=1.4)

    LEDGES_L = {18, 41, 67, 88, 112, 139, 163, 190, 217, 244}
    LEDGES_R = {25, 54, 82, 108, 134, 161, 189, 216, 243}

    # ---------- right massif: fills rightward from its left edge
    for (r, edge) in RIGHT.rows:
        y = r
        if not (0 <= y < H):
            continue
        l, rr = edge, W - 1
        span = max(1, rr - l)
        for x in range(max(0, l), W):
            u = (x - l) / float(span)
            k = len(RIGHT.keys) - 1
            for j, cut in enumerate(RIGHT.cuts):
                if u < cut:
                    k = j
                    break
            col = PAL[RIGHT.keys[min(k, len(RIGHT.keys) - 1)]]
            for cut in RIGHT.cuts[:-1]:
                if abs(u - cut) < 1.4 / (span + 2.0):
                    col = PAL[RIGHT.keys[max(0, k - 1)]]
            if r in LEDGES_R and (x - l) % 37 < 21:
                col = PAL[RIGHT.keys[min(len(RIGHT.keys) - 1, k + 1)]]
            c.px(x, y, col, 5, 2)
        if 0 <= l < W:
            c.px(l, y, PAL[RIGHT.keys[-1]], 5, 2)
    # pavilion crag: a shelf that juts out of the right massif
    for row in range(150, 250):
        t = (row - 150) / 100.0
        hw = 8 + (t ** 0.62) * 30
        x0 = int(370 - hw)
        x1 = int(370 + hw * 0.55)
        for x in range(max(0, x0), min(W, x1 + 1)):
            u = (x - x0) / max(1.0, (x1 - x0))
            k = 3 if u < 0.55 else 2
            col = PAL[RIGHT.keys[k]]
            if u > 0.93:
                col = PAL[RIGHT.keys[-1]]
            # keep the massif's strata rhythm on the shelf too
            if row in LEDGES_R and (x - x0) % 37 < 21:
                col = PAL[RIGHT.keys[min(len(RIGHT.keys) - 1, k + 1)]]
            c.px(x, row, col, 5, 8)
    draw_pavilion(c, 374, 172, 5)
    draw_waterfall(c, 348, 200, 302, 5)

    # ---------- left massif: fills leftward from its right edge (nearest)
    for (r, edge) in LEFT.rows:
        y = r
        if not (0 <= y < H):
            continue
        l, rr = 0, edge
        span = max(1, rr - l)
        for x in range(0, min(W, rr + 1)):
            u = (x - l) / float(span)
            k = len(LEFT.keys) - 1
            for j, cut in enumerate(LEFT.cuts):
                if u < cut:
                    k = j
                    break
            col = PAL[LEFT.keys[min(k, len(LEFT.keys) - 1)]]
            for cut in LEFT.cuts[:-1]:
                if abs(u - cut) < 1.4 / (span + 2.0):
                    col = PAL[LEFT.keys[max(0, k - 1)]]
            if r in LEDGES_L and (x - l) % 41 < 19:
                kk = min(len(LEFT.keys) - 1, k + 1)
                col = PAL[LEFT.keys[kk]]
            c.px(x, y, col, 6, 3)
        if 0 <= edge < W:
            c.px(edge, y, PAL[LEFT.keys[-1]], 6, 3)

    stamp(c, PINE, 196, 190, "-", 6, 4)
    stamp(c, PINE, 214, 206, "#", 6, 4)
    stamp(c, PINE, 176, 214, "#", 6, 4)

    # low mist: pools against the crags only, never a band across the frame
    for (cx, w, hgt, sd) in ((96, 62, 26, 61), (168, 40, 18, 62),
                             (352, 52, 22, 63), (430, 44, 20, 64)):
        for y in range(H - hgt - 18, min(H, 252)):
            t = (y - (H - hgt - 18)) / float(max(1, hgt))
            prof = 0.75 - abs(t - 0.5) * 1.2
            if prof <= 0:
                continue
            for x in range(max(0, cx - w), min(W, cx + w)):
                d = 1.0 - abs(x - cx) / float(w)
                nz = vn(x * 0.05 + y * 0.21, sd)
                c.dith(x, y, PAL["2"], prof * d * (0.35 + nz * 0.75))

    # contact shadow: rock darkens the water right where it enters
    for (x0, x1) in ((0, 176), (330, W - 1)):
        for y in range(240, 250):
            t = 1.0 - (y - 240) / 10.0
            for x in range(x0, x1):
                if vn(x * 0.08, 77) > 0.45:
                    c.dith(x, y, PAL["f"], t * 0.5)

    # ---------- water
    draw_water(c, 244, seed=5)

    # ---------- foreground: bottom-left only
    stamp(c, FOREGROUND, -8, 244, "#", 9, 5)
    stamp(c, PINE, 12, 236, "#", 9, 6)

    # ---------- warm accent: blossom twig entering top-left of the rock
    for i in range(26):
        bx = -3 + i
        by = 238 - int(np.sin(i * 0.19) * 6) - (i // 7) * 3
        c.px(bx, by, PAL["="], 9, 7)
    for k in range(13):
        bx = 2 + int((vn(k * 2.7, 71) - 0.5) * 26)
        by = 231 - int((vn(k * 3.9, 72) - 0.5) * 14)
        c.px(bx, by, PAL["p"], 9, 7)
        if vn(k * 1.3, 73) > 0.45:
            c.px(bx + 1, by, PAL["P"], 9, 7)

    os.makedirs("out", exist_ok=True)
    img = Image.fromarray(c.rgb, "RGB")
    img.save("out/panel_1x.png")
    img.resize((W * 4, H * 4), Image.NEAREST).save("out/panel_4x.png")
    print("wrote out/panel_1x.png / _4x.png")


if __name__ == "__main__":
    compose()
