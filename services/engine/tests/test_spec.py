"""Spec validation: what a clip may say, and how it refuses the rest.

Validation is the first place a bad document can be caught, so it is tested hardest: every
rejection asserts the stable code, because callers branch on the code and not on prose.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from framesafe import LAYER_KINDS, validate
from framesafe.protocol import EngineError

ROOT = Path(__file__).resolve().parents[3]
CLIPS = ROOT / "clips"


def minimal() -> dict[str, Any]:
    return {
        "id": "unit",
        "title": "Unit",
        "technique": ["fade"],
        "durationMs": 1000,
        "fps": 10,
        "width": 320,
        "height": 180,
        "layers": [
            {
                "kind": "rect",
                "t": {"startMs": 0, "inMs": 400, "holdMs": 400, "outMs": 200},
                "x": 10,
                "y": 10,
                "w": 100,
                "h": 50,
                "fill": "accent",
            }
        ],
    }


def test_every_shipped_clip_validates() -> None:
    specs = sorted(CLIPS.glob("*/spec.json"))
    assert specs, "the clip library must not be empty"
    for path in specs:
        spec = json.loads(path.read_text(encoding="utf-8"))
        plan = validate(spec)
        assert plan["id"] == path.parent.name, f"{path}: id must match its directory"


def test_defaults_are_materialised() -> None:
    plan = validate(minimal())
    assert plan["fps"] == 10
    assert plan["supersample"] == 2
    assert plan["continuityBudget"] == 0.18
    assert plan["background"] == "#0a0d11"
    assert plan["reducedMotion"]["holdFrame"] == 0


def test_required_top_level_fields() -> None:
    for field in ("id", "title", "durationMs", "layers"):
        spec = minimal()
        del spec[field]
        with pytest.raises(EngineError) as error:
            validate(spec)
        assert error.value.code in {"MISSING_FIELD", "BAD_SHAPE"}


def test_unknown_field_is_rejected() -> None:
    spec = minimal()
    spec["wat"] = 1
    with pytest.raises(EngineError) as error:
        validate(spec)
    assert error.value.code == "BAD_SHAPE"
    assert "wat" in error.value.message


def test_per_kind_extras_are_accepted_and_bad_types_are_not() -> None:
    """Geometry fields like `r` or `seed` are per-kind extras, so extras must be allowed."""
    spec = minimal()
    spec["layers"][0]["r"] = 12
    spec["layers"][0]["seed"] = 7
    plan = validate(spec)
    assert plan["layers"][0]["r"] == 12.0

    broken = minimal()
    broken["layers"][0]["points"] = {"not": "a list"}
    with pytest.raises(EngineError) as error:
        validate(broken)
    assert error.value.code == "BAD_SHAPE"


def test_unknown_layer_kind_is_rejected() -> None:
    spec = minimal()
    spec["layers"][0]["kind"] = "hologram"
    with pytest.raises(EngineError) as error:
        validate(spec)
    assert error.value.code == "BAD_LAYER"


def test_missing_required_layer_field_is_rejected() -> None:
    for kind, required in (
        ("rect", "w"),
        ("circle", "cx"),
        ("text", "scale"),
        ("grid", "cols"),
        ("strobe", "periodMs"),
    ):
        spec = minimal()
        layer: dict[str, Any] = {
            "kind": kind,
            "t": {"inMs": 100, "holdMs": 100, "outMs": 100},
            "x": 0,
            "y": 0,
            "w": 10,
            "h": 10,
            "cx": 5,
            "cy": 5,
            "r": 4,
            "scale": 4,
            "cols": 2,
            "rows": 2,
            "periodMs": 100,
            "text": "AB",
        }
        del layer[required]
        spec["layers"] = [layer]
        with pytest.raises(EngineError) as error:
            validate(spec)
        assert error.value.code == "MISSING_FIELD", kind


def test_bad_easing_is_rejected() -> None:
    spec = minimal()
    spec["layers"][0]["t"]["easing"] = "easeInTurbo"
    with pytest.raises(EngineError) as error:
        validate(spec)
    assert error.value.code == "BAD_EASING"


def test_steps_easing_is_accepted() -> None:
    spec = minimal()
    spec["layers"][0]["t"]["easing"] = "steps(4)"
    plan = validate(spec)
    assert plan["layers"][0]["t"]["easing"] == "steps(4)"
    assert plan["layers"][0]["t"]["steps"] == 4


def test_bad_colour_is_rejected_and_named() -> None:
    spec = minimal()
    spec["layers"][0]["fill"] = "burnt-orange"
    with pytest.raises(EngineError) as error:
        validate(spec)
    assert error.value.code == "BAD_COLOR"
    assert "burnt-orange" in error.value.message


def test_hex_colour_is_accepted() -> None:
    spec = minimal()
    spec["layers"][0]["fill"] = "#ff8800"
    assert validate(spec)["layers"][0]["fill"] == "#ff8800"


def test_unsupported_glyph_is_rejected() -> None:
    spec = minimal()
    spec["layers"][0] = {
        "kind": "text",
        "t": {"inMs": 100, "holdMs": 100, "outMs": 100},
        "text": "AЖB",
        "x": 0,
        "y": 0,
        "scale": 4,
    }
    with pytest.raises(EngineError) as error:
        validate(spec)
    assert error.value.code == "BAD_GLYPH"


def test_reveal_must_match_the_kind() -> None:
    spec = minimal()
    spec["layers"][0]["reveal"] = "sweep"
    with pytest.raises(EngineError) as error:
        validate(spec)
    assert error.value.code == "BAD_REVEAL"


def test_zero_duration_window_is_rejected() -> None:
    spec = minimal()
    spec["layers"][0]["t"] = {"startMs": 0, "inMs": 0, "holdMs": 0, "outMs": 0}
    with pytest.raises(EngineError) as error:
        validate(spec)
    assert error.value.code == "OUT_OF_RANGE"


def test_out_of_range_numbers_are_rejected() -> None:
    for field, value in (("fps", 0), ("width", 4), ("height", 99999), ("durationMs", 0)):
        spec = minimal()
        spec[field] = value
        with pytest.raises(EngineError) as error:
            validate(spec)
        assert error.value.code == "OUT_OF_RANGE", field


def test_reduced_motion_hold_frame_must_be_inside_the_clip() -> None:
    spec = minimal()
    spec["reducedMotion"] = {"holdFrame": 10_000}
    with pytest.raises(EngineError) as error:
        validate(spec)
    assert error.value.code == "OUT_OF_RANGE"


def test_points_must_be_pairs_of_numbers() -> None:
    spec = minimal()
    spec["layers"][0] = {
        "kind": "polyline",
        "t": {"inMs": 100, "holdMs": 100, "outMs": 100},
        "points": [[0, 0], [1]],
    }
    with pytest.raises(EngineError) as error:
        validate(spec)
    assert error.value.code == "BAD_SHAPE"


def test_validation_is_deterministic() -> None:
    """Same document in, byte-identical canonical form out — twice, and in any key order."""
    spec = minimal()
    first = validate(copy.deepcopy(spec))
    second = validate(copy.deepcopy(spec))
    assert first == second
    reordered = {key: spec[key] for key in reversed(list(spec))}
    assert validate(reordered) == first


def test_every_layer_kind_is_constructible() -> None:
    """A layer kind that cannot be built from its own required fields is a dead end."""
    layer_fields: dict[str, dict[str, Any]] = {
        "background": {"reveal": "fade"},
        "rect": {"x": 0, "y": 0, "w": 10, "h": 10},
        "line": {"x1": 0, "y1": 0, "x2": 5, "y2": 5},
        "polyline": {"points": [[0, 0], [5, 5]]},
        "polygon": {"cx": 5, "cy": 5, "r": 4},
        "circle": {"cx": 5, "cy": 5, "r": 4},
        "rings": {"cx": 5, "cy": 5, "count": 2},
        "particles": {"count": 5, "seed": 3},
        "bars": {"count": 5, "seed": 3},
        "grid": {"x": 0, "y": 0, "cols": 2, "rows": 2, "reveal": "sweep"},
        "text": {"text": "OK", "x": 0, "y": 0, "scale": 3},
        "guides": {},
        "strobe": {"periodMs": 100, "reveal": "flash"},
    }
    assert set(layer_fields) == set(LAYER_KINDS)
    for kind, fields in layer_fields.items():
        spec = minimal()
        spec["layers"] = [
            {
                "kind": kind,
                "t": {"inMs": 100, "holdMs": 100, "outMs": 100},
                "fill": "accent",
                **fields,
            }
        ]
        assert validate(spec)["layers"][0]["kind"] == kind
