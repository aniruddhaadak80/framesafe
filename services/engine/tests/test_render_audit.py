"""Rendering, digests, and the audits.

The golden test at the bottom is the anti-drift test: a known spec rendered to a known
digest. If a change to the renderer alters a pixel, that test fails with the frame index, and
the manifest diff says which clip moved.
"""

from __future__ import annotations

import json
from importlib.metadata import version
from pathlib import Path

import pytest

from framesafe import analyse, compile_spec, digest_image, first_difference, root_digest
from framesafe.audit import GENERAL_FLASH_THRESHOLD, flashes_in_window, measure
from framesafe.audit import _flash_events, luma_grid
from framesafe.render import render_frame
from framesafe.protocol import EngineError

from golden import GOLDEN_DIGESTS, GOLDEN_RENDERER, GOLDEN_SPEC

ROOT = Path(__file__).resolve().parents[3]
CLIPS = ROOT / "clips"


def test_render_produces_the_declared_size() -> None:
    plan = compile_spec(GOLDEN_SPEC)
    image = render_frame(plan, 0)
    assert (image.width, image.height) == (plan.width, plan.height)
    assert image.mode == "RGB"


def test_render_is_deterministic_within_a_process() -> None:
    plan = compile_spec(GOLDEN_SPEC)
    assert digest_image(3, render_frame(plan, 3)) == digest_image(3, render_frame(plan, 3))


def test_render_is_deterministic_across_compiles() -> None:
    first = compile_spec(GOLDEN_SPEC)
    second = compile_spec(GOLDEN_SPEC)
    assert [digest_image(i, render_frame(first, i)) for i in range(first.frame_count)] == [
        digest_image(i, render_frame(second, i)) for i in range(second.frame_count)
    ]


def test_digest_includes_the_frame_index() -> None:
    """Two frames with identical pixels must still have different addresses."""
    plan = compile_spec(GOLDEN_SPEC)
    settled = plan.frame_count - 1
    image = render_frame(plan, 0)
    assert digest_image(0, image) != digest_image(settled, image)


def test_root_digest_is_order_sensitive() -> None:
    a = ["sha256:a", "sha256:b"]
    assert root_digest(a) == root_digest(["sha256:a", "sha256:b"])
    assert root_digest(a) != root_digest(["sha256:b", "sha256:a"])


def test_root_digest_is_length_sensitive() -> None:
    assert root_digest(["sha256:a"]) != root_digest(["sha256:a", "sha256:a"])


def test_first_difference_reports_the_index_and_length_mismatch() -> None:
    result = first_difference(["a", "b", "c"], ["a", "x", "c"])
    assert result["identical"] is False
    assert result["frameIndex"] == 1

    shorter = first_difference(["a", "b"], ["a"])
    assert shorter["identical"] is False
    assert shorter["frameIndex"] == 1
    assert shorter["expectedLength"] == 2
    assert shorter["actualLength"] == 1

    assert first_difference(["a"], ["a"])["identical"] is True
    assert first_difference(["a"], ["a"])["frameIndex"] is None


def test_compile_operation_returns_a_plan_summary() -> None:
    result = analyse("compile", {"spec": GOLDEN_SPEC})
    assert result["frameCount"] == 6  # 500ms at 12fps
    assert result["specDigest"].startswith("sha256:")
    assert result["layers"][0]["kind"] == "background"


def test_digests_operation_can_return_a_slice() -> None:
    result = analyse("digests", {"spec": GOLDEN_SPEC, "from": 2, "to": 4})
    assert [frame["i"] for frame in result["frames"]] == [2, 3]
    assert "pillow" in result["renderer"]


def test_digests_operation_rejects_an_out_of_range_slice() -> None:
    with pytest.raises(EngineError) as error:
        analyse("digests", {"spec": GOLDEN_SPEC, "from": 0, "to": 999})
    assert error.value.code == "OUT_OF_RANGE"


def test_manifest_operation_reports_a_full_audit() -> None:
    manifest = analyse("manifest", {"spec": GOLDEN_SPEC})
    assert manifest["verdict"] in {"pass", "fail"}
    assert set(manifest["audits"]) == {"flash", "continuity", "luminance"}
    assert len(manifest["frames"]) == manifest["frameCount"]
    assert manifest["rootDigest"].startswith("sha256:")
    assert len(manifest["telemetry"]["luma"]) == manifest["frameCount"]


def test_audit_manifest_operation_needs_no_rendering() -> None:
    manifest = analyse("manifest", {"spec": GOLDEN_SPEC})
    replayed = analyse("audit_manifest", {"manifest": manifest})
    assert replayed["verdict"] == manifest["verdict"]
    assert replayed["failingAudits"] == manifest["failingAudits"]


