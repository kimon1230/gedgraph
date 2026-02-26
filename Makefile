.PHONY: venv install test lint fmt audit build clean distclean

venv:
	python -m venv .venv
	@echo "Virtual environment created. Activate with: source .venv/bin/activate"

install:
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

test:
	.venv/bin/pytest tests/ -v

lint:
	.venv/bin/ruff check .
	.venv/bin/black --check .

fmt:
	.venv/bin/black .

audit:
	.venv/bin/pip-audit

build:
	.venv/bin/python -m build

clean:
	rm -rf dist build *.egg-info
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
	find . -path ./.venv -prune -o -type f -name '*.pyc' -delete

distclean: clean
	rm -rf .venv
