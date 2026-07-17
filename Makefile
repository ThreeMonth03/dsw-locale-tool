PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
SPHINXOPTS ?= -W --keep-going

.PHONY: install-dev check compile format format-check lint test docs docs-clean clean

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)

install-dev: $(VENV)/bin/python
	$(BIN)/python -m pip install --upgrade pip
	$(BIN)/python -m pip install -e ".[dev]"

compile:
	$(BIN)/python -m compileall -q src tests

format:
	$(BIN)/ruff format --config config/ruff.toml src tests docs/conf.py
	$(BIN)/ruff check --fix --config config/ruff.toml src tests docs/conf.py

format-check:
	$(BIN)/ruff format --check --config config/ruff.toml src tests docs/conf.py

lint:
	$(BIN)/ruff check --config config/ruff.toml src tests docs/conf.py

test:
	$(BIN)/pytest

docs:
	$(BIN)/sphinx-build $(SPHINXOPTS) -b html docs docs/_build/html

docs-clean:
	$(BIN)/sphinx-build -M clean docs docs/_build

check: compile format-check lint test docs

clean:
	$(BIN)/python -c 'import shutil; [shutil.rmtree(path, ignore_errors=True) for path in ("build", "dist", "docs/_build", ".pytest_cache", ".ruff_cache")]'

