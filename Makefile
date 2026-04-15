.PHONY: install dev test lint fmt clean

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev]"

test:
	python -m pytest tests/ -v

lint:
	python -m ruff check src/ tests/

fmt:
	python -m ruff format src/ tests/

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
