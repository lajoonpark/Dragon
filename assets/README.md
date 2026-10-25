# assets/

Source-of-truth art, as **plain text**. Never a `.aseprite` binary as the
authority — it produces an opaque diff.

- `silhouettes/*.txt` — one character = one pixel, `.` = transparent.
  Hand-authored (see `docs/25-art-pipeline.md`). Reviewable in a PR.
- `palettes/*.txt` — named ramps, dark -> light. A test fails if any
  rendered pixel is outside a declared ramp.
- `overlays/` — hand-drawn stamps (ledges, cracks, tree bundles) stamped onto
  base silhouettes to make variety without new silhouettes.

Aseprite is used to *draw* these. `.aseprite` files, if kept, live beside the
text exports but are never the source of truth.
