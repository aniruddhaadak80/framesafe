"""The compiled plan: frame-exact progress, and the invariant the audit depends on.

The regression that matters here is `out_progress`. It once returned the eased exit curve
(0 -> 1) instead of the remaining share (1 -> 0), which made every layer vanish on the first
frame of its exit. The continuity audit caught it as a one-frame luminance cliff in a real
clip, and these tests exist so it cannot come back unnoticed.
"""

from __future__ import annotations

from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from framesafe import compile_spec
from framesafe.easing import CURVES, MONOTONE, clamp01
from framesafe.geometry import polyline_prefix, resample


def spec_with(window: dict[str, Any], duration_ms: int = 1000, fps: int = 10) -> dict[str, Any]:
    return {
        "id": "unit",
        "title": "Unit",
        "technique": ["fade"],
        "durationMs": duration_ms,
        "fps": fps,
        "width": 64,
        "height": 64,
        "layers": [
            {
                "kind": "rect",
                "t": window,
                "x": 0,
                "y": 0,
                "w": 8,
                "h": 8,
                "fill": "accent",
            }
        ],
    }


def test_frame_count_follows_the_time_base() -> None:
    plan = compile_spec(spec_with({"inMs": 500, "holdMs": 500, "outMs": 500}, 1000, 24))
    assert plan.frame_count == 24
    assert plan.duration_ms == 1000
    assert plan.time_of(0) == 0.0
    assert plan.time_of(24) == 1.0


def test_progress_is_zero_before_the_window_opens() -> None:
    plan = compile_spec(spec_with({"startMs": 500, "inMs": 250, "holdMs": 100, "outMs": 100}))
    layer = plan.layers[0]
    assert plan.progress(layer, 0) == 0.0
    assert plan.alpha(layer, 0) == 0.0
    assert plan.visible_layers(0) == ()


def test_progress_reaches_one_at_the_end_of_the_ease_in() -> None:
    plan = compile_spec(spec_with({"startMs": 0, "inMs": 400, "holdMs": 400, "outMs": 200}))
    layer = plan.layers[0]
    assert plan.in_progress(layer, 4) == pytest.approx(1.0)  # 0.4s at 10fps


def test_out_progress_starts_at_one_and_decreases_to_zero() -> None:
    plan = compile_spec(spec_with({"startMs": 0, "inMs": 200, "holdMs": 400, "outMs": 400}))
    layer = plan.layers[0]
    hold_end_frame = 6  # (0.2 + 0.4) seconds at 10fps

    assert plan.out_progress(layer, hold_end_frame - 1) == pytest.approx(1.0)
    assert plan.out_progress(layer, hold_end_frame) == pytest.approx(1.0)

    series = [plan.out_progress(layer, frame) for frame in range(plan.frame_count)]
    assert series[hold_end_frame] == pytest.approx(1.0)
    # The regression guard: the exit must be gradual, not a cliff on the first frame.
    assert all(later <= earlier + 1e-9 for earlier, later in zip(series, series[1:], strict=False))
    assert series[hold_end_frame + 1] < series[hold_end_frame]
    # The window ends exactly on the clip boundary, so the last rendered frame is one
    # frame short of zero rather than zero itself.
    assert series[-1] < 0.5 * series[hold_end_frame]
    assert series[-1] >= 0.0


def test_out_progress_reaches_zero_once_the_window_has_elapsed() -> None:
    plan = compile_spec(spec_with({"startMs": 0, "inMs": 100, "holdMs": 100, "outMs": 100}, 800))
    layer = plan.layers[0]
    assert plan.out_progress(layer, plan.frame_count - 1) == pytest.approx(0.0)


def test_progress_never_exceeds_one_and_never_goes_negative() -> None:
    plan = compile_spec(
        spec_with({"startMs": 100, "inMs": 300, "holdMs": 200, "outMs": 300}, 1200, 24)
    )
    layer = plan.layers[0]
    for frame in range(plan.frame_count):
        value = plan.progress(layer, frame)
        assert 0.0 <= value <= 1.0, f"frame {frame} produced {value}"


