"""The named operations — the whole product surface of the engine.

Every function here is pure in the sense that matters: same JSON in, same JSON out, no
clock, no network, no filesystem, no model. The TS host calls these as subprocesses and
the site reads the JSON they produce, which is why a CLI run, an MCP call, and a website
cannot disagree about a clip.

Operations:

    compile        spec -> compiled plan summary (no rendering)
    telemetry      spec -> per-frame luminance measurements (renders)
    digests        spec -> per-frame digests, optionally a range (renders)
    manifest       spec -> the full committed manifest: digests + telemetry + audits
    audit_manifest manifest -> re-run the audits from stored telemetry (no rendering)
    verify         spec + manifest -> did an independent render reproduce every frame?
"""

from __future__ import annotations

from typing import Any, Final

import numpy as np
from PIL import Image, __version__ as pillow_version

from . import audit as audit_module
from . import digest as digest_module
from .digest import digest_image, root_digest
from .plan import ClipPlan, compile_spec
from .protocol import EngineError
from .render import frame_plan_summary, render_frame

MANIFEST_SCHEMA = 1


def renderer_fingerprint() -> dict[str, str]:
    """Exactly which renderer produced a set of digests.

    Recorded in every manifest, because rasterisation is a Pillow behaviour: a different
    Pillow may legitimately produce different pixels for the same spec.
    """
    return {
        "pillow": pillow_version,
        "numpy": np.__version__,
        "digestRecipe": digest_module.DIGEST_RECIPE,
        "analysisGrid": f"{audit_module.GRID_WIDTH}x{audit_module.GRID_HEIGHT}",
    }


def _require_spec(payload: Any) -> ClipPlan:
    if not isinstance(payload, dict) or "spec" not in payload:
        raise EngineError("MISSING_FIELD", "input must be an object with a \"spec\"")
    return compile_spec(payload["spec"])


def _range_of(payload: dict[str, Any], plan: ClipPlan) -> tuple[int, int]:
    start = int(payload.get("from", 0))
    end = int(payload.get("to", plan.frame_count))
    if start < 0 or end > plan.frame_count or start > end:
        raise EngineError(
            "OUT_OF_RANGE",
            f"frame range {start}..{end} is outside 0..{plan.frame_count}",
        )
    return start, end


def op_compile(payload: Any) -> dict[str, Any]:
    plan = _require_spec(payload)
    return frame_plan_summary(plan)


def op_digests(payload: Any) -> dict[str, Any]:
    plan = _require_spec(payload)
    start, end = _range_of(payload if isinstance(payload, dict) else {}, plan)
    digests: list[dict[str, object]] = [
        {"i": index, "digest": digest_image(index, render_frame(plan, index))}
        for index in range(start, end)
    ]
    return {
        "id": plan.id,
        "from": start,
        "to": end,
        "renderer": renderer_fingerprint(),
        "frames": digests,
        "rootDigest": root_digest([str(frame["digest"]) for frame in digests]),
    }


def _measure_all(plan: ClipPlan) -> tuple[list[str], audit_module.Telemetry]:
    """Render every frame once, collecting digests and luma grids together."""
    digests: list[str] = []
    grids: list[np.ndarray] = []
    for index in range(plan.frame_count):
        image = render_frame(plan, index)
        digests.append(digest_image(index, image))
        grids.append(audit_module.luma_grid(image))
    return digests, audit_module.measure(plan, grids)


def op_telemetry(payload: Any) -> dict[str, Any]:
    plan = _require_spec(payload)
    _, telemetry = _measure_all(plan)
    return {
        "id": plan.id,
        "fps": plan.fps,
        "frameCount": plan.frame_count,
        "telemetry": telemetry.as_json(),
    }


def op_manifest(payload: Any) -> dict[str, Any]:
    """The artefact this product commits: every frame addressed, every audit evaluated."""
    plan = _require_spec(payload)
    digests, telemetry = _measure_all(plan)
    report = audit_module.verdicts(
        telemetry, plan.fps, plan.continuity_budget, plan.max_adjacent_contrast
    )
    return {
        "schema": MANIFEST_SCHEMA,
        "id": plan.id,
        "title": plan.title,
        "summary": plan.spec["summary"],
        "technique": plan.spec["technique"],
        "tags": plan.spec["tags"],
        "fps": plan.fps,
        "width": plan.width,
        "height": plan.height,
        "durationMs": plan.duration_ms,
        "frameCount": plan.frame_count,
        "specDigest": f"sha256:{plan.spec_digest}",
        "rootDigest": root_digest(digests),
        "continuityBudget": plan.continuity_budget,
        "maxAdjacentContrast": plan.max_adjacent_contrast,
        "reducedMotion": plan.spec["reducedMotion"],
        "renderer": renderer_fingerprint(),
        "frames": [{"i": index, "digest": digest} for index, digest in enumerate(digests)],
        "telemetry": telemetry.as_json(),
        "audits": report["audits"],
        "verdict": report["verdict"],
        "failingAudits": report["failingAudits"],
        "reasons": report["reasons"],
    }


