# ADR-0005 — Omitted surfaces, and where state actually lives

**Status:** accepted · **Date:** 2026-10-06

## Context

The product contract for this build drew eleven surfaces. Nine shipped. This ADR records what
was dropped and why, and settles where state lives — the two questions a reader of the README
should be able to answer without guessing.

## Omitted: Desktop (Electron)

The gallery is a website and the work happens in a terminal. An Electron shell would distribute
the same pixels with a different wrapper. It would also add a packaging pipeline, a second
build surface, and an Electron test that says nothing about whether a clip is correct.

## Omitted: Channels

A motion verdict delivered through a chat adapter is a verdict nobody can audit. The value of
this product is that a verdict is a committed JSON document that can be diffed, re-derived, and
reviewed in a pull request. A channel would put the same fact in a place where none of those
three are possible, and would add a retry queue whose failure modes are invisible.

## Omitted: Model providers

The credibility of this product is a proof: every frame digest reproduces, every audit verdict is
computed from rendered pixels. A model tier would sit next to that with a different kind of
claim and no way to check it. Deliberate, not incidental — there is no model call anywhere in
the render or audit path, and `providers` is absent from the workspace rather than disabled.

## State

The authoritative state is **git**: `clips/<id>/spec.json` plus the committed manifest and video.
Three derived stores exist, and none of them is allowed to become authoritative:

| Store                             | What it is                     | Rebuilt by         |
| --------------------------------- | ------------------------------ | ------------------ |
| `clips/*/manifest.json`           | the contract (ADR-0004)        | `framesafe render` |
| `apps/web/public/clips/*.mp4`     | encoded artefacts              | `framesafe render` |
| `.data/framesafe.db` (gitignored) | SQLite index of clips and runs | `framesafe index`  |

The SQLite index is the only database, and it is a **projection**: every column in it is
reproducible from the manifests, which is why `framesafe index` can rebuild it from nothing.
`PRAGMA user_version` and numbered migrations carry the schema; the run log is a convenience for
`framesafe runs`, not a record of truth.

The design draw for storage was Postgres. A hosted database would mean a committed connection
string, which the no-secrets rule forbids, and a Vercel function has no persistent filesystem to
keep one in. SQLite plus a git-tracked manifest is the honest local-first answer.

## Consequences

- A clone of the repository contains the entire product: the specs, the proofs, and the videos.
  Nothing needs to be provisioned to review it.
- `.data/` is gitignored, so `check:no-secrets` and `check:public-hygiene` never have to reason
  about a database file.
- Adding a channel later means revisiting this ADR, not just adding a package: the argument
  against it was about auditability, and it has to be answered, not assumed away.
