.PHONY: venv install test lint fmt audit clean

venv:
	python -m venv .venv
	@echo "Virtual environment created. Activate with: source .venv/bin/activate"

install:
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt

test:
	.venv/bin/pytest tests/ -v

lint:
	.venv/bin/ruff check .
	.venv/bin/black --check .

fmt:
	.venv/bin/black .

audit:
	.venv/bin/pip-audit

clean:
	rm -rf .venv
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
