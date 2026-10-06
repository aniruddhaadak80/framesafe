"""Print the golden digests for the render test. Used once, then the values are pasted in.

    python scripts/print-golden.py > services/engine/tests/golden.txt

The digests depend on the Pillow version, which is why the manifest records the renderer
fingerprint: a Pillow upgrade legitimately changes these, and the diff is the point.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine" / "src"))
sys.path.insert(0, str(ROOT / "services" / "engine" / "tests"))

from test_render_audit import GOLDEN_SPEC  # noqa: E402

from framesafe import compile_spec, digest_image  # noqa: E402
from framesafe.render import render_frame  # noqa: E402


def main() -> int:
    plan = compile_spec(GOLDEN_SPEC)
    print(f"# pillow plan frame count {plan.frame_count} renderer {plan.spec_digest[:12]}")
    for index in range(plan.frame_count):
        print(f'    "{digest_image(index, render_frame(plan, index))}",')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())