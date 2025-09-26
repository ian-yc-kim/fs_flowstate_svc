.PHONY: install lint test format setup run build unittest

install:
	poetry install --no-root

lint:
	poetry run black . && poetry run isort . && poetry run mypy src/

test:
	poetry run pytest

format:
	poetry run black . && poetry run isort .

build:
	poetry install

setup:
	poetry run alembic upgrade head

unittest:
	poetry run pytest tests

run:
	poetry run fs_flowstate_svc