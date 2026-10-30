"""Serve the Lambda handler over HTTP without API Gateway.

    python -m housing_api.local_server

Reads ``HOST`` (default 127.0.0.1) and ``PORT`` (default 8080). The model
comes from ``MODEL_PATH`` or ``artifacts/model.joblib``.
"""

from __future__ import annotations

import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from housing_api.handler import handler

logger = logging.getLogger(__name__)


class _Server(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class LocalHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler name
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802 - stdlib handler name
        self._dispatch("POST")

    def _dispatch(self, method: str) -> None:
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode("utf-8") if length else ""
        event = {
            "version": "2.0",
            "rawPath": path,
            "requestContext": {
                "http": {"method": method},
                "requestId": self.headers.get("x-request-id", "local"),
            },
            "isBase64Encoded": False,
            "body": raw,
        }
        result = handler(event, None)
        body = result["body"].encode("utf-8")
        self.send_response(result["statusCode"])
        for key, value in result.get("headers", {}).items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        logger.info("%s - %s", self.address_string(), fmt % args)


def create_server(host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    return _Server((host, port), LocalHandler)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    server = create_server(host, port)
    bound_host, bound_port = server.server_address[:2]
    logger.info("Listening on http://%s:%s", bound_host, bound_port)
    logger.info("GET /health    POST /predict")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
