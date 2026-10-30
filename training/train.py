#!/usr/bin/env python3
"""Train the California housing model and write the artifact used by the API.

The holdout metrics in ``artifacts/metrics.json`` are the numbers quoted in
the README. Re-run this script, then update that section, if you retrain.

    python training/train.py
"""

from __future__ import annotations

import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.datasets import fetch_california_housing
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import joblib  # noqa: E402
import sklearn  # noqa: E402

from housing_api.features import DATASET_NAME, FEATURE_NAMES, TARGET_NAME, TARGET_UNITS  # noqa: E402
from housing_api.preprocess import ValidationError, validate_features  # noqa: E402

MODEL_VERSION = "california-housing-hgb-v1"
RANDOM_STATE = 42
TEST_SIZE = 0.2
ARTIFACT_PATH = ROOT / "artifacts" / "model.joblib"
METRICS_PATH = ROOT / "artifacts" / "metrics.json"
EXAMPLE_PATH = ROOT / "examples" / "predict.json"
EVENT_PATH = ROOT / "examples" / "apigw_event.json"

HGB_PARAMS: dict[str, object] = {
    "loss": "squared_error",
    "learning_rate": 0.08,
    "max_iter": 300,
    "max_depth": 8,
    "min_samples_leaf": 20,
    "l2_regularization": 0.1,
    "early_stopping": False,
    "random_state": RANDOM_STATE,
}


def _r6(value: float) -> float:
    return float(f"{float(value):.6f}")


def _count_rows_within_api_bounds(rows: np.ndarray) -> int:
    kept = 0
    for row in rows:
        payload = {name: float(row[index]) for index, name in enumerate(FEATURE_NAMES)}
        try:
            validate_features(payload)
        except ValidationError:
            continue
        kept += 1
    return kept


def _evaluate(
    model: Pipeline | DummyRegressor,
    features: np.ndarray,
    target: np.ndarray,
) -> dict[str, float]:
    predicted = model.predict(features)
    return {
        "rmse": _r6(root_mean_squared_error(target, predicted)),
        "mae": _r6(mean_absolute_error(target, predicted)),
        "r2": _r6(r2_score(target, predicted)),
    }


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    dataset = fetch_california_housing(as_frame=False)
    if tuple(dataset.feature_names) != FEATURE_NAMES:
        raise SystemExit(f"Unexpected feature names: {dataset.feature_names}")

    features = np.asarray(dataset.data, dtype=np.float64)
    target = np.asarray(dataset.target, dtype=np.float64)
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    baseline = DummyRegressor(strategy="median")
    baseline.fit(x_train, y_train)
    baseline_metrics = _evaluate(baseline, x_test, y_test)

    pipeline = Pipeline(
        steps=[
            ("scale", StandardScaler()),
            ("model", HistGradientBoostingRegressor(**HGB_PARAMS)),
        ]
    )
    pipeline.fit(x_train, y_train)
    test_metrics = _evaluate(pipeline, x_test, y_test)
    train_metrics = _evaluate(pipeline, x_train, y_train)

    importance = permutation_importance(
        pipeline,
        x_test,
        y_test,
        n_repeats=5,
        random_state=RANDOM_STATE,
        scoring="neg_root_mean_squared_error",
        n_jobs=1,
    )
    order = np.argsort(-importance.importances_mean)
    ranked = [
        {
            "feature": FEATURE_NAMES[int(index)],
            "mean_rmse_increase": _r6(float(importance.importances_mean[int(index)])),
            "std_rmse_increase": _r6(float(importance.importances_std[int(index)])),
        }
        for index in order
    ]

    sample = x_test[0]
    example_features = {
        name: float(f"{float(sample[index]):.6f}") for index, name in enumerate(FEATURE_NAMES)
    }
    validate_features(example_features)
    example_row = np.array([[example_features[name] for name in FEATURE_NAMES]], dtype=np.float64)
    predicted = float(f"{round(float(pipeline.predict(example_row)[0]), 4):.4f}")
    actual = float(f"{float(y_test[0]):.4f}")

    trained_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    target_max = float(np.max(target))
    metrics: dict[str, object] = {
        "model_version": MODEL_VERSION,
        "trained_at": trained_at,
        "dataset": {
            "name": "California housing",
            "loader": DATASET_NAME,
            "rows": int(features.shape[0]),
            "feature_names": list(FEATURE_NAMES),
            "target": TARGET_NAME,
            "target_units": TARGET_UNITS,
            "target_min": _r6(float(np.min(target))),
            "target_max": _r6(target_max),
            "rows_at_target_max": int(np.sum(np.isclose(target, target_max))),
            "rows_within_api_bounds": _count_rows_within_api_bounds(features),
            "citation": "Pace and Barry, Statistics and Probability Letters, 1997",
        },
        "split": {
            "test_size": TEST_SIZE,
            "random_state": RANDOM_STATE,
            "train_rows": int(x_train.shape[0]),
            "test_rows": int(x_test.shape[0]),
        },
        "model": {
            "type": "Pipeline(StandardScaler, HistGradientBoostingRegressor)",
            "params": HGB_PARAMS,
        },
        "baseline": {
            "type": "DummyRegressor(strategy='median')",
            "test_metrics": baseline_metrics,
        },
        "train_metrics": train_metrics,
        "test_metrics": test_metrics,
        "rmse_improvement_vs_median_baseline": _r6(
            1.0 - test_metrics["rmse"] / baseline_metrics["rmse"]
        ),
        "permutation_importance": ranked,
        "example": {
            "split": "test",
            "row_index_within_test": 0,
            "features": example_features,
            "actual": actual,
            "predicted": predicted,
        },
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scikit_learn": sklearn.__version__,
        },
    }

    artifact = {
        "model_version": MODEL_VERSION,
        "pipeline": pipeline,
        "feature_names": list(FEATURE_NAMES),
        "target": TARGET_NAME,
        "target_units": TARGET_UNITS,
        "metrics": metrics,
        "trained_at": trained_at,
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, ARTIFACT_PATH, compress=3)
    _write_json(METRICS_PATH, metrics)
    _write_json(EXAMPLE_PATH, example_features)
    _write_json(
        EVENT_PATH,
        {
            "version": "2.0",
            "rawPath": "/predict",
            "requestContext": {"http": {"method": "POST"}, "requestId": "example"},
            "isBase64Encoded": False,
            "body": json.dumps(example_features),
        },
    )

    print(f"Wrote {ARTIFACT_PATH} ({ARTIFACT_PATH.stat().st_size} bytes)")
    print(f"Wrote {METRICS_PATH}")
    print(
        "test rmse={rmse:.6f} mae={mae:.6f} r2={r2:.6f} baseline_rmse={baseline:.6f}".format(
            rmse=test_metrics["rmse"],
            mae=test_metrics["mae"],
            r2=test_metrics["r2"],
            baseline=baseline_metrics["rmse"],
        )
    )
    print(f"example actual={actual:.4f} predicted={predicted:.4f}")
    top = ranked[0]
    print(
        "top importance {feature} mean_rmse_increase={gain:.6f}".format(
            feature=top["feature"],
            gain=top["mean_rmse_increase"],
        )
    )


if __name__ == "__main__":
    main()
