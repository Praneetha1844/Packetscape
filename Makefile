.PHONY: install lint format typecheck test check run clean

install:
	python -m pip install -e ".[dev,plots]"

lint:
	ruff check .
	ruff format --check .

format:
	ruff check --fix .
	ruff format .

typecheck:
	mypy

test:
	pytest --cov=packetscape --cov-report=term-missing

check: lint typecheck test

run:
	packetscape run examples/dumbbell_aimd.yaml --out results/dumbbell_aimd

clean:
	rm -rf build dist .pytest_cache .mypy_cache .ruff_cache .coverage htmlcov results
