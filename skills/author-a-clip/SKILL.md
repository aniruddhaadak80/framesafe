---
name: author-a-clip
description: Use when writing a new motion-graphics clip from scratch, because the spec schema, the layer kinds, and the reveal modes have to be right or the engine rejects the document.
metadata:
  version: 1.0.0
---

# Author a clip

## When to use this

You are adding a new clip under `clips/<id>/spec.json` and it does not exist yet.

## Steps

1. Create `clips/<id>/spec.json`. The directory name and `spec.id` must match exactly, or
   `npm run check:clip-specs` fails.
2. Start from the smallest thing that animates: one `background` layer with
   `"reveal": "hold"`, then add layers. Every layer needs `kind`, `t`, and `reveal`.
3. Give every layer a window: `startMs`, `inMs`, `holdMs`, `outMs`, `easing`. A window with
   `inMs`, `holdMs`, and `outMs` all zero is rejected — the layer would never appear.
4. Choose a reveal the kind actually supports. `check:clip-specs` prints the legal set for
   the kind you used when it does not.
5. Use `reveal: "draw"` for strokes and type, and never rely on `opacity` alone to show
   progress: `draw` and `mask` deliberately keep full opacity so the _length_ carries the
   motion.
6. Keep type inside the safe inset. `check:clip-specs` fails if a text layer leaves the
   5% margin or if two text layers overlap, and it prints the measured pixel overlap.
7. Run `npm run check:clip-specs`. Fix every reported problem before rendering anything.

## Layer kinds

| Kind         | Required fields           | Reveals                                                       |
| ------------ | ------------------------- | ------------------------------------------------------------- |
| `background` | –                         | `fade`, `hold`                                                |
| `rect`       | `x`, `y`, `w`, `h`        | `fade`, `hold`, `scale`, `wipeX`, `wipeY`, `slideX`, `slideY` |
| `line`       | `x1`, `y1`, `x2`, `y2`    | `draw`, `hold`, `wipeX`, `fade`                               |
| `polyline`   | `points`                  | `draw`, `hold`, `wipeX`, `fade`                               |
| `polygon`    | `cx`, `cy`, `r`           | `fade`, `hold`, `grow`, `morph`                               |
| `circle`     | `cx`, `cy`, `r`           | `fade`, `hold`, `grow`, `sweep`, `pulse`                      |
| `rings`      | `cx`, `cy`, `count`       | `expand`, `hold`, `fade`                                      |
| `particles`  | `count`, `seed`           | `drift`, `hold`, `fade`                                       |
| `bars`       | `count`, `seed`           | `rise`, `hold`, `fade`                                        |
| `grid`       | `x`, `y`, `cols`, `rows`  | `sweep`, `hold`, `pulse`                                      |
| `text`       | `text`, `x`, `y`, `scale` | `draw`, `fade`, `hold`, `slideUp`, `mask`                     |
| `guides`     | –                         | `fade`, `hold`, `sweep`                                       |
| `strobe`     | `periodMs`                | `flash`                                                       |

## Determinism rules

- Time is `frameIndex / fps`. There is no clock, so nothing in a spec may reference one.
- Randomness comes from `seed` through a fixed generator. Two layers with the same seed
  produce the same field, every machine, every time.
- Type is a stroke font defined in the engine source, so no system font can change a digest.
- Supersampling is `supersample` (default 2). Coordinates are canvas units and the renderer
  scales them; do not pre-multiply.

## Verify

- `python scripts/check-clip-specs.py` exits 0.
- `node packages/cli/dist/bin.js spec <id>` prints the compiled frame table.
- `node packages/cli/dist/bin.js render <id>` reproduces every digest across both passes.
