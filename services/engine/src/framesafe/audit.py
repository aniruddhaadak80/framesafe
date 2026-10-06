"""The audits: arithmetic claims about a rendered clip, each one falsifiable.

Three independent checks, all computed from the rendered frames rather than from the
spec's intentions:

  flash       - WCAG 2.3.1 / ITU-R BT.2020 style flashing. More than three polarity
                reversals of at least 10% relative luminance inside any one-second window
                fails. This is what makes a clip safe for photosensitive viewers.
  continuity  - every adjacent frame pair must stay inside the spec's declared
                continuityBudget of mean absolute luminance change. A budget is how a
                designer says "this transition is allowed to be abrupt", and the audit
                holds them to it instead of to taste.
  luminance   - the clip's brightness envelope, plus an adjacent-contrast ceiling, which
                is the property that reads as "strobing" even when it never trips the
                flash threshold.

Telemetry is emitted in integer milli-units so a manifest is exact: a float printed to
JSON is a float you cannot compare byte-for-byte later.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import numpy as np
from PIL import Image

from .plan import ClipPlan

#: Analysis grid. Big enough to catch a local strobe, small enough to be cheap.
GRID_WIDTH = 64
GRID_HEIGHT = 36

#: WCAG 2.3.1 general flash threshold: 10% of relative luminance.
GENERAL_FLASH_THRESHOLD = 0.10

#: More than three flashes in any one-second window is a failure.
MAX_FLASHES_PER_SECOND = 3

MILLI = 1000


def _linearise(channel: np.ndarray) -> np.ndarray:
    """sRGB 0..1 to linear light, per WCAG's relative-luminance definition."""
    return np.where(
        channel <= 0.04045,
        channel / 12.92,
        ((channel + 0.055) / 1.055) ** 2.4,
    )


def luma_grid(image: Image.Image) -> np.ndarray:
    """Mean relative luminance of `image` on a small analysis grid, shape (GRID_HEIGHT, GRID_WIDTH)."""
    small = image.convert("RGB").resize((GRID_WIDTH, GRID_HEIGHT), Image.Resampling.BOX)
    array = np.asarray(small, dtype=np.float64) / 255.0
    linear = _linearise(array)
    # Rec.709 luminance weights.
    return 0.2126 * linear[:, :, 0] + 0.7152 * linear[:, :, 1] + 0.0722 * linear[:, :, 2]


def mean_luma(grid: np.ndarray) -> float:
    return float(grid.mean())


@dataclass(frozen=True)
class Telemetry:
    """Per-frame measurements, exact to a thousandth."""

    luma: tuple[int, ...]
    delta: tuple[int, ...]
    flash_frames: tuple[int, ...]
    peak_delta: int
    worst_delta_frame: int

    def as_json(self) -> dict[str, Any]:
        return {
            "luma": list(self.luma),
            "delta": list(self.delta),
            "flashFrames": list(self.flash_frames),
            "peakDelta": self.peak_delta,
            "worstDeltaFrame": self.worst_delta_frame,
        }


def measure(plan: ClipPlan, grids: list[np.ndarray]) -> Telemetry:
    """Reduce per-frame grids into the integer telemetry a manifest carries."""
    luma: list[int] = []
    delta: list[int] = []
    peak = 0
    worst = 0
    previous: np.ndarray | None = None
    for grid in grids:
        value = mean_luma(grid)
        luma.append(int(round(value * MILLI)))
        if previous is None:
            delta.append(0)
        else:
            gap = float(np.abs(grid - previous).mean())
            scaled = int(round(gap * MILLI))
            delta.append(scaled)
            if scaled > peak:
                peak = scaled
                worst = len(delta) - 1
        previous = grid

    flash_frames = tuple(_flash_events(luma, plan.fps))
    return Telemetry(
        luma=tuple(luma),
        delta=tuple(delta),
        flash_frames=flash_frames,
        peak_delta=peak,
        worst_delta_frame=worst,
    )


def _flash_events(luma: Sequence[int], fps: int) -> list[int]:
    """Frame indices that carry a flash-polarity reversal.

    A flash is a rise followed by a fall (or the reverse) where both steps are at least
    the general flash threshold. Counting reversals rather than steps matters: a single
    bright fade is not a flash, and a symmetric strobe is two flashes per cycle.
    """
    events: list[int] = []
    last_sign = 0
    last_event = -(10**9)
    min_gap = max(1, round(fps * 0.25))
    for index in range(1, len(luma)):
        step = luma[index] - luma[index - 1]
        if abs(step) < GENERAL_FLASH_THRESHOLD * MILLI:
            continue
        sign = 1 if step > 0 else -1
        if last_sign != 0 and sign != last_sign and index - last_event >= min_gap:
            events.append(index)
            last_event = index
        last_sign = sign
    return events


