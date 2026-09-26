.PHONY: test test-cov lint train docker-build ci

test:
	pytest

test-cov:
	pytest --cov=ame_backend --cov=training/scripts --cov-report=term-missing

lint:
	ruff check ame_backend tests training || true
	python -m py_compile ame_backend/src/main.py ame_backend/src/services/ai_engine.py training/scripts/*.py

train:
	python training/scripts/orchestrator.py --skip-synthetic --epochs 1

docker-build:
	docker compose build

ci: lint test
