"""Golden digests for the render pipeline — the anti-drift test.

These are real values, produced by `python scripts/print-golden.py` on Pillow 12.3.0 /
numpy 2.5.3. If this test fails, a pixel changed: re-render the library and review the
manifest diff rather than pasting new values in. A renderer change is a product change.
"""

GOLDEN_SPEC = {
    "id": "golden",
    "title": "Golden",
    "technique": ["fade"],
    "fps": 12,
    "width": 96,
    "height": 54,
    "durationMs": 500,
    "supersample": 2,
    "layers": [
        {
            "kind": "background",
            "t": {"startMs": 0, "inMs": 100, "holdMs": 300, "outMs": 100},
            "fill": "panel",
            "reveal": "fade",
        },
        {
            "kind": "circle",
            "t": {"startMs": 0, "inMs": 250, "holdMs": 150, "outMs": 100},
            "cx": 48,
            "cy": 27,
            "r": 16,
            "stroke": "accent",
            "strokeWidth": 2,
            "reveal": "grow",
        },
    ],
}

GOLDEN_DIGESTS = [
    "sha256:e6626abe1c4260b23a872e598ad024272296a7d394c9f723a59228ac802728e1",
    "sha256:df0282a12974ed3418d670a411e901ab148a3a172918d4ebfcf7c01cfa17f6fb",
    "sha256:47e060638c3b3201f0ab323f81466432bf486896d9f33bfaa4f165c778d5b1ed",
    "sha256:653c01760f92bcccde35ad82078c67d935866b197112edb7159d6648cea3d871",
    "sha256:838aa3739ab452404291138a5fa0700952f12fd73c48fa0bbec8fbce87407aef",
    "sha256:3833663669fa1dec029b6af0a588787970df7666b8e967e3ec43283f36f82a55",
]

#: The renderer these digests were produced with. Recorded here so a failure explains
#: itself: "pillow upgraded" is a different conversation from "we changed the renderer".
GOLDEN_RENDERER = {"pillow": "12.3.0", "numpy": "2.5.3"}
