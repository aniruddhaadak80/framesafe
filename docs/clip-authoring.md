# Clip authoring

A clip is a JSON document. It describes **timings**, not pixels: what is on screen, when it
arrives, how it leaves, and on which easing curve. `framesafe` renders it.

The shortest route is `skills/author-a-clip/SKILL.md`. This page is the reference it points at.

## The document

```jsonc
{
  "id": "title-block", // must match the directory name
  "title": "Kinetic stroke type",
  "summary": "One sentence, shown on the gallery.",
  "technique": ["kinetic-type", "stroke-draw"], // at least one
  "tags": ["type", "draw-on"],
  "fps": 24,
  "width": 1280,
  "height": 720,
  "durationMs": 6000, // frameCount = round(durationMs * fps / 1000)
  "supersample": 2, // drawn at 2x and box-filtered down
  "background": "ink",
  "continuityBudget": 0.16, // max mean |luma change| per adjacent frame pair
  "maxAdjacentContrast": 0.6,
  "reducedMotion": { "holdFrame": 96, "note": "why this frame is a fair still" },
  "layers": [/* see below */],
}
```

Defaults are materialised during validation, which means the digest covers them: two specs that
draw identically digest identically.

## A layer

```jsonc
{
  "kind": "text",
  "name": "wordmark", // kebab-case, unique enough to read in a manifest
  "t": { "startMs": 500, "inMs": 1700, "holdMs": 3100, "outMs": 600, "easing": "easeInOutCubic" },
  "reveal": "draw",
  "stroke": "accent",
  "strokeWidth": 4,
  "text": "FRAMESAFE",
  "x": 640,
  "y": 250,
  "scale": 17,
  "align": "center",
  "stagger": 0.09,
}
```

- `t` is the window. A window with `inMs`, `holdMs` and `outMs` all zero is rejected: the layer
  would never appear.
- `easing` may be any name from `CURVES`, or `steps(n)` to quantise. `steps(1)` is how the
  `reduced-motion` clip builds its static half.
- `reveal` must be legal for the kind. `check:clip-specs` prints the legal set when it is not.
- `fill` or `stroke` (or both). Palette names or `#rrggbb`.

### Progress

A layer's progress at frame _i_ is `in_progress(i) * out_progress(i)`, both derived from the
frame index and the frame rate. There is no clock, so `progress(layer, 96)` is the same number
in every process on every machine. Reveals are driven by that scalar, and `opacity` follows it
too — except for `draw` and `mask`, where the visible _length_ is the progress indicator and
fading the stroke as well would hide the motion the clip exists to show.

### Layer kinds

| Kind         | Required                  | Typical extras                                             | Reveals                                                       |
| ------------ | ------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------- |
| `background` | –                         | `fill`                                                     | `fade`, `hold`                                                |
| `rect`       | `x`, `y`, `w`, `h`        | `radius`, `rotation`                                       | `fade`, `hold`, `scale`, `wipeX`, `wipeY`, `slideX`, `slideY` |
| `line`       | `x1`, `y1`, `x2`, `y2`    | –                                                          | `draw`, `hold`, `wipeX`, `fade`                               |
| `polyline`   | `points`                  | –                                                          | `draw`, `hold`, `wipeX`, `fade`                               |
| `polygon`    | `cx`, `cy`, `r`           | `sides`, `exponent`, `points`, `to`, `spin`                | `fade`, `hold`, `grow`, `morph`                               |
| `circle`     | `cx`, `cy`, `r`           | `startDeg`, `sweepDeg`                                     | `fade`, `hold`, `grow`, `sweep`, `pulse`                      |
| `rings`      | `cx`, `cy`, `count`       | `fromR`, `toR`, `sweepDeg`, `spin`                         | `expand`, `hold`, `fade`                                      |
| `particles`  | `count`, `seed`           | `cx`, `cy`, `spreadX`, `spreadY`, `drift`, `size`          | `drift`, `hold`, `fade`                                       |
| `bars`       | `count`, `seed`           | `x`, `baseline`, `barWidth`, `gap`, `height`               | `rise`, `hold`, `fade`                                        |
| `grid`       | `x`, `y`, `cols`, `rows`  | `cell`, `gap`                                              | `sweep`, `hold`, `pulse`                                      |
| `text`       | `text`, `x`, `y`, `scale` | `align`, `tracking`, `stagger`, `counterFrom`, `counterTo` | `draw`, `fade`, `hold`, `slideUp`, `mask`                     |
| `guides`     | –                         | `mode`: `safe`, `overscan`, `grid`                         | `fade`, `hold`, `sweep`                                       |
| `strobe`     | `periodMs`                | `dutyCycle`                                                | `flash`                                                       |

Coordinates are canvas units. The renderer applies the supersample factor; do not pre-multiply.

### Determinism rules

- **Time** is `frameIndex / fps`. Nothing in a spec may refer to a clock.
- **Randomness** comes from `seed` through a fixed LCG. Two layers with the same seed produce
  the same field on every machine — which is what lets `starfield-parallax` and `waveform-bars`
  look random and still hash identically.
- **Type** is the stroke font in `services/engine/src/framesafe/glyphs.py`. A character the font
  does not define is rejected with `BAD_GLYPH` rather than silently substituted.
- **Counters** (`counterFrom`/`counterTo`) are a function of progress. An odometer rests on a
  partially rolled wheel unless the value is a multiple of a hundred, which is why
  `counter-roll` counts down to zero.

## The gates

```bash
npm run check:clip-specs     # compiles every spec, checks layout
npm run check:manifests      # manifest agrees with spec, frames, audits and video
```

`check:clip-specs` measures text boxes against the canvas and against each other, because
overlapping captions are invisible in a thumbnail and obvious in the gallery. It found 26 real
layout defects across 13 clips in this repository, and it is the reason the two captions that
overlapped are not.

## Before you publish

`skills/publish-a-clip/SKILL.md` is the checklist. The short version: render, verify, audit,
index, then **look at a frame** with `scripts/preview-frame.py`. A clip that has never been
looked at has not been reviewed.
