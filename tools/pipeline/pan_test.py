"""Compare rigid panning against depth-banded parallax.

THE QUESTION: is a single rigid image enough, or do we need real layers?

Both answers are rendered from the same master and the same depth field, so the
only variable is how horizontal displacement is applied.

  rigid   every pixel moves by the same amount. One plane.
  banded  displacement scales with depth: near content slides faster than far
          content. This is real parallax from a single image, no layers.

WHY INVERSE WARP

The obvious way to do banded parallax is to shift each depth band forward by its
own amount and stack them. That creates HOLES: wherever a near band moves off a
far band, an uncovered strip appears -- and fixing it needs backing plates,
which is the whole expensive problem we are trying to avoid.

The inverse formulation has no holes, by construction. For every OUTPUT pixel we
ask "how far does content at this depth have travelled?" and sample the source
there:

    out[x] = src[x - shift(depth[x])]

Every output pixel is filled because every output pixel does its own lookup.
There is nothing to uncover. This is why the hole problem simply does not arise,
and it is the finding worth keeping from this test.

Cost: content is stretched/compressed slightly where depth changes abruptly.
At 7 px/s over a few minutes this is a sub-pixel concern in the mist, which is
where depth transitions actually happen.
"""

from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SCENE = Path("out/reduced_c01_24c.png")
DEPTH = Path("out/depth_c01.png")
OUT = Path("out/pan")

PAN_PX_S = 7.0          # docs/30-scene-composition.md
FPS = 12
SECONDS = 24
NEAR_GAIN = 0.15        # depth 0.0 travels at 15% of pan speed
NEAR_SPAN = 0.85        # depth 1.0 travels at 100%
WARP_SIGMA = 10.0       # smoothing applied to the depth field FOR WARPING ONLY


def shift_for(depth):
    """Displacement per pixel given depth. Near travels faster."""
    return PAN_PX_S * (NEAR_GAIN + NEAR_SPAN * depth)


def pan_rigid(scene, t):
    """One plane. The whole image slides together."""
    return np.roll(scene, -int(round(PAN_PX_S * t)), axis=1)


def pan_banded(scene, depth, t):
    """Per-depth displacement, inverse-warped. No holes possible."""
    h, w, _ = scene.shape
    shift = PAN_PX_S * t * (NEAR_GAIN + NEAR_SPAN * depth)   # (h, w)
    xs = (np.arange(w)[None, :] - shift).round().astype(np.int32)
    xs = np.clip(xs, 0, w - 1)
    rows = np.arange(h)[:, None]
    return scene[rows, xs]


def make_gif(frames, path, ms):
    pil = [Image.fromarray(f) for f in frames]
    pil[0].save(path, save_all=True, append_images=pil[1:],
                duration=ms, loop=0, optimize=True)


def diff_metric(a, b):
    d = np.abs(a.astype(int) - b.astype(int)).sum(axis=2)
    return d.mean(), (d > 0).mean() * 100


def main():
    scene = np.array(Image.open(SCENE).convert("RGB"))
    depth = np.array(Image.open(DEPTH).convert("L")).astype(np.float32) / 255
    h, w, _ = scene.shape

    # The depth field has to do two jobs that want opposite things:
    #   occlusion -> wants SHARP edges (a dragon is either behind a ridge or not)
    #   parallax  -> wants SMOOTH gradients (a hard edge becomes a tear)
    # 4603 pixels have a >0.4 horizontal depth jump; at 143px of shift that is a
    # 57px rip. So warp with a smoothed copy and keep the sharp one for depth
    # testing. Blurring the warp field costs nothing visually -- it only moves
    # where the stretch happens.
    warp_depth = ndimage.gaussian_filter(depth, WARP_SIGMA)

    OUT.mkdir(parents=True, exist_ok=True)

    n = FPS * SECONDS
    rigid, banded = [], []
    for i in range(n):
        t = i / FPS
        rigid.append(pan_rigid(scene, t))
        banded.append(pan_banded(scene, warp_depth, t))

    print(f"{w}x{h}  pan {PAN_PX_S}px/s  {SECONDS}s @ {FPS}fps = {n} frames")

    # how much do the two differ, and monotonic over time?
    print("\n rigid vs banded (mean abs diff per px, % px changed):")
    for secs in (0, 5, 10, 20, 24):
        i = min(n - 1, secs * FPS)
        m, pct = diff_metric(rigid[i], banded[i])
        print(f"   t={secs:2d}s   {m:6.2f}   {pct:5.1f}%")
    assert diff_metric(rigid[-1], banded[-1])[0] > 1.0, \
        "banded and rigid look identical: parallax is not being applied"

    # differential displacement, which is the thing viewers actually perceive
    print("\n differential (near vs far content, cumulatively):")
    for secs in (5, 10, 20, 24):
        dn = shift_for(0.84) * secs
        df = shift_for(0.24) * secs
        print(f"   t={secs:2d}s   near {dn:5.1f}px  far {df:5.1f}px  "
              f"separation {dn-df:5.1f}px")

    # seamless loop check: a roll is seamless, an inverse warp is not
    wrap_r = diff_metric(rigid[-1], rigid[0])[0]
    wrap_b = diff_metric(banded[-1], banded[0])[0]
    print(f"\n loop seam (last vs first frame): rigid {wrap_r:.2f}  banded {wrap_b:.2f}")

    make_gif(rigid, OUT / "pan_rigid.gif", 1000 // FPS)
    make_gif(banded, OUT / "pan_banded.gif", 1000 // FPS)
    print(f"\nwrote {OUT}/pan_rigid.gif and pan_banded.gif")

    # sampled stills for a side-by-side contact sheet
    picks = [0, 8, 16, 23]
    pad = 6
    sheet = Image.new("RGB", (len(picks) * (w + pad) + pad, 2 * (h + pad) + pad),
                      (22, 22, 26))
    for j, s in enumerate(picks):
        i = min(n - 1, s * FPS)
        sheet.paste(Image.fromarray(rigid[i]), (pad + j * (w + pad), pad))
        sheet.paste(Image.fromarray(banded[i]),
                    (pad + j * (w + pad), pad * 2 + h))
    sheet.save(OUT / "pan_compare.png")
    print(f"wrote {OUT}/pan_compare.png (top row rigid, bottom row banded)")


if __name__ == "__main__":
    main()
