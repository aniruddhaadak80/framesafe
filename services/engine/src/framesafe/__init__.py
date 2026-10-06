"""framesafe's deterministic engine.

Every operation is a pure function of its JSON input: same input, same output, no clock,
no network, no randomness, no filesystem, no model. Time in a clip is the frame index
divided by the frame rate; entropy is a seeded generator carried inside the spec. That is
what lets a manifest committed on one machine be re-verified on another.

The engine speaks JSON over stdin/stdout so the TypeScript host can call it as a
function rather than maintain a server.
"""

from .analysis import OPERATIONS, analyse, renderer_fingerprint
from .digest import digest_image, first_difference, frame_digest, root_digest
from .geometry import Point, Polyline
from .plan import ClipPlan, compile_spec
from .protocol import EngineError
from .render import render_frame
from .spec import LAYER_KINDS, PALETTE, REVEALS, validate

__all__ = [
    "ClipPlan",
    "EngineError",
    "LAYER_KINDS",
    "OPERATIONS",
    "PALETTE",
    "Point",
    "Polyline",
    "REVEALS",
    "analyse",
    "compile_spec",
    "digest_image",
    "first_difference",
    "frame_digest",
    "render_frame",
    "renderer_fingerprint",
    "root_digest",
    "validate",
]
__version__ = "0.1.0"
