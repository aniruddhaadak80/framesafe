#!/usr/bin/env python3
"""Developer helper: one contact sheet of every clip's mid frame.

    python scripts/contact-sheet.py [out.png]

Not part of the product surface. It exists so a human can review the whole library at
once instead of opening fifteen videos.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine" / "src"))

from PIL import Image  # noqa: E402

from framesafe import compile_spec  # noqa: E402
from framesafe.render import render_frame  # noqa: E402

COLUMNS = 4
TILE = (320, 180)


def main() -> int:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / ".contact-sheet.png"
    specs = sorted((ROOT / "clips").glob("*/spec.json"))
    rows = (len(specs) + COLUMNS - 1) // COLUMNS
    sheet = Image.new("RGB", (COLUMNS * TILE[0], rows * TILE[1]), (5, 6, 8))

    for index, spec_path in enumerate(specs):
        plan = compile_spec(json.loads(spec_path.read_text(encoding="utf-8")))
        frame = render_frame(plan, plan.frame_count // 2)
        tile = frame.resize(TILE, Image.Resampling.BOX)
        sheet.paste(tile, ((index % COLUMNS) * TILE[0], (index // COLUMNS) * TILE[1]))
        print(f"{plan.id:24} frame {plan.frame_count // 2}/{plan.frame_count}")

    sheet.save(out_path)
    print(f"-> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())