def test_alpha_is_full_opacity_for_draw_reveals() -> None:
    spec = spec_with({"startMs": 0, "inMs": 400, "holdMs": 200, "outMs": 400})
    spec["layers"][0] = {
        "kind": "line",
        "t": {"startMs": 0, "inMs": 400, "holdMs": 200, "outMs": 400},
        "x1": 0,
        "y1": 0,
        "x2": 20,
        "y2": 20,
        "stroke": "accent",
        "strokeWidth": 1,
        "reveal": "draw",
    }
    plan = compile_spec(spec)
    layer = plan.layers[0]
    assert layer.reveal == "draw"
    assert plan.alpha(layer, 1) == pytest.approx(layer.opacity)


def test_frame_index_for_ms_clamps_into_the_clip() -> None:
    plan = compile_spec(spec_with({"inMs": 500, "holdMs": 400, "outMs": 100}, 1000, 25))
    assert plan.frame_index_for_ms(0) == 0
    assert plan.frame_index_for_ms(40) == 1
    assert plan.frame_index_for_ms(-500) == 0
    assert plan.frame_index_for_ms(99_999) == plan.frame_count - 1


def test_spec_digest_changes_only_with_the_spec() -> None:
    first = compile_spec(spec_with({"inMs": 100, "holdMs": 100, "outMs": 100}))
    same = compile_spec(spec_with({"inMs": 100, "holdMs": 100, "outMs": 100}))
    changed = compile_spec(spec_with({"inMs": 200, "holdMs": 100, "outMs": 100}))
    assert first.spec_digest == same.spec_digest
    assert first.spec_digest != changed.spec_digest


@settings(max_examples=200, deadline=None)
@given(st.floats(min_value=0.0, max_value=1.0))
def test_every_curve_is_pinned_at_both_ends(t: float) -> None:
    del t
    for name, curve in CURVES.items():
        assert curve(0.0) == pytest.approx(0.0, abs=1e-9), name
        assert curve(1.0) == pytest.approx(1.0, abs=1e-9), name


@settings(max_examples=200, deadline=None)
@given(st.floats(min_value=0.0, max_value=1.0), st.floats(min_value=0.0, max_value=1.0))
def test_monotone_curves_never_decrease(a: float, b: float) -> None:
    """A monotone curve cannot invent a motion spike — the continuity audit relies on it."""
    lo, hi = min(a, b), max(a, b)
    for name in MONOTONE:
        curve = CURVES[name]
        assert curve(lo) <= curve(hi) + 1e-9, f"{name} decreased between {lo} and {hi}"


@settings(max_examples=100, deadline=None)
@given(st.floats(min_value=0.0, max_value=1.0))
def test_clamp01_is_total(fraction: float) -> None:
    assert clamp01(fraction) == pytest.approx(min(1.0, max(0.0, fraction)))


def test_clamp01_maps_nan_to_zero() -> None:
    assert clamp01(float("nan")) == 0.0


@settings(max_examples=100, deadline=None)
@given(st.floats(min_value=-5.0, max_value=5.0))
def test_polyline_prefix_is_monotone_in_length(fraction: float) -> None:
    path = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    lengths = [sum(
        ((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5
        for a, b in zip(part, part[1:], strict=False)
    ) for part in (polyline_prefix(path, 0.0), polyline_prefix(path, 0.5), polyline_prefix(path, 1.0))]
    assert lengths[0] <= lengths[1] <= lengths[2] + 1e-9


def test_polyline_prefix_of_an_empty_path() -> None:
    assert polyline_prefix([], 0.5) == []


def test_resample_returns_the_requested_vertex_count() -> None:
    points = [(0.0, 0.0), (4.0, 0.0), (4.0, 4.0)]
    assert len(resample(points, 7)) == 7
    assert resample(points, 1)[0] == points[0]


def test_resample_of_a_degenerate_path_does_not_divide_by_zero() -> None:
    same = [(2.0, 2.0)] * 4
    assert len(resample(same, 5)) == 5
