"""Frame digests: the address of a rendered frame.

A digest is computed over a canonical byte string — the clip's dimensions, the frame
index, and the frame's RGB bytes — so two digests are comparable only when they describe
the same geometry at the same instant. A digest is a statement about a render, never
about a file: the MP4 that ships to a browser is a lossy downstream encoding and is
digested separately.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Sequence

from PIL import Image

#: Bumped if the digest recipe itself changes, so old manifests can never be silently
#: compared against new digests.
DIGEST_RECIPE = "framesafe/frame-digest/1"


def frame_digest(index: int, width: int, height: int, pixels: bytes) -> str:
    """The sha256 of one frame, prefixed with the recipe so it is self-describing."""
    header = f"{DIGEST_RECIPE}|{width}x{height}|{index}|".encode()
    return "sha256:" + hashlib.sha256(header + pixels).hexdigest()


def digest_image(index: int, image: Image.Image) -> str:
    """Digest a Pillow image. Alpha is dropped: the canonical form is 8-bit RGB."""
    return frame_digest(index, image.width, image.height, image.convert("RGB").tobytes())


def short(digest: str) -> str:
    """The first 12 hex characters, for display. Never use this to compare frames."""
    return digest.split(":", 1)[-1][:12]


def root_digest(digests: Sequence[str]) -> str:
    """One digest standing for an ordered list of frame digests.

    Concatenation over `index:digest` leaves, in frame order. Order matters, so a
    reordered or dropped frame changes the root even when every leaf is still present.
    """
    accumulator = hashlib.sha256()
    for index, digest in enumerate(digests):
        accumulator.update(f"{index}:{digest}\n".encode())
    return "sha256:" + accumulator.hexdigest()


def spec_digest(canonical: str) -> str:
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def first_difference(left: Sequence[str], right: Sequence[str]) -> dict[str, int | None]:
    """Where two digest lists stop agreeing. Reports length disagreement explicitly."""
    shared = min(len(left), len(right))
    for index in range(shared):
        if left[index] != right[index]:
            return {
                "frameIndex": index,
                "expectedLength": len(left),
                "actualLength": len(right),
                "identical": False,
            }
    return {
        "frameIndex": shared if shared < max(len(left), len(right)) else None,
        "expectedLength": len(left),
        "actualLength": len(right),
        "identical": len(left) == len(right),
    }


def digest_lines(digests: Iterable[str]) -> str:
    return "\n".join(digests) + "\n"