def test_verify_operation_confirms_its_own_manifest() -> None:
    manifest = analyse("manifest", {"spec": GOLDEN_SPEC})
    result = analyse("verify", {"spec": GOLDEN_SPEC, "manifest": manifest})
    assert result["reproducible"] is True
    assert result["verdict"] == "reproduced"
    assert result["rendererMatches"] is True
    assert result["specDigestMatches"] is True


def test_verify_operation_detects_a_tampered_manifest() -> None:
    manifest = analyse("manifest", {"spec": GOLDEN_SPEC})
    manifest["frames"][2]["digest"] = "sha256:" + "0" * 64
    result = analyse("verify", {"spec": GOLDEN_SPEC, "manifest": manifest})
    assert result["reproducible"] is False
    assert result["firstDifference"]["frameIndex"] == 2
    assert result["verdict"] == "diverged"


def test_verify_operation_detects_a_truncated_manifest() -> None:
    manifest = analyse("manifest", {"spec": GOLDEN_SPEC})
    result = analyse(
        "verify", {"spec": GOLDEN_SPEC, "manifest": {**manifest, "frames": manifest["frames"][:2]}}
    )
    assert result["reproducible"] is False
    assert result["firstDifference"]["frameIndex"] == 2


def test_unknown_operation_is_rejected() -> None:
    with pytest.raises(EngineError) as error:
        analyse("render_movie", {"spec": GOLDEN_SPEC})
    assert error.value.code == "UNKNOWN_OP"


def test_missing_spec_is_rejected() -> None:
    with pytest.raises(EngineError) as error:
        analyse("compile", {})
    assert error.value.code == "MISSING_FIELD"


def test_flash_events_are_counted_as_reversals_not_steps() -> None:
    """A single rise and fall is one flash, not two steps."""
    luma = (100, 300, 100, 100, 100)
    events = _flash_events(luma, 24)
    assert len(events) == 1


def test_flashes_in_window_finds_the_densest_second() -> None:
    count, start = flashes_in_window([0, 5, 40, 45, 60], 24)
    assert count == 3
    assert start == 40


def test_measure_reports_the_peak_delta() -> None:
    plan = compile_spec(GOLDEN_SPEC)
    grids = [luma_grid(render_frame(plan, i)) for i in range(plan.frame_count)]
    telemetry = measure(plan, grids)
    assert len(telemetry.luma) == plan.frame_count
    assert telemetry.delta[0] == 0
    assert telemetry.peak_delta == max(telemetry.delta)
    assert all(0 <= value <= 1000 for value in telemetry.luma)


def test_general_flash_threshold_is_ten_percent() -> None:
    assert GENERAL_FLASH_THRESHOLD == pytest.approx(0.10)


def test_shipped_negative_tests_fail_and_shipped_clips_pass() -> None:
    """The library must contain both: a clip that passes and a clip the audit rejects."""
    verdicts: dict[str, str] = {}
    for path in sorted(CLIPS.glob("*/spec.json")):
        manifest_path = path.parent / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        verdicts[manifest["id"]] = manifest["verdict"]

    assert verdicts, "no committed manifests found"
    assert "pass" in verdicts.values(), "at least one clip must pass its audits"
    assert "fail" in verdicts.values(), "the audit must reject at least one clip, or it is untested"

    for clip_id, verdict in verdicts.items():
        spec = json.loads((CLIPS / clip_id / "spec.json").read_text(encoding="utf-8"))
        tags = spec.get("tags", [])
        if verdict == "fail":
            assert "intentional-fail" in tags, f"{clip_id} fails but is not marked intentional"


def test_golden_frame_digests_are_stable() -> None:
    """Anti-drift: if this fails, a pixel changed and every manifest must be re-derived."""
    plan = compile_spec(GOLDEN_SPEC)
    actual = [digest_image(index, render_frame(plan, index)) for index in range(plan.frame_count)]
    assert actual == GOLDEN_DIGESTS, (
        "the golden clip's frames changed — re-render the library and review the manifest "
        f"diff. Recorded with {GOLDEN_RENDERER}."
    )


def test_golden_render_records_the_renderer_that_produced_it() -> None:
    """The manifest must fingerprint the *installed* renderer, and record the same
    fingerprint fields the golden was written with. The pixels themselves are guarded by
    the digest comparisons above; pinning versions here would break on every Pillow or
    numpy release inside the declared supported ranges (pip picks a different numpy per
    interpreter in the CI matrix), which is drift noise, not a renderer change."""
    manifest = analyse("manifest", {"spec": GOLDEN_SPEC})
    assert set(GOLDEN_RENDERER) <= set(manifest["renderer"])
    assert manifest["renderer"]["pillow"] == version("pillow")
    assert manifest["renderer"]["numpy"] == version("numpy")
