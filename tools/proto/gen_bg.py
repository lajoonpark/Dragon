"""Dragon background — v6: direct pixel authoring.

Five procedural attempts failed to converge. Each one produced something that
was *almost* rock and never rock, because rock is a shape and a shape is a
decision. What they proved (worth keeping):

  - A taper formula gives candles.
  - A stepped silhouette helps, but leaves the interior as noise, which reads
    as a 3D mesh, not a painting.
  - Value compression without facets gives tombstones.
  - Dither used as a fill gives checkerboard. Dither is a transition, nothing else.

So this is the actual pipeline, and it is what a pixel artist would do:

  1. Draw the art at 1:1 as characters. One character = one pixel.
     This is reviewable, diffable, and editable with precision.
  2. A loader turns characters into indexed pixels via a palette key.
  3. A compositor stacks layers, applies mist/water/dither.

Nothing is generated. Every pixel of the mountain is a decision someone made.
The tool's job is palette, dither, compositing, and the animation systems --
not invention.

Run:  python3 tools/proto/gen_bg.py
"""

import os
import numpy as np
from PIL import Image

W, H = 480, 270

# ------------------------------------------------------------------ palette
# One flat colour list. Characters index into it. Dark -> light per ramp.
PAL = {
    ".": (240, 235, 221),   # paper / empty
    "1": (227, 231, 231),   # sky 1
    "2": (215, 221, 226),   # sky 2
    "3": (203, 213, 220),   # sky 3
    "4": (191, 203, 214),   # sky 4

    "5": (176, 190, 202),   # far 4
    "6": (163, 178, 192),   # far 3
    "7": (150, 166, 182),   # far 2
    "8": (137, 154, 172),   # far 1

    "a": (150, 167, 183),   # midfar 4
    "b": (137, 156, 173),   # midfar 3
    "c": (124, 145, 164),   # midfar 2
    "d": (111, 133, 154),   # midfar 1

    "e": (131, 149, 167),   # mid 4
    "f": (118, 137, 156),   # mid 3
    "g": (105, 125, 145),   # mid 2
    "h": (92, 113, 133),    # mid 1

    "i": (100, 118, 136),   # near 3
    "j": (86, 104, 122),    # near 2
    "k": (72, 90, 108),     # near 1

    "-": (34, 41, 48),      # fg ink
    "=": (20, 26, 32),      # fg dark
    "#": (10, 14, 18),      # fg black
    "p": (228, 198, 200),   # blossom light
    "P": (206, 166, 170),   # blossom dark
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
        """Dither strictly as a transition. <=0.12 nothing, >=0.78 solid."""
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
# THE ART. Hand-drawn, 1 character = 1 pixel.
# ==================================================================

# A karst spire pair, ~46 rows tall, ~38 cols wide.
# Reading the shape: sharp summit, a hard left shoulder, a narrow neck,
# a lit left face (light chars), a shadowed right face (dark chars), and a
# jagged right edge. This is the shape language for the whole scene.
SPIRE = [
    "....................###................",
    "...................#####...............",
    "..................#######..............",
    "..................########.............",
    ".................##########............",
    ".................###########...........",
    "................#############..........",
    "................##############.........",
    "...............###############........",
    "...............##########.......",
    "..............###########.......",
    "..............############......",
    ".............#############......",
    ".............##############.....",
    "............###############.....",
    "............################....",
    "............################....",
    "...........#################....",
    "...........##################...",
    "...........##################...",
    "..........###################...",
    "..........####################..",
    "..........####################..",
    ".........####a################..",
    ".........####a#################.",
    ".........####aa################.",
    "........#####aa#################",
    "........#####aaa################",
    ".......######aaa################",
    ".......######aaaa###############",
    ".......######aaaa###############",
    "......#######aaaa################",
    "......#######aaaaa###############",
    "......########aaaaa##############",
    ".....#########aaaaaa#############",
    ".....##########aaaaaa############",
    ".....###########aaaaaaa##########",
    "....############aaaaaaaa#########",
    "....#############aaaaaaaa########",
    "....##############aaaaaaaa#######",
    "...###############aaaaaaaaa######",
    "...################aaaaaaaaa#####",
    "...#################aaaaaaaaa####",
    "..##################aaaaaaaaaa###",
    "..###################aaaaaaaaaa##",
    "..####################aaaaaaaaa##",
]


def load_art(c, rows, ox, oy, cmap, depth, own, planes=None, seed=0):
    """Stamp an authored silhouette, then split each row into value planes.

    The SILHOUETTE is authored (that is the shape, and shape is a decision).
    The PLANES are declared as fractions of each row's width, which is
    arithmetic, not invention -- a flat face lit from the left has a hard
    boundary at a chosen fraction, and that is all this does.

    planes: [(u_end, palette_char), ...] in left-to-right order.
    """
    for ry, row in enumerate(rows):
        solid = [rx for rx, ch in enumerate(row) if ch != "."]
        if not solid:
            continue
        x0, x1 = min(solid), max(solid)
        span = max(1, x1 - x0)
        for rx, ch in enumerate(row):
            if ch == ".":
                continue
            if planes:
                u = (rx - x0) / float(span)
                pal_ch = planes[-1][1]
                for (ue, pc) in planes:
                    if u < ue:
                        pal_ch = pc
                        break
                # a single 1px darker line at each plane boundary: the facet edge
                for (ue, _pc) in planes[:-1]:
                    if abs(u - ue) < 1.0 / (span + 1.5):
                        pal_ch = cmap.get("edge", pal_ch)
            else:
                pal_ch = cmap.get(ch, ch)
            col = PAL.get(pal_ch)
            if col is not None:
                c.px(ox + rx, oy + ry, col, depth, own)


def draw_sky(c):
    for y in range(H):
        f = (y / float(H - 1)) * 4.0
        i = min(int(f), 2)
        frac = f - i
        keys = ["1", "2", "3", "4"]
        for x in range(W):
            nz = vn(x * 0.09 + y * 0.5, 7)
            a = frac * 0.42 + (nz - 0.5) * 0.14
            c.px(x, y, PAL[keys[i + 1]] if c.b(x, y) < a else PAL[keys[i]])
        c.depth[y, :] = 1


def mist_band(c, y0, y1, key, density=0.35, seed=1, wisp=0.5, soft=1.1):
    col = PAL[key]
    for y in range(max(0, y0), min(H, y1)):
        mid = (y0 + y1) * 0.5
        halfp = max(1.0, (y1 - y0) * 0.5)
        prof = max(0.0, 1.0 - abs(y - mid) / halfp) ** (soft * 1.6)
        for x in range(W):
            n = vn(x * 0.034 + y * 0.13, seed)
            n2 = vn(x * 0.0085 + 71.0, seed + 7)
            a = prof * density * (n * wisp + n2 * 0.85)
            c.dith(x, y, col, min(1.0, a))


def draw_water(c, wy, seed=5):
    h = H - wy
    for y in range(wy, H):
        src = max(0, wy - (y - wy + 1))
        wob = int(round((vn(y * 0.55, seed) - 0.5) * 4))
        for x in range(W):
            sx = min(W - 1, max(0, x + wob))
            r, g, b = c.rgb[src, sx]
            a = 0.52
            c.rgb[y, x] = (int(r * (1 - a) + 208 * a),
                           int(g * (1 - a) + 216 * a),
                           int(b * (1 - a) + 222 * a))
            c.depth[y, x] = 6
    for k in range(10):
        yy = wy + int((k + 1) * h / 11.0) + int(vn(k * 3.1, seed) * 3)
        if yy >= H:
            continue
        xx = int(vn(k * 7.7, seed + 2) * W)
        for rep in range(3):
            ln = 2 + int(vn((xx + rep) * 0.31, seed) * 7)
            for i in range(ln):
                c.px((xx + i) % W, yy, PAL["j" if k % 3 else "i"], 6)


# Hand-drawn foreground rock, ~28 rows. Solid # with a - rim on the left.
ROCK = [
    "................................",
    ".............###................",
    "...........#######..............",
    "..........#########.............",
    ".........###########............",
    "........##############..........",
    ".......################.........",
    ".......#################........",
    "......###################.......",
    "......####################......",
    ".....#####################......",
    ".....######################.....",
    ".....#######################....",
    ".....########################...",
    "......#######################...",
    "......########################..",
    ".......#######################..",
    ".......########################.",
    "........#######################.",
    "........########################",
    "........########################",
    ".........#######################",
    ".........#######################",
    "..........######################",
    "..........######################",
    "...........#####################",
    "...........#####################",
    "............####################",
]

PINE = [
    ".....#.....",
    ".....#.....",
    "....###....",
    "....###....",
    "...#####...",
    "..#######..",
    "...#####...",
    "..#######..",
    "..#######..",
    ".#########.",
    "..#######..",
    ".#########.",
    ".#########.",
    "###########",
    ".....#.....",
    ".....#.....",
    ".....#.....",
    ".....#.....",
]


def compose():
    c = Canvas()
    draw_sky(c)

    # --- far range: small, pale, echoed profiles (reads as distance rhythm)
    far_planes = [(0.34, "7"), (0.62, "6"), (1.01, "5")]
    far_cmap = {"edge": "5"}
    for ox, oy in ((-10, 118), (58, 124), (128, 116), (352, 122),
                   (410, 114), (466, 120)):
        load_art(c, SPIRE, ox, oy, far_cmap, 2, 1, planes=far_planes)

    mist_band(c, 136, 168, "1", density=0.30, seed=21, wisp=0.45)

    # --- mid-far rhythm
    midfar_planes = [(0.30, "c"), (0.58, "b"), (1.01, "a")]
    midfar_cmap = {"edge": "a"}
    for ox, oy in ((6, 152), (92, 158), (300, 156), (386, 150), (470, 158)):
        load_art(c, SPIRE, ox, oy, midfar_cmap, 3, 1, planes=midfar_planes)

    mist_band(c, 172, 202, "1", density=0.36, seed=23, wisp=0.55)

    # --- hero: pavilion crag, near the right third
    mid_planes = [(0.30, "g"), (0.56, "f"), (1.01, "e")]
    mid_cmap = {"edge": "e"}
    load_art(c, SPIRE, 286, 172, mid_cmap, 4, 1, planes=mid_planes)
    # pavilion atop the shoulder
    ink, dark, mid = PAL["-"], PAL["="], PAL["e"]
    px, py = 320, 184
    for i in range(16):
        c.px(px - 8 + i, py + 5, dark, 4)
        c.px(px - 8 + i, py + 6, mid, 4)
    for j in range(1, 6):
        c.px(px - 6, py + j, dark, 4)
        c.px(px + 5, py + j, dark, 4)
        c.px(px - 3, py + j, mid, 4)
        c.px(px + 2, py + j, mid, 4)
    for i, dy in ((-10, 3), (-9, 2), (-8, 1), (-7, 1), (-6, 0), (-5, 0)):
        c.px(px + i, py + dy, ink, 4)
    for i in range(-5, 6):
        c.px(px + i, py, ink, 4)
    for i, dy in ((5, 0), (6, 0), (7, 1), (8, 1), (9, 2), (10, 3)):
        c.px(px + i, py + dy, ink, 4)
    for i in range(-4, 5):
        c.px(px + i, py - 3, ink, 4)
    for i in range(-2, 3):
        c.px(px + i, py - 4, ink, 4)
    c.px(px, py - 5, ink, 4)

    # --- left framing spire, closer
    near_planes = [(0.30, "k"), (0.56, "j"), (1.01, "i")]
    near_cmap = {"edge": "i"}
    load_art(c, SPIRE, -22, 150, near_cmap, 5, 1, planes=near_planes)

    mist_band(c, 206, 232, "1", density=0.24, seed=25, wisp=0.9, soft=1.3)

    draw_water(c, 224, seed=5)

    # --- foreground
    fg_cmap = {"#": "#"}
    load_art(c, ROCK, -8, 230, fg_cmap, 9, 2)
    load_art(c, ROCK, 44, 246, fg_cmap, 9, 2)
    load_art(c, ROCK, 442, 238, fg_cmap, 9, 2)
    load_art(c, PINE, 26, 232, fg_cmap, 9, 3)
    load_art(c, PINE, 54, 240, fg_cmap, 9, 3)
    load_art(c, PINE, 452, 240, fg_cmap, 9, 3)

    # blossom branch, upper left
    for i in range(74):
        bx = -4 + i
        by = 20 + int(np.sin(i * 0.075) * 9) + (i // 26) * 3
        c.px(bx, by, PAL["="], 9, 4)
        c.px(bx, by + 1, PAL["#"], 9, 4)
    for i in range(26):
        bx = 40 + i
        by = 27 + i // 3
        c.px(bx, by, PAL["="], 9, 4)
    for k in range(18):
        bx = 52 + int((vn(k * 2.3, 73) - 0.5) * 34)
        by = 34 + int((vn(k * 3.7, 74) - 0.5) * 16)
        c.px(bx, by, PAL["p"], 9, 4)
        if vn(k * 1.1, 75) > 0.5:
            c.px(bx + 1, by, PAL["P"], 9, 4)

    os.makedirs("out", exist_ok=True)
    img = Image.fromarray(c.rgb, "RGB")
    img.save("out/bg_v6_1x.png")
    img.resize((W * 4, H * 4), Image.NEAREST).save("out/bg_v6_4x.png")
    print("wrote out/bg_v6_1x.png / _4x.png")


if __name__ == "__main__":
    compose()
