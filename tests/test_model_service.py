"""Artifact loading from disk and from S3."""

from __future__ import annotations

from pathlib import Path

import boto3
import joblib
import pytest

from housing_api.features import FEATURE_NAMES
from housing_api.model_service import (
    ModelLoadError,
    _download_s3,
    get_artifact,
    reset_cache,
)

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT = ROOT / "artifacts" / "model.joblib"


def test_local_artifact_matches_the_feature_contract():
    artifact = get_artifact()
    assert tuple(artifact["feature_names"]) == FEATURE_NAMES
    assert artifact["model_version"] == "california-housing-hgb-v1"
    assert callable(artifact["pipeline"].predict)


def test_missing_model_path(monkeypatch, tmp_path):
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "missing.joblib"))
    with pytest.raises(ModelLoadError, match="MODEL_PATH"):
        get_artifact()


def test_rejects_feature_mismatch(monkeypatch, tmp_path):
    path = tmp_path / "bad.joblib"
    joblib.dump(
        {"pipeline": object(), "feature_names": ("MedInc",), "model_version": "bad"},
        path,
    )
    monkeypatch.setenv("MODEL_PATH", str(path))
    with pytest.raises(ModelLoadError, match="feature"):
        get_artifact()


def test_s3_download_is_cached_in_memory_and_on_disk(monkeypatch, tmp_path):
    monkeypatch.delenv("MODEL_PATH")
    monkeypatch.setenv("MODEL_BUCKET", "example-bucket")
    monkeypatch.setenv("MODEL_KEY", "models/california-housing/model.joblib")
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path))
    calls: list[tuple[str, str]] = []

    def fake_download(bucket: str, key: str, destination: Path) -> None:
        calls.append((bucket, key))
        destination.write_bytes(ARTIFACT.read_bytes())

    monkeypatch.setattr("housing_api.model_service._download_s3", fake_download)

    first = get_artifact()
    reset_cache()
    second = get_artifact()
    (tmp_path / "california-housing-model.joblib").unlink()
    third = get_artifact()

    assert first["model_version"] == second["model_version"] == third["model_version"]
    assert calls == [("example-bucket", "models/california-housing/model.joblib")]


def test_s3_errors_do_not_leave_a_partial_artifact(monkeypatch, tmp_path):
    monkeypatch.delenv("MODEL_PATH")
    monkeypatch.setenv("MODEL_BUCKET", "example-bucket")
    monkeypatch.setenv("MODEL_KEY", "models/model.joblib")
    monkeypatch.setenv("MODEL_CACHE_DIR", str(tmp_path))

    def fake_client(*_args, **_kwargs):
        class _Client:
            def download_file(self, bucket: str, key: str, filename: str) -> None:
                Path(filename).write_text("partial", encoding="utf-8")
                raise RuntimeError("AccessDenied")

        return _Client()

    monkeypatch.setattr(boto3, "client", fake_client)
    with pytest.raises(ModelLoadError, match="S3"):
        get_artifact()
    assert list(tmp_path.iterdir()) == []


def test_download_helper_wraps_client_errors(monkeypatch, tmp_path):
    def fake_client(*_args, **_kwargs):
        class _Client:
            def download_file(self, bucket: str, key: str, filename: str) -> None:
                raise RuntimeError("denied")

        return _Client()

    monkeypatch.setattr(boto3, "client", fake_client)
    with pytest.raises(ModelLoadError, match="S3"):
        _download_s3("bucket", "key", tmp_path / "model.joblib")
