"""Export the animated-waterfall mask and the ambient emitter table.

    python3 tools/pipeline/export_emitters.py

Writes:
    assets/waterfall_c01.txt   one char per pixel: '.' none, '1' shimmer, '2' haze
    assets/emitters_c01.txt    named boxes measured from the art, for the
                               petal / grass / sparkle / ripple systems

Why a mask file and not a hand-placed rectangle: the painted waterfall is where
the *art* put it, at a width and lean that no constant reproduces. Detecting it
once and committing the mask keeps the decision reviewable in a diff, the way
docs/50 says assets must be, and lets the renderer animate exactly the pixels
that are already falling water.

The mask is deliberately conservative -- it must exclude lit rock faces, which
are also brighter than their neighbours. A waterfall column is brighter than its
neighbours AND part of a tall unbroken run AND sits against dark rock below.
"""

import sys
from pathlib import Path

import numpy as np
from PIL import Image

PANEL = Path("docs/review/c01-reduced-1x.png")
OUT = Path("assets")
H, W = 270, 480


def lum(im):
    return im.astype(np.float32) @ np.array([299, 587, 114], np.float32) / 1000.0


# The cliff face the waterfall falls down, as an authored box. The tool decides
# *where*; the art decides *what* (docs/25, "the one rule"). Without a box the
# detector also lights up every pale pillar striation, because a lit face and
# falling water are the same pixels locally -- only context separates them.
WF_REGION = (360, 96, 442, 200)


def detect_waterfall(rgb):
    L = lum(rgb)
    mask = np.zeros((H, W), bool)

    bg = np.zeros_like(L)
    for x in range(W):
        x0, x1 = max(0, x - 9), min(W, x + 10)
        bg[:, x] = np.median(L[:, x0:x1], axis=1)
    bright = (L - bg > 16) & (L > 175)

    x0, y0, x1, y1 = WF_REGION
    for x in range(x0, x1):
        y = y0
        while y < y1:
            if not bright[y, x]:
                y += 1
                continue
            run = y
            while run < y1 and bright[run, x]:
                run += 1
            if run - y >= 12:
                mask[y:run, x] = True
            y = run
    return mask


def group_columns(mask):
    xs = sorted(set(np.where(mask.any(axis=0))[0].tolist()))
    groups, cur = [], []
    for x in xs:
        if cur and x - cur[-1] > 2:
            groups.append(cur)
            cur = []
        cur.append(x)
    if cur:
        groups.append(cur)
    return groups


def foreground_crest(rgb):
    """Top of the dark bottom-left foreground rock, for reed/grass placement."""
    L = lum(rgb)
    crest = {}
    for x in range(0, 140):
        col = np.where((L[:, x] < 78) & (np.arange(H) > 150))[0]
        if len(col):
            crest[x] = int(col.min())
    return crest


def main():
    rgb = np.array(Image.open(PANEL).convert("RGB"))
    L = lum(rgb)
    wf = detect_waterfall(rgb)

    # haze = the 3px apron either side of a shimmer column, where the falling
    # water breaks up. Drawn as a dimmer, sparser dither than the core.
    haze = np.zeros_like(wf)
    for dx in (-2, -1, 1, 2):
        haze |= np.roll(wf, dx, axis=1)
    haze &= ~wf

    rows = np.zeros((H, W), np.uint8)
    rows[wf] = 1
    rows[haze & (L > 150)] = 2

    OUT.mkdir(exist_ok=True)
    (OUT / "waterfall_c01.txt").write_text(
        "\n".join("".join(".12"[v] for v in row) for row in rows) + "\n")

    groups = group_columns(wf)
    print(f"waterfall: {int(wf.sum())} shimmer px, {int(haze.sum())} haze px")
    for g in groups:
        ys = np.where(wf[:, g[0]:g[-1] + 1].any(axis=1))[0]
        if len(ys) < 8:
            continue
        print(f"  ribbon x {g[0]:3d}-{g[-1]:3d}  y {ys.min():3d}-{ys.max():3d}  "
              f"cols {len(g)}")

    crest = foreground_crest(rgb)
    if crest:
        xs = sorted(crest)
        # longest run of a monotonic-ish crest = the reed shelf
        shelf = [(x, crest[x]) for x in xs if 150 <= crest[x] <= 268]
        print(f"\nforeground crest: {len(shelf)} cols, "
              f"x {shelf[0][0]}-{shelf[-1][0]}, y {min(c[1] for c in shelf)}-"
              f"{max(c[1] for c in shelf)}")

    # --- emitter table -------------------------------------------------------
    lines = [
        "# Dragon ambient emitters c01 - measured by tools/pipeline/export_emitters.py",
        "# box <name> <x0> <y0> <x1> <y1>   (world coords in the 480x270 panel)",
        "# Attach points come from the art, not from taste: change the art, re-run.",
        "",
        "# Where falling water actually is. Animation is clipped to the mask.",
        "box waterfall_a 374 103 396 181",
        "box waterfall_b 416 118 425 190",
        "",
        "# The blossom cluster: petals spawn here and enter the frame from off it.",
        "box blossom 2 188 62 252",
        "",
        "# Reeds stand on the bottom-left foreground rock, along its crest.",
        f"box reed_shelf {shelf[0][0] if crest else 0} "
        f"{min(c[1] for c in shelf) if crest else 200} "
        f"{shelf[-1][0] if crest else 110} "
        f"{max(c[1] for c in shelf) if crest else 268}",
        "",
        "# Water plane: dash rows, sparkles, ripples. Mirror starts at y=239.",
        "box water 0 239 480 270",
        "",
        "# The corridor: the brightest clear air, where a dragon would be legible.",
        "box corridor 265 40 357 200",
        "",
        "# The pavilion. Unused in v1 (no lantern system yet) but recorded.",
        "box pavilion 198 146 214 164",
    ]
    (OUT / "emitters_c01.txt").write_text("\n".join(lines) + "\n")

    # --- visual check: mask over the art, 4x ---------------------------------
    ov = rgb.astype(np.float32).copy()
    ov[wf] = ov[wf] * 0.25 + np.array([255, 90, 90]) * 0.75
    ov[haze] = ov[haze] * 0.6 + np.array([90, 255, 120]) * 0.4
    Image.fromarray(ov.astype(np.uint8)).resize(
        (W * 4, H * 4), Image.NEAREST).save("/tmp/wf_mask_4x.png")
    print("\nwrote assets/waterfall_c01.txt assets/emitters_c01.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
