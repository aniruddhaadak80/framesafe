# The audit caught the engine, not the clip

The `continuity` audit exists to hold motion designers to a number they declared. During the
first full render of the library it failed on `orbit-grid`, and the clip was innocent.

## What happened

`orbit-grid` declared `continuityBudget: 0.2` and peaked at `0.211` between frames 129 and 130 —
a one-frame cliff of 0.208 of mean relative luminance. A grid that fades out over 900 ms should
not produce that. The fix belonged in the engine.

`ClipPlan.out_progress` returned `curve(elapsed / ease_out)`: the eased _exit_ progress, which
runs 0 → 1 as the layer leaves. `progress()` multiplies `in_progress` by it, so the product
collapsed to zero on the **first frame** of the exit. Every layer in every clip was disappearing
instantly instead of easing out. The gradient looked plausible; the arithmetic did not.

## Why no test caught it first

There was no test for `out_progress` before this. The curve was correct on its own terms — the
bug was in the _contract_ between two functions, which is exactly the class of defect unit tests
of each piece miss.

The fix was to return the remaining share instead: `1 - curve(q)`.

## What exists now

`services/engine/tests/test_plan.py` asserts the contract directly:

- `out_progress` is 1.0 through the hold, and only then decreases
- it never increases
- the first frame after the hold is already strictly below the hold value (the cliff guard)
- a window that elapses inside the clip reaches exactly 0.0

## The lesson worth keeping

An audit that has never failed is not evidence of quality. The same logic applies to the audit:
`flash-strobe` and `continuity-breach` ship with failing verdicts so that a future change to the
thresholds has something to reject.

If you loosen a threshold to make a clip pass, ask which of the two you were wrong about.
