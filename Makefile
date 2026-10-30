PYTHON ?= python3
export PYTHONPATH := src

.PHONY: train test lint format serve tf-fmt tf-validate

train:
	$(PYTHON) training/train.py

test:
	$(PYTHON) -m pytest

lint:
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

format:
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

serve:
	MODEL_PATH=artifacts/model.joblib $(PYTHON) -m housing_api.local_server

tf-fmt:
	terraform -chdir=infra fmt -recursive

tf-validate:
	terraform -chdir=infra fmt -check -recursive
	terraform -chdir=infra init -backend=false -input=false
	terraform -chdir=infra validate
