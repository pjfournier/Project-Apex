.PHONY: lint typecheck test-arch test-replay test-m2 test-volume test

lint:
	.venv/Scripts/python -m ruff check .

typecheck:
	.venv/Scripts/python -m mypy

test-arch:
	.venv/Scripts/python -m pytest tests/architecture

test-replay:
	.venv/Scripts/python -m pytest tests/replay

test-m2:
	.venv/Scripts/python -m pytest tests/unit/test_projections.py tests/integration/test_projection_service.py tests/replay/test_m2_golden_replay.py

test-volume:
	.venv/Scripts/python tests/performance/benchmark_projection_rebuild.py

test:
	.venv/Scripts/python -m pytest
