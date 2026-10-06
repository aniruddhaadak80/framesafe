"""The clip spec: what a motion graphic is, and what makes it invalid.

A spec is plain JSON. Nothing in this module touches a clock, a filesystem, or a random
number generator — validation is total and deterministic, so the same document always
compiles or always fails with the same code.

Every rejection carries a stable code so a caller can branch on it without parsing prose:
BAD_SHAPE, MISSING_FIELD, BAD_NUMBER, BAD_COLOR, BAD_EASING, BAD_LAYER, BAD_REVEAL,
BAD_GLYPH, OUT_OF_RANGE.
"""

from __future__ import annotations

import json
import re
from typing import Any, Final

from . import easing
from .glyphs import SUPPORTED as SUPPORTED_GLYPHS
from .protocol import EngineError

#: The clip palette. Named colours keep specs readable and keep the site on-brand without
#: every spec repeating hex values.
PALETTE: Final[dict[str, tuple[int, int, int]]] = {
    "ink": (10, 13, 17),
    "panel": (21, 25, 31),
    "line": (39, 44, 52),
    "paper": (244, 245, 247),
    "muted": (161, 164, 174),
    "subtle": (113, 116, 124),
    "accent": (34, 211, 238),
    "accentDeep": (8, 145, 178),
    "warm": (251, 146, 60),
    "alert": (244, 63, 94),
    "good": (74, 222, 128),
}

LAYER_KINDS: Final[frozenset[str]] = frozenset(
    {
        "background",
        "rect",
        "line",
        "polyline",
        "polygon",
        "circle",
        "rings",
        "particles",
        "bars",
        "grid",
        "text",
        "guides",
        "strobe",
    }
)

#: Which reveal modes each kind accepts. A wrong pairing is a spec bug, not a render bug.
#: `hold` means the geometry is complete from its first visible frame — the layer still
#: obeys its window's opacity, it simply does not travel.
REVEALS: Final[dict[str, frozenset[str]]] = {
    "background": frozenset({"fade", "hold"}),
    "rect": frozenset({"fade", "hold", "scale", "wipeX", "wipeY", "slideX", "slideY"}),
    "line": frozenset({"draw", "hold", "wipeX", "fade"}),
    "polyline": frozenset({"draw", "hold", "wipeX", "fade"}),
    "polygon": frozenset({"fade", "hold", "grow", "morph"}),
    "circle": frozenset({"fade", "hold", "grow", "sweep", "pulse"}),
    "rings": frozenset({"expand", "hold", "fade"}),
    "particles": frozenset({"drift", "hold", "fade"}),
    "bars": frozenset({"rise", "hold", "fade"}),
    "grid": frozenset({"sweep", "hold", "pulse"}),
    "text": frozenset({"draw", "fade", "hold", "slideUp", "mask"}),
    "guides": frozenset({"fade", "hold", "sweep"}),
    "strobe": frozenset({"flash"}),
}

_ID_RE: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_HEX_RE: Final[re.Pattern[str]] = re.compile(r"^#[0-9a-fA-F]{6}$")

#: Fields every layer carries, whatever its kind.
_LAYER_COMMON: Final[frozenset[str]] = frozenset(
    {"kind", "name", "t", "reveal", "fill", "stroke", "strokeWidth", "opacity", "fade", "rotation"}
)

_TOP_LEVEL: Final[frozenset[str]] = frozenset(
    {
        "id",
        "title",
        "summary",
        "technique",
        "tags",
        "fps",
        "width",
        "height",
        "durationMs",
        "supersample",
        "background",
        "continuityBudget",
        "maxAdjacentContrast",
        "reducedMotion",
        "layers",
        "version",
    }
)


def parse_color(value: Any, field: str) -> tuple[int, int, int]:
    """A palette name or a `#rrggbb` literal. Nothing else."""
    if not isinstance(value, str):
        raise EngineError("BAD_COLOR", f"{field} must be a palette name or #rrggbb")
    if value in PALETTE:
        return PALETTE[value]
    if _HEX_RE.match(value):
        return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
    raise EngineError(
        "BAD_COLOR",
        f"{field} is not a known colour: {value!r}; use one of {sorted(PALETTE)} or #rrggbb",
    )


