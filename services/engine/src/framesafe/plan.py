"""Compilation: a validated spec becomes a frame table.

The compiler never samples a layer. It resolves each layer's window into timings and
exposes `progress(layer, frame_index)`, the one function every renderer and every audit
reads. Because progress is derived from the integer frame index and nothing else, frame N
of a clip is computable without rendering frames 0..N-1 — which is what makes an
independent re-render a real check rather than a replay.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from . import easing
from .easing import Curve
from .protocol import EngineError
from .spec import canonical_json, frame_count, validate

_CURVE_CACHE: dict[str, Curve] = {}


def curve_for(name: str, steps: int) -> Curve:
    """Resolve a curve, memoised. `steps(n)` closes over its parameter."""
    key = f"{name}#{steps}"
    cached = _CURVE_CACHE.get(key)
    if cached is not None:
        return cached
    if steps > 0:
        curve: Curve = easing.steps(steps)
    else:
        resolved = easing.resolve(name)
        if resolved is None:
            raise EngineError("BAD_EASING", f"unknown easing {name!r}")
        curve = resolved
    _CURVE_CACHE[key] = curve
    return curve


@dataclass(frozen=True)
class Window:
    """One layer's local timeline, in seconds."""

    start: float
    ease_in: float
    hold: float
    ease_out: float
    easing: str
    steps: int

    @property
    def curve(self) -> Curve:
        return curve_for(self.easing, self.steps)

    @property
    def hold_end(self) -> float:
        return self.start + self.ease_in + self.hold


@dataclass(frozen=True)
class Layer:
    index: int
    kind: str
    name: str
    reveal: str
    window: Window
    fill: tuple[int, int, int] | None
    stroke: tuple[int, int, int] | None
    stroke_width: float
    opacity: float
    fade: bool
    rotation: float
    params: dict[str, Any]

    def number(self, key: str, default: float = 0.0) -> float:
        value = self.params.get(key, default)
        return float(value) if isinstance(value, (int, float)) else default

    def points(self, key: str) -> list[tuple[float, float]]:
        raw = self.params.get(key, [])
        return list(raw) if isinstance(raw, list) else []


def _rgb(value: str | None) -> tuple[int, int, int] | None:
    if value is None:
        return None
    return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))


@dataclass(frozen=True)
class ClipPlan:
    """A compiled clip: frame-exact, digest-addressed, and free of ambient state."""

    spec: dict[str, Any]
    layers: tuple[Layer, ...]
    spec_digest: str

    @property
    def id(self) -> str:
        return str(self.spec["id"])

    @property
    def title(self) -> str:
        return str(self.spec["title"])

    @property
    def fps(self) -> int:
        return int(self.spec["fps"])

    @property
    def width(self) -> int:
        return int(self.spec["width"])

    @property
    def height(self) -> int:
        return int(self.spec["height"])

    @property
    def supersample(self) -> int:
        return int(self.spec["supersample"])

    @property
    def duration_ms(self) -> int:
        return int(self.spec["durationMs"])

    @property
    def frame_count(self) -> int:
        return frame_count(self.spec)

    @property
    def duration_s(self) -> float:
        return self.frame_count / self.fps

    @property
    def continuity_budget(self) -> float:
        return float(self.spec["continuityBudget"])

    @property
    def max_adjacent_contrast(self) -> float:
        return float(self.spec["maxAdjacentContrast"])

    @property
    def reduced_hold_frame(self) -> int:
        return int(self.spec["reducedMotion"]["holdFrame"])

    def time_of(self, index: int) -> float:
        """The presentation time of a frame, in seconds."""
        return index / self.fps

    def in_progress(self, layer: Layer, index: int) -> float:
        """Ease-in progress in [0, 1]; 0 before the layer's start, 1 once it has landed."""
        window = layer.window
        elapsed = self.time_of(index) - window.start
        if elapsed <= 0.0:
            return 0.0
        if window.ease_in <= 0.0:
            return 1.0
        return window.curve(easing.clamp01(elapsed / window.ease_in))

    def out_progress(self, layer: Layer, index: int) -> float:
        """The *remaining* share of the layer after its ease-out begins.

        1.0 while the layer holds, easing to 0.0 once it has left. The curve is applied to
        the elapsed fraction and then inverted, because this factor multiplies the ease-in
        progress: returning the raw curve would drop the layer to zero on the first frame
        of its exit instead of easing it out.
        """
        window = layer.window
        if window.ease_out <= 0.0:
            return 1.0
        elapsed = self.time_of(index) - window.hold_end
        if elapsed <= 0.0:
            return 1.0
        return 1.0 - window.curve(easing.clamp01(elapsed / window.ease_out))

    def progress(self, layer: Layer, index: int) -> float:
        """The scalar every reveal mode is driven by. Zero means not yet on screen."""
        return self.in_progress(layer, index) * self.out_progress(layer, index)

    def alpha(self, layer: Layer, index: int) -> float:
        """Opacity for this frame, honouring the layer's `fade` flag.

        `draw` and `mask` reveals are exempt: there, the visible *length* of the stroke is
        the progress indicator, and fading the stroke as well would hide the very motion
        the clip exists to show.
        """
        if layer.reveal == "hold":
            return layer.opacity
        if self.progress(layer, index) <= 0.0:
            return 0.0
        if not layer.fade or layer.reveal in {"draw", "mask"}:
            return layer.opacity
        return layer.opacity * self.progress(layer, index)

    def visible_layers(self, index: int) -> tuple[Layer, ...]:
        return tuple(layer for layer in self.layers if self.progress(layer, index) > 0.0)

    def frame_index_for_ms(self, milliseconds: float) -> int:
        """The frame a wall-clock millisecond lands on, clamped into the clip."""
        raw = int(milliseconds * self.fps / 1000.0)
        return max(0, min(self.frame_count - 1, raw))


def compile_spec(raw: Any) -> ClipPlan:
    """Validate, canonicalise, digest, and resolve windows. The only way to get a plan."""
    spec = validate(raw)
    layers: list[Layer] = []
    for index, entry in enumerate(spec["layers"]):
        window_raw = entry["t"]
        window = Window(
            start=window_raw["startMs"] / 1000.0,
            ease_in=window_raw["inMs"] / 1000.0,
            hold=window_raw["holdMs"] / 1000.0,
            ease_out=window_raw["outMs"] / 1000.0,
            easing=window_raw["easing"],
            steps=int(window_raw["steps"]),
        )
        known = {"kind", "name", "t", "reveal", "fill", "stroke", "strokeWidth", "opacity", "fade", "rotation"}
        layers.append(
            Layer(
                index=index,
                kind=entry["kind"],
                name=entry["name"],
                reveal=entry["reveal"],
                window=window,
                fill=_rgb(entry.get("fill")),
                stroke=_rgb(entry.get("stroke")),
                stroke_width=float(entry.get("strokeWidth", 0.0)),
                opacity=float(entry.get("opacity", 1.0)),
                fade=bool(entry.get("fade", True)),
                rotation=float(entry.get("rotation", 0.0)),
                params={k: v for k, v in entry.items() if k not in known},
            )
        )
    digest = hashlib.sha256(canonical_json(spec).encode("utf-8")).hexdigest()
    return ClipPlan(spec=spec, layers=tuple(layers), spec_digest=digest)
