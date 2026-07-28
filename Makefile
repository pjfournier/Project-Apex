.PHONY: lint typecheck test-arch test

lint:
	.venv/Scripts/python -m ruff check .

typecheck:
	.venv/Scripts/python -m mypy

test-arch:
	.venv/Scripts/python -m pytest tests/architecture

test:
	.venv/Scripts/python -m pytest
