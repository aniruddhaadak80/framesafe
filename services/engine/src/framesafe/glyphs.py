"""A stroke font defined in source, so a rendered frame never depends on a system font.

Each glyph is a list of polylines on a 4 x 6 grid (x right, y down). Rendering scales the
grid by `scale` and strokes it with a round cap, which gives a geometric, constructed
letterform that reads as motion-graphics type rather than as a bitmap font.

Why not a TTF: a system font would make frame digests depend on which machine rendered
them. The whole reproducibility claim rests on the render being a function of the spec
alone, so the type has to travel with the code.
"""

from __future__ import annotations

from .geometry import Point

#: One glyph is a list of polylines; each polyline is a list of points on the cell grid.
Glyph = list[list[Point]]

#: Glyph cells are 5 wide and 7 tall so glyphs can be spaced by an integer advance.
CELL_WIDTH = 5.0
CELL_HEIGHT = 7.0

GLYPHS: dict[str, Glyph] = {
    " ": [],
    "A": [[(0, 6), (2, 0), (4, 6)], [(0.8, 4), (3.2, 4)]],
    "B": [[(0, 0), (0, 6)], [(0, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)], [(0, 3), (3, 3), (4, 4), (4, 5), (3, 6), (0, 6)]],
    "C": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)]],
    "D": [[(0, 0), (0, 6)], [(0, 0), (2, 0), (4, 2), (4, 4), (2, 6), (0, 6)]],
    "E": [[(4, 0), (0, 0), (0, 6), (4, 6)], [(0, 3), (3,3)]],
    "F": [[(4, 0), (0, 0), (0, 6)], [(0, 3), (3, 3)]],
    "G": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 3), (2, 3)]],
    "H": [[(0, 0), (0, 6)], [(4, 0), (4, 6)], [(0, 3), (4, 3)]],
    "I": [[(0, 0), (4, 0)], [(2, 0), (2, 6)], [(0, 6), (4, 6)]],
    "J": [[(4, 0), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "K": [[(0, 0), (0, 6)], [(4, 0), (0, 3), (4, 6)]],
    "L": [[(0, 0), (0, 6), (4, 6)]],
    "M": [[(0, 6), (0, 0), (2, 2.5), (4, 0), (4, 6)]],
    "N": [[(0, 6), (0, 0), (4, 6), (4, 0)]],
    "O": [[(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)]],
    "P": [[(0, 6), (0, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)]],
    "Q": [
        [(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)],
        [(2.4, 4.2), (4, 6)],
    ],
    "R": [[(0, 6), (0, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)], [(2, 3), (4, 6)]],
    "S": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 2), (1, 3), (3, 3), (4, 4), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "T": [[(0, 0), (4, 0)], [(2, 0), (2, 6)]],
    "U": [[(0, 0), (0, 5), (1, 6), (3, 6), (4, 5), (4, 0)]],
    "V": [[(0, 0), (2, 6), (4, 0)]],
    "W": [[(0, 0), (1, 6), (2, 3.2), (3, 6), (4, 0)]],
    "X": [[(0, 0), (4, 6)], [(4, 0), (0, 6)]],
    "Y": [[(0, 0), (2, 3), (4, 0)], [(2, 3), (2, 6)]],
    "Z": [[(0, 0), (4, 0), (0, 6), (4, 6)]],
    "0": [
        [(1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0)],
        [(0.6, 5.2), (3.4, 0.8)],
    ],
    "1": [[(0.6, 1.4), (2, 0), (2, 6)], [(0.6, 6), (3.4, 6)]],
    "2": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (0, 6), (4, 6)]],
    "3": [[(0, 0), (4, 0), (2, 3), (4, 4), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "4": [[(3, 6), (3, 0), (0, 4), (4, 4)]],
    "5": [[(4, 0), (0, 0), (0, 3), (3, 3), (4, 4), (4, 5), (3, 6), (1, 6), (0, 5)]],
    "6": [[(4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (3, 3), (1, 3), (0, 4)]],
    "7": [[(0, 0), (4, 0), (1, 6)]],
    "8": [
        [(1, 0), (3, 0), (4, 1), (3, 3), (1, 3), (0, 1), (1, 0)],
        [(1, 3), (3, 3), (4, 4), (4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3)],
    ],
    "9": [[(0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0), (0, 1), (0, 2), (1, 3), (3, 3), (4, 2)]],
    ".": [[(2, 5), (2, 6)]],
    ",": [[(2.2, 5), (1.2, 7)]],
    ":": [[(2, 2), (2, 2.6)], [(2, 4.4), (2, 5)]],
    "-": [[(1, 3), (3, 3)]],
    "+": [[(2, 2), (2, 4)], [(1, 3), (3, 3)]],
    "=": [[(0.6, 2.4), (3.4, 2.4)], [(0.6, 3.8), (3.4, 3.8)]],
    "_": [[(0, 6), (4, 6)]],
    "/": [[(0, 6), (4, 0)]],
    "\\": [[(0, 0), (4, 6)]],
    "'": [[(2, 0), (2, 1.8)]],
    '"': [[(1.2, 0), (1.2, 1.8)], [(2.8, 0), (2.8, 1.8)]],
    "!": [[(2, 0), (2, 4)], [(2, 5.2), (2, 5.8)]],
    "?": [[(0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (2, 3.2), (2, 4.2)], [(2, 5.2), (2, 5.8)]],
    "(": [[(3, 0), (1, 2), (1, 4.4), (3, 6.4)]],
    ")": [[(1, 0), (3, 2), (3, 4.4), (1, 6.4)]],
    "[": [[(3, 0), (1, 0), (1, 6.4), (3, 6.4)]],
    "]": [[(1, 0), (3, 0), (3, 6.4), (1, 6.4)]],
    "<": [[(3, 1), (1, 3), (3, 5)]],
    ">": [[(1, 1), (3, 3), (1, 5)]],
    "*": [[(2, 1), (2, 5)], [(0.2, 2), (3.8, 4)], [(3.8, 2), (0.2, 4)]],
    "#": [[(1.2, 0.4), (0.8, 6)], [(3.2, 0.4), (2.8, 6)], [(0, 2.4), (4, 2.4)], [(0, 4.4), (4, 4.4)]],
    "%": [
        [(0, 6), (4, 0)],
        [(0, 0), (1.2, 0), (1.2, 1.6), (0, 1.6), (0, 0)],
        [(2.8, 4.4), (4, 4.4), (4, 6), (2.8, 6), (2.8, 4.4)],
    ],
    "&": [
        [(4, 6), (1, 2.4), (1, 1), (2, 0), (3, 0.6), (3, 2), (0.4, 4), (0.6, 5.4), (1.6, 6), (3, 5.2), (4, 4)],
    ],
    "@": [
        [(3.4, 2), (2, 1.4), (1.2, 2.4), (1.6, 4), (2.8, 4.2), (3.4, 3.2), (3.4, 2)],
        [(3.4, 3.2), (4, 3.8), (3.6, 5.6), (1.6, 6), (0, 4.6), (0, 1.6), (1.6, 0), (3.6, 0.4)],
    ],
    "·": [[(2, 3), (2, 3.6)]],
    "•": [[(1.4, 2.6), (2.6, 4.2)]],
}

#: Characters the renderer can draw. A spec naming anything else fails with BAD_GLYPH.
SUPPORTED: frozenset[str] = frozenset(GLYPHS)

#: Extra advance per glyph beyond the cell, in grid units.
DEFAULT_TRACKING = 1.4


def text_width(count: int, scale: float, tracking: float = DEFAULT_TRACKING) -> float:
    """Total advance width of `count` glyphs, in device units."""
    if count <= 0:
        return 0.0
    cell = CELL_WIDTH + tracking
    return (cell * (count - 1) + CELL_WIDTH) * scale


def glyph_polylines(character: str, scale: float, origin: Point) -> list[list[Point]]:
    """One glyph's polylines in device units, with `origin` at the glyph's top-left.

    Grid coordinates are scaled and translated only — no per-glyph special casing, so the
    rendered letterform is a pure function of the table above and the requested scale.
    """
    strokes = GLYPHS.get(character.upper())
    if not strokes:
        return []
    ox, oy = origin
    return [
        [(ox + x * scale, oy + y * scale) for (x, y) in stroke]
        for stroke in strokes
    ]
