"""Easing curves. Every curve is a pure function of a normalised time in [0, 1].

The contract every curve honours:

    f(0) == 0        f(1) == 1        f is continuous

Curves marked monotone are also non-decreasing, which is what the continuity audit
relies on: a monotone curve cannot invent a motion spike inside a transition.

There is no clock and no randomness here. A curve is arithmetic, and arithmetic is the
part of motion design that must not be a model call.
"""

from __future__ import annotations

import math
from collections.abc import Callable

Curve = Callable[[float], float]


def clamp01(value: float) -> float:
    """Clamp to [0, 1]. NaN collapses to 0.0 rather than propagating."""
    if math.isnan(value):
        return 0.0
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def linear(t: float) -> float:
    return clamp01(t)


def ease_in_quad(t: float) -> float:
    x = clamp01(t)
    return x * x


def ease_out_quad(t: float) -> float:
    x = 1.0 - clamp01(t)
    return 1.0 - x * x


def ease_in_out_quad(t: float) -> float:
    x = clamp01(t)
    if x < 0.5:
        return 2.0 * x * x
    y = 1.0 - x
    return 1.0 - 2.0 * y * y


def ease_in_cubic(t: float) -> float:
    x = clamp01(t)
    return x * x * x


def ease_out_cubic(t: float) -> float:
    x = 1.0 - clamp01(t)
    return 1.0 - x * x * x


def ease_in_out_cubic(t: float) -> float:
    x = clamp01(t)
    if x < 0.5:
        return 4.0 * x * x * x
    y = 1.0 - x
    return 1.0 - 4.0 * y * y * y


def ease_in_quart(t: float) -> float:
    x = clamp01(t)
    return x * x * x * x


def ease_out_quart(t: float) -> float:
    x = 1.0 - clamp01(t)
    return 1.0 - x * x * x * x


def ease_in_expo(t: float) -> float:
    x = clamp01(t)
    if x <= 0.0:
        return 0.0
    return 2.0 ** (10.0 * (x - 1.0))


def ease_out_expo(t: float) -> float:
    x = clamp01(t)
    if x >= 1.0:
        return 1.0
    return 1.0 - 2.0 ** (-10.0 * x)


def ease_out_back(t: float) -> float:
    """Overshoots past 1 before settling — the classic anticipation-free punch."""
    x = clamp01(t)
    c1 = 1.70158
    c3 = c1 + 1.0
    u = x - 1.0
    return 1.0 + c3 * u * u * u + c1 * u * u


def ease_out_elastic(t: float) -> float:
    """A decaying oscillation. Non-monotone on purpose: it is a budget, not a curve."""
    x = clamp01(t)
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    c4 = (2.0 * 3.141592653589793) / 3.0
    return 2.0 ** (-10.0 * x) * ((x * 10.0 - 0.75) * c4 - 1.0) + 1.0


def ease_out_bounce(t: float) -> float:
    x = clamp01(t)
    if x < 4.0 / 11.0:
        return (121.0 * x * x) / 16.0
    if x < 8.0 / 11.0:
        u = x - 3.0 / 4.0
        return (363.0 / 40.0) * u * u + 8.0 / 5.0
    if x < 9.0 / 10.0:
        u = x - 8.0 / 11.0
        return (4356.0 / 361.0) * u * u + 205.0 / 216.0
    u = x - 1.0
    return (1.0 / 1.0) + (2.0 / 1.0) * u * u


def steps(count: int) -> Curve:
    """A quantised curve. `count` holds are distributed evenly, the last one is exact."""

    def curve(t: float) -> float:
        x = clamp01(t)
        n = max(1, count)
        return clamp01((int(x * n) + (1.0 if x >= 1.0 else 0.0)) / n)

    return curve


#: The names a clip spec may use. Anything else is rejected with BAD_EASING.
CURVES: dict[str, Curve] = {
    "linear": linear,
    "easeInQuad": ease_in_quad,
    "easeOutQuad": ease_out_quad,
    "easeInOutQuad": ease_in_out_quad,
    "easeInCubic": ease_in_cubic,
    "easeOutCubic": ease_out_cubic,
    "easeInOutCubic": ease_in_out_cubic,
    "easeInQuart": ease_in_quart,
    "easeOutQuart": ease_out_quart,
    "easeInExpo": ease_in_expo,
    "easeOutExpo": ease_out_expo,
    "easeOutBack": ease_out_back,
    "easeOutElastic": ease_out_elastic,
    "easeOutBounce": ease_out_bounce,
}

#: Curves that never decrease. The continuity audit can rely on these.
MONOTONE: frozenset[str] = frozenset(
    {
        "linear",
        "easeInQuad",
        "easeOutQuad",
        "easeInOutQuad",
        "easeInCubic",
        "easeOutCubic",
        "easeInOutCubic",
        "easeInQuart",
        "easeOutQuart",
        "easeInExpo",
        "easeOutExpo",
    }
)


def resolve(name: str) -> Curve | None:
    """Look up a curve by spec name. `steps(n)` is resolved by the caller."""
    return CURVES.get(name)


def names() -> list[str]:
    return sorted(CURVES)
