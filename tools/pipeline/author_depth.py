"""Author a depth field for the reduced master image.

Output: an 8-bit grayscale depth map, 0 = infinitely far, 255 = at the glass.
Saved as out/depth_c01.png, plus a colourised preview for eyeballing.

WHY THIS EXISTS INSTEAD OF LAYER SPLITTING

Dragons only need a depth FIELD, not separate image layers -- the renderer does
one test per pixel, `dragon_depth < scene_depth`. Splitting the image into
layers is one way to BUILD that field, but the split is hard here (the two
framing massifs are 68% of all rock and each spans every depth band, so
connected components merge depth instead of separating it). Authoring the field
directly is both cheaper and more accurate: it sidesteps the hole problem
entirely, because nothing is ever removed from the image.

THE KNOWN LIMITATION

Depth is assigned per connected rock mass, from that mass's MEAN luminance. So
the giant left and right massifs each get ONE depth for their whole extent, even
though they recede from near foreground to mid background. A dragon flying at
0.5 will therefore pass in FRONT of all of the left massif, including its
far-looking upper reaches. That is a real simplification. It is acceptable for
v1 because the massifs are continuous walls -- there is no walkable gap behind
their upper parts anyway -- but it is the thing to fix if the test looks wrong.

Per-pixel luminance must NOT be used as depth: a lit near face is paler than a
shadowed far ridge, so it inverts. That was measured, and it failed.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

SRC = Path("out/reduced_c01_24c.png")
OUT = Path("out")

# (mean luminance floor, depth) for a rock mass, near -> far. A mass's average
# value is its atmospheric depth; its lit faces are pale but they belong to it.
ROCK_BANDS = [
    (0, 0.84),     # near, very dark
    (95, 0.72),
    (118, 0.60),
    (145, 0.47),
    (160, 0.36),
    (172, 0.24),   # far ridges
]

WATER_DEPTH = 0.96
SKY_DEPTH = 0.03
MIST_DEPTH = 0.15


def lum_of(im):
    return (im.astype(np.int16) @ np.array([299, 587, 114]) // 1000)


def rock_depth(mean_lum):
    d = ROCK_BANDS[-1][1]
    for floor, depth in ROCK_BANDS:
        if mean_lum >= floor:
            d = depth
    return d


def author(im):
    h, w, _ = im.shape
    lum = lum_of(im)
    rock = lum <= 195
    rock = ndimage.binary_opening(rock, np.ones((2, 2)))
    lab, n = ndimage.label(rock)
    sizes = ndimage.sum(rock, lab, range(1, n + 1))

    depth = np.full((h, w), MIST_DEPTH, np.float32)

    # rock masses
    for c in range(1, n + 1):
        if sizes[c - 1] < 40:
            continue
        m = lab == c
        depth[m] = rock_depth(float(lum[m].mean()))

    # sky: pale AND above the highest non-pale pixel in that column
    pale = lum > 200
    for x in range(w):
        col = np.where(~pale[:, x])[0]
        if len(col):
            depth[: col[0], x] = SKY_DEPTH

    # water: pale, below the waterline. Waterline = the row nearest the bottom
    # where pale coverage drops below half and stays there.
    rows = [(pale[y].mean(), y) for y in range(h)]
    water_top = h
    for frac, y in rows:
        if y > h * 0.6 and frac > 0.45:
            water_top = y
            break
    water = np.zeros((h, w), bool)
    water[water_top:, :] = pale[water_top:, :]
    depth[water] = WATER_DEPTH

    return depth, lab, sizes, n, water_top


def colourise(depth):
    """Blue = far, warm = near. Easier to read than greyscale when checking."""
    d = depth[..., None]
    far = np.array([24, 44, 78], np.float32)
    near = np.array([255, 214, 150], np.float32)
    return (far * (1 - d) + near * d).astype(np.uint8)


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC
    im = np.array(Image.open(src).convert("RGB"))
    h, w, _ = im.shape
    depth, lab, sizes, n, water_top = author(im)

    print(f"{src.name} {w}x{h}")
    print(f"masses: {n}   water top y={water_top}")
    vals, cnts = np.unique((depth * 255).astype(np.uint8), return_counts=True)
    print("\ndepth levels in use:")
    for v, c in sorted(zip(vals, cnts), key=lambda t: -t[1])[:12]:
        print(f"  {v/255:4.2f}   {c*100/(h*w):5.1f}%")

    OUT.mkdir(exist_ok=True)
    Image.fromarray((depth * 255).astype(np.uint8)).save(OUT / "depth_c01.png")
    Image.fromarray(colourise(depth)).save(OUT / "depth_c01_preview.png")

    # side-by-side: master | depth | amplified
    pad = 8
    strip = Image.new("RGB", (w * 2 + pad * 3, h + pad * 2), (30, 30, 34))
    strip.paste(Image.fromarray(im), (pad, pad))
    strip.paste(Image.fromarray(colourise(depth)), (pad * 2 + w, pad))
    strip.save("/tmp/depth_compare.png")
    strip.resize((strip.width * 2, strip.height * 2), Image.NEAREST).save(
        "/tmp/depth_compare_2x.png")
    print("\nwrote out/depth_c01.png, out/depth_c01_preview.png")


if __name__ == "__main__":
    main()
