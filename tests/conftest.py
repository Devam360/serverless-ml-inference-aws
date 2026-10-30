"""Point tests at the committed artifact and isolate the model cache."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
os.environ["MODEL_PATH"] = str(ROOT / "artifacts" / "model.joblib")


@pytest.fixture(autouse=True)
def _reset_model_cache():
    from housing_api.model_service import reset_cache

    reset_cache()
    yield
    reset_cache()
