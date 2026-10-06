---
name: publish-a-clip
description: Use when a clip is finished and you are about to commit it, because the manifest and the encoded video have to agree before anyone can verify the library later.
metadata:
  version: 1.0.0
---

# Publish a clip

## When to use this

A new or changed clip is ready to go into the repository and the deployed gallery.

## Steps

1. `python scripts/check-clip-specs.py` — compiles every spec and checks layout. Must exit 0.
2. `node packages/cli/dist/bin.js render <id>` — renders the MP4, writes
   `clips/<id>/manifest.json`, and refuses to write anything if the two render passes
   disagree on a single frame digest.
3. `node packages/cli/dist/bin.js verify <id>` — re-renders in a fresh process and compares
   against the committed manifest. Must print `every frame digest reproduced`.
4. `node packages/cli/dist/bin.js audit <id>` — read the verdict. A failing verdict is fine
   only for a deliberate negative test, and only when its intent is in the spec.
5. `node packages/cli/dist/bin.js index` — refresh the derived SQLite index.
6. Look at the clip: `python scripts/preview-frame.py clips/<id>/spec.json <frame>` writes
   one frame as a PNG you can actually inspect. A clip that has never been looked at has
   not been reviewed.

## What must be committed together

- `clips/<id>/spec.json` — the source of truth
- `clips/<id>/manifest.json` — the proof: digests, telemetry, audits, verdict
- `apps/web/public/clips/<id>.mp4` — the encoded artefact the site serves

Committing a spec without re-rendering leaves a manifest that describes a different clip,
and `framesafe verify` will say so.

## Verify

- `npm run check` exits 0.
- The clip appears in the gallery with its verdict badge.
