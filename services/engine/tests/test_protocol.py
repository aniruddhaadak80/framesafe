"""The wire protocol: one JSON object in, one JSON object out, never a traceback.

The boundary is the only place a malformed caller can hurt the engine, so the tests here are
about refusal: bad JSON, a missing op, an oversized payload, and an op that does not exist.
"""

from __future__ import annotations

import io
import json
from typing import Any

import pytest

from framesafe import analyse
from framesafe.__main__ import handle
from framesafe import protocol
from framesafe.protocol import EngineError, read_request, write_response

SPEC: dict[str, Any] = {
    "id": "unit",
    "title": "Unit",
    "technique": ["fade"],
    "durationMs": 200,
    "fps": 10,
    "width": 32,
    "height": 32,
    "layers": [
        {
            "kind": "rect",
            "t": {"inMs": 50, "holdMs": 100, "outMs": 50},
            "x": 0,
            "y": 0,
            "w": 4,
            "h": 4,
            "fill": "accent",
        }
    ],
}


def test_read_request_parses_op_and_input() -> None:
    op, payload = read_request(io.StringIO(json.dumps({"op": "compile", "input": {"spec": SPEC}})))
    assert op == "compile"
    assert payload == {"spec": SPEC}


def test_read_request_rejects_empty_stdin() -> None:
    with pytest.raises(EngineError) as error:
        read_request(io.StringIO("   "))
    assert error.value.code == "EMPTY_INPUT"


def test_read_request_rejects_bad_json() -> None:
    with pytest.raises(EngineError) as error:
        read_request(io.StringIO("{not json"))
    assert error.value.code == "BAD_JSON"


def test_read_request_rejects_a_non_object() -> None:
    with pytest.raises(EngineError) as error:
        read_request(io.StringIO("[1,2,3]"))
    assert error.value.code == "BAD_SHAPE"


def test_read_request_requires_an_op() -> None:
    with pytest.raises(EngineError) as error:
        read_request(io.StringIO(json.dumps({"input": {}})))
    assert error.value.code == "MISSING_OP"


def test_read_request_rejects_an_oversized_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    """The size limit is enforced before parsing, so a huge body is never deserialised."""

    class Huge:
        def read(self, _count: int) -> str:
            return "x" * 64

    monkeypatch.setattr(protocol, "MAX_INPUT_BYTES", 16)
    with pytest.raises(EngineError) as error:
        read_request(Huge())
    assert error.value.code == "INPUT_TOO_LARGE"


def test_write_response_emits_one_line_of_json() -> None:
    stream = io.StringIO()
    write_response({"ok": True, "value": {"a": 1}, "durationMs": 3}, stream)
    raw = stream.getvalue()
    assert raw.endswith("\n")
    assert "\n" not in raw[:-1]
    assert json.loads(raw) == {"ok": True, "value": {"a": 1}, "durationMs": 3}


def test_handle_routes_to_the_real_operations() -> None:
    result = handle("compile", {"spec": SPEC})
    assert result["frameCount"] == 2


def test_a_failing_handler_propagates_its_code() -> None:
    with pytest.raises(EngineError) as error:
        handle("compile", {"spec": {"id": "bad"}})
    assert error.value.code == "MISSING_FIELD"


def test_stream_mode_cannot_be_reached_through_the_json_path() -> None:
    """render_stream writes pixels to stdout; it must never answer a JSON request."""
    with pytest.raises(EngineError) as error:
        handle("render_stream", {"spec": SPEC})
    assert error.value.code == "STREAM_MODE"


def test_analyse_lists_the_available_operations_when_unknown() -> None:
    with pytest.raises(EngineError) as error:
        analyse("summarize", {"records": []})
    assert error.value.code == "UNKNOWN_OP"
    assert "compile" in error.value.message
