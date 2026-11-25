.PHONY: install test lint format build run down

install:
	pip install -r requirements-dev.txt

test:
	pytest

lint:
	ruff check .
	ruff format --check .

format:
	ruff format .

build:
	docker build -t secure-devops-platform:0.1.0 .

run:
	docker compose up -d --build

down:
	docker compose down