def color_hex(rgb: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def _require_mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EngineError("BAD_SHAPE", f"{field} must be an object, got {type(value).__name__}")
    return value


def _number(container: dict[str, Any], field: str, path: str, default: float) -> float:
    if field not in container:
        return default
    value = container[field]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EngineError("BAD_NUMBER", f"{path}.{field} must be a number, got {type(value).__name__}")
    return float(value)


def _integer(container: dict[str, Any], field: str, path: str, default: int) -> int:
    if field not in container:
        return default
    value = container[field]
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, float) and value.is_integer():
            return int(value)
        raise EngineError("BAD_NUMBER", f"{path}.{field} must be an integer, got {type(value).__name__}")
    return value


def _text(container: dict[str, Any], field: str, path: str, default: str) -> str:
    if field not in container:
        return default
    value = container[field]
    if not isinstance(value, str):
        raise EngineError("BAD_SHAPE", f"{path}.{field} must be a string")
    return value


def _string_list(container: dict[str, Any], field: str, path: str) -> list[str]:
    if field not in container:
        return []
    value = container[field]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise EngineError("BAD_SHAPE", f"{path}.{field} must be a list of strings")
    return [str(item) for item in value]


def _points(value: Any, field: str) -> list[tuple[float, float]]:
    if not isinstance(value, list) or len(value) < 2:
        raise EngineError("BAD_SHAPE", f"{field} must be a list of at least two [x, y] points")
    out: list[tuple[float, float]] = []
    for index, item in enumerate(value):
        if (
            not isinstance(item, list)
            or len(item) != 2
            or any(isinstance(axis, bool) or not isinstance(axis, (int, float)) for axis in item)
        ):
            raise EngineError("BAD_SHAPE", f"{field}[{index}] must be a two-number [x, y] point")
        out.append((float(item[0]), float(item[1])))
    return out


def _curve(value: Any, field: str) -> tuple[str, int]:
    """Resolve an easing reference to (name, steps). `steps(n)` carries its parameter."""
    if isinstance(value, str):
        if value.startswith("steps(") and value.endswith(")"):
            inner = value[6:-1].strip()
            if not inner.isdigit() or int(inner) < 1:
                raise EngineError("BAD_EASING", f"{field}: steps(n) needs a positive integer, got {value!r}")
            return (value, int(inner))
        if easing.resolve(value) is None:
            raise EngineError("BAD_EASING", f"{field}: unknown easing {value!r}; known: {easing.names()}")
        return (value, 0)
    raise EngineError("BAD_EASING", f"{field} must be an easing name string, got {type(value).__name__}")


def _range(value: float, low: float, high: float, path: str) -> float:
    if not (low <= value <= high):
        raise EngineError("OUT_OF_RANGE", f"{path} must be between {low} and {high}, got {value}")
    return value


def _validate_window(raw: Any, path: str) -> dict[str, Any]:
    window = _require_mapping(raw, path)
    for key in window:
        if key not in {"startMs", "inMs", "holdMs", "outMs", "easing"}:
            raise EngineError("BAD_SHAPE", f"{path}.{key} is not a window field")
    start = _integer(window, "startMs", path, 0)
    ease_in = _integer(window, "inMs", path, 0)
    hold = _integer(window, "holdMs", path, 0)
    ease_out = _integer(window, "outMs", path, 0)
    for name, value in (
        ("startMs", start),
        ("inMs", ease_in),
        ("holdMs", hold),
        ("outMs", ease_out),
    ):
        if value < 0:
            raise EngineError("OUT_OF_RANGE", f"{path}.{name} must be >= 0, got {value}")
    if ease_in == 0 and ease_out == 0 and hold == 0:
        raise EngineError("OUT_OF_RANGE", f"{path} has zero duration, so the layer would never appear")
    name, steps = _curve(window.get("easing", "easeInOutCubic"), f"{path}.easing")
    return {
        "startMs": start,
        "inMs": ease_in,
        "holdMs": hold,
        "outMs": ease_out,
        "easing": name,
        "steps": steps,
    }