def op_audit_manifest(payload: Any) -> dict[str, Any]:
    """Re-evaluate the audits from a manifest's telemetry, without re-rendering anything.

    This is the cheap review path: it is what the site and CI run to decide whether a
    committed clip still passes, using only the numbers the manifest already carries.
    """
    if not isinstance(payload, dict) or not isinstance(payload.get("manifest"), dict):
        raise EngineError("MISSING_FIELD", "input must be an object with a \"manifest\"")
    manifest = payload["manifest"]
    telemetry_raw = manifest.get("telemetry")
    if not isinstance(telemetry_raw, dict):
        raise EngineError("MISSING_FIELD", "manifest.telemetry is missing")

    try:
        telemetry = audit_module.Telemetry(
            luma=tuple(int(value) for value in telemetry_raw["luma"]),
            delta=tuple(int(value) for value in telemetry_raw["delta"]),
            flash_frames=tuple(int(value) for value in telemetry_raw["flashFrames"]),
            peak_delta=int(telemetry_raw["peakDelta"]),
            worst_delta_frame=int(telemetry_raw["worstDeltaFrame"]),
        )
        fps = int(manifest["fps"])
        budget = float(manifest["continuityBudget"])
        ceiling = float(manifest["maxAdjacentContrast"])
    except (KeyError, TypeError, ValueError) as cause:
        raise EngineError("BAD_SHAPE", f"manifest telemetry is malformed: {cause}") from cause

    if len(telemetry.luma) != len(telemetry.delta):
        raise EngineError(
            "BAD_SHAPE",
            f"telemetry lengths disagree: {len(telemetry.luma)} luma vs {len(telemetry.delta)} delta",
        )

    report = audit_module.verdicts(telemetry, fps, budget, ceiling)
    return {
        "id": manifest.get("id"),
        "frameCount": len(telemetry.luma),
        "audits": report["audits"],
        "verdict": report["verdict"],
        "failingAudits": report["failingAudits"],
        "reasons": report["reasons"],
    }


def op_verify(payload: Any) -> dict[str, Any]:
    """Re-render independently and compare against a committed manifest.

    Two separate processes render these frames; agreement is therefore evidence that the
    renderer is deterministic, not a tautology about one process agreeing with itself.
    """
    if not isinstance(payload, dict):
        raise EngineError("BAD_SHAPE", "input must be an object")
    plan = _require_spec(payload)
    manifest = payload.get("manifest")
    if not isinstance(manifest, dict):
        raise EngineError("MISSING_FIELD", "input must be an object with a \"manifest\"")

    expected_frames = manifest.get("frames")
    if not isinstance(expected_frames, list) or not expected_frames:
        raise EngineError("MISSING_FIELD", "manifest.frames is missing or empty")
    expected = [str(frame["digest"]) for frame in expected_frames]

    actual, _ = _measure_all(plan)
    difference = digest_module.first_difference(expected, actual)

    expected_renderer = manifest.get("renderer")
    current_renderer = renderer_fingerprint()
    renderer_matches = expected_renderer == current_renderer

    spec_matches = manifest.get("specDigest") == f"sha256:{plan.spec_digest}"
    return {
        "id": plan.id,
        "reproducible": bool(difference["identical"]),
        "framesCompared": min(len(expected), len(actual)),
        "expectedFrameCount": len(expected),
        "actualFrameCount": len(actual),
        "firstDifference": difference,
        "rootDigestExpected": manifest.get("rootDigest"),
        "rootDigestActual": root_digest(actual),
        "specDigestMatches": spec_matches,
        "rendererMatches": renderer_matches,
        "rendererExpected": expected_renderer,
        "rendererActual": current_renderer,
        "verdict": (
            "reproduced"
            if difference["identical"] and spec_matches
            else "diverged"
        ),
    }


OPERATIONS: Final[dict[str, Any]] = {
    "compile": op_compile,
    "digests": op_digests,
    "telemetry": op_telemetry,
    "manifest": op_manifest,
    "audit_manifest": op_audit_manifest,
    "verify": op_verify,
}


def analyse(op: str, payload: Any) -> Any:
    handler = OPERATIONS.get(op)
    if handler is None:
        known = ", ".join(sorted(OPERATIONS))
        raise EngineError("UNKNOWN_OP", f"unknown op {op!r}; available: {known}")
    return handler(payload)


def manifest_from_image(frame: int, image: Image.Image) -> str:  # pragma: no cover - helper
    return digest_image(frame, image)
