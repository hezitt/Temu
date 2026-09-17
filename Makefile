PYTHON ?= python3.12
VENV := .venv

.PHONY: setup run test lint migration upgrade downgrade

setup:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements-dev.txt

run:
	$(VENV)/bin/uvicorn app.main:app --reload

test:
	$(VENV)/bin/pytest

lint:
	$(VENV)/bin/ruff check .

migration:
	$(VENV)/bin/alembic revision --autogenerate -m "$(m)"

upgrade:
	$(VENV)/bin/alembic upgrade head

downgrade:
	$(VENV)/bin/alembic downgrade -1

