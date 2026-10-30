"""The stdlib server used for demos without AWS."""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request

from housing_api.local_server import create_server

VALID = {
    "MedInc": 3.5,
    "HouseAge": 20.0,
    "AveRooms": 5.0,
    "AveBedrms": 1.0,
    "Population": 1000.0,
    "AveOccup": 3.0,
    "Latitude": 37.5,
    "Longitude": -122.0,
}


def test_local_server_health_predict_and_validation():
    server = create_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    health_url = f"http://127.0.0.1:{port}/health"
    try:
        deadline = time.monotonic() + 2
        while True:
            try:
                with urllib.request.urlopen(health_url, timeout=5) as response:
                    body = json.load(response)
                    assert response.status == 200
                    assert body["status"] == "ok"
                break
            except urllib.error.URLError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

        with urllib.request.urlopen(health_url, timeout=5) as response:
            body = json.load(response)
            assert response.status == 200
            assert body["status"] == "ok"

        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/predict",
            data=json.dumps(VALID).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            body = json.load(response)
            assert response.status == 200
            assert body["prediction"] > 0

        missing = dict(VALID)
        del missing["MedInc"]
        bad = urllib.request.Request(
            f"http://127.0.0.1:{port}/predict",
            data=json.dumps(missing).encode(),
            headers={"content-type": "application/json"},
            method="POST",
        )
        with pytest_http_error(bad) as error:
            assert error.code == 400
            payload = json.load(error)
            assert any("MedInc" in item for item in payload["details"])
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class pytest_http_error:
    """Expect ``urllib`` to raise for a 4xx response."""

    def __init__(self, request: urllib.request.Request) -> None:
        self.request = request
        self.error: urllib.error.HTTPError | None = None

    def __enter__(self) -> urllib.error.HTTPError:
        try:
            urllib.request.urlopen(self.request, timeout=5)
        except urllib.error.HTTPError as exc:
            self.error = exc
            return exc
        raise AssertionError("expected an HTTP error")

    def __exit__(self, *_args: object) -> None:
        if self.error is not None:
            self.error.close()
