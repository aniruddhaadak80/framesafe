#!/usr/bin/env python3
"""check:clip-specs — every clip spec must compile, and must agree with its directory.

This gate is cheap on purpose: it compiles each spec and refuses to render anything, so a
typo in a spec fails in under a second instead of after a four-minute encode.

    python scripts/check-clip-specs.py [clips-root]

Exits 1 on the first invalid spec, naming the file and the engine error code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "engine" / "src"))

from framesafe import compile_spec  # noqa: E402
from framesafe.glyphs import CELL_HEIGHT, CELL_WIDTH  # noqa: E402
from framesafe.plan import ClipPlan  # noqa: E402
from framesafe.protocol import EngineError  # noqa: E402

#: How close to the canvas edge a text layer may come. Broadcast practice keeps type
#: inside the title-safe box, so the gate holds clips to the same rule the safe-area clip
#: draws on screen.
SAFE_INSET_RATIO = 0.05


def text_box(plan: ClipPlan, layer: object) -> tuple[float, float, float, float] | None:
    """The (left, top, right, bottom) a static text layer occupies, in canvas units."""
    params = layer.params  # type: ignore[attr-defined]
    if "counterFrom" in params:
        return None  # a counter's width depends on its value, not on the spec
    text = str(params.get("text", ""))
    if not text:
        return None
    unit = layer.number("scale", 10.0)  # type: ignore[attr-defined]
    tracking = layer.number("tracking", 1.4)  # type: ignore[attr-defined]
    total = ((CELL_WIDTH + tracking) * (len(text) - 1) + CELL_WIDTH) * unit
    left = layer.number("x")  # type: ignore[attr-defined]
    align = str(params.get("align", "left"))
    if align == "center":
        left -= total / 2.0
    elif align == "right":
        left -= total
    top = layer.number("y")  # type: ignore[attr-defined]
    return (left, top, left + total, top + CELL_HEIGHT * unit)


def check_layout(root: Path, spec_path: Path, plan: ClipPlan, problems: list[str]) -> None:
    rel = spec_path.relative_to(root)
    inset = plan.width * SAFE_INSET_RATIO
    boxes: list[tuple[str, tuple[float, float, float, float]]] = []

    for layer in plan.layers:
        if layer.kind != "text":
            continue
        box = text_box(plan, layer)
        if box is None:
            continue
        boxes.append((layer.name, box))
        left, top, right, bottom = box
        if left < inset - 1 or right > plan.width - inset + 1:
            problems.append(
                f"  {rel} — text layer {layer.name!r} spans {round(left)}..{round(right)} "
                f"of a {plan.width}px canvas; keep type inside the "
                f"{round(SAFE_INSET_RATIO * 100)}% safe inset ({round(inset)}px)"
            )
        if top < 0 or bottom > plan.height:
            problems.append(
                f"  {rel} — text layer {layer.name!r} spans {round(top)}..{round(bottom)} "
                f"of a {plan.height}px canvas"
            )

    for index, (name_a, box_a) in enumerate(boxes):
        for name_b, box_b in boxes[index + 1 :]:
            overlap_x = min(box_a[2], box_b[2]) - max(box_a[0], box_b[0])
            overlap_y = min(box_a[3], box_b[3]) - max(box_a[1], box_b[1])
            if overlap_x > 1 and overlap_y > 1:
                problems.append(
                    f"  {rel} — text layers {name_a!r} and {name_b!r} overlap by "
                    f"{round(overlap_x)}x{round(overlap_y)}px"
                )


def main() -> int:
    clips_root = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "clips"
    specs = sorted(clips_root.glob("*/spec.json"))
    if not specs:
        print(f"check:clip-specs FAILED — no specs found under {clips_root}", file=sys.stderr)
        return 1

    problems: list[str] = []
    for path in specs:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            plan = compile_spec(raw)
        except EngineError as error:
            problems.append(f"  {path.relative_to(ROOT)} — {error.code}: {error.message}")
            continue
        except json.JSONDecodeError as error:
            problems.append(f"  {path.relative_to(ROOT)} — invalid JSON: {error}")
            continue

        if plan.id != path.parent.name:
            problems.append(
                f"  {path.relative_to(ROOT)} — spec.id is {plan.id!r} but the directory is "
                f"{path.parent.name!r}"
            )
        for layer in plan.layers:
            end_ms = (
                layer.window.start + layer.window.ease_in + layer.window.hold + layer.window.ease_out
            ) * 1000
            if end_ms < plan.duration_ms * 0.5:
                problems.append(
                    f"  {path.relative_to(ROOT)} — layer {layer.name!r} leaves the frame at "
                    f"{round(end_ms)}ms of a {plan.duration_ms}ms clip"
                )
        check_layout(ROOT, path, plan, problems)

    if problems:
        print(f"check:clip-specs FAILED — {len(problems)} problem(s)", file=sys.stderr)
        for problem in problems:
            print(problem, file=sys.stderr)
        return 1

    print(f"check:clip-specs — {len(specs)} spec(s) compile and lay out")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())