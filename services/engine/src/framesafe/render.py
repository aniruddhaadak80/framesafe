"""Turning a compiled plan into pixels.

`render_frame(plan, n)` is a pure function: the same plan and the same index produce the
same bytes on any machine with the same Pillow. There is no font file, no GPU, no clock
and no randomness — the two places where motion graphics usually acquires hidden inputs
are simply absent by construction.

Antialiasing comes from supersampling: layers are drawn at `supersample` times the output
size and the result is box-filtered down, which for an integer factor is exact area
averaging rather than an approximation.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator
from typing import Any

from PIL import Image, ImageDraw

from . import geometry
from .geometry import Point
from .glyphs import CELL_HEIGHT, CELL_WIDTH, glyph_polylines, text_width
from .plan import ClipPlan, Layer

RGB = tuple[int, int, int]
RGBA = tuple[int, int, int, int]

#: Fractional progress, layer opacity, supersample factor, and the frame index. Every
#: painter gets the frame index because a strobe and a waveform are functions of time, and
#: time in a clip is the frame index divided by the frame rate — never a clock read.
Painter = Callable[..., None]


def lcg(seed: int) -> Iterator[float]:
    """A fixed linear congruential generator in [0, 1).

    Seeded per layer, so a spec's apparent randomness is a pure function of the spec and
    no global RNG is ever touched.
    """
    state = (int(seed) & 0xFFFFFFFF) or 0x9E3779B9
    while True:
        state = (state * 1664525 + 1013904223) & 0xFFFFFFFF
        yield state / 4294967296.0


def take(generator: Iterator[float], count: int) -> list[float]:
    return [next(generator) for _ in range(count)]


def lerp_rgb(a: RGB, b: RGB, t: float) -> RGB:
    return (
        int(round(a[0] + (b[0] - a[0]) * t)),
        int(round(a[1] + (b[1] - a[1]) * t)),
        int(round(a[2] + (b[2] - a[2]) * t)),
    )


def clip_segment_above(p0: Point, p1: Point, line_y: float) -> list[Point]:
    """The part of a segment that lies above `line_y`, as a 0-, 1- or 2-point polyline."""
    above0 = p0[1] <= line_y
    above1 = p1[1] <= line_y
    if above0 and above1:
        return [p0, p1]
    if not above0 and not above1:
        return []
    t = (line_y - p0[1]) / (p1[1] - p0[1]) if p1[1] != p0[1] else 0.0
    cut = geometry.lerp_point(p0, p1, t)
    return [p0, cut] if above0 else [cut, p1]


class FramePainter:
    """Draws one clip. Holds no state between frames."""

    def __init__(self, plan: ClipPlan) -> None:
        self.plan = plan
        self.ss = max(1, plan.supersample)
        self.canvas_size = (plan.width * self.ss, plan.height * self.ss)
        background = plan.spec["background"]
        self.background: RGB = (
            int(background[1:3], 16),
            int(background[3:5], 16),
            int(background[5:7], 16),
        )
        self._painters: dict[str, Painter] = {
            "background": self._paint_background,
            "rect": self._paint_rect,
            "line": self._paint_line,
            "polyline": self._paint_polyline,
            "polygon": self._paint_polygon,
            "circle": self._paint_circle,
            "rings": self._paint_rings,
            "particles": self._paint_particles,
            "bars": self._paint_bars,
            "grid": self._paint_grid,
            "text": self._paint_text,
            "guides": self._paint_guides,
            "strobe": self._paint_strobe,
        }

    # ------------------------------------------------------------------ frame

    def frame(self, index: int) -> Image.Image:
        """The composited frame at `index`, at output resolution."""
        canvas = Image.new("RGB", self.canvas_size, self.background)
        for layer in self.plan.layers:
            self._draw_layer(canvas, layer, index)
        if self.ss == 1:
            return canvas
        return canvas.resize((self.plan.width, self.plan.height), Image.Resampling.BOX)

    def raw_frames(self) -> Iterator[bytes]:
        """Raw 8-bit RGB, row-major, no header — exactly what a video encoder consumes."""
        for index in range(self.plan.frame_count):
            yield self.frame(index).tobytes()

    # ------------------------------------------------------------------ plumbing

    def _draw_layer(self, canvas: Image.Image, layer: Layer, index: int) -> None:
        progress = self.plan.progress(layer, index)
        alpha = self.plan.alpha(layer, index)
        if progress <= 0.0 or alpha <= 0.0:
            return

        opaque = alpha >= 0.999
        target = canvas if opaque else Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(target)
        self._painters[layer.kind](draw, layer, progress, alpha, float(self.ss), target, index)
        if not opaque:
            canvas.paste(target, (0, 0), target)

    def _colour(self, rgb: RGB | None, alpha: float, opaque: bool) -> RGBA | None:
        if rgb is None:
            return None
        return (rgb[0], rgb[1], rgb[2], int(round(255 * (1.0 if opaque else alpha))))

    def _primary(self, layer: Layer, alpha: float, opaque: bool) -> RGBA | None:
        """Stroke first when only a stroke is set, so a line layer needs no fill."""
        return self._colour(layer.stroke, alpha, opaque) or self._colour(layer.fill, alpha, opaque)

    def _width(self, layer: Layer, factor: float = 1.0) -> float:
        return max(1.0, layer.stroke_width * self.ss * factor)

    def _closed(
        self,
        draw: ImageDraw.ImageDraw,
        points: list[Point],
        fill: RGBA | None,
        outline: RGBA | None,
        width: int,
    ) -> None:
        if len(points) < 2:
            return
        if fill is not None:
            draw.polygon(points, fill=fill)
        if outline is not None and width > 0:
            draw.line([*points, points[0]], fill=outline, width=width, joint="curve")

    # ------------------------------------------------------------------ kinds

    def _paint_background(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        if layer.fill is None:
            return
        mixed = lerp_rgb(self.background, layer.fill, progress)
        draw.rectangle(
            [0, 0, target.size[0] - 1, target.size[1] - 1],
            fill=(mixed[0], mixed[1], mixed[2], int(round(255 * alpha))),
        )

    def _paint_rect(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        x = layer.number("x") * scale
        y = layer.number("y") * scale
        width = layer.number("w") * scale
        height = layer.number("h") * scale
        radius = layer.number("radius") * scale
        fill = self._colour(layer.fill, alpha, False)
        outline = self._colour(layer.stroke, alpha, False)
        line_width = int(round(self._width(layer)))
        centre = (x + width / 2.0, y + height / 2.0)

        if layer.reveal in {"scale", "fade"}:
            points = geometry.rounded_rect_points(x, y, width, height, radius)
            if layer.reveal == "scale":
                points = geometry.scale_all_about(points, max(0.001, progress), centre)
            self._closed(draw, points, fill, outline, line_width)
        elif layer.reveal == "wipeX":
            self._closed(
                draw,
                geometry.rounded_rect_points(x, y, max(1.0, width * progress), height, radius),
                fill, outline, line_width,
            )
        elif layer.reveal == "wipeY":
            self._closed(
                draw,
                geometry.rounded_rect_points(x, y, width, max(1.0, height * progress), radius),
                fill, outline, line_width,
            )
        else:
            offset_x = (1.0 - progress) * width if layer.reveal == "slideX" else 0.0
            offset_y = (1.0 - progress) * height if layer.reveal == "slideY" else 0.0
            self._closed(
                draw,
                geometry.rounded_rect_points(x + offset_x, y + offset_y, width, height, radius),
                fill, outline, line_width,
            )

    def _paint_line(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        start = (layer.number("x1") * scale, layer.number("y1") * scale)
        end = (layer.number("x2") * scale, layer.number("y2") * scale)
        points: list[Point] = [start, end]
        if layer.reveal == "draw":
            points = geometry.polyline_prefix(points, progress)
        elif layer.reveal == "wipeX":
            cutoff = start[0] + (end[0] - start[0]) * progress
            points = [point for point in points if point[0] <= cutoff] or [start]
        colour = self._primary(layer, alpha, False)
        if colour is not None and len(points) >= 2:
            draw.line(points, fill=colour, width=int(round(self._width(layer))), joint="curve")

    def _paint_polyline(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        raw = [(px * scale, py * scale) for px, py in layer.points("points")]
        if not raw:
            return
        if layer.reveal == "draw":
            points = geometry.polyline_prefix(raw, progress)
        elif layer.reveal == "wipeX":
            low = min(point[0] for point in raw)
            high = max(point[0] for point in raw)
            cutoff = low + (high - low) * progress
            points = [point for point in raw if point[0] <= cutoff] or [raw[0]]
        else:
            points = raw
        colour = self._primary(layer, alpha, False)
        if colour is not None and len(points) >= 2:
            draw.line(points, fill=colour, width=int(round(self._width(layer))), joint="curve")

    def _paint_polygon(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        cx = layer.number("cx") * scale
        cy = layer.number("cy") * scale
        radius = layer.number("r") * scale
        # Explicit paths arrive in canvas units, so they need the same supersample
        # conversion as every other coordinate before they touch the canvas.
        explicit = [(px * scale, py * scale) for px, py in layer.points("points")]
        morph_to = [(px * scale, py * scale) for px, py in layer.points("to")]
        spin = layer.number("spin")

        if explicit:
            count = max(3, len(explicit))
            source = geometry.resample(explicit, count)
            if layer.reveal == "morph" and morph_to:
                destination = geometry.resample(morph_to, len(source))
                points = [
                    (
                        source[i][0] + (destination[i][0] - source[i][0]) * progress,
                        source[i][1] + (destination[i][1] - source[i][1]) * progress,
                    )
                    for i in range(len(source))
                ]
            else:
                points = source
        else:
            sides = int(layer.number("sides"))
            exponent = layer.number("exponent", 2.0)
            grow = progress if layer.reveal in {"grow", "morph"} else 1.0
            diameter = max(2.0, 2.0 * radius * grow)
            if sides >= 3:
                points = geometry.regular_polygon(cx, cy, max(1.0, radius * grow), sides, -90.0)
            else:
                points = geometry.superellipse(cx, cy, diameter, diameter, exponent)

        if spin:
            points = geometry.rotate_all(points, spin * progress, (cx, cy))
        self._closed(
            draw,
            points,
            self._colour(layer.fill, alpha, False),
            self._colour(layer.stroke, alpha, False),
            int(round(self._width(layer))),
        )

    def _paint_circle(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        cx = layer.number("cx") * scale
        cy = layer.number("cy") * scale
        radius = layer.number("r") * scale
        width = int(round(self._width(layer)))

        if layer.reveal == "sweep":
            points = geometry.arc_points(
                cx, cy, radius, layer.number("startDeg", -90.0), layer.number("sweepDeg", 360.0) * progress, 96
            )
            colour = self._primary(layer, alpha, False)
            if colour is not None and len(points) >= 2:
                draw.line(points, fill=colour, width=width, joint="curve")
            return

        effective = radius
        if layer.reveal == "grow":
            effective = max(1.0, radius * progress)
        elif layer.reveal == "pulse":
            effective = max(1.0, radius * (0.55 + 0.45 * math.sin(math.pi * progress)))
        box = [cx - effective, cy - effective, cx + effective, cy + effective]
        if layer.fill is not None:
            draw.ellipse(box, fill=self._colour(layer.fill, alpha, False))
        if layer.stroke is not None and layer.stroke_width > 0:
            draw.ellipse(box, outline=self._colour(layer.stroke, alpha, False), width=width)

    def _paint_rings(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        cx = layer.number("cx") * scale
        cy = layer.number("cy") * scale
        count = max(1, int(layer.number("count", 3.0)))
        from_r = layer.number("fromR", 40.0) * scale
        to_r = layer.number("toR", 240.0) * scale
        sweep = layer.number("sweepDeg", 360.0)
        spin = layer.number("spin", 90.0)
        colour = self._primary(layer, alpha, False)
        if colour is None:
            return
        width = int(round(self._width(layer)))

        for ring in range(count):
            delay = 0.08 * ring
            local = max(0.0, min(1.0, (progress - delay) / 0.6))
            if local <= 0.0:
                continue
            radius = from_r + (to_r - from_r) * local
            points = geometry.arc_points(
                cx, cy, radius, -90.0 + spin * local, sweep * local, 72
            )
            if len(points) >= 2:
                draw.line(points, fill=colour, width=width, joint="curve")

    def _paint_particles(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        count = max(1, int(layer.number("count", 120.0)))
        seed = int(layer.number("seed", 1.0))
        cx = layer.number("cx", self.plan.width / 2.0) * scale
        cy = layer.number("cy", self.plan.height / 2.0) * scale
        spread_x = layer.number("spreadX", 900.0) * scale
        spread_y = layer.number("spreadY", 600.0) * scale
        drift = layer.number("drift", 220.0) * scale
        size = layer.number("size", 3.0) * scale
        colour = self._primary(layer, alpha, False)
        if colour is None:
            return

        travel = drift * progress
        rng = lcg(seed)
        for _ in range(count):
            px = cx + (next(rng) - 0.5) * spread_x
            py = cy + (next(rng) - 0.5) * spread_y
            depth = next(rng)
            angle = next(rng) * math.tau
            radius = size * (0.35 + depth)
            x = px + math.cos(angle) * travel * depth
            y = py + math.sin(angle) * travel * depth
            shade = int(colour[3] * (0.3 + 0.7 * depth))
            draw.ellipse(
                [x - radius, y - radius, x + radius, y + radius],
                fill=(colour[0], colour[1], colour[2], shade),
            )

    def _paint_bars(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        count = max(1, int(layer.number("count", 32.0)))
        seed = int(layer.number("seed", 7.0))
        x = layer.number("x", 120.0) * scale
        baseline = layer.number("baseline", 560.0) * scale
        bar_width = layer.number("barWidth", 18.0) * scale
        gap = layer.number("gap", 8.0) * scale
        max_height = layer.number("height", 320.0) * scale
        colour = self._primary(layer, alpha, False)
        if colour is None:
            return

        time_s = self.plan.time_of(index)
        phases = take(lcg(seed), 3)
        for index_bar in range(count):
            position = index_bar / max(1, count - 1)
            wave = (
                math.sin(time_s * 2.4 + position * 6.1 + phases[0]) * 0.5
                + math.sin(time_s * 3.7 + position * 13.7 + phases[1]) * 0.32
                + math.sin(time_s * 5.1 + position * 27.3 + phases[2]) * 0.18
            )
            envelope = 0.5 + 0.5 * wave
            height = max_height * envelope * progress
            left = x + index_bar * (bar_width + gap)
            draw.rectangle(
                [left, baseline - height, left + bar_width, baseline],
                fill=(colour[0], colour[1], colour[2], colour[3]),
            )

    def _paint_grid(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        cols = max(1, int(layer.number("cols", 8.0)))
        rows = max(1, int(layer.number("rows", 5.0)))
        x = layer.number("x", 120.0) * scale
        y = layer.number("y", 120.0) * scale
        cell = layer.number("cell", 90.0) * scale
        gap = layer.number("gap", 12.0) * scale
        fill = self._colour(layer.fill, alpha, False)
        outline = self._colour(layer.stroke, alpha, False)
        colour = fill or outline
        if colour is None:
            return
        line_width = int(round(self._width(layer)))

        span = max(1, cols + rows - 2)
        for column in range(cols):
            for row in range(rows):
                order = (column + row) / span
                if layer.reveal == "sweep":
                    # A travelling band, not an accumulating wipe: a wipe saturates the
                    # whole grid to one flat brightness and stops being a sweep at all.
                    brightness = max(0.0, 1.0 - abs(order - progress) * 2.6)
                    if brightness <= 0.02:
                        continue
                else:
                    brightness = 0.3 + 0.7 * (0.5 + 0.5 * math.sin(math.pi * progress - order * 2.2))
                left = x + column * (cell + gap)
                top = y + row * (cell + gap)
                box = [left, top, left + cell, top + cell]
                if fill is not None:
                    draw.rectangle(
                        box,
                        fill=(
                            int(fill[0] * brightness),
                            int(fill[1] * brightness),
                            int(fill[2] * brightness),
                            fill[3],
                        ),
                    )
                if outline is not None and line_width > 0:
                    draw.rectangle(
                        box,
                        outline=(
                            int(outline[0] * brightness),
                            int(outline[1] * brightness),
                            int(outline[2] * brightness),
                            outline[3],
                        ),
                        width=line_width,
                    )

    def _paint_guides(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        colour = self._primary(layer, alpha, False)
        if colour is None:
            return
        width, height = target.size
        line_width = int(round(self._width(layer)))
        mode = str(layer.params.get("mode", "safe"))

        if mode == "safe":
            for inset in (0.05, 0.10):
                x = width * inset
                y = height * inset
                draw.rectangle([x, y, width - x, height - y], outline=colour, width=line_width)
        elif mode == "overscan":
            draw.rectangle([0, 0, width - 1, height - 1], outline=colour, width=line_width)
        else:
            for fraction in (1 / 3, 2 / 3):
                draw.line([width * fraction, 0, width * fraction, height], fill=colour, width=line_width)
                draw.line([0, height * fraction, width, height * fraction], fill=colour, width=line_width)

        if layer.reveal == "sweep":
            # A wipe-in along the top edge, so guides arrive instead of appearing.
            step = max(1, int(self._width(layer)))
            offset = int((1.0 - progress) * width)
            draw.line([0, 0, width, 0], fill=colour, width=offset + step)

    def _paint_text(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        text = str(layer.params.get("text", "")).upper()
        unit = layer.number("scale", 10.0) * scale
        tracking = layer.number("tracking", 1.4)
        stagger = layer.number("stagger", 0.12)
        origin_x = layer.number("x") * scale
        origin_y = layer.number("y") * scale
        align = str(layer.params.get("align", "left"))
        stroke_only = layer.stroke is not None and layer.fill is None
        colour = (
            self._colour(layer.stroke, alpha, False)
            if stroke_only
            else self._colour(layer.fill, alpha, False)
        )
        if colour is None:
            return

        if "counterFrom" in layer.params and "counterTo" in layer.params:
            self._paint_roll(
                draw, target, layer, progress, colour, unit, tracking, origin_x, origin_y, align
            )
            return

        count = len(text)
        advance = (CELL_WIDTH + tracking) * unit
        # text_width already folds the scale in, so this is a device-space width.
        total = text_width(count, unit, tracking)
        start_x = origin_x
        if align == "center":
            start_x -= total / 2.0
        elif align == "right":
            start_x -= total

        offset_y = (1.0 - progress) * CELL_HEIGHT * unit * 0.7 if layer.reveal == "slideUp" else 0.0
        block_height = CELL_HEIGHT * unit
        mask_line = origin_y + offset_y + block_height * progress
        width = max(1.0, self._width(layer, 0.9))
        span = 1.0 + (count - 1) * stagger

        for position, character in enumerate(text):
            if layer.reveal == "hold":
                local = 1.0
            else:
                local = max(0.0, min(1.0, progress * span - position * stagger))
            if local <= 0.0:
                continue
            glyph_origin = (start_x + position * advance, origin_y + offset_y)
            for polyline in glyph_polylines(character, unit, glyph_origin):
                if layer.reveal == "draw":
                    visible = geometry.polyline_prefix(polyline, local)
                    if len(visible) >= 2:
                        draw.line(visible, fill=colour, width=int(round(width)), joint="curve")
                    self._dot(draw, visible[-1], width, colour)
                elif layer.reveal == "mask":
                    visible = geometry.polyline_prefix(polyline, local)
                    for index_a in range(1, len(visible)):
                        piece = clip_segment_above(visible[index_a - 1], visible[index_a], mask_line)
                        if len(piece) >= 2:
                            draw.line(piece, fill=colour, width=int(round(width)))
                else:
                    faded = (
                        (colour[0], colour[1], colour[2], colour[3])
                        if stroke_only
                        else (colour[0], colour[1], colour[2], int(round(colour[3] * local)))
                    )
                    drawn = geometry.polyline_prefix(polyline, local)
                    if len(drawn) >= 2:
                        draw.line(drawn, fill=faded, width=int(round(width)), joint="curve")
                    self._dot(draw, drawn[-1], width, faded)

    def _dot(self, draw: ImageDraw.ImageDraw, point: Point, width: float, colour: RGBA) -> None:
        """A round cap at a partially drawn stroke tip, so a draw-on never ends flat."""
        radius = width / 2.0
        draw.ellipse(
            [point[0] - radius, point[1] - radius, point[0] + radius, point[1] + radius],
            fill=colour,
        )

    def _paint_roll(
        self,
        draw: ImageDraw.ImageDraw,
        target: Image.Image,
        layer: Layer,
        progress: float,
        colour: RGBA,
        unit: float,
        tracking: float,
        origin_x: float,
        origin_y: float,
        align: str,
    ) -> None:
        """A counter whose digits roll, odometer style.

        The value is a pure function of the layer's progress, and each digit is drawn at
        the fractional offset implied by the digits to its right — so the roll is
        frame-exact rather than an accumulation of frame-to-frame state.
        """
        start_value = layer.number("counterFrom", 0.0)
        end_value = layer.number("counterTo", 100.0)
        digits = max(1, len(str(int(max(abs(start_value), abs(end_value))))))
        cell_height = CELL_HEIGHT * unit
        advance = (CELL_WIDTH + tracking) * unit
        total = text_width(digits, unit, tracking)
        stroke_width = max(1.0, self._width(layer, 0.9))

        left = origin_x
        if align == "center":
            left -= total / 2.0
        elif align == "right":
            left -= total

        margin = unit
        box_width = int(math.ceil(total + 2 * margin))
        box_height = int(math.ceil(2 * cell_height))
        sheet = Image.new("RGBA", (box_width, box_height), (0, 0, 0, 0))
        pen = ImageDraw.Draw(sheet)

        value = start_value + (end_value - start_value) * progress
        for position in range(digits):
            place = 10.0 ** (digits - 1 - position)
            digit = int(value // place) % 10
            fraction = (value / place) % 1.0
            cell_x = margin + position * advance
            offset = cell_height - fraction * cell_height

            for glyph_index, character in enumerate((str(digit), str((digit + 1) % 10))):
                if glyph_index == 1 and fraction <= 0.0:
                    continue
                top = offset + glyph_index * cell_height
                for polyline in glyph_polylines(character, unit, (cell_x, top)):
                    if len(polyline) >= 2:
                        pen.line(polyline, fill=colour, width=int(round(stroke_width)), joint="curve")
                        self._dot(pen, polyline[-1], stroke_width, colour)

        # Show only the one-cell-tall window the digits roll through.
        window = sheet.crop((0, int(cell_height), box_width, int(2 * cell_height)))
        target.paste(
            window,
            (int(round(left - margin)), int(round(origin_y))),
            window,
        )

    def _paint_strobe(
        self, draw: ImageDraw.ImageDraw, layer: Layer, progress: float,
        alpha: float, scale: float, target: Image.Image, index: int,
    ) -> None:
        period = max(1.0, layer.number("periodMs", 120.0)) / 1000.0
        duty = max(0.05, min(1.0, layer.number("dutyCycle", 0.5)))
        on_colour: RGB = layer.fill or (255, 255, 255)
        off_colour: RGB = layer.stroke or (0, 0, 0)
        elapsed = max(0.0, self.plan.time_of(index) - layer.window.start)
        phase = (elapsed % period) / period
        mixed = lerp_rgb(off_colour, on_colour, 1.0 if phase < duty else 0.0)
        draw.rectangle(
            [0, 0, target.size[0] - 1, target.size[1] - 1],
            fill=(mixed[0], mixed[1], mixed[2], int(round(255 * alpha))),
        )


def render_frame(plan: ClipPlan, index: int) -> Image.Image:
    """Render one frame. The unit of work behind every digest in a manifest."""
    if not 0 <= index < plan.frame_count:
        raise IndexError(f"frame {index} is outside 0..{plan.frame_count - 1}")
    return FramePainter(plan).frame(index)


def raw_frame_bytes(plan: ClipPlan, index: int) -> bytes:
    return render_frame(plan, index).tobytes()


def iter_raw_frames(plan: ClipPlan) -> Iterator[bytes]:
    return FramePainter(plan).raw_frames()


def frame_plan_summary(plan: ClipPlan) -> dict[str, Any]:
    """A small, JSON-safe description of the compiled clip. Used by CLI, MCP and the site."""
    return {
        "id": plan.id,
        "title": plan.title,
        "specDigest": f"sha256:{plan.spec_digest}",
        "fps": plan.fps,
        "width": plan.width,
        "height": plan.height,
        "supersample": plan.supersample,
        "durationMs": plan.duration_ms,
        "frameCount": plan.frame_count,
        "durationS": round(plan.duration_s, 6),
        "continuityBudget": plan.continuity_budget,
        "maxAdjacentContrast": plan.max_adjacent_contrast,
        "reducedMotion": plan.spec["reducedMotion"],
        "technique": plan.spec["technique"],
        "tags": plan.spec["tags"],
        "layers": [
            {
                "index": layer.index,
                "kind": layer.kind,
                "name": layer.name,
                "reveal": layer.reveal,
                "easing": layer.window.easing,
                "startMs": int(round(layer.window.start * 1000)),
                "inMs": int(round(layer.window.ease_in * 1000)),
                "holdMs": int(round(layer.window.hold * 1000)),
                "outMs": int(round(layer.window.ease_out * 1000)),
            }
            for layer in plan.layers
        ],
    }
