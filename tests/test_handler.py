"""Lambda handler routes, validation, and scoring."""

from __future__ import annotations

import base64
import json
from pathlib import Path

from housing_api.features import TARGET_UNITS
from housing_api.handler import MAX_BODY_BYTES, handler

ROOT = Path(__file__).resolve().parents[1]
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


def _api(method: str, path: str, body=None, *, base64_body: bool = False):
    if body is None:
        encoded = None
    elif isinstance(body, str):
        encoded = body
    else:
        encoded = json.dumps(body)
    if base64_body and encoded is not None:
        encoded = base64.b64encode(encoded.encode()).decode()
    event = {
        "version": "2.0",
        "rawPath": path,
        "requestContext": {"http": {"method": method}, "requestId": "req-test"},
        "isBase64Encoded": base64_body,
        "body": encoded,
    }
    result = handler(event, None)
    return result["statusCode"], json.loads(result["body"]), result["headers"]


def test_health_reports_loaded_model_and_metrics():
    metrics = json.loads((ROOT / "artifacts" / "metrics.json").read_text())
    status, body, headers = _api("GET", "/health")
    assert status == 200
    assert headers["content-type"] == "application/json"
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_version"] == metrics["model_version"]
    assert body["test_metrics"]["r2"] == metrics["test_metrics"]["r2"]
    assert body["test_metrics"]["rmse"] == metrics["test_metrics"]["rmse"]


def test_predict_returns_units_and_a_finite_score():
    status, body, _headers = _api("POST", "/predict", VALID)
    assert status == 200
    assert body["units"] == TARGET_UNITS
    assert body["model_version"] == "california-housing-hgb-v1"
    assert 0.0 < body["prediction"] < 10.0


def test_documented_example_matches_training_metrics():
    metrics = json.loads((ROOT / "artifacts" / "metrics.json").read_text())
    example = json.loads((ROOT / "examples" / "predict.json").read_text())
    status, body, _headers = _api("POST", "/predict/", example)
    assert status == 200
    assert f"{body['prediction']:.4f}" == f"{metrics['example']['predicted']:.4f}"


def test_documented_api_gateway_event():
    event = json.loads((ROOT / "examples" / "apigw_event.json").read_text())
    result = handler(event, None)
    assert result["statusCode"] == 200


def test_direct_invocation_without_api_gateway_envelope():
    result = handler(dict(VALID), None)
    body = json.loads(result["body"])
    assert result["statusCode"] == 200
    assert "prediction" in body


def test_higher_income_raises_the_prediction_at_a_fixed_location():
    low = dict(VALID)
    high = dict(VALID)
    low["MedInc"] = 1.5
    high["MedInc"] = 8.0
    _, low_body, _ = _api("POST", "/predict", low)
    _, high_body, _ = _api("POST", "/predict", high)
    assert high_body["prediction"] > low_body["prediction"]


def test_invalid_input_lists_every_problem():
    payload = dict(VALID)
    del payload["Population"]
    payload["Neighborhood"] = "Mission"
    status, body, _headers = _api("POST", "/predict", payload)
    assert status == 400
    assert body["error"] == "Invalid input."
    assert "Missing required field 'Population'." in body["details"]
    assert "Unknown field(s): 'Neighborhood'." in body["details"]


def test_malformed_json_base64_and_non_object_bodies():
    status, body, _headers = _api("POST", "/predict", "{not json")
    assert status == 400
    assert "valid JSON" in body["error"]

    event = {
        "version": "2.0",
        "rawPath": "/predict",
        "requestContext": {"http": {"method": "POST"}},
        "isBase64Encoded": True,
        "body": "!!!!",
    }
    invalid = handler(event, None)
    status = invalid["statusCode"]
    body = json.loads(invalid["body"])
    assert status == 400
    assert "base64" in body["error"]

    status, body, _headers = _api("POST", "/predict", "[1, 2, 3]")
    assert status == 400
    assert "JSON object" in body["error"]


def test_valid_base64_body_is_scored():
    status, body, _headers = _api("POST", "/predict", VALID, base64_body=True)
    assert status == 200
    assert body["prediction"] > 0


def test_oversize_body_is_rejected():
    payload = dict(VALID)
    payload["note"] = "x" * (MAX_BODY_BYTES + 100)
    status, body, _headers = _api("POST", "/predict", payload)
    assert status == 413
    assert "too large" in body["error"]


def test_unknown_route_and_wrong_method():
    status, body, _headers = _api("GET", "/missing")
    assert status == 404
    assert body["routes"] == ["GET /health", "POST /predict"]

    status, body, _headers = _api("POST", "/health", {})
    assert status == 405

    status, body, _headers = _api("GET", "/predict")
    assert status == 405


def test_health_and_predict_fail_closed_when_the_model_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "missing.joblib"))
    status, body, _headers = _api("GET", "/health")
    assert status == 503
    assert body["model_loaded"] is False

    status, body, _headers = _api("POST", "/predict", VALID)
    assert status == 503
    assert body["model_loaded"] is False


def test_non_dict_event():
    result = handler(["nope"], None)
    assert result["statusCode"] == 400
