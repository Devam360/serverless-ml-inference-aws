"""API Gateway HTTP API (payload v2) entrypoint.

Routes:
  GET  /health
  POST /predict

A bare JSON object of features is also accepted so the Lambda console can
invoke the function without an API Gateway envelope.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

from housing_api.features import TARGET_UNITS
from housing_api.model_service import ModelLoadError, get_artifact, predict_row
from housing_api.preprocess import ValidationError, order_features, validate_features

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 16_384
_HTTP_MARKERS = ("requestContext", "rawPath", "httpMethod", "routeKey")

_ROUTES: dict[str, set[str]] = {
    "/health": {"GET"},
    "/predict": {"POST"},
}


def handler(event: Any, context: Any) -> dict[str, Any]:
    if not isinstance(event, dict):
        return _response(400, {"error": "Event must be a JSON object."})
    try:
        if _is_http_event(event):
            return _handle_http(event, context)
        return _predict_payload(event, context)
    except Exception:
        logger.exception("unhandled error request_id=%s", _request_id(event, context))
        return _response(500, {"error": "Internal server error."})


def _handle_http(event: dict[str, Any], context: Any) -> dict[str, Any]:
    path = _normalize_path(str(event.get("rawPath") or event.get("path") or "/"))
    method = _method(event)
    allowed = _ROUTES.get(path)
    if allowed is None:
        return _response(
            404,
            {
                "error": "Not found.",
                "routes": ["GET /health", "POST /predict"],
            },
        )
    if method not in allowed:
        return _response(405, {"error": f"Method {method} is not allowed for {path}."})
    if path == "/health":
        return _health(event, context)
    return _predict_http(event, context)


def _health(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_id = _request_id(event, context)
    try:
        artifact = get_artifact()
    except ModelLoadError:
        logger.exception("model load failed request_id=%s", request_id)
        return _response(503, {"status": "unavailable", "model_loaded": False})

    payload: dict[str, Any] = {
        "status": "ok",
        "model_loaded": True,
        "model_version": artifact.get("model_version"),
    }
    test_metrics = artifact.get("metrics", {}).get("test_metrics")
    if isinstance(test_metrics, dict):
        payload["test_metrics"] = {key: test_metrics.get(key) for key in ("rmse", "mae", "r2")}
    logger.info("health ok request_id=%s", request_id)
    return _response(200, payload)


def _predict_http(event: dict[str, Any], context: Any) -> dict[str, Any]:
    payload, error = _parse_body(event)
    if error is not None:
        return error
    return _predict_payload(payload, context, event)


def _predict_payload(
    payload: dict[str, Any],
    context: Any,
    event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    request_id = _request_id(event or payload, context)
    try:
        features = validate_features(payload)
        prediction, model_version = predict_row(order_features(features))
    except ValidationError as exc:
        logger.info("rejected input request_id=%s errors=%s", request_id, len(exc.errors))
        return _response(400, {"error": "Invalid input.", "details": exc.errors})
    except ModelLoadError:
        logger.exception("model load failed request_id=%s", request_id)
        return _response(503, {"error": "Model is not available.", "model_loaded": False})

    logger.info(
        "prediction=%.4f model=%s request_id=%s",
        prediction,
        model_version,
        request_id,
    )
    return _response(
        200,
        {
            "prediction": prediction,
            "units": TARGET_UNITS,
            "model_version": model_version,
        },
    )


def _parse_body(event: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Return ``(payload, None)`` or ``({}, error_response)``."""
    raw = event.get("body")
    if raw is None or raw == "":
        return {}, None
    if isinstance(raw, dict):
        return raw, None
    if not isinstance(raw, str):
        return {}, _response(400, {"error": "Request body must be valid JSON."})
    if event.get("isBase64Encoded"):
        try:
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError):
            return {}, _response(400, {"error": "Request body is not valid base64-encoded JSON."})
    if len(raw.encode("utf-8")) > MAX_BODY_BYTES:
        return {}, _response(413, {"error": "Request body is too large."})
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}, _response(400, {"error": "Request body must be valid JSON."})
    if not isinstance(parsed, dict):
        return {}, _response(400, {"error": "Request body must be a JSON object."})
    return parsed, None


def _is_http_event(event: dict[str, Any]) -> bool:
    if any(marker in event for marker in _HTTP_MARKERS):
        return True
    return event.get("version") == "2.0" and "body" in event


def _normalize_path(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return path


def _method(event: dict[str, Any]) -> str:
    request_context = event.get("requestContext")
    if isinstance(request_context, dict):
        http = request_context.get("http")
        if isinstance(http, dict) and http.get("method"):
            return str(http["method"]).upper()
    if event.get("httpMethod"):
        return str(event["httpMethod"]).upper()
    return "GET"


def _request_id(event: dict[str, Any], context: Any) -> str:
    aws_request_id = getattr(context, "aws_request_id", None)
    if aws_request_id:
        return str(aws_request_id)
    request_context = event.get("requestContext")
    if isinstance(request_context, dict) and request_context.get("requestId"):
        return str(request_context["requestId"])
    return "-"


def _response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "content-type": "application/json",
            "cache-control": "no-store",
        },
        "body": json.dumps(payload, indent=2),
    }
