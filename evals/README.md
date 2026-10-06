# Evals

`evals/cases.json` is a scored suite of real clip specs with the verdict and failing audits each
one must produce. `framesafe` renders every case and compares.

```bash
npm run evals
npm run evals -- --json
```

```
  case                  verdict   audits              result
  calm-fade             pass     -                  pass
  flash-breach          fail     flash              pass
  teleport-breach       fail     continuity         pass
  contrast-breach       fail     luminance          pass
  monotonic-pulse       pass     -                  pass
  reduced-motion-hold   pass     -                  pass
  double-breach         fail     continuity,flash   pass

  7/7 cases passed (score 1.00)
```

## Why this suite is not a formality

Two of these cases are **negative controls**: they must pass because the audit should _not_ fire.

- `monotonic-pulse` changes luminance on every frame and must still pass flash. The flash audit
  counts polarity _reversals_, not deltas, so an audit that merely counted large changes would
  fail this case. It is the test that keeps the threshold honest.
- `reduced-motion-hold` is a quantised still. A static frame cannot flash, and its continuity
  delta is zero.

And the breach cases are per-audit, so a change that made one audit swallow another would show up
as a mismatch rather than as a quieter pass.

## Two instructive failures

Both of these were wrong in the suite, not in the audit:

- A strobe with a period exactly divisible by the frame interval **aliases**: the duty boundary
  lands on the sample point and the wave renders as blocks instead of alternation. The audit
  faithfully reported what had been rendered.
- A strobe at exactly three reversals per second **passes**, because WCAG 2.3.1 forbids _more
  than_ three in a one-second window. An expectation of failure there was simply wrong.

Both cases are annotated in `cases.json` so the next person does not rediscover them.

## Scoring

A case passes only when the verdict matches **and** the set of failing audits matches exactly. An
audit that returns the right verdict for the wrong reason is not a pass. The runner exits non-zero
on any failure, so it works as a gate.
