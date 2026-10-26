"""Rigid pan + independently drifting mist = cheap fake depth.

WHY THIS AND NOT BANDED PARALLAX

Banded parallax on a single image fails progressively: the displacement grows
linearly with time, so the smear grows with it. Measured, 24s in, at 7px/s:

    span 0.15 -> 1.1% of pixels smeared past 1.5x
    span 0.30 -> 6.1%
    span 0.85 -> 11.2%   (visually: the mountains melt like lava)

A wallpaper runs for hours, not 24 seconds, so any nonzero span eventually
degrades. Rigid pan is the only thing that stays undistorted forever.

BUT: structure is what smears. Mist has no structure. A soft, amorphous,
low-contrast veil can be slid at a different rate and the eye reads it as a
nearer or farther air mass, because there is nothing in it whose shape could be
seen to change.

So the cheap depth cue is:
    background  rigid pan               (undistorted, guaranteed)
    mist        its own extraction, drifting at a different rate
    dragons     depth-tested against the scene

That delivers most of the perceived depth of a layer split, with none of the
holes, because the only thing being displaced independently is the one thing
that cannot visibly distort.

The mist extraction here is deliberately crude -- a soft alpha from paleness,
then a blur. A production version would paint it. The point is to prove the
technique, not to ship the veil.
"""

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SCENE = Path("out/reduced_c01_24c.png")
DEPTH = Path("out/depth_c01.png")
OUT = Path("out/pan")

PAN_PX_S = 7.0
MIST_PX_S = 2.5          # within the 2-5px/s the docs already specify
FPS = 12
SECONDS = 24


def mist_alpha(rgb, depth):
    """Soft veil where the scene is pale and far. Low contrast on purpose: the
    drift must be imperceptible as motion of any particular shape."""
    lum = rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114])
    a = np.clip((lum - 165) / 70.0, 0, 1)
    a *= np.clip((0.55 - depth) / 0.35, 0, 1)      # only the far half of the scene
    a = ndimage.gaussian_filter(a, 2.0)            # soft edges, no hard cut
    return a.astype(np.float32)


def warp_rgb(rgb, xs):
    """Horizontal-only resample with wraparound. Vertical stays put -- the
    camera is documented as nearly fixed vertically (00-vision.md)."""
    h, w, _ = rgb.shape
    xi = np.floor(xs).astype(np.int32)
    fx = (xs - xi)[..., None]
    x0, x1 = xi % w, (xi + 1) % w
    rows = np.arange(h)[:, None]
    a = rgb[rows, x0]
    b = rgb[rows, x1]
    return a * (1 - fx) + b * fx


def main():
    rgb = np.array(Image.open(SCENE).convert("RGB"))
    depth = np.array(Image.open(DEPTH).convert("L")).astype(np.float32) / 255
    h, w, _ = rgb.shape
    alpha = mist_alpha(rgb, depth)

    # the mist plate is the scene recoloured towards veil-cream, so drifting it
    # over the base adds air rather than pasting a rectangle
    veil = (rgb.astype(np.float32) * 0.35 +
            np.array([246, 243, 232], np.float32) * 0.65)

    print(f"{w}x{h}  pan {PAN_PX_S}px/s  mist {MIST_PX_S}px/s")
    print(f"mist alpha coverage: {alpha.mean()*100:.1f}% of frame")

    frames = []
    for i in range(FPS * SECONDS):
        t = i / FPS
        base_shift = PAN_PX_S * t
        mist_shift = (PAN_PX_S + MIST_PX_S) * t     # drifts faster than the base

        xs = (np.arange(w)[None, :] - base_shift)
        base = warp_rgb(rgb.astype(np.float32), np.mod(xs, w))

        mxs = np.mod(np.arange(w)[None, :] - mist_shift, w)
        mist_rgb = warp_rgb(veil, mxs)
        mist_a = np.roll(alpha, -int(round(mist_shift)) % w, axis=1)[..., None]

        frames.append(np.clip(base * (1 - mist_a) + mist_rgb * mist_a,
                              0, 255).astype(np.uint8))

    OUT.mkdir(parents=True, exist_ok=True)
    gif = [Image.fromarray(f) for f in frames]
    gif[0].save(OUT / "pan_mist.gif", save_all=True, append_images=gif[1:],
                duration=1000 // FPS, loop=0)

    picks = [0, 8, 16, 23]
    pad = 6
    sheet = Image.new("RGB", (len(picks) * (w + pad) + pad, h + pad * 2),
                      (22, 22, 26))
    for j, s in enumerate(picks):
        sheet.paste(Image.fromarray(frames[min(len(frames) - 1, s * FPS)]),
                    (pad + j * (w + pad), pad))
    sheet.save(OUT / "pan_mist.png")
    print(f"wrote {OUT}/pan_mist.gif and pan_mist.png")


if __name__ == "__main__":
    main()
