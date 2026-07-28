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
	.venv/bin/mypy

fmt:
	.venv/bin/black .

# Project-path mode, matching CI: a bare `pip-audit` would audit the installed
# environment, including every dev tool, instead of the runtime dependencies.
audit:
	.venv/bin/pip-audit --strict --progress-spinner off .

build:
	.venv/bin/python -m build

clean:
	rm -rf dist build *.egg-info
	find . -path ./.venv -prune -o -type d -name __pycache__ -exec rm -rf {} +
	# -delete implies -depth, which makes the preceding -prune a no-op; bfs
	# rejects the combination outright and GNU findutils warns. Use -exec, as
	# the line above already does.
	find . -path ./.venv -prune -o -type f -name '*.pyc' -exec rm -f {} +

distclean: clean
	rm -rf .venv
