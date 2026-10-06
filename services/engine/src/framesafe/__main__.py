#!/usr/bin/env python3
"""Entry point. Two modes, one JSON contract.

JSON mode — one request on stdin, one response on stdout:

    {"op": "manifest", "input": {"spec": {...}}}

    {"ok": true,  "value": <result>, "durationMs": 3}
    {"ok": false, "error": {"code": "<CODE>", "message": "<human readable>"}, "durationMs": 3}

Stream mode — for `framesafe render`, where a video encoder consumes the pixels:

    {"op": "render_stream", "input": {"spec": {...}}}

stdout then carries raw 8-bit RGB frames back to back with no header or padding, and
stderr carries one `frame <index> <digest>` line per frame. Keeping pixels on stdout and
digests on stderr means the encoder can pipe the first while the host reads the second,
and the engine still needs no socket, no port, and no state that outlives a call.
"""

from __future__ import annotations

import sys
import time
from typing import Any

from .analysis import analyse
from .digest import frame_digest
from .plan import compile_spec
from .protocol import EngineError, read_request, write_response
from .render import FramePainter

STREAM_OP = "render_stream"


def handle(op: str, payload: Any) -> Any:
    if op == STREAM_OP:
        raise EngineError("STREAM_MODE", "render_stream must be requested with --stream")
    return analyse(op, payload)


def run_stream(payload: Any) -> int:
    """Write every frame of a clip to stdout as raw RGB, digests to stderr."""
    if not isinstance(payload, dict) or "spec" not in payload:
        raise EngineError("MISSING_FIELD", "input must be an object with a \"spec\"")
    plan = compile_spec(payload["spec"])

    out = sys.stdout.buffer
    progress = sys.stderr
    for index, frame_bytes in enumerate(FramePainter(plan).raw_frames()):
        out.write(frame_bytes)
        digest = frame_digest(index, plan.width, plan.height, frame_bytes)
        progress.write(f"frame {index} {digest}\n")
        progress.flush()
    out.flush()
    return 0


def main() -> int:
    started = time.perf_counter()

    # `--stream` is read without touching stdin, so a host can pipe the request in.
    stream_mode = "--stream" in sys.argv[1:]

    try:
        op, payload = read_request()
        if stream_mode:
            if op != STREAM_OP:
                raise EngineError("UNKNOWN_OP", f"--stream only accepts {STREAM_OP!r}, got {op!r}")
            return run_stream(payload)
        value = handle(op, payload)
    except EngineError as error:
        duration = int((time.perf_counter() - started) * 1000)
        # The boundary must never leak a traceback to stdout: a caller parses it blindly.
        write_response(
            {
                "ok": False,
                "error": {"code": error.code, "message": error.message},
                "durationMs": duration,
            }
        )
        return 0
    except Exception as error:  # noqa: BLE001 - deliberately total
        duration = int((time.perf_counter() - started) * 1000)
        write_response(
            {
                "ok": False,
                "error": {"code": "INTERNAL", "message": f"{type(error).__name__}: {error}"},
                "durationMs": duration,
            }
        )
        return 0

    duration = int((time.perf_counter() - started) * 1000)
    write_response({"ok": True, "value": value, "durationMs": duration})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
