"""Dragon — ONE LAYER: the mountain range. Iteration 5.

Four attempts failed the same way: vertical stripes. The cause was always the
same, and it took four tries to name it properly:

    Shading was computed per COLUMN, from a parameter that was itself a step
    function of x. So every column got one value for its whole height, and the
    layer came out as a barcode of one stripe per flank.

The fix is structural: **shade from the run, not from the column.**

For every row y, the ridge occupies an interval [left(y), right(y)]. Within
that interval each pixel gets `s = (x - left) / (right - left)` -- where it sits
across the mass *at that height*. That single change makes isophotes follow the
silhouette: they curve up into the peaks and flatten in the saddles, which is
what a painted mountain does.

Everything else follows from that:
  - light is a function of s (lit toward s=0, i.e. the left faces)
  - terraces are bands of constant s, so they wrap the mass rather than running
    as horizontal rulers
  - the silhouette edge gets a shadow plane, which is what makes rock read as
    turning away from you

Mist is the layer's own dithered alpha at the base, so a ridge genuinely
dissolves into air rather than having a grey band painted over it.

Scope: this layer only. No water, no foreground, no pavilion, no dragons.

Run: python3 tools/proto/gen_layer.py [tag]
"""

import os
import sys
import numpy as np
from PIL import Image

W, H = 480, 270

# Six depth bands, far -> near. Each is a 6-step ramp from cool shadow to warm
# crest. Atmospheric perspective is built in: band 0 has almost no contrast and
# sits near the sky value; band 5 is deep and saturated.
BANDS = [
    [(174, 188, 199), (185, 197, 205), (196, 205, 211), (207, 213, 216),
     (218, 221, 220), (230, 230, 222)],
    [(157, 175, 191), (169, 186, 199), (182, 196, 207), (195, 206, 214),
     (208, 216, 220), (223, 226, 220)],
    [(136, 158, 177), (150, 170, 186), (164, 182, 196), (180, 194, 205),
     (197, 208, 215), (216, 221, 218)],
    [(113, 136, 158), (128, 150, 170), (144, 165, 182), (161, 181, 195),
     (182, 197, 207), (206, 214, 216)],
    [(88, 112, 136), (103, 127, 150), (120, 143, 164), (139, 161, 179),
     (162, 180, 195), (191, 204, 208)],
    [(60, 80, 102), (74, 96, 119), (91, 113, 136), (110, 132, 154),
     (133, 154, 172), (167, 181, 193)],
]

WARM = [(233, 225, 203), (236, 226, 200), (239, 227, 197),
        (242, 228, 194), (244, 229, 191), (246, 230, 188)]
SHADOW = (44, 61, 80)
VEG = [(28, 46, 40), (21, 37, 33), (13, 25, 23)]
VEG_FAR = [(104, 126, 128), (86, 108, 112), (70, 92, 98)]

BAYER4 = np.array([[0, 8, 2, 10], [12, 4, 14, 6],
                   [3, 11, 1, 9], [15, 7, 13, 5]], dtype=np.float32) / 16.0


def h1(i, s):
    n = (int(i) * 374761393 + int(s) * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((n ^ (n >> 16)) & 0xFFFFFF) / float(0xFFFFFF)


def lerp(a, b, t):
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t),
            int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


