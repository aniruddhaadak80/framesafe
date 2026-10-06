#!/usr/bin/env python3
"""Developer helper: render one frame of a clip to a PNG so it can be looked at.

    python scripts/preview-frame.py clips/title-block/spec.json 96 [out.png]

Not part of the product surface — the product renders through `framesafe render`, which
goes via the JSON protocol. This exists so a human can inspect a single frame without
encoding a video first.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine" / "src"))

from framesafe import compile_spec  # noqa: E402
from framesafe.render import render_frame  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    spec_path = Path(sys.argv[1])
    index = int(sys.argv[2])
    out_path = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / ".preview.png"

    import json

    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    plan = compile_spec(spec)
    if not 0 <= index < plan.frame_count:
        print(f"frame {index} is outside 0..{plan.frame_count - 1}", file=sys.stderr)
        return 2
    image = render_frame(plan, index)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    print(f"{spec_path.name} frame {index}/{plan.frame_count} -> {out_path} ({image.width}x{image.height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())