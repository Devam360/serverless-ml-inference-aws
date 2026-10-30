"""Keep the README, packaging, and workflows aligned with the training run."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

import sklearn

ROOT = Path(__file__).resolve().parents[1]


def _metrics() -> dict:
    return json.loads((ROOT / "artifacts" / "metrics.json").read_text(encoding="utf-8"))


def test_readme_quotes_the_training_run():
    metrics = _metrics()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    test = metrics["test_metrics"]
    baseline = metrics["baseline"]["test_metrics"]
    top_feature = metrics["permutation_importance"][0]["feature"]
    required = [
        f"{test['rmse']:.6f}",
        f"{test['mae']:.6f}",
        f"{test['r2']:.6f}",
        f"{baseline['rmse']:.6f}",
        f"{baseline['r2']:.6f}",
        f"{metrics['rmse_improvement_vs_median_baseline']:.6f}",
        f"{metrics['example']['predicted']:.4f}",
        f"{metrics['example']['actual']:.4f}",
        f"largest holdout permutation importance is {top_feature}",
        str(metrics["split"]["train_rows"]),
        str(metrics["split"]["test_rows"]),
        str(metrics["dataset"]["rows"]),
        str(metrics["dataset"]["rows_within_api_bounds"]),
        str(metrics["dataset"]["rows_at_target_max"]),
        metrics["model_version"],
        metrics["versions"]["scikit_learn"],
    ]
    missing = [item for item in required if item not in readme]
    assert missing == []


def test_artifact_metrics_match_the_json_file():
    from housing_api.model_service import get_artifact

    artifact = get_artifact()
    on_disk = _metrics()
    assert artifact["model_version"] == on_disk["model_version"]
    for key in ("rmse", "mae", "r2"):
        assert artifact["metrics"]["test_metrics"][key] == on_disk["test_metrics"][key]
    assert (
        artifact["metrics"]["test_metrics"]["rmse"]
        < artifact["metrics"]["baseline"]["test_metrics"]["rmse"]
    )
    assert (
        artifact["metrics"]["test_metrics"]["r2"]
        > artifact["metrics"]["baseline"]["test_metrics"]["r2"]
    )


def test_installed_sklearn_matches_the_trained_artifact():
    assert _metrics()["versions"]["scikit_learn"] == sklearn.__version__


def test_runtime_requirements_match_pyproject():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    required = [
        line.strip()
        for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    assert required == project["project"]["dependencies"]


def test_terraform_routes_and_workflows():
    api = (ROOT / "infra" / "apigateway.tf").read_text(encoding="utf-8")
    assert 'route_key = "GET /health"' in api or "GET /health" in api
    assert "POST /predict" in api

    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert 'CMD ["housing_api.handler.handler"]' in dockerfile

    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pytest" in ci
    assert "ruff check" in ci
    assert "terraform validate" in ci
    assert "terraform fmt -check" in ci

    deploy = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch" in deploy
    assert "id-token: write" in deploy
    assert "AWS_ROLE_ARN" in deploy
    assert "TF_STATE_BUCKET" in deploy
