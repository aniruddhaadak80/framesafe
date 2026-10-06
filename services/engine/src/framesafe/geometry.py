"""Vector geometry. Pure arithmetic on points; nothing here knows about pixels.

Points are 2-tuples of float. Polylines and polygons are lists of them. The renderer is
the only module allowed to turn these into pixels, which is what keeps a digest proof
about geometry rather than about a drawing library's internals.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

Point = tuple[float, float]
Polyline = list[Point]


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_point(a: Point, b: Point, t: float) -> Point:
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t))


def rotate(point: Point, degrees: float, origin: Point = (0.0, 0.0)) -> Point:
    """Rotate `point` about `origin` by `degrees`, counter-clockwise in maths axes."""
    radians = math.radians(degrees)
    cos_a = math.cos(radians)
    sin_a = math.sin(radians)
    dx = point[0] - origin[0]
    dy = point[1] - origin[1]
    return (origin[0] + dx * cos_a - dy * sin_a, origin[1] + dx * sin_a + dy * cos_a)


def rotate_all(points: Sequence[Point], degrees: float, origin: Point) -> list[Point]:
    return [rotate(point, degrees, origin) for point in points]


def scale_about(point: Point, factor: float, origin: Point) -> Point:
    return (origin[0] + (point[0] - origin[0]) * factor, origin[1] + (point[1] - origin[1]) * factor)


def scale_all_about(points: Sequence[Point], factor: float, origin: Point) -> list[Point]:
    return [scale_about(point, factor, origin) for point in points]


def polyline_length(points: Sequence[Point]) -> float:
    """Total Euclidean length. A single point has length 0, not NaN."""
    total = 0.0
    for index in range(1, len(points)):
        ax, ay = points[index - 1]
        bx, by = points[index]
        total += math.hypot(bx - ax, by - ay)
    return total


def polyline_prefix(points: Sequence[Point], fraction: float) -> Polyline:
    """The leading `fraction` of a polyline, cut at an exact arc-length position.

    This is what makes a stroke draw-on frame-exact: the visible length is a pure
    function of the frame's progress, not of how many segments happen to be in the path.
    """
    if not points:
        return []
    if fraction <= 0.0:
        return [points[0]]
    total = polyline_length(points)
    if total <= 0.0 or fraction >= 1.0:
        return list(points)

    target = total * fraction
    out: Polyline = [points[0]]
    travelled = 0.0
    for index in range(1, len(points)):
        ax, ay = points[index - 1]
        bx, by = points[index]
        segment = math.hypot(bx - ax, by - ay)
        if segment <= 0.0:
            continue
        if travelled + segment >= target:
            remaining = target - travelled
            out.append((lerp(ax, bx, remaining / segment), lerp(ay, by, remaining / segment)))
            return out
        travelled += segment
        out.append(points[index])
    return out


def regular_polygon(
    cx: float, cy: float, radius: float, sides: int, rotation_degrees: float = -90.0
) -> list[Point]:
    """A regular polygon. `sides` below 3 is a line, which the spec validator rejects."""
    n = max(3, int(sides))
    points: list[Point] = []
    for index in range(n):
        angle = math.radians(rotation_degrees + (360.0 * index) / n)
        points.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return points


def star_points(
    cx: float, cy: float, outer: float, inner: float, points_count: int, rotation_degrees: float = -90.0
) -> list[Point]:
    """A star polygon with `points_count` spikes."""
    n = max(2, int(points_count))
    out: list[Point] = []
    for index in range(n * 2):
        radius = outer if index % 2 == 0 else inner
        angle = math.radians(rotation_degrees + (180.0 * index) / n)
        out.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return out


def superellipse(
    cx: float, cy: float, width: float, height: float, exponent: float, count: int = 64
) -> list[Point]:
    """A squircle-style closed path. `exponent` 2 is an ellipse, higher is boxier."""
    n = max(8, int(count))
    a = width / 2.0
    b = height / 2.0
    out: list[Point] = []
    for index in range(n):
        theta = 2.0 * math.pi * index / n
        cos_t = math.cos(theta)
        sin_t = math.sin(theta)
        x = math.copysign(abs(cos_t) ** (2.0 / exponent), cos_t)
        y = math.copysign(abs(sin_t) ** (2.0 / exponent), sin_t)
        out.append((cx + a * x, cy + b * y))
    return out


def rounded_rect_points(
    x: float, y: float, width: float, height: float, radius: float, segments: int = 6
) -> list[Point]:
    """A closed rounded-rectangle path, walked clockwise from the top-left corner."""
    r = max(0.0, min(radius, width / 2.0, height / 2.0))
    if r <= 0.0:
        return [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
    steps = max(1, int(segments))
    corners = (
        (x + width - r, y + r, -90.0, 0.0),
        (x + width - r, y + height - r, 0.0, 90.0),
        (x + r, y + height - r, 90.0, 180.0),
        (x + r, y + r, 180.0, 270.0),
    )
    out: list[Point] = []
    for cx, cy, start_deg, end_deg in corners:
        for step in range(steps + 1):
            angle = math.radians(start_deg + (end_deg - start_deg) * step / steps)
            out.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    return out


def arc_points(
    cx: float, cy: float, radius: float, start_degrees: float, sweep_degrees: float, steps: int = 48
) -> Polyline:
    """An open arc. A sweep of 360 or more closes the path onto itself."""
    n = max(1, int(steps))
    out: list[Point] = []
    for step in range(n + 1):
        angle = math.radians(start_degrees + sweep_degrees * step / n)
        out.append((cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return out


def ellipse_points(cx: float, cy: float, width: float, height: float, steps: int = 64) -> list[Point]:
    return superellipse(cx, cy, width, height, 2.0, steps)


def centroid(points: Sequence[Point]) -> Point:
    """Area centroid with a vertex-average fallback for degenerate paths."""
    if not points:
        return (0.0, 0.0)
    twice_area = 0.0
    cx = 0.0
    cy = 0.0
    for index in range(len(points)):
        ax, ay = points[index]
        bx, by = points[(index + 1) % len(points)]
        cross = ax * by - bx * ay
        twice_area += cross
        cx += (ax + bx) * cross
        cy += (ay + by) * cross
    if abs(twice_area) < 1e-9:
        return (
            sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points),
        )
    factor = 1.0 / (3.0 * twice_area)
    return (cx * factor, cy * factor)


def bounds(points: Sequence[Point]) -> tuple[float, float, float, float]:
    """(min_x, min_y, max_x, max_y). An empty path has a zero-extent box at the origin."""
    if not points:
        return (0.0, 0.0, 0.0, 0.0)
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def resample(points: Sequence[Point], count: int) -> list[Point]:
    """Resample a polyline to exactly `count` points by arc length.

    Morph targets need matching vertex counts, and forcing that here keeps the spec
    author from having to know the arc-length arithmetic.
    """
    n = max(2, int(count))
    if len(points) < 2:
        return [points[0] if points else (0.0, 0.0)] * n
    lengths: list[float] = [0.0]
    for index in range(1, len(points)):
        ax, ay = points[index - 1]
        bx, by = points[index]
        lengths.append(lengths[-1] + math.hypot(bx - ax, by - ay))
    total = lengths[-1]
    if total <= 0.0:
        return [points[0]] * n
    out: list[Point] = []
    segment = 0
    for index in range(n):
        target = total * index / (n - 1)
        while segment < len(points) - 2 and lengths[segment + 1] < target:
            segment += 1
        span = lengths[segment + 1] - lengths[segment]
        local = 0.0 if span <= 0.0 else (target - lengths[segment]) / span
        out.append(lerp_point(points[segment], points[segment + 1], local))
    return out
