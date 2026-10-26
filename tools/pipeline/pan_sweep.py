"""Sweep parallax strength and measure the visible cost.

FINDING SO FAR (both directions are bad, and the second one is worse):

  tears    stacking each depth band and shifting it opens holes at every depth
           boundary -- the hole problem again, in motion.
  smears   inverse-warping per depth has no holes BY CONSTRUCTION (every output
           pixel does its own lookup, so nothing can be uncovered) but it
           STRETCHES content wherever depth changes, because the source image
           contains no hidden content behind the near layers. Asking for that
           content makes the pixels elongate instead.

The smear is the fundamental one, and it is not a bug in my warp. It is the
information-theoretic limit: a single flat image cannot produce real parallax,
because parallax reveals what is behind things, and there is nothing behind
things in a flat image.

This file measures how much smear each parallax strength costs, to see whether a
SUBTLE amount is tolerable even though a strong amount is not.

Metric: local stretch = how much each source pixel is elongated horizontally.
Computed from the sampling coordinate's derivative along x. A value near 1.0
means undistorted; 2.0 means content smeared to twice its width.
"""

import numpy as np
from PIL import Image
from scipy import ndimage

SCENE = Image.open("out/reduced_c01_24c.png").convert("RGB")
DEPTH = Image.open("out/depth_c01.png").convert("L")

PAN_PX_S = 7.0
FPS = 12
SECONDS = 24
WARP_SIGMA = 10.0


def sample_coord(depth, t, span):
    """x position in the source for each output x, at time t.

    Wraps modulo width rather than clamping: a panning wallpaper is a loop, and
    clamping produced artificial streaky bands down the left edge that were a
    bug in the test, not a property of the technique.
    """
    h, w = depth.shape
    shift = PAN_PX_S * t * (0.15 + span * depth)
    xs = (np.arange(w)[None, :] - shift)
    return np.mod(xs, w)


def warp(scene, xs):
    h, w, _ = scene.shape
    xi = np.floor(xs).astype(np.int32)
    frac = (xs - xi)[..., None]
    rows = np.arange(h)[:, None]
    a = scene[rows, xi % w].astype(np.float32)
    b = scene[rows, (xi + 1) % w].astype(np.float32)
    return (a * (1 - frac) + b * frac).astype(np.uint8)


def local_stretch(xs, w):
    """dx_source/dx_output. 1.0 = undistorted. >1 = smeared, <1 = compressed."""
    d = np.gradient(xs, axis=1)
    d = np.where(np.abs(d) > 2.0, np.nan, d)      # ignore wrap discontinuities
    return np.nanmean(np.abs(d))


def main():
    scene = np.array(SCENE)
    depth = np.array(DEPTH).astype(np.float32) / 255
    warp_depth = ndimage.gaussian_filter(depth, WARP_SIGMA)
    h, w, _ = scene.shape

    print(f"{w}x{h}  pan {PAN_PX_S}px/s  {SECONDS}s\n")
    print(" span   t     stretch   smeared>1.5   note")
    results = {}
    for span in (0.0, 0.15, 0.30, 0.50, 0.85):
        for secs in (10, 24):
            xs = sample_coord(warp_depth, secs, span)
            st = local_stretch(xs, w)
            d = np.gradient(xs, axis=1)
            d = np.where(np.abs(d) > 2.0, np.nan, d)
            bad = float(np.nanmean(np.abs(d) > 1.5) * 100)
            results[(span, secs)] = (st, bad)
            tag = ""
            if span == 0.0:
                tag = "rigid, by definition undistorted"
            elif bad < 2:
                tag = "subtle"
            elif bad < 10:
                tag = "noticeable"
            else:
                tag = "broken"
            print(f" {span:4.2f}  {secs:2d}s  {st:7.3f}   {bad:6.1f}%    {tag}")

    # render the honest side-by-side at a subtle and a strong setting
    frames = {}
    for span, tag in ((0.0, "rigid"), (0.15, "subtle"), (0.85, "strong")):
        out = []
        for i in range(4):
            t = i * SECONDS / 3
            out.append(warp(scene, sample_coord(warp_depth, t, span)))
        frames[tag] = out

    pad = 6
    rows = len(frames)
    sheet = Image.new("RGB", (4 * (w + pad) + pad, rows * (h + pad) + pad),
                      (22, 22, 26))
    for r, (tag, fs) in enumerate(frames.items()):
        for c, f in enumerate(fs):
            sheet.paste(Image.fromarray(f), (pad + c * (w + pad),
                                             pad + r * (h + pad)))
    Path("out/pan").mkdir(parents=True, exist_ok=True)
    sheet.save("out/pan/pan_sweep.png")
    print("\nwrote out/pan/pan_sweep.png  rows: rigid / subtle(0.15) / strong(0.85)")


from pathlib import Path

if __name__ == "__main__":
    main()