def flashes_in_window(events: list[int], fps: int) -> tuple[int, int]:
    """The densest one-second window: (count, first frame index of that window)."""
    best_count = 0
    best_start = 0
    for start_index, start in enumerate(events):
        limit = start + fps
        count = sum(1 for event in events[start_index:] if event < limit)
        if count > best_count:
            best_count = count
            best_start = start
    return best_count, best_start


def flash_audit(telemetry: Telemetry, fps: int) -> dict[str, Any]:
    events = list(telemetry.flash_frames)
    count, window_start = flashes_in_window(events, fps)
    passed = count <= MAX_FLASHES_PER_SECOND
    return {
        "name": "flash",
        "passed": passed,
        "threshold": {
            "generalFlashDelta": GENERAL_FLASH_THRESHOLD,
            "maxFlashesPerSecond": MAX_FLASHES_PER_SECOND,
            "windowFrames": fps,
        },
        "maxFlashesInWindow": count,
        "windowStartFrame": window_start,
        "flashCount": len(events),
        "firstFlashFrame": events[0] if events else None,
        "worstAdjacentDelta": telemetry.peak_delta / MILLI,
        "worstAdjacentFrame": telemetry.worst_delta_frame,
        "reason": (
            f"{count} flash reversals inside frames {window_start}-{window_start + fps} "
            f"(limit {MAX_FLASHES_PER_SECOND})"
            if not passed
            else f"{count} flash reversals in the densest one-second window (limit {MAX_FLASHES_PER_SECOND})"
        ),
    }


def continuity_audit(telemetry: Telemetry, budget: float) -> dict[str, Any]:
    limit = int(round(budget * MILLI))
    passed = telemetry.peak_delta <= limit
    return {
        "name": "continuity",
        "passed": passed,
        "budget": budget,
        "peakDelta": telemetry.peak_delta / MILLI,
        "peakFrame": telemetry.worst_delta_frame,
        "overBudgetBy": max(0, telemetry.peak_delta - limit) / MILLI,
        "reason": (
            f"frame {telemetry.worst_delta_frame - 1}->{telemetry.worst_delta_frame} moves "
            f"{telemetry.peak_delta / MILLI:.3f} of mean luminance, over the declared "
            f"{budget:.3f} budget"
            if not passed
            else f"peak inter-frame motion {telemetry.peak_delta / MILLI:.3f} within the "
            f"{budget:.3f} budget"
        ),
    }


def luminance_audit(telemetry: Telemetry, ceiling: float) -> dict[str, Any]:
    luma = telemetry.luma
    lowest = min(luma) if luma else 0
    highest = max(luma) if luma else 0
    mean = sum(luma) / len(luma) if luma else 0.0
    peak = telemetry.peak_delta
    passed = peak <= ceiling * MILLI and highest - lowest > 0
    return {
        "name": "luminance",
        "passed": passed,
        "maxAdjacentContrast": ceiling,
        "minLuma": lowest / MILLI,
        "maxLuma": highest / MILLI,
        "meanLuma": round(mean / MILLI, 6),
        "range": (highest - lowest) / MILLI,
        "peakAdjacentContrast": peak / MILLI,
        "reason": (
            f"peak adjacent contrast {peak / MILLI:.3f} exceeds the declared ceiling "
            f"{ceiling:.3f}"
            if peak > ceiling * MILLI
            else f"luminance envelope {lowest / MILLI:.3f}..{highest / MILLI:.3f} inside the "
            f"{ceiling:.3f} adjacent-contrast ceiling"
        ),
    }


def verdicts(
    telemetry: Telemetry,
    fps: int,
    continuity_budget: float,
    contrast_ceiling: float,
) -> dict[str, Any]:
    """Run all three audits and fold them into one verdict with explicit reasons."""
    audits = {
        "flash": flash_audit(telemetry, fps),
        "continuity": continuity_audit(telemetry, continuity_budget),
        "luminance": luminance_audit(telemetry, contrast_ceiling),
    }
    failing = [name for name, audit in audits.items() if not audit["passed"]]
    return {
        "audits": audits,
        "verdict": "pass" if not failing else "fail",
        "failingAudits": sorted(failing),
        "reasons": [audits[name]["reason"] for name in sorted(failing)],
    }
