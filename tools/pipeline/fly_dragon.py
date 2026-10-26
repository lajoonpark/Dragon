"""Validate the depth field by flying a dragon through it.

PROVES: a single continuous dragon body can be partly in front of the scenery
and partly behind it, with no layer stack and no per-dragon mask -- just one
depth test per pixel. That is D-001, and it is the mechanic the whole project
depends on.

CONVENTION (matches docs/10-depth-and-occlusion.md after the fix)
    0.0 = infinitely far (sky)        1.0 = at the glass
    occluded when  dragon_depth < scene_depth
A dragon at 0.30 is BEHIND rock at 0.60. Flight toward the viewer INCREASES
depth. The diagram in the doc had this inverted; the assertions here exist to
catch that if it ever flips again.

THE TEST SHOT
The scene has a mid-depth spire at x 232-282, y 94-157 (depth ~0.47) with fully
open mist at x 282-340 (depth ~0.15). A dragon flying right-to-left at depth
0.42 through that is visible in the open air, then swallowed by the spire, then
re-emerges. Mid-sweep, both halves are on screen at once.
"""

from pathlib import Path

import numpy as np
from PIL import Image

SCENE = Path("out/reduced_c01_24c.png")
DEPTH = Path("out/depth_c01.png")
OUT = Path("out")

FAR, MID, NEAR = (np.array(c, np.float32) for c in
                  ([206, 214, 208], [104, 148, 132], [22, 52, 50]))
LIT = np.array([150, 195, 175], np.float32)

GHOST_ALPHA = 0.30
GHOST_MAX_SCENE_DEPTH = 0.40     # ghost against mist only, never solid rock

DRAGON_DEPTH = 0.42


def dist_to_polyline(xx, yy, px, py):
    best = np.full(xx.shape, 1e9, np.float32)
    best_s = np.zeros(xx.shape, np.float32)
    for i in range(len(px) - 1):
        ax, ay, bx, by = px[i], py[i], px[i + 1], py[i + 1]
        vx, vy = bx - ax, by - ay
        l2 = vx * vx + vy * vy
        if l2 < 1e-6:
            continue
        t = np.clip(((xx - ax) * vx + (yy - ay) * vy) / l2, 0, 1)
        d = np.hypot(xx - (ax + t * vx), yy - (ay + t * vy))
        upd = d < best - 1e-4
        best = np.where(upd, d, best)
        best_s = np.where(upd, (i + t) / (len(px) - 1), best_s)
    return best, best_s


def make_dragon(body_depth, width=210, height=120):
    """Serpentine body. `body_depth` may be a scalar or an array sampled along
    the spine (head -> tail), so depth can vary down one body."""
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)

    n = 72
    s = np.linspace(0, 1, n)
    px = 8 + s * (width - 16)
    py = height / 2 + np.sin(s * np.pi * 1.6 - 0.5) * 27

    d_px, d_s = dist_to_polyline(xx, yy, px, py)
    thickness = 4.2 * (1.0 - 0.72 * d_s)
    mask = d_px <= thickness

    head = (xx - px[0]) ** 2 + (yy - py[0]) ** 2 <= 6.4 ** 2
    mask |= head

    if np.isscalar(body_depth):
        dmap = np.full((height, width), float(body_depth), np.float32)
    else:
        idx = np.clip((d_s * (len(body_depth) - 1)).astype(int),
                      0, len(body_depth) - 1)
        dmap = np.asarray(body_depth, np.float32)[idx]

    t = np.clip((dmap - 0.10) / 0.40, 0, 1)[..., None]
    colour = np.where(t < 0.5,
                      FAR + (MID - FAR) * (t / 0.5),
                      MID + (NEAR - MID) * ((t - 0.5) / 0.5))

    spine_y = py[np.clip((d_s * (n - 1)).astype(int), 0, n - 1)]
    lit = mask & (yy < spine_y - 1.0)
    colour = np.where(lit[..., None], colour * 0.45 + LIT * 0.55, colour)

    return mask, colour.astype(np.float32), dmap


