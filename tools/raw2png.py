"""Convert a raw RGBA8888 frame dump into a PNG, for inspection.

    python3 tools/raw2png.py /tmp/frame.raw /tmp/frame.png [--scale 4]
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

def main():
    src, dst = sys.argv[1], sys.argv[2]
    scale = 1
    if "--scale" in sys.argv:
        scale = int(sys.argv[sys.argv.index("--scale") + 1])
    a = np.fromfile(src, dtype=np.uint8)
    if a.size != 480 * 270 * 4:
        raise SystemExit(f"expected {480*270*4} bytes, got {a.size}")
    im = Image.fromarray(a.reshape(270, 480, 4)[..., :3], "RGB")
    if scale > 1:
        im = im.resize((480 * scale, 270 * scale), Image.NEAREST)
    im.save(dst)
    print(f"wrote {dst} {im.size}")

if __name__ == "__main__":
    main()
