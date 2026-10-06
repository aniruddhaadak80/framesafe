# Layout defects are invisible in thumbnails

Fifteen clips looked finished. A contact sheet of all fifteen at 320px wide showed overlapping
captions, type running past the canvas edge, and two labels sitting on top of each other. None
of it was visible at that size, and all of it was wrong.

## What the gate checks

`scripts/check-clip-specs.py` measures every static text layer:

- its box, from the stroke font's cell width and the layer's `tracking`
- against the canvas, requiring a 5% safe inset (the same rule the `safe-area` clip draws)
- against every other text layer, requiring non-overlap in both axes

It reported **26 problems across 13 of 15 clips**: captions wider than 1280px, a `y` that put a
caption 11px inside the line above it, a footer 5px off the bottom edge.

Counters are exempt — a counter's width depends on its value, not on the spec.

## Why a script and not an eye

Because an eye does not scale and does not remember. The gate is 40 lines, runs in well under a
second, and fails CI. The contact sheet that found these is `scripts/contact-sheet.py`: still a
useful review tool, but a review aid rather than the gate.

## What it does not check

It does not check that a caption is _readable_ — only that two boxes do not intersect. A clip can
pass this gate and still be visually wrong. That is what the single-frame preview is for:

```bash
python scripts/preview-frame.py clips/<id>/spec.json <frame> .preview.png
```

Both tools exist because they catch different things. The gate catches arithmetic; the eye
catches taste.
