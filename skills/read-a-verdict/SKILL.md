---
name: read-a-verdict
description: Use when a clip fails an audit and you need to decide whether to fix the motion or change the budget, because those are very different kinds of change.
metadata:
  version: 1.0.0
---

# Read a verdict

## When to use this

`framesafe audit` or `framesafe clips` reported `fail`, and you have to decide what to do.

## Steps

1. `framesafe clips --failing` lists only the failing clips.
2. `framesafe audit <id>` prints which audit failed and the reason sentence with real numbers.
   The reason names the frame pair and the measured value, not a label.
3. Decide whether the clip or the budget is wrong. Read the two rules below before editing.
4. Fix the clip, then `framesafe audit <id>` again. Fixing the budget instead is a
   separate decision that belongs in a review, not in a drive-by edit.

## The three audits

| Audit        | Fails when                                                   | Usually fixed by                                                              |
| ------------ | ------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| `flash`      | more than 3 flash reversals in any one-second window         | lengthening the period, dropping the contrast, or removing the `strobe` layer |
| `continuity` | an adjacent frame pair exceeds the clip's `continuityBudget` | easing the transition, or lengthening `outMs`                                 |
| `luminance`  | peak adjacent contrast exceeds `maxAdjacentContrast`         | softening a cut, or raising the ceiling deliberately                          |

## When to raise a budget instead

Raise `continuityBudget` only when the motion you want _is_ the motion the audit objects to
— a designed snap, a hard cut. Do not raise it because a clip is easier to pass. A budget
exists to make "this transition is allowed to be abrupt" an explicit, reviewable statement.

## Failure clips are part of the library

`flash-strobe` and `continuity-breach` ship with failing verdicts on purpose. They are the
negative tests: they prove the audit rejects something. If you make every clip pass, the
audit may have stopped working.

## Verify

- `framesafe audit <id>` exits 1 for a failing clip and prints the reason.
- `framesafe verify <id>` still reproduces every frame digest.
