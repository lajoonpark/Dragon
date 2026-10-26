"""Prototype: derive candidate background layers from a flat master image.

The point of this file is NOT to produce final art. It is to answer one question
before we commit to a layer strategy:

    if we split the image this way, does re-compositing the layers reproduce
    the original?

That test is cheap and it is decisive. If the reconstruction differs from the
master by more than a little, the split is wrong -- the layers do not actually
contain what is on screen, and anything animated on top of them will expose the
lie. If it reproduces, the split is structurally sound and the remaining work is
hole-filling (backing plates), not guesswork.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

SRC = Path("out/reduced_c01_24c.png")

# Bands, far to near. Thresholds are on component MEAN luminance: a mass's
# average value is its atmospheric depth, even though its lit faces are bright.
# Per-pixel luminance is NOT a depth signal (a lit near cliff is paler than a
# shadowed far ridge), which is why the segmentation is by connectivity first.
BANDS = [(172, 0), (160, 1), (145, 2), (118, 3), (95, 4), (0, 5)]


def band_for(mean_lum):
    for threshold, band in BANDS:
        if mean_lum > threshold:
            return band
    return 5


def segment(im):
    """Rock masses = dark, connected, above a size floor."""
    lum = (im.astype(np.int16) @ np.array([299, 587, 114]) // 1000)
    rock = lum <= 195
    rock = ndimage.binary_opening(rock, np.ones((2, 2)))
    lab, n = ndimage.label(rock)
    sizes = ndimage.sum(rock, lab, range(1, n + 1))
    return lum, lab, sizes, n


def propose(im, lab, sizes, n, min_px=40):
    """One layer per band. A layer is the union of the masses in that band."""
    h, w = lab.shape
    layers = {}
    for c in range(1, n + 1):
        if sizes[c - 1] < min_px:
            continue
        mask = lab == c
        ml = (im.astype(np.int16) @ np.array([299, 587, 114]) // 1000)[mask].mean()
        b = band_for(ml)
        layers.setdefault(b, []).append(mask)
    out = {}
    for b, masks in layers.items():
        out[b] = np.logical_or.reduce(masks)
    return out


def mist_base(im, lum):
    """Everything not rock becomes a far mist plate. Per-row modal pale colour,
    because mist is a vertical value ramp with a wavy top."""
    h, w = lum.shape
    base = np.zeros_like(im)
    for y in range(h):
        row = im[y]
        pale = row[(lum[y] > 178)]
        if len(pale):
            vals, cnts = np.unique(pale, axis=0, return_counts=True)
            base[y] = vals[cnts.argmax()]
        else:
            base[y] = base[y - 1] if y else (245, 240, 228)
    return base


def composite(im, layers, base, order):
    """Paint base, then layers far to near. Occlusion is plain overdraw."""
    out = base.copy()
    for b in order:
        if b in layers:
            out[layers[b]] = im[layers[b]]
    return out


def diff(a, b):
    d = (a.astype(int) - b.astype(int))
    return np.abs(d).sum(axis=2)


def main():
    src = Path(sys.argv[1]) if len(sys.argv) > 1 else SRC
    im = np.array(Image.open(src).convert("RGB"))
    h, w, _ = im.shape
    lum, lab, sizes, n = segment(im)
    layers = propose(im, lab, sizes, n)
    base = mist_base(im, lum)

    print(f"{src.name}  {w}x{h}")
    print(f"components: {n}, kept {sum(len(v) for v in layers.values())} masses in {len(layers)} bands")
    print("\nband  masses   coverage")
    for b in sorted(layers):
        print(f"  {b}   {len(layers[b]):5d}   {layers[b].mean()*100:5.2f}%")

    order = sorted(layers, reverse=True)  # far first
    comp = composite(im, layers, base, order)
    d = diff(comp, im)
    print(f"\nreconstruction vs master:")
    print(f"  mean abs diff / px  {d.mean():7.2f}")
    print(f"  identical pixels    {(d == 0).mean()*100:7.2f}%")
    print(f"  px off by >30       {(d > 30).mean()*100:7.2f}%")

    out = Path("out")
    out.mkdir(exist_ok=True)
    Image.fromarray(comp).save(out / "layerproposal_composite.png")
    Image.fromarray(base).save(out / "layerproposal_base.png")
    for b in sorted(layers):
        rgba = np.zeros((h, w, 4), np.uint8)
        rgba[..., :3] = im
        rgba[..., 3] = np.where(layers[b], 255, 0)
        Image.fromarray(rgba, "RGBA").save(out / f"layerproposal_band{b}.png")
    # amplified error map
    err = np.clip(d * 3, 0, 255).astype(np.uint8)
    Image.fromarray(err).save(out / "layerproposal_error.png")
    print(f"\nwrote out/layerproposal_*.png")


if __name__ == "__main__":
    main()
