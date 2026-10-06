# The gallery

`apps/web` is the deployed surface: a single-column gallery of every clip in the library, each
with its video, its verdict, and the measurement behind that verdict.

## Why single column

The frame rail is one column per frame. At 144 frames that is 144 columns of real data, and its
job is to make the shape of a clip's motion legible at a glance: where the luminance sits, when
the motion spikes, where the flash reversals are. Cropping that into a card grid would destroy
the only thing the page exists to show, so the layout gives it the full width of the page.

## The frame rail

`apps/web/components/frame-rail.tsx` draws, per frame:

| Encoding   | Meaning                                        | Source                                 |
| ---------- | ---------------------------------------------- | -------------------------------------- |
| bar height | mean relative luminance of the frame           | `telemetry.luma` (integer milli-units) |
| step line  | motion between this frame and the previous one | `telemetry.delta`                      |
| red tick   | a frame the flash audit counted as a reversal  | `telemetry.flashFrames`                |
| white line | the playhead                                   | the video's current time               |

It is a `role="slider"` with `aria-valuenow` and `aria-valuetext`, driven by arrows, PageUp/Down,
Home and End. Pointer scrubbing seeks the video. Because the rail and the `<video>` live in one
client component, the playhead and the measurement cannot drift apart.

Telemetry is integer milli-units rather than floats on purpose: a manifest is compared
byte-for-byte by `check:manifests` and by `framesafe verify`, and a float printed to JSON is not
a value you can compare exactly.

## Data

`apps/web/lib/clips.ts` reads `clips/<id>/manifest.json` and nothing else. The site never
re-computes a verdict, never renders a frame, and never talks to a database — so it cannot
disagree with `framesafe audit`.

`allClips()` is memoised per server process, and every page that reads it is statically
generated (`export const dynamic = 'force-static'`, plus `generateStaticParams` for
`/clips/[id]`). The build produces 15 clip pages plus the gallery, which is why the deployment
needs no runtime filesystem and no secrets.

## Routes

| Route             | Rendering | Contents                                                    |
| ----------------- | --------- | ----------------------------------------------------------- |
| `/`               | static    | the gallery, one row per clip                               |
| `/clips/[id]`     | SSG       | video, rail, audits, timeline, first and last frame digests |
| `/surfaces`       | static    | what ships and what is deliberately omitted                 |
| `/health`         | dynamic   | live probe results from `/api/health`                       |
| `/api/health`     | dynamic   | real probes, 200 or 503                                     |
| `/api/clips`      | dynamic   | the library as JSON                                         |
| `/api/clips/[id]` | dynamic   | one full manifest, 404 when unknown                         |

`/api/health` reports what it can observe: the runtime version, the package version, how many
manifests parsed, how many clips pass, and whether every clip had its digests reproduced across
both render passes. It returns 503 when a manifest is missing or when a clip's determinism was
never proven, because a health check that cannot fail is decoration.

## Design tokens

`apps/web/styles/tokens.css` is the only file allowed to contain a colour literal;
`npm run check:theme-tokens` fails the build otherwise. The palette is zinc plus a single cyan
accent, because a gallery of rendered motion should not compete with its own chrome for
attention — the videos own the colour.

Type is IBM Plex Sans with IBM Plex Mono for anything measured. Radii are pill, so the chips and
the scrub rail read as one instrument. Motion in the chrome is short (90–160 ms) and
`prefers-reduced-motion: reduce` collapses it to nothing: the product under review is motion,
and the interface around it is not allowed to be the thing that moves.

## States

Loading (`app/loading.tsx`) is a skeleton of the gallery row. The empty state explains that a
clip exists once its manifest does, and names the command that creates one. Error states are
distinct components rather than one reused box.

## Responsive

Single column at every width, so there is no horizontal scroll at 360, 768 or 1280. The rail
keeps one column per frame at any width; below 360 the caption wraps to two lines.
