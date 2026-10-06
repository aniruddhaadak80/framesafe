#!/usr/bin/env python3
"""check:manifests — every committed manifest must agree with its spec and its video.

This is the cheap counterpart to `framesafe verify`. It re-renders nothing: it re-derives
the spec digest with the engine's own compiler and checks the manifest against itself, so a
hand-edited or truncated file fails in milliseconds instead of after a four-minute encode.

It deliberately calls the engine rather than re-implementing canonicalisation. A gate with
its own idea of what a spec hashes to is a second implementation of the contract, and two
implementations of a digest is how a digest stops meaning anything.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine" / "src"))

from framesafe import compile_spec  # noqa: E402
from framesafe.digest import root_digest  # noqa: E402

CLIPS = ROOT / "clips"
VIDEO_DIR = ROOT / "apps" / "web" / "public" / "clips"

problems: list[str] = []


def note(clip: str, why: str) -> None:
    problems.append(f"  {clip} - {why}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def check_clip(clip_id: str) -> None:
    spec_path = CLIPS / clip_id / "spec.json"
    manifest_path = CLIPS / clip_id / "manifest.json"

    if not spec_path.exists():
        note(clip_id, "no spec.json")
        return
    if not manifest_path.exists():
        note(clip_id, "no manifest.json - run `framesafe render " + clip_id + "`")
        return

    spec: dict[str, Any] = json.loads(spec_path.read_text(encoding="utf-8"))
    manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))

    if spec.get("id") != clip_id:
        note(clip_id, f"spec.id is {spec.get('id')!r}")
    if manifest.get("schema") != 1:
        note(clip_id, f"unknown manifest schema {manifest.get('schema')}")

    frames = manifest.get("frames")
    if not isinstance(frames, list) or not frames:
        note(clip_id, "manifest.frames is missing or empty")
        return

    frame_count = manifest.get("frameCount")
    if len(frames) != frame_count:
        note(clip_id, f"frames.length {len(frames)} != frameCount {frame_count}")
    if any(frame.get("i") != index for index, frame in enumerate(frames)):
        note(clip_id, "frame indices are not contiguous and in order")
    digests = [str(frame.get("digest", "")) for frame in frames]
    if any(not digest.startswith("sha256:") for digest in digests):
        note(clip_id, "a frame digest is missing or malformed")

    if root_digest(digests) != manifest.get("rootDigest"):
        note(clip_id, "rootDigest does not match the frame digests it stands for")

    plan = compile_spec(spec)
    if f"sha256:{plan.spec_digest}" != manifest.get("specDigest"):
        note(clip_id, "specDigest does not match spec.json - the manifest describes another spec")
    if plan.frame_count != frame_count:
        note(clip_id, f"spec compiles to {plan.frame_count} frames, manifest says {frame_count}")

    telemetry = manifest.get("telemetry", {})
    for key in ("luma", "delta"):
        values = telemetry.get(key)
        if not isinstance(values, list) or len(values) != frame_count:
            note(clip_id, f"telemetry.{key} does not have {frame_count} entries")

    audits = manifest.get("audits", {})
    for name in ("flash", "continuity", "luminance"):
        if not isinstance(audits.get(name, {}).get("passed"), bool):
            note(clip_id, f"audit {name} has no boolean 'passed'")
    failing = sorted(name for name, audit in audits.items() if audit.get("passed") is False)
    expected = "pass" if not failing else "fail"
    if manifest.get("verdict") != expected:
        note(clip_id, f"verdict {manifest.get('verdict')!r} disagrees with the audits")
    if sorted(manifest.get("failingAudits", [])) != failing:
        note(clip_id, "failingAudits disagrees with the audit results")
    if expected == "fail" and "intentional-fail" not in manifest.get("tags", []):
        note(clip_id, "fails its audits but is not tagged intentional-fail")
    if expected == "pass" and not manifest.get("digestsReproducedAcrossPasses"):
        note(clip_id, "digests were never reproduced across two render passes")

    video = manifest.get("video")
    if not isinstance(video, dict):
        note(clip_id, "manifest has no video block")
        return
    video_path = VIDEO_DIR / f"{clip_id}.mp4"
    if not video_path.exists():
        note(clip_id, f"video file is missing at {video_path}")
        return
    if video_path.stat().st_size != video.get("bytes"):
        note(
            clip_id,
            f"video is {video_path.stat().st_size} bytes, manifest says {video.get('bytes')}",
        )
    if sha256_file(video_path) != video.get("sha256"):
        note(clip_id, "video sha256 does not match the file")


def main() -> int:
    if not CLIPS.is_dir():
        print("check:manifests FAILED - no clips directory", file=sys.stderr)
        return 1
    ids = sorted(path.name for path in CLIPS.iterdir() if path.is_dir())
    if not ids:
        print("check:manifests FAILED - the clip library is empty", file=sys.stderr)
        return 1

    for clip_id in ids:
        check_clip(clip_id)

    if problems:
        print(f"check:manifests FAILED - {len(problems)} problem(s)", file=sys.stderr)
        for problem in problems:
            print(problem, file=sys.stderr)
        print("\n  fix: re-render the affected clips with `framesafe render all`.", file=sys.stderr)
        return 1

    print(f"check:manifests - {len(ids)} manifest(s) consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())