# ==================================================================
#  ARCHETYPE TABLES  (u, v): u = fraction across, v = height fraction.
#  The v-upticks are karst shoulders. Remove them and every peak is a cone.
# ==================================================================
ARCH = {
    "spire": [(0.00, 1.00), (0.06, 0.93), (0.10, 0.84), (0.14, 0.87),
              (0.20, 0.75), (0.25, 0.78), (0.32, 0.63), (0.38, 0.59),
              (0.46, 0.47), (0.54, 0.42), (0.64, 0.30), (0.75, 0.20),
              (0.88, 0.09), (1.00, 0.00)],
    "needle": [(0.00, 1.00), (0.04, 0.90), (0.08, 0.79), (0.12, 0.83),
               (0.17, 0.67), (0.22, 0.72), (0.29, 0.54), (0.35, 0.49),
               (0.43, 0.37), (0.53, 0.30), (0.65, 0.21), (0.79, 0.12),
               (1.00, 0.00)],
    "tower": [(0.00, 1.00), (0.09, 0.96), (0.16, 0.99), (0.23, 0.86),
              (0.29, 0.90), (0.36, 0.75), (0.43, 0.70), (0.51, 0.58),
              (0.60, 0.50), (0.70, 0.38), (0.81, 0.25), (0.91, 0.12),
              (1.00, 0.00)],
    "bulk": [(0.00, 1.00), (0.12, 0.95), (0.21, 0.99), (0.29, 0.85),
             (0.37, 0.89), (0.46, 0.73), (0.54, 0.69), (0.63, 0.55),
             (0.72, 0.43), (0.81, 0.30), (0.91, 0.15), (1.00, 0.00)],
    "saddle": [(0.00, 1.00), (0.16, 0.80), (0.28, 0.68), (0.42, 0.56),
               (0.57, 0.42), (0.72, 0.29), (0.86, 0.15), (1.00, 0.00)],
}


def arch_v(arch, u):
    tbl = ARCH[arch]
    for (ua, va), (ub, vb) in zip(tbl, tbl[1:]):
        if ua <= u < ub:
            return va
    return tbl[0][1] if u < tbl[0][0] else tbl[-1][1]


class Peak:
    def __init__(self, x, height, half_w, arch, seed, base, jitter=1.0):
        self.x, self.h, self.hw = x, height, half_w
        self.arch, self.seed, self.j = arch, seed, jitter
        self.base = base

    def top_at(self, x):
        dx = abs(x - self.x)
        if dx > self.hw:
            return None
        u = dx / float(self.hw)
        v = arch_v(self.arch, u)
        if self.j:
            # held runs, one jump per block: never continuous (that reads organic)
            blk = int(x) // 5
            v += (h1(blk, self.seed + 5) - 0.5) * 2.0 * self.j / float(max(8, self.h))
        return self.base - self.h * v

    def anchors(self):
        out = []
        for f in (0.0, 0.10, 0.19, 0.31, 0.46):
            out.append(self.x - self.hw * f)
            if f > 0:
                out.append(self.x + self.hw * f)
        return out