def render(scene, depth, mask, colour, dmap, x, y):
    """The entire renderer. Stateless: always composited onto the clean scene --
    an earlier version accumulated onto the previous frame and the ghost pass
    built up into a washed rectangular slab."""
    sh, sw = scene.shape[:2]
    dh, dw = mask.shape
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(sw, x + dw), min(sh, y + dh)
    if x1 <= x0 or y1 <= y0:
        return scene.copy(), 0, 0

    sub_m = mask[y0 - y:y1 - y, x0 - x:x1 - x]
    sub_c = colour[y0 - y:y1 - y, x0 - x:x1 - x]
    sub_d = dmap[y0 - y:y1 - y, x0 - x:x1 - x]
    sub_scene_d = depth[y0:y1, x0:x1]

    out = scene.copy()
    region = out[y0:y1, x0:x1].astype(np.float32)

    front = sub_m & (sub_d >= sub_scene_d)
    behind = sub_m & (sub_d < sub_scene_d)

    ghost = behind & (sub_scene_d < GHOST_MAX_SCENE_DEPTH)
    region[ghost] = region[ghost] * (1 - GHOST_ALPHA) + sub_c[ghost] * GHOST_ALPHA
    region[front] = sub_c[front]

    out[y0:y1, x0:x1] = np.clip(region, 0, 255).astype(np.uint8)
    return out, int(front.sum()), int(behind.sum())


def check_convention(depth):
    flat = depth.ravel()
    sky = flat[flat < 0.10]
    near = flat[flat > 0.80]
    assert sky.size > 1000 and near.size > 1000, "depth field looks broken"
    sky_d, near_d = float(sky.mean()), float(near.mean())

    print("depth convention")
    print(f"  sky  {sky_d:.3f}  ({sky.size*100/flat.size:4.1f}% of frame)")
    print(f"  near {near_d:.3f}  ({near.size*100/flat.size:4.1f}% of frame)")
    print(f"  spread {near_d-sky_d:.3f}")
    assert sky_d < 0.10 and near_d > 0.80 and near_d - sky_d > 0.6

    assert DRAGON_DEPTH > sky_d, "dragon must be IN FRONT of sky"
    assert DRAGON_DEPTH < near_d, "dragon must be BEHIND near rock"
    print(f"  dragon@{DRAGON_DEPTH}: in front of sky, behind near rock     OK")


def main():
    scene = np.array(Image.open(SCENE).convert("RGB"))
    depth = np.array(Image.open(DEPTH).convert("L")).astype(np.float32) / 255
    sh, sw, _ = scene.shape
    check_convention(depth)

    mask, colour, dmap = make_dragon(DRAGON_DEPTH)
    dh, dw = mask.shape
    spine_y = 112 - dh // 2

    frames, stats = [], []
    steps = 10
    for i in range(steps):
        t = i / (steps - 1)
        x = int(345 - t * 215)
        frame, front, behind = render(scene, depth, mask, colour, dmap, x, spine_y)
        frames.append(frame)
        stats.append((t, x, front, behind))

    print("\n  t     x    in front  occluded   verdict")
    for t, x, f, b in stats:
        v = "straddling" if f > 40 and b > 40 else (
            "fully visible" if b <= 40 else "fully behind")
        print(f"  {t:4.2f}  {x:4d}  {f:7d}  {b:8d}   {v}")

    straddle = [s for s in stats if s[2] > 40 and s[3] > 40]
    print(f"\n  frames where ONE body is both in front of and behind scenery: "
          f"{len(straddle)}/{len(stats)}")
    assert len(straddle) >= 3, "body never straddles an edge: test is inert"
    print("  depth-sorted occlusion works on a single unbroken body      OK")

    OUT.mkdir(exist_ok=True)
    cols = 5
    rows = (len(frames) + cols - 1) // cols
    pad = 6
    sheet = Image.new("RGB", (cols * (sw + pad) + pad, rows * (sh + pad) + pad),
                      (22, 22, 26))
    for i, f in enumerate(frames):
        sheet.paste(Image.fromarray(f), (pad + (i % cols) * (sw + pad),
                                         pad + (i // cols) * (sh + pad)))
    sheet.save(OUT / "dragon_depth_test.png")

    zt = [i for i, s in enumerate(stats) if s[2] > 40 and s[3] > 40]
    if zt:
        mid = zt[len(zt) // 2]
        zs = Image.fromarray(frames[mid][60:200, 170:420])
        zs = zs.resize((zs.width * 3, zs.height * 3), Image.NEAREST)
        zs.save(OUT / "dragon_depth_test_zoom.png")

    gif = [Image.fromarray(f) for f in frames]
    gif[0].save(OUT / "dragon_depth_test.gif", save_all=True,
                append_images=gif[1:], duration=140, loop=0)
    print("\nwrote out/dragon_depth_test.png, _zoom.png, .gif")


if __name__ == "__main__":
    main()
