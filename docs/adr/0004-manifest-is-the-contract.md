# ADR-0004 — The manifest is the contract

**Status:** accepted · **Date:** 2026-10-06

## Context

A motion-graphics repository can store three things: the source, the rendered video, or a
description of the render. We store all three, and the question this ADR settles is which one
is authoritative when they disagree.

The obvious answer is the video: it is what a viewer watches. But an MP4 is a lossy downstream
encoding — chroma subsampled, frames predicted, quantised — so its bytes are not a function of
the spec in any useful sense. Treating it as the contract would mean "reproducible" is
unprovable, because re-encoding with a different ffmpeg build changes the file without anyone
having changed the motion.

## Decision

`clips/<id>/manifest.json` is the contract. It contains:

- the spec digest, over the **normalised** spec, so two specs that draw identically hash alike
- a SHA-256 per frame, over the canonical RGB bytes at the clip's dimensions
- a root digest folding the frame digests in frame order
- per-frame telemetry in integer milli-units: mean relative luminance and inter-frame motion
- the three audit results with the measured numbers and a reason sentence
- the verdict, the failing audits, and the encoded video's own size and digest

The MP4 is a **derived artefact**, committed so the gallery can serve it and digested so it can
be checked. The spec is the **source**. The manifest is the **evidence**.

## Consequences

- `framesafe verify` is meaningful: it re-renders and compares digests, and a divergence names
  the frame that diverged.
- `check:manifests` can run in milliseconds because it never renders, only re-derives the spec
  digest — with the engine's own compiler, never a re-implementation.
- Telemetry is integers, not floats. A manifest is compared byte for byte, and a float printed
  to JSON is not a value you can compare exactly.
- A Pillow upgrade legitimately changes frame digests. That is recorded rather than hidden:
  every manifest carries a `renderer` fingerprint, and `verify` reports `rendererMatches: false`
  separately from `reproducible: false` so the two causes are never confused.
- Encoding is a host concern. The engine renders pixels and never spawns a process, so a codec
  change cannot change a digest.

## Alternatives rejected

- **Digest the MP4.** Lossy and build-dependent; makes reproducibility unprovable.
- **Digest the spec only.** Says nothing about whether the renderer is deterministic, which is
  the actual risk.
- **A tree hash over the whole clip instead of per-frame digests.** Cheaper to store, but it
  cannot name the frame that diverged, and that name is the entire debugging value.
