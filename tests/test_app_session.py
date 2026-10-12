"""Run the real app and drive a session over its websocket, as a browser would.

`GET /` only builds the page; the reactive and render code runs when a session
connects, so this is the test that catches an error inside them.
"""

import json
import socket
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect
from websockets.sync.connection import Connection

from daioe_regions.config import PATHS

STARTUP_SECONDS = 60
QUIET_SECONDS = 2.5
INITIAL_INPUTS = {
    "subindex": "genai",
    "year": 2024,
    "sex": "all",
    "level": "SSYK1",
    "group": "all",
    ".clientdata_output_county_map_hidden": False,
}


def free_port() -> int:
    """Ask the OS for an unused TCP port."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture(scope="module")
def server(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[int, Path]]:
    """Start `shiny run app.py` on a free port; yield the port and its log file."""
    port = free_port()
    log = tmp_path_factory.mktemp("app") / "server.log"
    with log.open("w") as handle:
        process = subprocess.Popen(
            [sys.executable, "-m", "shiny", "run", "app.py", "--port", str(port)],
            cwd=PATHS.root,
            stdout=handle,
            stderr=subprocess.STDOUT,
        )
        try:
            deadline = time.monotonic() + STARTUP_SECONDS
            while True:
                try:
                    urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=2)
                    break
                except OSError:
                    if time.monotonic() > deadline or process.poll() is not None:
                        pytest.fail(f"app did not start:\n{log.read_text()}")
                    time.sleep(0.5)
            yield port, log
        finally:
            process.terminate()
            process.wait(timeout=10)


def drain(websocket: Connection) -> list[dict[str, Any]]:
    """Read messages until the session has been quiet for a moment."""
    messages = []
    while True:
        try:
            messages.append(json.loads(websocket.recv(timeout=QUIET_SECONDS)))
        except TimeoutError:
            return messages
        except ConnectionClosed:
            pytest.fail("the server closed the session")


def errors_in(messages: list[dict[str, Any]]) -> dict[str, Any]:
    """Every output error the server reported in these messages."""
    found: dict[str, Any] = {}
    for message in messages:
        found.update(message.get("errors") or {})
    return found


def recalculated(messages: list[dict[str, Any]], output: str) -> bool:
    """Whether the output finished recalculating in these messages."""
    return any(
        message.get("recalculating") == {"name": output, "status": "recalculated"}
        for message in messages
    )


def test_session_renders_the_map_and_survives_changes(
    server: tuple[int, Path],
) -> None:
    port, log = server
    with connect(f"ws://127.0.0.1:{port}/websocket/", max_size=None) as websocket:
        websocket.send(json.dumps({"method": "init", "data": INITIAL_INPUTS}))
        initial = drain(websocket)
        assert errors_in(initial) == {}
        assert any("county_map" in (m.get("values") or {}) for m in initial)

        # Each change recalculates the map; the level change also refreshes the
        # group choices and must not leave a stale group behind.
        for change in (
            {"subindex": "imgcompr", "year": 2014},
            {"sex": "women"},
            {"level": "SSYK3"},
            {"level": "SSYK4", "group": "1111"},
            {"subindex": "videogames", "year": 2024, "sex": "all"},
        ):
            websocket.send(json.dumps({"method": "update", "data": change}))
            messages = drain(websocket)
            assert errors_in(messages) == {}, change
            assert recalculated(messages, "county_map"), change

    assert "Traceback" not in log.read_text()