#: Per-kind required fields. A layer missing one of these cannot be drawn.
_REQUIRED: Final[dict[str, tuple[str, ...]]] = {
    "background": (),
    "rect": ("x", "y", "w", "h"),
    "line": ("x1", "y1", "x2", "y2"),
    "polyline": ("points",),
    "polygon": ("cx", "cy", "r"),
    "circle": ("cx", "cy", "r"),
    "rings": ("cx", "cy", "count"),
    "particles": ("count", "seed"),
    "bars": ("count", "seed"),
    "grid": ("x", "y", "cols", "rows"),
    "text": ("text", "x", "y", "scale"),
    "guides": (),
    "strobe": ("periodMs",),
}


def _validate_layer(raw: Any, index: int, spec_path: str) -> dict[str, Any]:
    path = f"{spec_path}.layers[{index}]"
    layer = _require_mapping(raw, path)

    kind = layer.get("kind")
    if not isinstance(kind, str) or kind not in LAYER_KINDS:
        raise EngineError(
            "BAD_LAYER",
            f"{path}.kind must be one of {sorted(LAYER_KINDS)}, got {kind!r}",
        )

    for field in _REQUIRED[kind]:
        if field not in layer:
            raise EngineError("MISSING_FIELD", f"{path} ({kind}) is missing required field {field!r}")

    reveal = layer.get("reveal", "fade")
    if not isinstance(reveal, str) or reveal not in REVEALS[kind]:
        raise EngineError(
            "BAD_REVEAL",
            f"{path}.reveal={reveal!r} is not valid for kind {kind!r}; use one of {sorted(REVEALS[kind])}",
        )

    normalised: dict[str, Any] = {
        "kind": kind,
        "name": _text(layer, "name", path, f"{kind}-{index}"),
        "t": _validate_window(layer.get("t", {}), f"{path}.t"),
        "reveal": reveal,
        "strokeWidth": _number(layer, "strokeWidth", path, 0.0),
        "opacity": _range(_number(layer, "opacity", path, 1.0), 0.0, 1.0, f"{path}.opacity"),
        "fade": bool(layer.get("fade", True)),
        "rotation": _number(layer, "rotation", path, 0.0),
    }
    if normalised["strokeWidth"] < 0:
        raise EngineError("OUT_OF_RANGE", f"{path}.strokeWidth must be >= 0")
    if not _ID_RE.match(normalised["name"]):
        raise EngineError("BAD_SHAPE", f"{path}.name={normalised['name']!r} must be kebab-case")

    for field in ("fill", "stroke"):
        if layer.get(field) is not None:
            normalised[field] = color_hex(parse_color(layer[field], f"{path}.{field}"))
        else:
            normalised[field] = None

    # Numeric passthrough, coerced to float, with unknown keys rejected loudly.
    for key, value in layer.items():
        if key in _LAYER_COMMON or key == "t":
            continue
        if isinstance(value, bool):
            normalised[key] = value
        elif isinstance(value, (int, float)):
            normalised[key] = float(value)
        elif isinstance(value, str):
            normalised[key] = value
        elif isinstance(value, list):
            normalised[key] = _points(value, f"{path}.{key}")
        else:
            raise EngineError("BAD_SHAPE", f"{path}.{key} has unsupported type {type(value).__name__}")

    if kind == "text":
        text = normalised.get("text", "")
        if not isinstance(text, str) or not text:
            raise EngineError("MISSING_FIELD", f"{path}.text must be a non-empty string")
        unsupported = sorted({ch for ch in text.upper()} - set(SUPPORTED_GLYPHS))
        if unsupported:
            raise EngineError(
                "BAD_GLYPH",
                f"{path}.text uses glyphs the stroke font does not define: {unsupported}",
            )
        normalised["tracking"] = _range(
            _number(layer, "tracking", path, 1.4), 0.0, 6.0, f"{path}.tracking"
        )
        normalised["stagger"] = _range(
            _number(layer, "stagger", path, 0.12), 0.0, 1.0, f"{path}.stagger"
        )

    if kind == "grid":
        for field in ("cols", "rows"):
            if int(normalised[field]) < 1:
                raise EngineError("OUT_OF_RANGE", f"{path}.{field} must be >= 1")

    if kind in {"particles", "bars", "rings"}:
        for field in ("count", "seed"):
            value = normalised.get(field)
            if value is not None and value < 0:
                raise EngineError("OUT_OF_RANGE", f"{path}.{field} must be >= 0")
        if int(normalised.get("count", 1.0)) < 1:
            raise EngineError("OUT_OF_RANGE", f"{path}.count must be >= 1")

    return normalised


