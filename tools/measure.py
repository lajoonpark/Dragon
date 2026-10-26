"""Measure a rendered frame against the acceptance gates in the docs.

    python3 tools/measure.py /tmp/frame.raw [--label name]

Reports only what docs/27 divides into "automatic" (objectively decidable) and
"needs eyes" (a pointer, not a verdict):

  contrast        std of luma. c01-parallax-test.md records 67.3 base / 67.9
                  with the drifting veil: the veil must not wash the art out.
  detail          mean |laplacian|, the 'high-frequency detail retained' figure
                  (88% in the same report).
  palette         every pixel must be a step in the locked ramps (D-007, gate 8).
  warm            warm pixels above the mist top (gate 6, scoped per docs/27 --
                  counting the cream mist is how the old gate passed a defect).
  flat field      largest single-colour area (gate: <=22%).
  eyes            longest seam / banding row, WITH coordinates to zoom.
"""

import sys
from pathlib import Path

import numpy as np

W, H = 480, 270


def load(path):
    a = np.fromfile(path, dtype=np.uint8)
    if a.size != W * H * 4:
        raise SystemExit(f"expected raw RGBA 480x270, got {a.size} bytes")
    return a.reshape(H, W, 4)[..., :3]


def palette():
    cols = []
    for ln in Path("assets/palette_c01.txt").read_text().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        h = ln.split()[2].lstrip("#")
        cols.append((int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)))
    return np.array(cols, np.uint8)


def luma(rgb):
    return rgb.astype(np.float32) @ np.array([0.299, 0.587, 0.114], np.float32)


def mist_top(rgb):
    """The highest row carrying real mist, i.e. where the scene stops being sky.

    The warm gate is scoped above this (docs/27): counting cream mist is how the
    original gate reported 33% warm while every rock face was monochrome.
    """
    L = luma(rgb)
    return int(np.argmax([(L[y] > 200).mean() > 0.5 for y in range(0, H, 2)]) * 2)


def main():
    path = sys.argv[1]
    label = path
    if "--label" in sys.argv:
        label = sys.argv[sys.argv.index("--label") + 1]
    rgb = load(path)
    pal = palette()
    L = luma(rgb)

    # --- contrast / detail
    contrast = float(L.std())
    lap = np.abs(4 * L[1:-1, 1:-1] - L[:-2, 1:-1] - L[2:, 1:-1]
                 - L[1:-1, :-2] - L[1:-1, 2:])
    detail = float(lap.mean())

    # --- palette adherence (exact membership in the locked ramps)
    flat = rgb.reshape(-1, 3)
    uniq, counts = np.unique(flat, axis=0, return_counts=True)
    pset = {tuple(c) for c in pal}
    stray = [tuple(c) for c in uniq if tuple(c) not in pset]

    # --- warm above the mist top
    mt = mist_top(rgb)
    r, b = rgb[..., 0].astype(np.int16), rgb[..., 2].astype(np.int16)
    warm_above = float(((r - b >= 8)[:mt]).mean() * 100) if mt > 0 else 0.0

    # --- flat field
    largest = float(counts.max() * 100 / flat.shape[0])

    # --- seams / banding (pointers, not verdicts)
    seam = 0
    seam_at = (0, 0)
    for x in range(W - 1):
        same = (rgb[:, x] != rgb[:, x + 1]).any(axis=1)
        run = 0
        for y in range(H):
            run = run + 1 if same[y] else 0
            if run > seam:
                seam, seam_at = run, (x, y)
    rows = [int((rgb[y] != rgb[y - 1]).any(axis=1).sum()) for y in range(1, H)]

    print(f"=== {label} ===")
    print(f"  colours used      {len(uniq)}")
    print(f"  stray colours     {len(stray)}      {'PASS' if not stray else 'FAIL'}")
    print(f"  contrast (std)    {contrast:6.2f}    target ~67 (veil must not wash)")
    print(f"  detail  (|lap|)   {detail:6.2f}")
    print(f"  warm above mist   {warm_above:5.2f}%   (>=8)  mist top y={mt}")
    print(f"  largest flat      {largest:5.2f}%   (<=22)")
    print(f"  seam              {seam:3d}px at x={seam_at[0]} y_end={seam_at[1]}"
          f"   (eyeball; <=24 or a confirmed feature)")
    print(f"  worst row change  {max(rows)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