class Ridge:
    """A ridge = union of its peaks. Per row, an interval [left, right]."""

    def __init__(self, band, peaks, base, mist_rows=0, veg=0.0, veg_seed=0):
        self.band, self.peaks, self.base = band, peaks, base
        self.mist_rows, self.veg, self.veg_seed = mist_rows, veg, veg_seed
        self.crest = [None] * W
        for p in peaks:
            for x in range(max(0, int(p.x - p.hw)), min(W, int(p.x + p.hw) + 1)):
                y = p.top_at(x)
                if y is None:
                    continue
                if self.crest[x] is None or y < self.crest[x]:
                    self.crest[x] = y
        last = None
        for x in range(W):
            if self.crest[x] is not None:
                last = self.crest[x]
            elif last is not None:
                self.crest[x] = last
        nxt = None
        for x in range(W - 1, -1, -1):
            if self.crest[x] is not None:
                nxt = self.crest[x]
            elif nxt is not None:
                self.crest[x] = nxt

    # ---- the only thing that matters: which x-range exists at row y
    def run_at(self, y):
        if y > self.base:
            return None
        xs = [x for x in range(W)
              if self.crest[x] is not None and self.crest[x] <= y]
        if not xs:
            return None
        return min(xs), max(xs)

    def draw(self, rgb, alpha, depth, depthval, seed):
        """Draw each peak INDIVIDUALLY, back to front.

        Unioning the peaks and shading across the union was the bug: at any row
        the run spans the whole band, so `s` varied over ~480px and the shading
        became one soft wash. Shading each peak against its own run restores
        per-peak form -- each summit gets its own lit crown and shadow flank,
        and overlaps read as separate mountains.
        """
        ramp, warmc = BANDS[self.band], WARM[self.band]
        warm_amt = [0.14, 0.20, 0.28, 0.38, 0.50, 0.62][self.band]
        shadow_amt = [0.10, 0.14, 0.20, 0.28, 0.36, 0.44][self.band]
        mist_top = self.base - self.mist_rows

        # tallest last, so the dominant summit is in front
        for p in sorted(self.peaks, key=lambda q: q.h):
            self._draw_peak(p, rgb, alpha, depth, depthval, seed, ramp, warmc,
                            warm_amt, shadow_amt, mist_top)

    def _draw_peak(self, p, rgb, alpha, depth, depthval, seed, ramp, warmc,
                   warm_amt, shadow_amt, mist_top):
        top_all = p.base - p.h
        for y in range(max(0, int(top_all)), min(H, p.base + 1)):
            xs = [x for x in range(max(0, int(p.x - p.hw)),
                                   min(W, int(p.x + p.hw) + 1))
                  if (t := p.top_at(x)) is not None and t <= y]
            if not xs:
                continue
            l, r = min(xs), max(xs)
            span = max(1, r - l)

            for x in range(l, r + 1):
                s = (x - l) / float(span)          # across THIS peak, at this row
                d = y - p.top_at(x)                # below this peak's own crest

                v = 0.92 - min(1.0, d / float(max(20, p.h))) * 0.60
                v += (0.5 - s) * 0.30              # left lit, right away
                v += (1.0 - abs(2.0 * s - 1.0)) * 0.06

                # terraces wrap this peak only
                bw = 0.10 + h1(p.seed, seed) * 0.06
                q = int(s / bw)
                v += (h1(q * 17 + int(y) // 11 + p.seed * 3, seed + 3) - 0.5) * 0.09

                if s > 0.88:
                    v -= 0.14

                idx = max(0, min(len(ramp) - 1, int(round(v * (len(ramp) - 1)))))
                col = ramp[idx]

                if s < 0.42:
                    col = lerp(col, warmc, warm_amt * (1.0 - s / 0.42)
                               * (1.0 - min(1.0, d / 120.0)))
                if s > 0.66:
                    col = lerp(col, SHADOW, shadow_amt * ((s - 0.66) / 0.34))

                a = 1.0
                if y > mist_top:
                    dd = (y - mist_top) / float(max(1, self.base - mist_top + 1))
                    a = max(0.0, 1.0 - dd * 1.1)
                    if a < 0.10:
                        continue
                    if a < 0.90 and BAYER4[y & 3, x & 3] > a:
                        continue
                rgb[y, x] = col
                alpha[y, x] = 255
                depth[y, x] = depthval

    def draw_veg(self, rgb, alpha, depth, depthval):
        if self.veg <= 0:
            return
        pal = VEG if self.band >= 3 else VEG_FAR
        for p in self.peaks:
            for k, ax in enumerate(p.anchors()):
                x0 = int(round(ax))
                if not (0 <= x0 < W):
                    continue
                if h1(x0 * 3 + k, self.veg_seed) > self.veg:
                    continue
                top = self.crest[x0]
                if top is None:
                    continue
                top = int(round(top))
                # clusters sit ON the crest and hang down-slope
                size = 3 + int(h1(x0 + k * 5, self.veg_seed + 3) * 6)
                col = pal[int(h1(x0, self.veg_seed + 7) * len(pal)) % len(pal)]
                for i in range(size):
                    xx = x0 + i - size // 2
                    if not (0 <= xx < W) or self.crest[xx] is None:
                        continue
                    ct = int(round(self.crest[xx]))
                    hh = 1 + int((1.0 - abs(i - size / 2.0) / (size / 2.0 + 1e-6)) * 3)
                    for yy in range(ct - 1, ct + hh):
                        if 0 <= yy < H:
                            rgb[yy, xx] = col
                            alpha[yy, xx] = 255
                            depth[yy, xx] = depthval


# ==================================================================
#  THE RANGE. (x, height, half_width, archetype, seed)
#  Bases sit BELOW the frame for near bands -- mountains should be cut off by
#  the bottom edge, not sit on it.
# ==================================================================
SPEC = [
    (0, 150, 10, 0.00, 0, [
        (-40, 34, 170, "bulk", 1), (150, 42, 180, "tower", 2),
        (340, 36, 175, "bulk", 3), (500, 40, 165, "saddle", 4)]),

    (1, 176, 16, 0.00, 0, [
        (-30, 58, 175, "spire", 5), (140, 68, 185, "tower", 6),
        (320, 60, 180, "bulk", 7), (480, 66, 170, "spire", 8)]),

    (2, 202, 22, 0.30, 17, [
        (-20, 84, 170, "tower", 11), (150, 98, 175, "spire", 12),
        (330, 88, 172, "tower", 13), (490, 94, 168, "spire", 14)]),

    (3, 228, 28, 0.50, 25, [
        (-50, 118, 172, "spire", 18), (130, 134, 178, "tower", 19),
        (330, 124, 174, "spire", 20), (500, 116, 170, "tower", 21)]),

    (4, 258, 34, 0.70, 32, [
        (-70, 150, 178, "tower", 26), (150, 168, 172, "spire", 27),
        (360, 156, 176, "spire", 28), (520, 148, 170, "tower", 29)]),

    (5, 300, 40, 0.85, 38, [
        (-90, 196, 180, "spire", 33), (160, 214, 175, "needle", 34),
        (390, 202, 178, "spire", 35), (540, 188, 172, "tower", 36)]),
]


def compose(tag):
    rgb = np.zeros((H, W, 3), dtype=np.uint8)
    rgb[:, :] = (238, 233, 219)
    alpha = np.zeros((H, W), dtype=np.uint8)
    depth = np.zeros((H, W), dtype=np.uint8)

    for i, (band, base, mist, veg, vseed, peaks) in enumerate(SPEC):
        pr = [Peak(x, h, hw, arch, sd, base) for (x, h, hw, arch, sd) in peaks]
        rng = Ridge(band, pr, base, mist_rows=mist, veg=veg, veg_seed=vseed)
        rng.draw(rgb, alpha, depth, i + 1, seed=100 + i)
        rng.draw_veg(rgb, alpha, depth, i + 1)

    os.makedirs("out", exist_ok=True)
    img = Image.fromarray(np.dstack([rgb, alpha]).astype(np.uint8), "RGBA")
    img.save(f"out/layer_{tag}.png")
    flat = Image.new("RGB", (W, H), (238, 233, 219))
    flat.paste(img, (0, 0), img)
    flat.save(f"out/layer_{tag}_flat_1x.png")
    flat.resize((W * 2, H * 2), Image.NEAREST).save(f"out/layer_{tag}_flat_2x.png")
    print(f"wrote out/layer_{tag}.png  alpha={100.0*(alpha>0).mean():.1f}%")
    # crest diagnostics: a plateau means peaks are too wide to read separately
    for i, (band, base, mist, veg, vseed, peaks) in enumerate(SPEC):
        pr = [Peak(x, h, hw, arch, sd, base) for (x, h, hw, arch, sd) in peaks]
        r = Ridge(band, pr, base, mist)
        c = [v for v in r.crest if v is not None]
        mx, mn = max(c), min(c)
        # count local maxima = how many distinct summits actually read
        lm = sum(1 for x in range(2, W-2)
                 if r.crest[x] is not None and r.crest[x-2] is not None and r.crest[x+2] is not None
                 and r.crest[x] < r.crest[x-2] - 1 and r.crest[x] < r.crest[x+2] - 1)
        print(f"  band{i}: crest span={mx-mn:5.1f}px  summits={lm:2d}  "
              f"relief_ratio={(mx-mn)/ (mx-mn+1e-9):.2f}")


if __name__ == "__main__":
    compose(sys.argv[1] if len(sys.argv) > 1 else "r05")