def validate(raw: Any) -> dict[str, Any]:
    """Validate and normalise a clip spec. Returns a canonical document.

    The returned dict is what gets digested, so defaults are materialised here rather than
    at render time — otherwise two specs that draw identically would digest differently.
    """
    spec = _require_mapping(raw, "spec")

    for key in spec:
        if key not in _TOP_LEVEL:
            raise EngineError("BAD_SHAPE", f"spec.{key} is not a clip spec field")

    for field in ("id", "title", "durationMs", "layers"):
        if field not in spec:
            raise EngineError("MISSING_FIELD", f"spec is missing required field {field!r}")

    identifier = _text(spec, "id", "spec", "")
    if not _ID_RE.match(identifier):
        raise EngineError("BAD_SHAPE", f"spec.id={identifier!r} must be kebab-case")

    fps = _integer(spec, "fps", "spec", 24)
    width = _integer(spec, "width", "spec", 1280)
    height = _integer(spec, "height", "spec", 720)
    duration_ms = _integer(spec, "durationMs", "spec", 0)
    supersample = _integer(spec, "supersample", "spec", 2)
    version = _integer(spec, "version", "spec", 1)

    if fps < 1 or fps > 120:
        raise EngineError("OUT_OF_RANGE", f"spec.fps must be 1..120, got {fps}")
    if width < 16 or width > 3840 or height < 16 or height > 2160:
        raise EngineError("OUT_OF_RANGE", "spec.width/height must be within 16..3840 x 16..2160")
    if duration_ms <= 0 or duration_ms > 600_000:
        raise EngineError("OUT_OF_RANGE", f"spec.durationMs must be 1..600000, got {duration_ms}")
    if supersample < 1 or supersample > 4:
        raise EngineError("OUT_OF_RANGE", f"spec.supersample must be 1..4, got {supersample}")

    technique = _string_list(spec, "technique", "spec")
    if not technique:
        raise EngineError("MISSING_FIELD", "spec.technique must list at least one motion idiom")

    layers_raw = spec.get("layers")
    if not isinstance(layers_raw, list) or not layers_raw:
        raise EngineError("BAD_SHAPE", "spec.layers must be a non-empty list")

    layers = [_validate_layer(item, index, "spec") for index, item in enumerate(layers_raw)]

    reduced = _require_mapping(spec.get("reducedMotion", {"holdFrame": 0, "note": ""}), "spec.reducedMotion")
    hold_frame = _integer(reduced, "holdFrame", "spec.reducedMotion", 0)
    frame_count = round(duration_ms * fps / 1000)
    if not (0 <= hold_frame < frame_count):
        raise EngineError(
            "OUT_OF_RANGE",
            f"spec.reducedMotion.holdFrame must be within 0..{frame_count - 1}, got {hold_frame}",
        )

    return {
        "version": version,
        "id": identifier,
        "title": _text(spec, "title", "spec", identifier),
        "summary": _text(spec, "summary", "spec", ""),
        "technique": technique,
        "tags": _string_list(spec, "tags", "spec"),
        "fps": fps,
        "width": width,
        "height": height,
        "durationMs": duration_ms,
        "supersample": supersample,
        "background": color_hex(parse_color(spec.get("background", "ink"), "spec.background")),
        "continuityBudget": _range(
            _number(spec, "continuityBudget", "spec", 0.18), 0.0, 1.0, "spec.continuityBudget"
        ),
        "maxAdjacentContrast": _range(
            _number(spec, "maxAdjacentContrast", "spec", 0.6), 0.0, 1.0, "spec.maxAdjacentContrast"
        ),
        "reducedMotion": {
            "holdFrame": hold_frame,
            "note": _text(reduced, "note", "spec.reducedMotion", ""),
        },
        "layers": layers,
    }


def frame_count(spec: dict[str, Any]) -> int:
    return round(int(spec["durationMs"]) * int(spec["fps"]) / 1000)


def canonical_json(spec: dict[str, Any]) -> str:
    """The exact bytes that get digested: sorted keys, no whitespace, UTF-8 safe."""
    return json.dumps(spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
