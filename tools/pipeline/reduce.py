"""Reduce a generated master image to a true pixel-art asset.

    python3 tools/pipeline/reduce.py docs/refs/master-candidate-01.png --colors 32 --tag c01

Order matters and was established empirically:

  1. CROP        to a size that divides by an integer factor.
  2. QUANTISE    to the palette WHILE STILL AT FULL RESOLUTION.
  3. MODE-FILTER each NxN block down to one pixel.

Step 2 must precede step 3. A generated image has ~87k unique colours, so "most
common colour in this 3x3 block" is meaningless on raw pixels -- every pixel is a
unique colour and the mode is a coin flip. Quantise first, then the mode is a real
majority vote over palette indices, which preserves the pixel decisions the image
already made. Averaging instead would invent colours in neither the source nor
the palette.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

SRC = Path("docs/refs/master-candidate-01.png")
OUT = Path("out")


def crop_to_factor(im, target_w, target_h, factor):
    """Centre-crop so the result divides by `factor` exactly."""
    want_w, want_h = target_w * factor, target_h * factor
    w, h = im.size
    if want_w > w or want_h > h:
        raise SystemExit(f"source {w}x{h} is smaller than {want_w}x{want_h}")
    left, top = (w - want_w) // 2, (h - want_h) // 2
    return im.crop((left, top, left + want_w, top + want_h)), (left, top)


def quantise(im, colors):
    """Adaptive palette, no dither. Dither would survive as visible noise."""
    return im.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.NONE)


def mode_downsample(idx, colors, factor):
    """Majority vote per factor x factor block, on palette indices.

    The centre pixel is weighted x3 so a 1px feature (a thin spire, a strata
    line) survives instead of being outvoted by its background, and so ties
    break toward the middle of the block rather than an arbitrary index.
    """
    h, w = idx.shape
    oh, ow = h // factor, w // factor
    blocks = idx[:oh * factor, :ow * factor].reshape(oh, factor, ow, factor)
    blocks = blocks.transpose(0, 2, 1, 3).reshape(oh, ow, factor * factor)

    counts = np.zeros((oh, ow, colors), dtype=np.int16)
    for c in range(colors):
        counts[..., c] = (blocks == c).sum(axis=2)

    if factor % 2 == 1:
        mid = (factor * factor) // 2
        ys, xs = np.arange(oh)[:, None], np.arange(ow)[None, :]
        np.add.at(counts, (ys, xs, blocks[:, :, mid]), 3)

    return counts.argmax(axis=2).astype(np.uint8)


def audit(rgb, palette, name):
    """The acceptance gates, adapted for generated art."""
    h, w, _ = rgb.shape
    flat = rgb.reshape(-1, 3)
    cols, cnt = np.unique(flat, axis=0, return_counts=True)
    n = flat.shape[0]

    pset = set(map(tuple, palette.tolist()))
    stray = [c for c in map(tuple, cols.tolist()) if c not in pset]

    largest = cnt.max() / n * 100
    r = flat[:, 0].astype(np.int16)
    b = flat[:, 2].astype(np.int16)
    warm = ((r - b) >= 8).mean() * 100

    lum = rgb.astype(np.int16) @ np.array([299, 587, 114]) // 1000

    # A "seam" is a long straight run of column-to-column change that is BOTH
    # long and HIGH-CONTRAST. A low-contrast run is an authored vertical fissure
    # in the rock, which is the style, not a defect; a barcode is a strong value
    # step held dead straight. Both numbers are reported.
    seam = seam_hi = 0
    seam_hi_x = seam_hi_y = seam_hi_delta = 0
    for x in range(w - 1):
        run = run_hi = 0
        same = (rgb[:, x] != rgb[:, x + 1]).any(axis=1)
        delta = np.abs(lum[:, x] - lum[:, x + 1])
        for y in range(h):
            if same[y]:
                run += 1
                run_hi = run_hi + 1 if delta[y] >= 20 else 0
            else:
                run = run_hi = 0
            if run > seam:
                seam = run
            if run_hi > seam_hi:
                seam_hi, seam_hi_x, seam_hi_y = run_hi, x, y
                seam_hi_delta = int(delta[y])

    # A single high-change row is a legitimate horizon (the waterline). Banding
    # is many adjacent rows all high-change, i.e. a repeating scanline family.
    rowcounts = np.array([int((rgb[y] != rgb[y - 1]).any(axis=1).sum())
                          for y in range(1, h)])
    rowch = int(rowcounts.max())
    banded = int((rowcounts > 190).sum())
    run_band = run = 0
    for c in rowcounts > 190:
        run = run + 1 if c else 0
        run_band = max(run_band, int(run))

    print(f"\n=== audit {name} ===")
    print(f"  colours used       {len(cols)} (palette {len(palette)})")
    print(f"  stray colours      {len(stray)}")
    print(f"  largest flat field {largest:.2f}%   (<=22)")
    print(f"  warm pixels        {warm:.2f}%   (>=8)")
    print(f"  worst row change   {rowch}   (single horizon is legitimate)")
    print(f"  banded rows >190   {banded}   (longest consecutive run {run_band})")
    print(f"  seam (any)         {seam}px")
    print(f"  seam (high-contrast) {seam_hi}px at x={seam_hi_x} y_end={seam_hi_y} "
          f"(delta {seam_hi_delta})")

    auto = {
        "no stray colours": len(stray) == 0,
        "flat field <=22%": largest <= 22,
        "warm >=8%": warm >= 8,
    }
    # Seam and banding cannot be decided by threshold: a karst fissure, a
    # waterfall ribbon, a horizon and a barcode all produce the same numbers.
    # They are reported with coordinates so a human looks at the exact pixel.
    review = {
        "seam<=24 or confirmed feature": seam_hi <= 24,
        "banding<=2 or confirmed feature": run_band <= 2,
    }
    print("\n  automatic: " + "  ".join(
        ("PASS " if v else "FAIL ") + k for k, v in auto.items()))
    print("  needs eyes: " + "  ".join(
        ("OK   " if v else "LOOK ") + k for k, v in review.items()))
    print("  -> zoom the reported coordinates at 6x before deciding they are wrong.")
    return dict(largest=largest, warm=warm, seam=seam, seam_hi=seam_hi,
                rowch=rowch, banded=banded, run_band=run_band,
                stray=len(stray), ncolours=len(cols))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src", nargs="?", default=str(SRC))
    ap.add_argument("--colors", type=int, default=24)
    ap.add_argument("--target", default="480x270")
    ap.add_argument("--factor", type=int, default=3)
    ap.add_argument("--tag", default="c01")
    args = ap.parse_args()

    tw, th = map(int, args.target.split("x"))
    src = Image.open(args.src).convert("RGB")
    print(f"source {src.size[0]}x{src.size[1]}")

    cropped, origin = crop_to_factor(src, tw, th, args.factor)
    print(f"cropped {cropped.size[0]}x{cropped.size[1]} "
          f"(offset {origin[0]},{origin[1]})  -> /{args.factor} = {tw}x{th}")

    q = quantise(cropped, args.colors)
    palette = np.array(q.getpalette()[: args.colors * 3], dtype=np.uint8).reshape(-1, 3)

    small = mode_downsample(np.array(q), args.colors, args.factor)
    assert small.shape == (th, tw), small.shape

    rgb = palette[small]
    audit(rgb, palette, f"{args.tag} {args.colors}c")

    OUT.mkdir(exist_ok=True)
    img = Image.fromarray(rgb, "RGB")
    img.save(OUT / f"reduced_{args.tag}_{args.colors}c.png")
    img.resize((tw * 2, th * 2), Image.NEAREST).save(
        OUT / f"reduced_{args.tag}_{args.colors}c_2x.png")
    img.resize((tw * 4, th * 4), Image.NEAREST).save(
        OUT / f"reduced_{args.tag}_{args.colors}c_4x.png")
    print(f"\nwrote out/reduced_{args.tag}_{args.colors}c*.png")


if __name__ == "__main__":
    sys.exit(main())
