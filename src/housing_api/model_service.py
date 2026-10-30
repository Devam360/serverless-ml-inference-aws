"""Load the trained pipeline from disk or S3 and score one row.

Lambda sets ``MODEL_BUCKET`` and ``MODEL_KEY``. The object is downloaded once
per execution environment. Local runs and tests set ``MODEL_PATH`` instead,
which wins when both are present.
"""

from __future__ import annotations

import math
import os
import threading
from pathlib import Path
from typing import Any

import joblib

from housing_api.features import FEATURE_NAMES

_CACHE: dict[str, Any] = {}
_LOCK = threading.Lock()


class ModelLoadError(RuntimeError):
    """The artifact could not be read or does not match this service."""


def reset_cache() -> None:
    """Drop the in-process artifact. Tests use this between cases."""
    with _LOCK:
        _CACHE.clear()


def get_artifact() -> dict[str, Any]:
    cached = _CACHE.get("artifact")
    if cached is not None:
        return cached
    with _LOCK:
        cached = _CACHE.get("artifact")
        if cached is not None:
            return cached
        artifact = _read_artifact(resolve_model_path())
        _CACHE["artifact"] = artifact
        return artifact


def predict_row(features: list[float]) -> tuple[float, str]:
    """Score one ordered feature row. Returns ``(prediction, model_version)``."""
    artifact = get_artifact()
    predicted = float(artifact["pipeline"].predict([features])[0])
    if not math.isfinite(predicted):
        raise ModelLoadError("Model returned a non-finite prediction.")
    rounded = float(f"{round(predicted, 4):.4f}")
    return rounded, str(artifact["model_version"])


def resolve_model_path() -> Path:
    explicit = os.environ.get("MODEL_PATH")
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise ModelLoadError(f"MODEL_PATH does not exist: {explicit}")
        return path

    bucket = os.environ.get("MODEL_BUCKET")
    key = os.environ.get("MODEL_KEY")
    if bucket and key:
        return _materialize_from_s3(bucket, key)

    found = _find_local_artifact()
    if found is not None:
        return found
    raise ModelLoadError("Set MODEL_PATH, or MODEL_BUCKET and MODEL_KEY, to a trained artifact.")


def _materialize_from_s3(bucket: str, key: str) -> Path:
    destination = _cache_file()
    if not destination.is_file():
        _download_s3(bucket, key, destination)
    return destination


def _cache_file() -> Path:
    directory = Path(os.environ.get("MODEL_CACHE_DIR", "/tmp"))
    return directory / "california-housing-model.joblib"


def _download_s3(bucket: str, key: str, destination: Path) -> None:
    import boto3

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".partial")
    try:
        boto3.client("s3").download_file(bucket, key, str(partial))
        partial.replace(destination)
    except Exception as exc:
        partial.unlink(missing_ok=True)
        raise ModelLoadError("Could not download the model artifact from S3.") from exc


def _find_local_artifact() -> Path | None:
    candidates = [Path.cwd() / "artifacts" / "model.joblib"]
    for parent in Path(__file__).resolve().parents:
        candidates.append(parent / "artifacts" / "model.joblib")
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _read_artifact(path: Path) -> dict[str, Any]:
    try:
        artifact = joblib.load(path)
    except Exception as exc:
        raise ModelLoadError(f"Could not read the model artifact at {path}.") from exc
    if not isinstance(artifact, dict) or "pipeline" not in artifact:
        raise ModelLoadError("Model artifact is missing a pipeline.")
    names = tuple(artifact.get("feature_names", ()))
    if names != FEATURE_NAMES:
        raise ModelLoadError("Model feature names do not match the API contract.")
    if not artifact.get("model_version"):
        raise ModelLoadError("Model artifact is missing model_version.")
    predict = getattr(artifact["pipeline"], "predict", None)
    if not callable(predict):
        raise ModelLoadError("Model artifact pipeline has no predict method.")
    return artifact
